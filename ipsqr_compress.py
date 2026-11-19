#!/usr/bin/env python3
"""Compress and decompress batches of Serbian IPS QR payloads.

The input format is one canonical IPS QR text payload per line.  The codec is
specialized for the PR/01/1 form used by printed payment slips: that fixed
prefix is omitted, numeric fields are stored as integers, and unchanged field
values are inherited from the previous record.  A raw DEFLATE stream with a
small, built-in IPS/Serbian-payments dictionary compresses the remaining text.

This is a batch format.  Its output is binary and is not itself an IPS payload.
"""

from __future__ import annotations

import argparse
import gzip
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import BinaryIO, Callable, Sequence


MAGIC = b"IPQ1"
FIXED_PREFIX = "K:PR|V:01|C:1|"
FIELD_NAMES = ("R", "N", "I", "P", "SF", "S", "RO")
TEXT_FIELDS = frozenset(("N", "P", "S"))
FLAG_FINAL_NEWLINE = 1
FLAG_CRLF = 2
MAX_RECORDS = 1_000_000
MAX_TEXT_BYTES = 1_000_000

ACCOUNT_RE = re.compile(r"[0-9]{18}\Z")
AMOUNT_RE = re.compile(r"RSD(0|[1-9][0-9]*),([0-9]{2})\Z")
PAYMENT_CODE_RE = re.compile(r"[0-9]{3}\Z")
REFERENCE_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REFERENCE_INDEX = {char: index for index, char in enumerate(REFERENCE_ALPHABET)}

# A trained dictionary is especially effective for tiny files, where gzip has
# too little prior text to learn this vocabulary.  Keep generic domain phrases
# near the end because DEFLATE gives the end of a preset dictionary priority.
STATIC_DICTIONARY = (
    "nalog za uplatu platilac primalac iznos račun primaoca poziv na broj "
    "odobrenje svrha plaćanja šifra plaćanja valuta RSD javni prihodi "
    "Republika Srbija Republike Srbije ministarstvo uprava porez doprinos "
    "osiguranje zdravstveno penzijsko invalidsko nezaposlenost samostalna "
    "delatnost porez na prihode doprinos za osiguranje Poreska uprava "
    "Republike Srbije Porez na prihode od samostalne delatnosti "
    "Doprinos za zdravstveno osiguranje Doprinos za slucaj nezaposlenosti "
    "Doprinos za penzijsko i invalidsko osiguranje"
).encode("utf-8")


class FormatError(ValueError):
    """Raised when input is not valid for this IPS batch format."""


def _write_uvarint(output: bytearray, value: int) -> None:
    if value < 0:
        raise ValueError("uvarint cannot encode a negative value")
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)


def _read_uvarint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise FormatError("truncated variable-length integer")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
    raise FormatError("variable-length integer is too large")


def _zigzag_encode(value: int) -> int:
    return value * 2 if value >= 0 else (-value * 2) - 1


def _zigzag_decode(value: int) -> int:
    return value // 2 if value % 2 == 0 else -((value // 2) + 1)


def _split_input(data: bytes) -> tuple[list[str], int]:
    if not data:
        return [], 0

    if b"\r" in data:
        without_crlf = data.replace(b"\r\n", b"")
        if b"\r" in without_crlf or b"\n" in without_crlf:
            raise FormatError("mixed or unsupported line endings")
        separator = b"\r\n"
        flags = FLAG_CRLF
    else:
        separator = b"\n"
        flags = 0

    if data.endswith(separator):
        flags |= FLAG_FINAL_NEWLINE
        data = data[: -len(separator)]

    raw_lines = data.split(separator) if data else []
    if any(not line for line in raw_lines):
        raise FormatError("blank lines are not supported")
    try:
        return [line.decode("utf-8") for line in raw_lines], flags
    except UnicodeDecodeError as exc:
        raise FormatError("input is not valid UTF-8") from exc


def _parse_record(line: str, line_number: int) -> tuple[str | None, ...]:
    if not line.startswith(FIXED_PREFIX):
        raise FormatError(
            f"line {line_number}: expected fixed prefix {FIXED_PREFIX!r}"
        )

    parts = line[len(FIXED_PREFIX) :].split("|")
    parsed: dict[str, str] = {}
    order: list[str] = []
    for part in parts:
        if ":" not in part:
            raise FormatError(f"line {line_number}: malformed field {part!r}")
        name, value = part.split(":", 1)
        if name not in FIELD_NAMES:
            raise FormatError(f"line {line_number}: unsupported field {name!r}")
        if name in parsed:
            raise FormatError(f"line {line_number}: duplicate field {name!r}")
        parsed[name] = value
        order.append(name)

    expected_order = [name for name in FIELD_NAMES if name in parsed]
    if order != expected_order:
        raise FormatError(f"line {line_number}: fields are not in IPS canonical order")
    if not parsed:
        raise FormatError(f"line {line_number}: record has no variable fields")

    account = parsed.get("R")
    if account is not None and ACCOUNT_RE.fullmatch(account) is None:
        raise FormatError(f"line {line_number}: R must contain exactly 18 digits")
    amount = parsed.get("I")
    if amount is not None and AMOUNT_RE.fullmatch(amount) is None:
        raise FormatError(f"line {line_number}: unsupported I amount {amount!r}")
    payment_code = parsed.get("SF")
    if payment_code is not None and PAYMENT_CODE_RE.fullmatch(payment_code) is None:
        raise FormatError(f"line {line_number}: SF must contain exactly 3 digits")

    return tuple(parsed.get(name) for name in FIELD_NAMES)


def _encode_cached_text(
    output: bytearray, value: str, cache: list[bytes]
) -> None:
    encoded = value.encode("utf-8")
    try:
        cache_index = cache.index(encoded)
    except ValueError:
        cache_index = -1

    if cache_index >= 0:
        _write_uvarint(output, cache_index + 1)
        cache.insert(0, cache.pop(cache_index))
        return

    _write_uvarint(output, 0)
    _write_uvarint(output, len(encoded))
    output.extend(encoded)
    cache.insert(0, encoded)


def _decode_cached_text(
    data: bytes, offset: int, cache: list[bytes]
) -> tuple[str, int]:
    code, offset = _read_uvarint(data, offset)
    if code:
        cache_index = code - 1
        if cache_index >= len(cache):
            raise FormatError("invalid text dictionary reference")
        encoded = cache.pop(cache_index)
        cache.insert(0, encoded)
    else:
        length, offset = _read_uvarint(data, offset)
        if length > MAX_TEXT_BYTES or offset + length > len(data):
            raise FormatError("invalid or truncated text field")
        encoded = data[offset : offset + length]
        offset += length
        cache.insert(0, encoded)
    try:
        return encoded.decode("utf-8"), offset
    except UnicodeDecodeError as exc:
        raise FormatError("compressed text field is not valid UTF-8") from exc


def _pack_reference(value: str) -> bytes | None:
    try:
        symbols = [REFERENCE_INDEX[char] for char in value]
    except KeyError:
        return None

    packed = bytearray()
    accumulator = 0
    bits = 0
    for symbol in symbols:
        accumulator = (accumulator << 6) | symbol
        bits += 6
        while bits >= 8:
            bits -= 8
            packed.append((accumulator >> bits) & 0xFF)
    if bits:
        packed.append((accumulator << (8 - bits)) & 0xFF)
    return bytes(packed)


def _unpack_reference(packed: bytes, length: int) -> str:
    symbols: list[str] = []
    accumulator = 0
    bits = 0
    for byte in packed:
        accumulator = (accumulator << 8) | byte
        bits += 8
        while bits >= 6 and len(symbols) < length:
            bits -= 6
            index = (accumulator >> bits) & 0x3F
            if index >= len(REFERENCE_ALPHABET):
                raise FormatError("invalid packed RO character")
            symbols.append(REFERENCE_ALPHABET[index])
    if len(symbols) != length:
        raise FormatError("truncated packed RO field")
    return "".join(symbols)


def _encode_value(
    output: bytearray,
    field: str,
    value: str,
    previous: str | None,
    text_cache: dict[str, list[bytes]],
    text_encoder: Callable[[bytearray, str, list[bytes]], None],
) -> None:
    if field == "R":
        number = int(value)
        if previous is None:
            output.extend(number.to_bytes(8, "big"))
        else:
            _write_uvarint(output, _zigzag_encode(number - int(previous)))
    elif field == "I":
        match = AMOUNT_RE.fullmatch(value)
        assert match is not None
        cents = int(match.group(1)) * 100 + int(match.group(2))
        _write_uvarint(output, cents)
    elif field == "SF":
        _write_uvarint(output, int(value))
    elif field == "RO":
        packed = _pack_reference(value)
        if packed is not None:
            output.append(0)
            _write_uvarint(output, len(value))
            output.extend(packed)
        else:
            output.append(1)
            text_encoder(output, value, text_cache[field])
    elif field in TEXT_FIELDS:
        text_encoder(output, value, text_cache[field])
    else:
        raise AssertionError(f"no encoder for {field}")


def _decode_value(
    data: bytes,
    offset: int,
    field: str,
    previous: str | None,
    text_cache: dict[str, list[bytes]],
    text_decoder: Callable[[bytes, int, list[bytes]], tuple[str, int]],
) -> tuple[str, int]:
    if field == "R":
        if previous is None:
            if offset + 8 > len(data):
                raise FormatError("truncated R field")
            number = int.from_bytes(data[offset : offset + 8], "big")
            offset += 8
        else:
            encoded_delta, offset = _read_uvarint(data, offset)
            number = int(previous) + _zigzag_decode(encoded_delta)
        if not 0 <= number < 10**18:
            raise FormatError("decoded R field is outside the 18-digit range")
        return f"{number:018d}", offset
    if field == "I":
        cents, offset = _read_uvarint(data, offset)
        return f"RSD{cents // 100},{cents % 100:02d}", offset
    if field == "SF":
        code, offset = _read_uvarint(data, offset)
        if code > 999:
            raise FormatError("decoded SF field is outside the 3-digit range")
        return f"{code:03d}", offset
    if field == "RO":
        if offset >= len(data):
            raise FormatError("truncated RO field")
        encoding = data[offset]
        offset += 1
        if encoding == 0:
            length, offset = _read_uvarint(data, offset)
            packed_length = (length * 6 + 7) // 8
            if length > MAX_TEXT_BYTES or offset + packed_length > len(data):
                raise FormatError("invalid or truncated packed RO field")
            value = _unpack_reference(data[offset : offset + packed_length], length)
            return value, offset + packed_length
        if encoding == 1:
            return text_decoder(data, offset, text_cache[field])
        raise FormatError("unknown RO field encoding")
    if field in TEXT_FIELDS:
        return text_decoder(data, offset, text_cache[field])
    raise AssertionError(f"no decoder for {field}")


def _build_payload(
    data: bytes,
    text_encoder: Callable[
        [bytearray, str, list[bytes]], None
    ] = _encode_cached_text,
) -> bytes:
    lines, flags = _split_input(data)
    if len(lines) > MAX_RECORDS:
        raise FormatError(f"input has more than {MAX_RECORDS} records")
    records = [_parse_record(line, index) for index, line in enumerate(lines, 1)]

    output = bytearray((flags,))
    _write_uvarint(output, len(records))
    previous: tuple[str | None, ...] = (None,) * len(FIELD_NAMES)
    text_cache = {field: [] for field in (*TEXT_FIELDS, "RO")}

    for record in records:
        status = 0
        multiplier = 1
        for value, old_value in zip(record, previous):
            trit = 0 if value is None else 1 if value == old_value else 2
            status += trit * multiplier
            multiplier *= 3
        _write_uvarint(output, status)

        for field, value, old_value in zip(FIELD_NAMES, record, previous):
            if value is not None and value != old_value:
                _encode_value(
                    output, field, value, old_value, text_cache, text_encoder
                )
        previous = record

    return bytes(output)


def _restore_payload(
    payload: bytes,
    text_decoder: Callable[
        [bytes, int, list[bytes]], tuple[str, int]
    ] = _decode_cached_text,
) -> bytes:
    if not payload:
        raise FormatError("compressed payload is empty")
    flags = payload[0]
    if flags & ~(FLAG_FINAL_NEWLINE | FLAG_CRLF):
        raise FormatError("compressed payload uses unknown flags")
    offset = 1
    record_count, offset = _read_uvarint(payload, offset)
    if record_count > MAX_RECORDS:
        raise FormatError(f"archive has more than {MAX_RECORDS} records")

    previous: tuple[str | None, ...] = (None,) * len(FIELD_NAMES)
    text_cache = {field: [] for field in (*TEXT_FIELDS, "RO")}
    lines: list[str] = []
    powers_of_three = tuple(3**index for index in range(len(FIELD_NAMES)))

    for _ in range(record_count):
        status, offset = _read_uvarint(payload, offset)
        if status >= 3 ** len(FIELD_NAMES):
            raise FormatError("record has an invalid field-state value")
        values: list[str | None] = []
        for index, field in enumerate(FIELD_NAMES):
            trit = (status // powers_of_three[index]) % 3
            old_value = previous[index]
            if trit == 0:
                value = None
            elif trit == 1:
                if old_value is None:
                    raise FormatError(f"record inherits absent {field} field")
                value = old_value
            else:
                value, offset = _decode_value(
                    payload,
                    offset,
                    field,
                    old_value,
                    text_cache,
                    text_decoder,
                )
            values.append(value)

        record = tuple(values)
        fields = [
            f"{name}:{value}"
            for name, value in zip(FIELD_NAMES, record)
            if value is not None
        ]
        if not fields:
            raise FormatError("decoded record has no variable fields")
        lines.append(FIXED_PREFIX + "|".join(fields))
        previous = record

    if offset != len(payload):
        raise FormatError("compressed payload has trailing data")

    separator = "\r\n" if flags & FLAG_CRLF else "\n"
    text = separator.join(lines)
    if flags & FLAG_FINAL_NEWLINE:
        text += separator
    return text.encode("utf-8")


def compress(data: bytes) -> bytes:
    """Return an IPQ1 archive containing newline-separated IPS records."""
    payload = _build_payload(data)
    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=-15,
        memLevel=9,
        strategy=zlib.Z_DEFAULT_STRATEGY,
        zdict=STATIC_DICTIONARY,
    )
    compressed = compressor.compress(payload) + compressor.flush()
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    return MAGIC + struct.pack(">I", checksum) + compressed


def decompress(archive: bytes) -> bytes:
    """Restore newline-separated IPS records from an IPQ1 archive."""
    if len(archive) < len(MAGIC) + 5 or not archive.startswith(MAGIC):
        raise FormatError("not an IPQ1 archive")
    expected_checksum = struct.unpack(">I", archive[4:8])[0]
    decompressor = zlib.decompressobj(wbits=-15, zdict=STATIC_DICTIONARY)
    try:
        payload = decompressor.decompress(archive[8:]) + decompressor.flush()
    except zlib.error as exc:
        raise FormatError(f"invalid DEFLATE stream: {exc}") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise FormatError("truncated stream or trailing archive data")
    if zlib.crc32(payload) & 0xFFFFFFFF != expected_checksum:
        raise FormatError("archive checksum mismatch")
    return _restore_payload(payload)


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("compress", "compress newline-separated IPS QR strings"),
        ("decompress", "decompress an IPQ1 archive"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("input", nargs="?", default="-", help="input file")
        subparser.add_argument("-o", "--output", default="-", help="output file")

    benchmark = subparsers.add_parser("bench", help="compare IPQ1 with gzip -9")
    benchmark.add_argument("input", nargs="?", default="-", help="input text file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        source = _read_file(args.input)
        if args.command == "compress":
            _write_file(args.output, compress(source))
        elif args.command == "decompress":
            _write_file(args.output, decompress(source))
        else:
            archive = compress(source)
            if decompress(archive) != source:
                raise AssertionError("internal round-trip check failed")
            gzipped = gzip.compress(source, compresslevel=9, mtime=0)
            ratio = (len(archive) / len(gzipped) * 100) if gzipped else 0.0
            print(f"input:  {len(source):6d} bytes")
            print(f"gzip-9:{len(gzipped):6d} bytes")
            print(f"IPQ1:  {len(archive):6d} bytes")
            print(f"IPQ1/gzip-9: {ratio:.1f}%")
    except (FormatError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
