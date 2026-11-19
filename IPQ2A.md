# IPQ2a format

IPQ2a is an experimental, prefix-inheriting variant of IPQ2 for batches of
Serbian IPS QR payment strings. It moves fields that commonly change to the
front of each semantic record and lets the remaining suffix inherit values
from the preceding record.

The reference implementation is
[`ipsqr_zstd_prefix.py`](ipsqr_zstd_prefix.py). It uses the same
[`serbian_english_vocabulary.tsv`](serbian_english_vocabulary.tsv) and
Zstandard dictionary derivation as IPQ2.

IPQ2a is not wire-compatible with IPQ2. The distinct `IPQ2a` magic prevents
either decoder from silently accepting the other format.

## Requirements

The implementation uses the standard-library `compression.zstd` module on
Python 3.14 or newer. On earlier Python versions it uses the third-party
`zstandard` package when installed.

## Field model

The fixed IPS prefix is implicit:

```text
K:PR|V:01|C:1|
```

Field keys are also implicit in semantic modes. IPQ2a stores variable fields
in this internal order:

```text
R, I, S, N, P, SF, RO
```

`R`, `I`, and `S` usually vary between related payment records, so they are
placed first. `N`, `P`, `SF`, and `RO` are more likely to remain invariant and
form the inheritable suffix. The decoder restores the canonical IPS order:

```text
R, N, I, P, SF, S, RO
```

## Archive envelope

| Offset | Size | Description |
|-------:|-----:|-------------|
| 0 | 5 bytes | ASCII magic and version, `IPQ2a` |
| 5 | 8 bytes | IPQ2 vocabulary fingerprint |
| 13 | 1 byte | Representation mode |
| 14 | remaining bytes | Checksummed Zstandard frame |

The fingerprint has the same derivation as IPQ2 and covers the raw Zstandard
dictionary and token table. Decompression fails if a different vocabulary is
loaded.

## Adaptive representations

IPQ2a builds and Zstandard-compresses five representations, then stores the
smallest complete frame. Ties select the lower-numbered mode.

| Mode | Representation |
|---:|---|
| 0 | Original IPS UTF-8 text |
| 1 | IPQ2 legacy semantic payload |
| 2 | Tokenized IPQ2 legacy semantic payload |
| 3 | Prefix-inheriting semantic payload |
| 4 | Tokenized prefix-inheriting semantic payload |

All modes use the same raw-content Zstandard dictionary. Modes 0 through 2
make the format adaptive on heterogeneous data for which prefix inheritance
does not help.

## Prefix payload

A prefix payload starts with:

```text
flags | uvarint(record_count) | encoded_record...
```

The flags retain LF versus CRLF input and whether the input ended in a final
newline, using the same encoding as IPQ1 and IPQ2.

Each record starts with an unsigned control value. Controls `0` through `7`
are prefix controls: the value is the number of leading fields replaced by
the record. The unencoded suffix inherits from the preceding record.

For example, control `3` stores new `R`, `I`, and `S` values and inherits
`N`, `P`, `SF`, and `RO`:

```text
R:b | I:b | S:b
```

This reconstructs the conceptual record:

```text
R:b | I:b | S:b | N:a | P:a | SF:a | RO:a
```

Control `0` repeats the complete preceding record. Control `7` replaces every
field. On the first record, inherited values begin as absent.

The encoder chooses the shortest prefix that reaches the last changed field.
A prefix form is invalid when an absent field would create a hole inside that
prefix, or when a field must be removed. Such records use the general form.

## General records

Controls of `8` or greater encode independent three-state values for all seven
fields. If `t[i]` is the state for field `i` in IPQ2a field order, the control
is:

```text
8 + sum(t[i] * 3**i)
```

| State | Meaning |
|---:|---|
| 0 | Field is absent |
| 1 | Inherit the preceding value |
| 2 | Decode a new value |

The general form handles optional-field holes, field removal, and changes that
would require an inefficient long prefix.

For every record, the encoder independently builds prefix and general
candidates and emits the shorter one. A tie selects the prefix form.

## Text-cache handling

Semantic text fields use the existing IPQ2 cache and vocabulary token
encodings. Encoding a candidate can update this cache, so IPQ2a clones the
cache before building each candidate. Only the cache belonging to the selected
candidate becomes the starting state for the next record. This keeps encoder
and decoder cache indexes deterministic.

## Value encodings

IPQ2a reuses the IPQ1 and IPQ2 field encodings:

- `R` uses an eight-byte initial account and signed varint deltas afterward.
- `I` stores integer para as an unsigned varint; `RSD` and the decimal comma
  are implicit.
- `SF` stores the canonical three-digit payment code numerically.
- `RO` uses the existing packed numeric/reference encoding when applicable.
- Text fields use cache references, literals, or IPQ2 vocabulary tokens,
  depending on the selected representation.

The original fixed prefix, field keys, canonical field order, line endings,
and final newline are restored during decompression.

## Benchmarks

Sizes include the complete archive envelope:

| Dataset | gzip-9 | IPQ2 | IPQ2a | IPQ2a delta |
|---|---:|---:|---:|---:|
| [`example.txt`](example.txt), 4 related tax records | 283 B | 158 B | 155 B | -3 B |
| [`example_memberships.txt`](example_memberships.txt), 20 heterogeneous records | 695 B | 552 B | 553 B | +1 B |

Results across the fixed random subset corpora:

| Subset size | Files | gzip-9 average | IPQ2 average | IPQ2a average | IPQ2a total delta |
|---:|---:|---:|---:|---:|---:|
| 3 records | 10 | 257.3 B | 171.4 B | 171.5 B | +1 B |
| 4 records | 10 | 329.6 B | 226.9 B | 226.2 B | -7 B |
| 5 records | 10 | 372.9 B | 260.0 B | 258.7 B | -13 B |
| 6 records | 10 | 423.2 B | 303.3 B | 301.7 B | -16 B |

The heterogeneous 20-record corpus selects raw mode in both formats. IPQ2a is
one byte larger there because its magic is five bytes instead of IPQ2's four.
Prefix inheritance becomes more useful as a batch contains more related
records, but it does not guarantee a smaller archive.

## Command-line interface

```bash
./ipsqr_zstd_prefix.py compress payments.txt -o payments.ipq2a
./ipsqr_zstd_prefix.py decompress payments.ipq2a -o restored.txt
```

The IPQ2 benchmark command also reports IPQ2a:

```bash
./ipsqr_zstd.py bench payments.txt
```

## Limits

- Input must satisfy the same canonical IPS constraints enforced by IPQ1.
- Archives require the exact vocabulary identified by their fingerprint.
- Compression and decompression operate on the complete archive in memory.
- Prefix inheritance is local to the immediately preceding record.
- Per-record candidate selection minimizes semantic bytes before Zstandard;
  it does not search every possible control sequence for the globally smallest
  compressed frame.
