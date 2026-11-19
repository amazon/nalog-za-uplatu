# IPQ2 format

IPQ2 is a vocabulary-backed Zstandard compressor for batches of Serbian IPS
QR payment strings. It succeeds IPQ1 without changing the IPQ1 wire format or
its fixed DEFLATE dictionary.

The reference implementation is [`ipsqr_zstd.py`](ipsqr_zstd.py). Its source
vocabulary is
[`serbian_english_vocabulary.tsv`](serbian_english_vocabulary.tsv).

## Requirements

The implementation uses the standard-library `compression.zstd` module on
Python 3.14 or newer. On earlier Python versions it uses the third-party
`zstandard` package when installed.

Benchmark mode uses the `brotli` or `brotlicffi` Python module when available,
then falls back to the `brotli` command-line executable. It reports Brotli as
unavailable when neither backend exists. The same benchmark imports the
separate prefix-inheriting [IPQ2a](IPQ2A.md) and Brotli-based
[IPQ3](IPQ3.md) implementations and reports their sizes and ratios. IPQ3
requires a Brotli CLI with `--dictionary` support; otherwise the benchmark
reports it as unavailable.

## Vocabulary

Only the `sr_latn` and `en` columns participate in compression. The Serbian
Cyrillic column remains available for translation and future formats but does
not affect an IPQ2 archive.

IPQ2 derives two structures from the TSV:

1. A 32,822-byte raw-content Zstandard dictionary containing Serbian Latin and
   English values, separated by LF bytes.
2. A deterministic token table containing complete values and individual
   words.

For every value, IPQ2 generates the original spelling, lowercase,
first-capital, and uppercase forms. It also generates the same case variants
after applying common Serbian ASCII substitutions:

```text
č, ć -> c     š -> s     ž -> z     đ -> dj
```

The current vocabulary has 414 rows and produces 2,831 tokens. Token IDs 0
through 255 are reserved for distinct lowercase, category-weighted common
words. A curated boost ensures that payment words and short Serbian connectors
such as `za`, `i`, `u`, `na`, `račun`, `racun`, `porez`, and `doprinos`
receive one-byte IDs. Remaining tokens, including capitalized and uppercase
forms, are ordered by estimated usefulness, category, language, length, and
byte value.

## Archive envelope

| Offset | Size | Description |
|-------:|-----:|-------------|
| 0 | 4 bytes | ASCII magic and version, `IPQ2` |
| 4 | 8 bytes | Vocabulary fingerprint |
| 12 | 1 byte | Representation mode |
| 13 | remaining bytes | Checksummed Zstandard frame |

The fingerprint is the first eight bytes of SHA-256 over a derivation-version
marker, the complete raw dictionary, and every length-prefixed token in token
ID order. It therefore covers both source content and the algorithm that
derives case and ASCII variants.

The fingerprint prevents an archive from being decoded with a changed or
reordered vocabulary. A vocabulary change that must remain compatible should
therefore be released under a new format version.

## Adaptive modes

The compressor creates three candidate Zstandard frames and stores the
smallest one. The mode byte identifies the selected representation:

| Mode | Representation |
|-----:|----------------|
| 0 | Original UTF-8 input text |
| 1 | IPQ1 field-aware semantic payload |
| 2 | IPQ1 semantic payload with IPQ2 vocabulary-tokenized text |

All candidates use the same raw-content Zstandard dictionary. The semantic
candidates first validate the input as canonical IPS data, so compression
still rejects malformed records even when mode 0 wins.

Mode 0 is useful for diverse records where Zstandard can model repeated field
keys and text globally. Mode 1 is useful when numeric field encoding and
previous-record inheritance dominate. Mode 2 is useful when many text values
or words appear in the shared vocabulary.

## Tokenized text

Mode 2 retains the IPQ1 per-field move-to-front caches. A new text literal has
one additional representation byte:

| Value | Meaning |
|------:|---------|
| 0 | Raw UTF-8: byte length as `uvarint`, then bytes |
| 1 | Tokenized text |

Tokenized text starts with a piece count as `uvarint`, followed by a two-bit
type for each piece. Four types are packed into each byte, least-significant
bits first. Piece payloads then follow in order:

| Type | Meaning |
|-----:|---------|
| 0 | Literal: byte length as `uvarint`, then bytes |
| 1 | Common token: one-byte token ID from 0 through 255 |
| 2 | Extended token: `uvarint(token_id - 256)` |
| 3 | Reserved and rejected |

The encoder uses greedy longest matching over UTF-8 bytes. Consecutive
unmatched bytes form one literal piece. Tokens beginning or ending with a
letter or digit must match at a Unicode word boundary; short tokens such as
`i`, `u`, or `nis` therefore cannot match inside unrelated words. The encoder
uses tokenized form only when that form is shorter than raw form before
Zstandard compression.

Mode 1 uses the semantic format documented in [`IPQ1.md`](IPQ1.md), including
field-state trits, numeric accounts and amounts, cached text, packed reference
numbers, and exact line-ending restoration.

## Zstandard frame

The reference encoder uses:

- compression level 19;
- the vocabulary as a raw-content dictionary;
- content size in the frame header;
- the Zstandard content checksum; and
- no Zstandard dictionary ID, because the envelope carries a stronger
  vocabulary fingerprint.

The checksum covers the selected representation payload. It detects accidental
corruption but is not authentication and is not resistant to deliberate
modification.

## Benchmarks

The benchmark compares complete archives, including their envelopes:

| Dataset | Input | gzip-9 | Brotli 11 | IPQ1 | IPQ2 | IPQ2/gzip-9 | IPQ2/Brotli |
|---------|------:|-------:|----------:|-----:|-----:|-------------:|-------------:|
| [`example.txt`](example.txt) | 723 B | 283 B | 251 B | 128 B | 158 B | 55.8% | 62.9% |
| [`example_memberships.txt`](example_memberships.txt) | 2,428 B | 695 B | 628 B | 698 B | 552 B | 79.4% | 87.9% |

IPQ2 is more general than the original tax-specific IPQ1 dictionary and
improves the held-out membership corpus by 146 bytes relative to IPQ1. It does
not reach 50% of gzip on either current corpus. The original IPQ1 result does
so only because its preset dictionary closely matches the four tax examples.

IPQ2a adds prefix inheritance while retaining IPQ2's legacy representations
as adaptive fallbacks. It produces 155 bytes for `example.txt` and 553 bytes
for `example_memberships.txt`. See [IPQ2A.md](IPQ2A.md) for its wire format and
the 3- through 6-record subset benchmarks.

## Web Share Links Integration (`/s/v2/`)

IPQ2 powers the compressed web share links (`/s/v2/<payload>`) in the frontend application:

- **Browser Implementation**: A complete TypeScript port of the IPQ2 encoder and decoder runs in the browser (`src/ipq2/`), backed by `zstdify` for raw-dictionary Zstandard WebAssembly execution.
- **Ahead-of-Time Vocabulary**: The 32 KB raw dictionary, token table, and 8-byte SHA-256 fingerprint are compiled at build time into `src/generated/ipq2-vocabulary.ts`, requiring no runtime network requests or TSV parsing.
- **Wire Format in Links**: The binary IPQ2 archive (including its 13-byte envelope) is encoded using unpadded URL-safe Base64 (RFC 4648 §5).
- **Efficiency**: For a typical 4-slip tax batch, `/s/v2/` reduces the share link from 646 characters (legacy `/s/v1/`) down to 242 characters—a 63% reduction.

See [doc/share-link-formats-and-compression.md](doc/share-link-formats-and-compression.md) for the full specification of link formats, sparsification, and codecs.

## Command-line interface

```bash
./ipsqr_zstd.py compress payments.txt -o payments.ipq2
./ipsqr_zstd.py decompress payments.ipq2 -o restored.txt
./ipsqr_zstd.py bench payments.txt
```

A different compatible TSV can be selected explicitly:

```bash
./ipsqr_zstd.py compress --vocabulary vocabulary.tsv payments.txt -o payments.ipq2
./ipsqr_zstd.py decompress --vocabulary vocabulary.tsv payments.ipq2 -o restored.txt
```

Use `-` or omit the input/output path for standard input or standard output.
Compressed output is binary.

## Validation and limits

The decoder rejects the wrong magic, a vocabulary fingerprint mismatch,
unknown modes, malformed or checksummed-corrupt Zstandard frames, trailing
archive data, malformed semantic payloads, invalid token IDs, invalid UTF-8,
and semantic output larger than 256 MiB.

Mode 0 can represent arbitrary bytes when produced manually, but the reference
compressor always parses and validates the input as canonical IPS records
before selecting a mode.
