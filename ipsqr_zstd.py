#!/usr/bin/env python3
"""Compress IPS QR batches with vocabulary tokenization and Zstandard.

IPQ2 keeps IPQ1's field-aware semantic representation, tokenizes text using
the Serbian Latin and English columns of serbian_english_vocabulary.tsv, and
compresses the result with a raw-content Zstandard dictionary derived from
the same vocabulary.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import BinaryIO, Sequence

import ipsqr_compress as ipq1

try:
    from compression import zstd as _stdlib_zstd
except ImportError:
    _stdlib_zstd = None

try:
    import zstandard as _third_party_zstd
except ImportError:
    _third_party_zstd = None

try:
    import brotli as _brotli
except ImportError:
    try:
        import brotlicffi as _brotli
    except ImportError:
        _brotli = None


MAGIC = b"IPQ2"
DEFAULT_VOCABULARY = Path(__file__).with_name("serbian_english_vocabulary.tsv")
MAX_SEMANTIC_PAYLOAD = 256 * 1024 * 1024
ZSTD_LEVEL = 19
BROTLI_QUALITY = 11
MODE_RAW_TEXT = 0
MODE_SEMANTIC = 1
MODE_TOKENIZED_SEMANTIC = 2
COMMON_TOKEN_COUNT = 256
PIECE_LITERAL = 0
PIECE_COMMON_TOKEN = 1
PIECE_EXTENDED_TOKEN = 2
TEXT_RAW = 0
TEXT_TOKENIZED = 1
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
SERBIAN_ASCII_TRANSLATION = str.maketrans(
    {
        "č": "c",
        "ć": "c",
        "š": "s",
        "ž": "z",
        "đ": "dj",
        "Č": "C",
        "Ć": "C",
        "Š": "S",
        "Ž": "Z",
        "Đ": "DJ",
    }
)

# These receive the highest token-ranking weight. The rest of the 256 common
# slots are filled deterministically from category-weighted vocabulary words.
PRIORITY_WORDS = (
    "za",
    "i",
    "u",
    "na",
    "od",
    "po",
    "sa",
    "do",
    "iz",
    "bez",
    "o",
    "ili",
    "pri",
    "prema",
    "račun",
    "racun",
    "porez",
    "doprinos",
    "taksa",
    "naknada",
    "uplata",
    "isplata",
    "plaćanje",
    "placanje",
    "članarina",
    "clanarina",
    "registracija",
    "usluga",
    "troškovi",
    "troskovi",
    "osiguranje",
    "zdravstveno",
    "penzijsko",
    "invalidsko",
    "nezaposlenosti",
    "prihodi",
    "prihode",
    "administrativna",
    "administrativni",
    "škola",
    "skola",
    "fakultet",
    "univerzitet",
    "udruženje",
    "udruzenje",
    "savez",
    "srbija",
    "srbije",
    "republika",
    "grad",
    "opština",
    "opstina",
    "ulica",
    "bulevar",
    "izvod",
    "uverenje",
    "potvrda",
    "dozvola",
    "upis",
    "ispit",
    "školarina",
    "skolarina",
    "član",
    "clan",
    "dostava",
    "kazna",
    "kamata",
    "rata",
    "dugovanje",
    "donacija",
    "pretplata",
    "registracije",
)


def _serbian_ascii(value: str) -> str:
    return value.translate(SERBIAN_ASCII_TRANSLATION)


def _text_variants(value: str) -> tuple[str, ...]:
    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        if candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)

    add(value)
    add(value.lower())
    add(value[:1].upper() + value[1:])
    add(value.upper())
    for candidate in tuple(variants):
        add(_serbian_ascii(candidate))
    return tuple(variants)


class VocabularyError(ValueError):
    """Raised when the IPQ2 vocabulary is missing or malformed."""


class Vocabulary:
    """Deterministic IPQ2 token table and raw Zstandard dictionary."""

    def __init__(self, path: Path) -> None:
        self.path = path
        rows = self._read_rows(path)
        self.entry_count = len(rows)
        self.raw_dictionary = self._build_raw_dictionary(rows)
        self.terms = self._build_terms(rows)
        self.fingerprint = self._fingerprint(self.raw_dictionary, self.terms)
        self.trie = self._build_trie(self.terms)
        self.term_word_edges = tuple(
            (term.decode("utf-8")[0].isalnum(), term.decode("utf-8")[-1].isalnum())
            for term in self.terms
        )

    @staticmethod
    def _read_rows(path: Path) -> list[tuple[str, str, str]]:
        try:
            stream = path.open("r", encoding="utf-8", newline="")
        except OSError as exc:
            raise VocabularyError(f"cannot read vocabulary {path}: {exc}") from exc

        with stream:
            reader = csv.DictReader(stream, delimiter="\t")
            required = {"category", "sr_latn", "en"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise VocabularyError(
                    "vocabulary must contain category, sr_latn, and en columns"
                )
            rows: list[tuple[str, str, str]] = []
            for line_number, row in enumerate(reader, 2):
                category = (row.get("category") or "").strip()
                serbian = (row.get("sr_latn") or "").strip()
                english = (row.get("en") or "").strip()
                if not category or not serbian or not english:
                    raise VocabularyError(
                        f"vocabulary line {line_number} has an empty required value"
                    )
                rows.append((category, serbian, english))
        if not rows:
            raise VocabularyError("vocabulary contains no entries")
        return rows

    @staticmethod
    def _build_raw_dictionary(rows: list[tuple[str, str, str]]) -> bytes:
        values: list[str] = []
        seen: set[str] = set()
        for _, serbian, english in rows:
            for value in (serbian, english):
                for variant in _text_variants(value):
                    if variant not in seen:
                        seen.add(variant)
                        values.append(variant)
        for word in PRIORITY_WORDS:
            for variant in _text_variants(word):
                if variant not in seen:
                    seen.add(variant)
                    values.append(variant)
        return ("\n".join(values) + "\n").encode("utf-8")

    @staticmethod
    def _category_weight(category: str) -> int:
        if category.startswith("payment."):
            return 8
        if category.startswith("organization."):
            return 6
        if category.startswith("geo."):
            return 4
        return 2

    @classmethod
    def _build_terms(cls, rows: list[tuple[str, str, str]]) -> tuple[bytes, ...]:
        scores: defaultdict[bytes, int] = defaultdict(int)
        words: set[bytes] = set()

        for category, serbian, english in rows:
            category_weight = cls._category_weight(category)
            for column_weight, value in ((2, serbian), (1, english)):
                base_weight = category_weight * column_weight
                for variant in _text_variants(value):
                    encoded = variant.encode("utf-8")
                    scores[encoded] += base_weight * max(2, len(encoded) // 4)
                word_spellings = {value, _serbian_ascii(value)}
                for spelling in word_spellings:
                    for word in WORD_RE.findall(spelling):
                        word_bytes = word.lower().encode("utf-8")
                        words.add(word_bytes)
                        scores[word_bytes] += base_weight

        priority_boost = 1_000_000
        for rank, word in enumerate(PRIORITY_WORDS):
            word_bytes = word.encode("utf-8")
            words.add(word_bytes)
            scores[word_bytes] += priority_boost - rank

        ranked_words = sorted(
            words,
            key=lambda term: (-scores[term], -len(term), term),
        )
        if len(ranked_words) < COMMON_TOKEN_COUNT:
            raise VocabularyError(
                f"vocabulary has fewer than {COMMON_TOKEN_COUNT} distinct words"
            )
        common = ranked_words[:COMMON_TOKEN_COUNT]
        common_set = set(common)
        extended = sorted(
            (term for term in scores if term not in common_set),
            key=lambda term: (-scores[term], -len(term), term),
        )
        return tuple((*common, *extended))

    @staticmethod
    def _fingerprint(raw_dictionary: bytes, terms: tuple[bytes, ...]) -> bytes:
        digest = hashlib.sha256(b"IPQ2-derived-vocabulary-v2\0")
        digest.update(len(raw_dictionary).to_bytes(8, "big"))
        digest.update(raw_dictionary)
        for term in terms:
            digest.update(len(term).to_bytes(4, "big"))
            digest.update(term)
        return digest.digest()[:8]

    @staticmethod
    def _build_trie(terms: tuple[bytes, ...]) -> dict[int, dict]:
        root: dict[int, dict] = {}
        for token_id, term in enumerate(terms):
            node = root
            for byte in term:
                node = node.setdefault(byte, {})
            node[-1] = token_id
        return root

    def tokenize(self, data: bytes) -> list[int | bytes]:
        pieces: list[int | bytes] = []
        literal = bytearray()
        offset = 0
        text = data.decode("utf-8")
        word_before: dict[int, bool] = {0: False}
        word_after: dict[int, bool] = {}
        byte_offset = 0
        previous_is_word = False
        for character in text:
            character_is_word = character.isalnum()
            word_before[byte_offset] = previous_is_word
            word_after[byte_offset] = character_is_word
            byte_offset += len(character.encode("utf-8"))
            previous_is_word = character_is_word
        word_before[byte_offset] = previous_is_word
        word_after[byte_offset] = False

        while offset < len(data):
            node = self.trie
            cursor = offset
            best_token: int | None = None
            best_end = offset
            while cursor < len(data) and data[cursor] in node:
                node = node[data[cursor]]
                cursor += 1
                token_id = node.get(-1)
                if token_id is not None:
                    starts_with_word, ends_with_word = self.term_word_edges[token_id]
                    starts_inside_word = starts_with_word and word_before[offset]
                    ends_inside_word = ends_with_word and word_after[cursor]
                    if not starts_inside_word and not ends_inside_word:
                        best_token = token_id
                        best_end = cursor

            if best_token is None:
                literal.append(data[offset])
                offset += 1
                continue

            if literal:
                pieces.append(bytes(literal))
                literal.clear()
            pieces.append(best_token)
            offset = best_end

        if literal:
            pieces.append(bytes(literal))
        return pieces


def _serialize_tokenized(vocabulary: Vocabulary, encoded: bytes) -> bytes:
    pieces = vocabulary.tokenize(encoded)
    output = bytearray((TEXT_TOKENIZED,))
    ipq1._write_uvarint(output, len(pieces))

    piece_types = bytearray((len(pieces) + 3) // 4)
    for index, piece in enumerate(pieces):
        if isinstance(piece, bytes):
            piece_type = PIECE_LITERAL
        elif piece < COMMON_TOKEN_COUNT:
            piece_type = PIECE_COMMON_TOKEN
        else:
            piece_type = PIECE_EXTENDED_TOKEN
        piece_types[index // 4] |= piece_type << ((index % 4) * 2)
    output.extend(piece_types)

    for piece in pieces:
        if isinstance(piece, bytes):
            ipq1._write_uvarint(output, len(piece))
            output.extend(piece)
        elif piece < COMMON_TOKEN_COUNT:
            output.append(piece)
        else:
            ipq1._write_uvarint(output, piece - COMMON_TOKEN_COUNT)
    return bytes(output)


def _encode_text(
    vocabulary: Vocabulary,
    output: bytearray,
    value: str,
    cache: list[bytes],
) -> None:
    encoded = value.encode("utf-8")
    try:
        cache_index = cache.index(encoded)
    except ValueError:
        cache_index = -1

    if cache_index >= 0:
        ipq1._write_uvarint(output, cache_index + 1)
        cache.insert(0, cache.pop(cache_index))
        return

    ipq1._write_uvarint(output, 0)
    raw = bytearray((TEXT_RAW,))
    ipq1._write_uvarint(raw, len(encoded))
    raw.extend(encoded)
    tokenized = _serialize_tokenized(vocabulary, encoded)
    output.extend(tokenized if len(tokenized) < len(raw) else raw)
    cache.insert(0, encoded)


def _decode_text(
    vocabulary: Vocabulary,
    data: bytes,
    offset: int,
    cache: list[bytes],
) -> tuple[str, int]:
    code, offset = ipq1._read_uvarint(data, offset)
    if code:
        cache_index = code - 1
        if cache_index >= len(cache):
            raise ipq1.FormatError("invalid IPQ2 text dictionary reference")
        encoded = cache.pop(cache_index)
        cache.insert(0, encoded)
    else:
        if offset >= len(data):
            raise ipq1.FormatError("truncated IPQ2 text representation")
        representation = data[offset]
        offset += 1

        if representation == TEXT_RAW:
            length, offset = ipq1._read_uvarint(data, offset)
            if length > ipq1.MAX_TEXT_BYTES or offset + length > len(data):
                raise ipq1.FormatError("invalid or truncated IPQ2 text field")
            encoded = data[offset : offset + length]
            offset += length
        elif representation == TEXT_TOKENIZED:
            piece_count, offset = ipq1._read_uvarint(data, offset)
            if piece_count > ipq1.MAX_TEXT_BYTES:
                raise ipq1.FormatError("IPQ2 text has too many token pieces")
            piece_types_length = (piece_count + 3) // 4
            if offset + piece_types_length > len(data):
                raise ipq1.FormatError("truncated IPQ2 token piece types")
            piece_types = data[offset : offset + piece_types_length]
            offset += piece_types_length
            decoded = bytearray()
            for index in range(piece_count):
                piece_type = (piece_types[index // 4] >> ((index % 4) * 2)) & 3
                if piece_type == PIECE_LITERAL:
                    length, offset = ipq1._read_uvarint(data, offset)
                    if length > ipq1.MAX_TEXT_BYTES or offset + length > len(data):
                        raise ipq1.FormatError("invalid IPQ2 literal text piece")
                    decoded.extend(data[offset : offset + length])
                    offset += length
                elif piece_type == PIECE_COMMON_TOKEN:
                    if offset >= len(data):
                        raise ipq1.FormatError("truncated IPQ2 common token")
                    token_id = data[offset]
                    offset += 1
                    if token_id >= min(COMMON_TOKEN_COUNT, len(vocabulary.terms)):
                        raise ipq1.FormatError("invalid IPQ2 common token")
                    decoded.extend(vocabulary.terms[token_id])
                elif piece_type == PIECE_EXTENDED_TOKEN:
                    extended_id, offset = ipq1._read_uvarint(data, offset)
                    token_id = COMMON_TOKEN_COUNT + extended_id
                    if token_id >= len(vocabulary.terms):
                        raise ipq1.FormatError("invalid IPQ2 vocabulary token")
                    decoded.extend(vocabulary.terms[token_id])
                else:
                    raise ipq1.FormatError("reserved IPQ2 token piece type")
                if len(decoded) > ipq1.MAX_TEXT_BYTES:
                    raise ipq1.FormatError("decoded IPQ2 text field is too large")
            encoded = bytes(decoded)
        else:
            raise ipq1.FormatError("unknown IPQ2 text representation")
        cache.insert(0, encoded)

    try:
        return encoded.decode("utf-8"), offset
    except UnicodeDecodeError as exc:
        raise ipq1.FormatError("IPQ2 text field is not valid UTF-8") from exc


def _zstd_compress(data: bytes, dictionary: bytes) -> bytes:
    if _stdlib_zstd is not None:
        zstd_dict = _stdlib_zstd.ZstdDict(dictionary, is_raw=True)
        options = {
            _stdlib_zstd.CompressionParameter.compression_level: ZSTD_LEVEL,
            _stdlib_zstd.CompressionParameter.content_size_flag: 1,
            _stdlib_zstd.CompressionParameter.checksum_flag: 1,
            _stdlib_zstd.CompressionParameter.dict_id_flag: 0,
        }
        return _stdlib_zstd.compress(data, options=options, zstd_dict=zstd_dict)

    if _third_party_zstd is not None:
        zstd_dict = _third_party_zstd.ZstdCompressionDict(
            dictionary,
            dict_type=_third_party_zstd.DICT_TYPE_RAWCONTENT,
        )
        compressor = _third_party_zstd.ZstdCompressor(
            level=ZSTD_LEVEL,
            dict_data=zstd_dict,
            write_checksum=True,
            write_content_size=True,
            write_dict_id=False,
        )
        return compressor.compress(data)

    raise RuntimeError(
        "Zstandard support requires Python 3.14+ or the 'zstandard' package"
    )


def _zstd_decompress(frame: bytes, dictionary: bytes) -> bytes:
    if _stdlib_zstd is not None:
        zstd_dict = _stdlib_zstd.ZstdDict(dictionary, is_raw=True)
        decompressor = _stdlib_zstd.ZstdDecompressor(zstd_dict=zstd_dict)
        try:
            payload = decompressor.decompress(frame, MAX_SEMANTIC_PAYLOAD + 1)
        except (_stdlib_zstd.ZstdError, EOFError) as exc:
            raise ipq1.FormatError(f"invalid Zstandard frame: {exc}") from exc
        if len(payload) > MAX_SEMANTIC_PAYLOAD:
            raise ipq1.FormatError("IPQ2 semantic payload is too large")
        if not decompressor.eof or decompressor.unused_data:
            raise ipq1.FormatError("truncated frame or trailing IPQ2 archive data")
        return payload

    if _third_party_zstd is not None:
        zstd_dict = _third_party_zstd.ZstdCompressionDict(
            dictionary,
            dict_type=_third_party_zstd.DICT_TYPE_RAWCONTENT,
        )
        decompressor = _third_party_zstd.ZstdDecompressor(dict_data=zstd_dict)
        try:
            payload = decompressor.decompress(
                frame,
                max_output_size=MAX_SEMANTIC_PAYLOAD + 1,
                allow_extra_data=False,
            )
        except _third_party_zstd.ZstdError as exc:
            raise ipq1.FormatError(f"invalid Zstandard frame: {exc}") from exc
        if len(payload) > MAX_SEMANTIC_PAYLOAD:
            raise ipq1.FormatError("IPQ2 semantic payload is too large")
        return payload

    raise RuntimeError(
        "Zstandard support requires Python 3.14+ or the 'zstandard' package"
    )


def _brotli_compress(data: bytes) -> bytes | None:
    if _brotli is not None:
        mode_text = getattr(_brotli, "MODE_TEXT", 1)
        return _brotli.compress(data, mode=mode_text, quality=BROTLI_QUALITY)

    executable = shutil.which("brotli")
    if executable is None:
        return None
    result = subprocess.run(
        [executable, f"--quality={BROTLI_QUALITY}", "--stdout"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Brotli benchmark failed: {detail or result.returncode}")
    return result.stdout


def compress(data: bytes, vocabulary: Vocabulary) -> bytes:
    """Return an IPQ2 archive for newline-separated IPS records."""
    semantic_payload = ipq1._build_payload(data)
    encoder = lambda output, value, cache: _encode_text(  # noqa: E731
        vocabulary, output, value, cache
    )
    tokenized_payload = ipq1._build_payload(data, text_encoder=encoder)
    candidates = (
        (MODE_RAW_TEXT, data),
        (MODE_SEMANTIC, semantic_payload),
        (MODE_TOKENIZED_SEMANTIC, tokenized_payload),
    )
    mode, frame = min(
        (
            (mode, _zstd_compress(payload, vocabulary.raw_dictionary))
            for mode, payload in candidates
        ),
        key=lambda candidate: (len(candidate[1]), candidate[0]),
    )
    return MAGIC + vocabulary.fingerprint + bytes((mode,)) + frame


def decompress(archive: bytes, vocabulary: Vocabulary) -> bytes:
    """Restore newline-separated IPS records from an IPQ2 archive."""
    if len(archive) < 19 or not archive.startswith(MAGIC):
        raise ipq1.FormatError("not an IPQ2 archive")
    if archive[4:12] != vocabulary.fingerprint:
        raise ipq1.FormatError("IPQ2 vocabulary fingerprint mismatch")
    mode = archive[12]
    payload = _zstd_decompress(archive[13:], vocabulary.raw_dictionary)
    if mode == MODE_RAW_TEXT:
        return payload
    if mode == MODE_SEMANTIC:
        return ipq1._restore_payload(payload)
    if mode != MODE_TOKENIZED_SEMANTIC:
        raise ipq1.FormatError(f"unknown IPQ2 representation mode {mode}")
    decoder = lambda data, offset, cache: _decode_text(  # noqa: E731
        vocabulary, data, offset, cache
    )
    return ipq1._restore_payload(payload, text_decoder=decoder)


def _open_input(path: str) -> tuple[BinaryIO, bool]:
    if path == "-":
        return sys.stdin.buffer, False
    return Path(path).open("rb"), True


def _open_output(path: str) -> tuple[BinaryIO, bool]:
    if path == "-":
        return sys.stdout.buffer, False
    return Path(path).open("wb"), True


def _read_file(path: str) -> bytes:
    stream, should_close = _open_input(path)
    try:
        return stream.read()
    finally:
        if should_close:
            stream.close()


def _write_file(path: str, data: bytes) -> None:
    stream, should_close = _open_output(path)
    try:
        stream.write(data)
    finally:
        if should_close:
            stream.close()


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", nargs="?", default="-", help="input file")
    parser.add_argument(
        "--vocabulary",
        default=str(DEFAULT_VOCABULARY),
        help="Serbian-English TSV vocabulary",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compressor = subparsers.add_parser("compress", help="create an IPQ2 archive")
    _add_common_arguments(compressor)
    compressor.add_argument("-o", "--output", default="-", help="output file")

    decompressor = subparsers.add_parser(
        "decompress", help="decompress an IPQ2 archive"
    )
    _add_common_arguments(decompressor)
    decompressor.add_argument("-o", "--output", default="-", help="output file")

    benchmark = subparsers.add_parser(
        "bench", help="compare IPQ2/IPQ2a with gzip, Brotli, IPQ1, and IPQ3"
    )
    _add_common_arguments(benchmark)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        vocabulary = Vocabulary(Path(args.vocabulary))
        source = _read_file(args.input)
        if args.command == "compress":
            _write_file(args.output, compress(source, vocabulary))
        elif args.command == "decompress":
            _write_file(args.output, decompress(source, vocabulary))
        else:
            import ipsqr_brotli as ipq3
            import ipsqr_zstd_prefix as ipq2a

            archive = compress(source, vocabulary)
            if decompress(archive, vocabulary) != source:
                raise AssertionError("internal IPQ2 round-trip check failed")
            ipq2a_archive = ipq2a.compress(source, vocabulary)
            if ipq2a.decompress(ipq2a_archive, vocabulary) != source:
                raise AssertionError("internal IPQ2a round-trip check failed")
            ipq3_archive = None
            if ipq3.available():
                ipq3_archive = ipq3.compress(source, vocabulary)
                if ipq3.decompress(ipq3_archive, vocabulary) != source:
                    raise AssertionError("internal IPQ3 round-trip check failed")
            gzipped = gzip.compress(source, compresslevel=9, mtime=0)
            brotlied = _brotli_compress(source)
            ipq1_archive = ipq1.compress(source)
            gzip_ratio = len(archive) / len(gzipped) * 100 if gzipped else 0.0
            print(f"input:  {len(source):6d} bytes")
            print(f"gzip-9:{len(gzipped):6d} bytes")
            if brotlied is None:
                print("brotli-11: unavailable")
            else:
                print(f"brotli-11:{len(brotlied):6d} bytes")
            print(f"IPQ1:  {len(ipq1_archive):6d} bytes")
            print(f"IPQ2:  {len(archive):6d} bytes")
            print(f"IPQ2a: {len(ipq2a_archive):6d} bytes")
            if ipq3_archive is None:
                print("IPQ3:  unavailable")
            else:
                print(f"IPQ3:  {len(ipq3_archive):6d} bytes")
            print(f"IPQ2/gzip-9: {gzip_ratio:.1f}%")
            if brotlied is not None:
                brotli_ratio = len(archive) / len(brotlied) * 100
                print(f"IPQ2/brotli-11: {brotli_ratio:.1f}%")
            ipq2a_gzip_ratio = len(ipq2a_archive) / len(gzipped) * 100
            print(f"IPQ2a/gzip-9: {ipq2a_gzip_ratio:.1f}%")
            if brotlied is not None:
                ipq2a_brotli_ratio = len(ipq2a_archive) / len(brotlied) * 100
                print(f"IPQ2a/brotli-11: {ipq2a_brotli_ratio:.1f}%")
            if ipq3_archive is not None:
                ipq3_gzip_ratio = len(ipq3_archive) / len(gzipped) * 100
                print(f"IPQ3/gzip-9: {ipq3_gzip_ratio:.1f}%")
                if brotlied is not None:
                    ipq3_brotli_ratio = len(ipq3_archive) / len(brotlied) * 100
                    print(f"IPQ3/brotli-11: {ipq3_brotli_ratio:.1f}%")
            print(
                f"vocabulary: {vocabulary.entry_count} entries, "
                f"{len(vocabulary.terms)} tokens, "
                f"{len(vocabulary.raw_dictionary)} dictionary bytes"
            )
            if ipq3_archive is not None:
                ipq3_dictionary = ipq3.SharedDictionary(vocabulary)
                print(
                    f"IPQ3 dictionary: {len(ipq3_dictionary.data)} bytes, "
                    f"{ipq3_dictionary.term_count} terms"
                )
    except (VocabularyError, ipq1.FormatError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
