#!/usr/bin/env python3
"""Compress IPS QR batches with a shared Serbian-English Brotli dictionary.

IPQ3 derives a raw Brotli history dictionary from every IPQ2 vocabulary term.
It adaptively compares ordinary and dictionary-backed Brotli representations,
using IPQ1's field-aware semantic payload as an additional candidate.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol, Sequence

import ipsqr_compress as ipq1

try:
    import brotli as _brotli
except ImportError:
    try:
        import brotlicffi as _brotli
    except ImportError:
        _brotli = None


MAGIC = b"IPQ3"
DEFAULT_VOCABULARY = Path(__file__).with_name("serbian_english_vocabulary.tsv")
BROTLI_QUALITY = 11
MAX_PAYLOAD = 256 * 1024 * 1024
MAX_SHARED_DICTIONARY = 16 * 1024 * 1024
MODE_RAW_TEXT = 0
MODE_SEMANTIC = 1
MODE_DICTIONARY_RAW_TEXT = 2
MODE_DICTIONARY_SEMANTIC = 3

# These fragments help the raw-text mode encode the first record. They are put
# at the far end of the history; reversed vocabulary terms follow so the most
# useful payment terms have the shortest backward distances.
IPS_FORMAT_DICTIONARY = (
    b"K:PR|V:01|C:1|R:\n"
    b"|N:\n"
    b"|I:RSD\n"
    b",00|\n"
    b"|P:\n"
    b"|SF:\n"
    b"|S:\n"
    b"|RO:\n"
)


class VocabularyLike(Protocol):
    """The subset of the IPQ2 vocabulary API used by IPQ3."""

    terms: tuple[bytes, ...]


class BrotliUnavailable(RuntimeError):
    """Raised when the required Brotli backend is unavailable."""


class SharedDictionary:
    """Deterministic Brotli history derived from the complete vocabulary."""

    def __init__(self, vocabulary: VocabularyLike) -> None:
        terms = tuple(vocabulary.terms)
        if not terms:
            raise ValueError("IPQ3 vocabulary contains no terms")
        if len(set(terms)) != len(terms):
            raise ValueError("IPQ3 vocabulary contains duplicate terms")
        if any(not term or b"\n" in term for term in terms):
            raise ValueError("IPQ3 vocabulary terms must be nonempty single lines")

        # IPQ2 orders terms from most to least useful. Brotli treats a raw
        # dictionary as bytes immediately preceding the input, so reverse the
        # order to place the highest-ranked terms nearest the input.
        self.data = IPS_FORMAT_DICTIONARY + b"\n".join(reversed(terms)) + b"\n"
        if len(self.data) > MAX_SHARED_DICTIONARY:
            raise ValueError("IPQ3 shared dictionary is too large")
        self.term_count = len(terms)
        self.fingerprint = self._fingerprint(self.data)

    @staticmethod
    def _fingerprint(data: bytes) -> bytes:
        digest = hashlib.sha256(b"IPQ3-brotli-shared-dictionary-v2\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        return digest.digest()[:8]


def _brotli_executable() -> str | None:
    return shutil.which("brotli")


@functools.lru_cache(maxsize=1)
def _dictionary_executable() -> str | None:
    executable = _brotli_executable()
    if executable is None:
        return None
    result = subprocess.run(
        [executable, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    help_text = result.stdout + result.stderr
    if result.returncode or b"--dictionary" not in help_text:
        return None
    return executable


def available() -> bool:
    """Return whether Brotli shared-dictionary support is available."""
    return _dictionary_executable() is not None


@contextmanager
def _temporary_dictionary(data: bytes) -> Iterator[str]:
    stream = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix="ipq3-",
        suffix=".dict",
        delete=False,
    )
    path = Path(stream.name)
    try:
        with stream:
            stream.write(data)
        yield str(path)
    finally:
        path.unlink(missing_ok=True)


def _run_brotli_cli(
    data: bytes,
    *,
    decompressing: bool,
    dictionary: bytes | None,
) -> bytes:
    if dictionary is None:
        executable = _brotli_executable()
        if executable is None:
            raise BrotliUnavailable(
                "Brotli requires the 'brotli', 'brotlicffi', or Brotli CLI backend"
            )
    else:
        executable = _dictionary_executable()
        if executable is None:
            raise BrotliUnavailable(
                "IPQ3 requires a Brotli CLI with --dictionary support"
            )

    arguments = [executable]
    if decompressing:
        arguments.append("--decompress")
    else:
        arguments.append(f"--quality={BROTLI_QUALITY}")

    def run() -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [*arguments, "--stdout"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    if dictionary is None:
        result = run()
    else:
        with _temporary_dictionary(dictionary) as dictionary_path:
            arguments.append(f"--dictionary={dictionary_path}")
            result = run()

    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        operation = "decompression" if decompressing else "compression"
        raise RuntimeError(f"Brotli {operation} failed: {detail or result.returncode}")
    return result.stdout


def _brotli_compress(
    data: bytes,
    *,
    text_mode: bool,
    dictionary: bytes | None = None,
) -> bytes:
    if dictionary is not None:
        return _run_brotli_cli(
            data,
            decompressing=False,
            dictionary=dictionary,
        )

    if _brotli is not None:
        mode_name = "MODE_TEXT" if text_mode else "MODE_GENERIC"
        mode = getattr(_brotli, mode_name, 1 if text_mode else 0)
        try:
            return _brotli.compress(data, mode=mode, quality=BROTLI_QUALITY)
        except Exception as exc:
            raise RuntimeError(f"Brotli compression failed: {exc}") from exc

    return _run_brotli_cli(data, decompressing=False, dictionary=None)


def _brotli_decompress(
    frame: bytes,
    *,
    dictionary: bytes | None = None,
) -> bytes:
    if dictionary is not None:
        try:
            payload = _run_brotli_cli(
                frame,
                decompressing=True,
                dictionary=dictionary,
            )
        except BrotliUnavailable:
            raise
        except RuntimeError as exc:
            raise ipq1.FormatError(f"invalid IPQ3 Brotli stream: {exc}") from exc
    elif _brotli is not None:
        try:
            payload = _brotli.decompress(frame)
        except Exception as exc:
            raise ipq1.FormatError(f"invalid IPQ3 Brotli stream: {exc}") from exc
    else:
        try:
            payload = _run_brotli_cli(
                frame,
                decompressing=True,
                dictionary=None,
            )
        except BrotliUnavailable:
            raise
        except RuntimeError as exc:
            raise ipq1.FormatError(f"invalid IPQ3 Brotli stream: {exc}") from exc

    if len(payload) > MAX_PAYLOAD:
        raise ipq1.FormatError("IPQ3 Brotli payload is too large")
    return payload


def compress(data: bytes, vocabulary: VocabularyLike) -> bytes:
    """Return an IPQ3 archive for newline-separated IPS records."""
    if len(data) > MAX_PAYLOAD:
        raise ValueError("IPQ3 input is too large")
    if not available():
        raise BrotliUnavailable(
            "IPQ3 compression requires a Brotli CLI with --dictionary support"
        )

    shared_dictionary = SharedDictionary(vocabulary)
    semantic_payload = ipq1._build_payload(data)
    candidates = (
        (MODE_RAW_TEXT, data, True, None),
        (MODE_SEMANTIC, semantic_payload, False, None),
        (MODE_DICTIONARY_RAW_TEXT, data, True, shared_dictionary.data),
        (
            MODE_DICTIONARY_SEMANTIC,
            semantic_payload,
            False,
            shared_dictionary.data,
        ),
    )
    mode, frame = min(
        (
            (
                mode,
                _brotli_compress(
                    payload,
                    text_mode=text_mode,
                    dictionary=dictionary,
                ),
            )
            for mode, payload, text_mode, dictionary in candidates
        ),
        key=lambda candidate: (len(candidate[1]), candidate[0]),
    )
    checksum = struct.pack(">I", zlib.crc32(data))
    return MAGIC + shared_dictionary.fingerprint + bytes((mode,)) + checksum + frame


def decompress(archive: bytes, vocabulary: VocabularyLike) -> bytes:
    """Restore newline-separated IPS records from an IPQ3 archive."""
    if len(archive) < 18 or not archive.startswith(MAGIC):
        raise ipq1.FormatError("not an IPQ3 archive")

    shared_dictionary = SharedDictionary(vocabulary)
    if archive[4:12] != shared_dictionary.fingerprint:
        raise ipq1.FormatError("IPQ3 vocabulary fingerprint mismatch")

    mode = archive[12]
    if mode not in {
        MODE_RAW_TEXT,
        MODE_SEMANTIC,
        MODE_DICTIONARY_RAW_TEXT,
        MODE_DICTIONARY_SEMANTIC,
    }:
        raise ipq1.FormatError(f"unknown IPQ3 representation mode {mode}")

    dictionary = (
        shared_dictionary.data
        if mode in {MODE_DICTIONARY_RAW_TEXT, MODE_DICTIONARY_SEMANTIC}
        else None
    )
    expected_checksum = struct.unpack(">I", archive[13:17])[0]
    payload = _brotli_decompress(archive[17:], dictionary=dictionary)
    if mode in {MODE_RAW_TEXT, MODE_DICTIONARY_RAW_TEXT}:
        restored = payload
    else:
        restored = ipq1._restore_payload(payload)

    if zlib.crc32(restored) != expected_checksum:
        raise ipq1.FormatError("IPQ3 checksum mismatch")
    return restored


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", help="input file, or - for standard input")
    parser.add_argument(
        "--vocabulary",
        default=str(DEFAULT_VOCABULARY),
        help="Serbian-English TSV vocabulary",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compressor = subparsers.add_parser("compress", help="create an IPQ3 archive")
    _add_common_arguments(compressor)
    compressor.add_argument("-o", "--output", help="output file; defaults to stdout")

    decompressor = subparsers.add_parser(
        "decompress", help="restore an IPQ3 archive"
    )
    _add_common_arguments(decompressor)
    decompressor.add_argument("-o", "--output", help="output file; defaults to stdout")
    return parser


def _read_file(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _write_file(path: str | None, data: bytes) -> None:
    if path is None or path == "-":
        stream: BinaryIO = sys.stdout.buffer
        stream.write(data)
        return
    Path(path).write_bytes(data)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        # Kept local so ipsqr_zstd.py can import IPQ3 in benchmark mode.
        import ipsqr_zstd as ipq2

        vocabulary = ipq2.Vocabulary(Path(args.vocabulary))
        source = _read_file(args.input)
        if args.command == "compress":
            output = compress(source, vocabulary)
        else:
            output = decompress(source, vocabulary)
        _write_file(args.output, output)
    except (ValueError, ipq1.FormatError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
