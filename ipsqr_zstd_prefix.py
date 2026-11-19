#!/usr/bin/env python3
"""Compress IPS QR batches with IPQ2a prefix inheritance and Zstandard."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import BinaryIO, Callable, Sequence

import ipsqr_compress as ipq1
import ipsqr_zstd as ipq2


MAGIC = b"IPQ2a"
DEFAULT_VOCABULARY = Path(__file__).with_name("serbian_english_vocabulary.tsv")
MODE_RAW_TEXT = 0
MODE_SEMANTIC = 1
MODE_TOKENIZED_SEMANTIC = 2
MODE_PREFIX_SEMANTIC = 3
MODE_TOKENIZED_PREFIX_SEMANTIC = 4
GENERAL_STATUS_OFFSET = 8

# Fields that usually change are first. An omitted suffix inherits values from
# the preceding record.
PREFIX_FIELD_NAMES = ("R", "I", "S", "N", "P", "SF", "RO")
CANONICAL_INDEX = {
    field: index for index, field in enumerate(ipq1.FIELD_NAMES)
}

TextEncoder = Callable[[bytearray, str, list[bytes]], None]
TextDecoder = Callable[[bytes, int, list[bytes]], tuple[str, int]]
Record = tuple[str | None, ...]
TextCache = dict[str, list[bytes]]


def _to_prefix_order(record: Record) -> Record:
    return tuple(record[CANONICAL_INDEX[field]] for field in PREFIX_FIELD_NAMES)


def _clone_text_cache(cache: TextCache) -> TextCache:
    return {field: list(values) for field, values in cache.items()}


def _general_record(
    record: Record,
    previous: Record,
    text_cache: TextCache,
    text_encoder: TextEncoder,
) -> tuple[bytes, TextCache]:
    candidate_cache = _clone_text_cache(text_cache)
    output = bytearray()
    status = 0
    multiplier = 1
    for value, old_value in zip(record, previous):
        trit = 0 if value is None else 1 if value == old_value else 2
        status += trit * multiplier
        multiplier *= 3
    ipq1._write_uvarint(output, GENERAL_STATUS_OFFSET + status)

    for field, value, old_value in zip(PREFIX_FIELD_NAMES, record, previous):
        if value is not None and value != old_value:
            ipq1._encode_value(
                output,
                field,
                value,
                old_value,
                candidate_cache,
                text_encoder,
            )
    return bytes(output), candidate_cache


def _prefix_record(
    record: Record,
    previous: Record,
    text_cache: TextCache,
    text_encoder: TextEncoder,
) -> tuple[bytes, TextCache] | None:
    changed = [
        index
        for index, (value, old_value) in enumerate(zip(record, previous))
        if value != old_value
    ]
    prefix_length = changed[-1] + 1 if changed else 0
    if any(value is None for value in record[:prefix_length]):
        return None

    candidate_cache = _clone_text_cache(text_cache)
    output = bytearray((prefix_length,))
    for field, value, old_value in zip(
        PREFIX_FIELD_NAMES[:prefix_length],
        record[:prefix_length],
        previous[:prefix_length],
    ):
        assert value is not None
        ipq1._encode_value(
            output,
            field,
            value,
            old_value,
            candidate_cache,
            text_encoder,
        )
    return bytes(output), candidate_cache


def _build_prefix_payload(
    data: bytes,
    text_encoder: TextEncoder = ipq1._encode_cached_text,
) -> bytes:
    lines, flags = ipq1._split_input(data)
    if len(lines) > ipq1.MAX_RECORDS:
        raise ipq1.FormatError(
            f"input has more than {ipq1.MAX_RECORDS} records"
        )
    records = [
        _to_prefix_order(ipq1._parse_record(line, index))
        for index, line in enumerate(lines, 1)
    ]

    output = bytearray((flags,))
    ipq1._write_uvarint(output, len(records))
    previous: Record = (None,) * len(PREFIX_FIELD_NAMES)
    text_cache: TextCache = {
        field: [] for field in (*ipq1.TEXT_FIELDS, "RO")
    }

    for record in records:
        general, general_cache = _general_record(
            record,
            previous,
            text_cache,
            text_encoder,
        )
        prefix = _prefix_record(record, previous, text_cache, text_encoder)
        if prefix is not None and len(prefix[0]) <= len(general):
            encoded, text_cache = prefix
        else:
            encoded, text_cache = general, general_cache
        output.extend(encoded)
        previous = record
    return bytes(output)


def _decode_general_record(
    data: bytes,
    offset: int,
    status: int,
    previous: Record,
    text_cache: TextCache,
    text_decoder: TextDecoder,
) -> tuple[Record, int]:
    if status >= 3 ** len(PREFIX_FIELD_NAMES):
        raise ipq1.FormatError("IPQ2a record has an invalid field-state value")

    values: list[str | None] = []
    for index, field in enumerate(PREFIX_FIELD_NAMES):
        trit = (status // (3**index)) % 3
        old_value = previous[index]
        if trit == 0:
            value = None
        elif trit == 1:
            if old_value is None:
                raise ipq1.FormatError(
                    f"IPQ2a record inherits absent {field} field"
                )
            value = old_value
        else:
            value, offset = ipq1._decode_value(
                data,
                offset,
                field,
                old_value,
                text_cache,
                text_decoder,
            )
        values.append(value)
    return tuple(values), offset


def _decode_prefix_record(
    data: bytes,
    offset: int,
    prefix_length: int,
    previous: Record,
    text_cache: TextCache,
    text_decoder: TextDecoder,
) -> tuple[Record, int]:
    values = list(previous)
    for index, field in enumerate(PREFIX_FIELD_NAMES[:prefix_length]):
        values[index], offset = ipq1._decode_value(
            data,
            offset,
            field,
            previous[index],
            text_cache,
            text_decoder,
        )
    return tuple(values), offset


def _restore_prefix_payload(
    payload: bytes,
    text_decoder: TextDecoder = ipq1._decode_cached_text,
) -> bytes:
    if not payload:
        raise ipq1.FormatError("IPQ2a semantic payload is empty")
    flags = payload[0]
    if flags & ~(ipq1.FLAG_FINAL_NEWLINE | ipq1.FLAG_CRLF):
        raise ipq1.FormatError("IPQ2a semantic payload uses unknown flags")

    offset = 1
    record_count, offset = ipq1._read_uvarint(payload, offset)
    if record_count > ipq1.MAX_RECORDS:
        raise ipq1.FormatError(
            f"archive has more than {ipq1.MAX_RECORDS} records"
        )

    previous: Record = (None,) * len(PREFIX_FIELD_NAMES)
    text_cache: TextCache = {
        field: [] for field in (*ipq1.TEXT_FIELDS, "RO")
    }
    lines: list[str] = []
    for _ in range(record_count):
        control, offset = ipq1._read_uvarint(payload, offset)
        if control < GENERAL_STATUS_OFFSET:
            record, offset = _decode_prefix_record(
                payload,
                offset,
                control,
                previous,
                text_cache,
                text_decoder,
            )
        else:
            record, offset = _decode_general_record(
                payload,
                offset,
                control - GENERAL_STATUS_OFFSET,
                previous,
                text_cache,
                text_decoder,
            )

        by_name = dict(zip(PREFIX_FIELD_NAMES, record))
        fields = [
            f"{field}:{by_name[field]}"
            for field in ipq1.FIELD_NAMES
            if by_name[field] is not None
        ]
        if not fields:
            raise ipq1.FormatError("decoded IPQ2a record has no variable fields")
        lines.append(ipq1.FIXED_PREFIX + "|".join(fields))
        previous = record

    if offset != len(payload):
        raise ipq1.FormatError("IPQ2a semantic payload has trailing data")

    separator = "\r\n" if flags & ipq1.FLAG_CRLF else "\n"
    text = separator.join(lines)
    if flags & ipq1.FLAG_FINAL_NEWLINE:
        text += separator
    return text.encode("utf-8")


def compress(data: bytes, vocabulary: ipq2.Vocabulary) -> bytes:
    """Return an IPQ2a archive for newline-separated IPS records."""
    semantic_payload = ipq1._build_payload(data)
    encoder = lambda output, value, cache: ipq2._encode_text(  # noqa: E731
        vocabulary, output, value, cache
    )
    tokenized_payload = ipq1._build_payload(data, text_encoder=encoder)
    prefix_payload = _build_prefix_payload(data)
    tokenized_prefix_payload = _build_prefix_payload(
        data,
        text_encoder=encoder,
    )
    candidates = (
        (MODE_RAW_TEXT, data),
        (MODE_SEMANTIC, semantic_payload),
        (MODE_TOKENIZED_SEMANTIC, tokenized_payload),
        (MODE_PREFIX_SEMANTIC, prefix_payload),
        (MODE_TOKENIZED_PREFIX_SEMANTIC, tokenized_prefix_payload),
    )
    mode, frame = min(
        (
            (
                mode,
                ipq2._zstd_compress(payload, vocabulary.raw_dictionary),
            )
            for mode, payload in candidates
        ),
        key=lambda candidate: (len(candidate[1]), candidate[0]),
    )
    return MAGIC + vocabulary.fingerprint + bytes((mode,)) + frame


def decompress(archive: bytes, vocabulary: ipq2.Vocabulary) -> bytes:
    """Restore newline-separated IPS records from an IPQ2a archive."""
    if len(archive) < 14 or not archive.startswith(MAGIC):
        raise ipq1.FormatError("not an IPQ2a archive")
    if archive[5:13] != vocabulary.fingerprint:
        raise ipq1.FormatError("IPQ2a vocabulary fingerprint mismatch")

    mode = archive[13]
    payload = ipq2._zstd_decompress(
        archive[14:],
        vocabulary.raw_dictionary,
    )
    if mode == MODE_RAW_TEXT:
        return payload
    if mode == MODE_SEMANTIC:
        return ipq1._restore_payload(payload)
    if mode == MODE_TOKENIZED_SEMANTIC:
        decoder = lambda data, offset, cache: ipq2._decode_text(  # noqa: E731
            vocabulary, data, offset, cache
        )
        return ipq1._restore_payload(payload, text_decoder=decoder)
    if mode == MODE_PREFIX_SEMANTIC:
        return _restore_prefix_payload(payload)
    if mode == MODE_TOKENIZED_PREFIX_SEMANTIC:
        decoder = lambda data, offset, cache: ipq2._decode_text(  # noqa: E731
            vocabulary, data, offset, cache
        )
        return _restore_prefix_payload(payload, text_decoder=decoder)
    raise ipq1.FormatError(f"unknown IPQ2a representation mode {mode}")


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

    compressor = subparsers.add_parser("compress", help="create an IPQ2a archive")
    _add_common_arguments(compressor)
    compressor.add_argument("-o", "--output", help="output file; defaults to stdout")

    decompressor = subparsers.add_parser(
        "decompress",
        help="restore an IPQ2a archive",
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
        vocabulary = ipq2.Vocabulary(Path(args.vocabulary))
        source = _read_file(args.input)
        if args.command == "compress":
            output = compress(source, vocabulary)
        else:
            output = decompress(source, vocabulary)
        _write_file(args.output, output)
    except (ipq2.VocabularyError, ipq1.FormatError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
