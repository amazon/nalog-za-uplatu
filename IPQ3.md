# IPQ3 format

IPQ3 is a Brotli-based compressor for batches of Serbian IPS QR payment
strings. It supplies Brotli with a deterministic shared raw dictionary derived
from the complete Serbian-English vocabulary and also evaluates IPQ1's
field-aware semantic representation.

The reference implementation is
[`ipsqr_brotli.py`](ipsqr_brotli.py). Its vocabulary source is
[`serbian_english_vocabulary.tsv`](serbian_english_vocabulary.tsv), interpreted
by IPQ2's `Vocabulary` class.

This design replaces the earlier IPQ3 rare-word alias prototype. IPQ3 was not
released, so compatibility with prototype archives is intentionally not
preserved.

## Requirements

IPQ3 compression requires a Brotli command-line executable that supports the
`--dictionary` option. Brotli 1.2 provides this option:

```text
-D FILE, --dictionary=FILE  use FILE as raw (LZ77) dictionary
```

The common Python `brotli` and `brotlicffi` APIs do not expose shared
dictionary attachment. IPQ3 can use them for ordinary Brotli modes, but it
requires the command-line backend to create or restore dictionary-backed
frames.

## Shared dictionary

The current vocabulary produces 2,831 distinct terms. These include complete
values, individual words, capitalization variants, and common Serbian ASCII
spellings such as `članarina` / `clanarina`.

IPQ3 builds the shared dictionary as follows:

1. Append fixed IPS field fragments used by raw-text mode.
2. Append every vocabulary term separated by LF bytes.
3. Reverse IPQ2's term order before appending.

Brotli treats a raw dictionary as history immediately preceding the input.
IPQ2 orders terms from most useful to least useful, so reversing that order
places high-value payment terms at the end of the dictionary and gives them
shorter backward distances.

The resulting dictionary is currently 35,984 bytes:

```text
IPS format fragments
least useful vocabulary term
...
most useful vocabulary term
```

The dictionary is not stored in each archive. Encoder and decoder independently
derive the same bytes from the vocabulary.

## Adaptive representations

IPQ3 Brotli-compresses four candidates at quality 11 and stores the smallest:

| Mode | Representation | Shared dictionary |
|---:|---|---|
| 0 | Original IPS UTF-8 text | No |
| 1 | IPQ1 semantic payload | No |
| 2 | Original IPS UTF-8 text | Yes |
| 3 | IPQ1 semantic payload | Yes |

Modes 0 and 1 prevent a shared dictionary from making unusual input larger.
Typical IPS batches select mode 2 or 3.

## Archive envelope

| Offset | Size | Description |
|---:|---:|---|
| 0 | 4 bytes | ASCII magic and version, `IPQ3` |
| 4 | 8 bytes | Shared-dictionary fingerprint |
| 12 | 1 byte | Representation mode |
| 13 | 4 bytes | CRC-32 of the original IPS data, big-endian |
| 17 | remaining bytes | Brotli stream |

The fingerprint is the first eight bytes of SHA-256 over a derivation-version
marker, the dictionary length, and all dictionary bytes. A changed vocabulary,
term ordering, or derivation algorithm is rejected before decompression.

Modes 2 and 3 are not self-contained Brotli streams. A decoder must attach the
exact shared dictionary identified by the fingerprint. Decompressing one of
these streams with ordinary Brotli and no dictionary fails.

The CRC-32 validates the fully reconstructed IPS data. It detects corruption
but is not authentication against deliberate modification.

## Usage

```bash
./ipsqr_brotli.py compress payments.txt -o payments.ipq3
./ipsqr_brotli.py decompress payments.ipq3 -o restored.txt
./ipsqr_zstd.py bench payments.txt
```

## Current benchmark

| Dataset | Plain Brotli 11 | Alias prototype | Shared-dictionary IPQ3 |
|---|---:|---:|---:|
| Four tax records | 251 bytes | 220 bytes | 177 bytes |
| 20 membership records | 628 bytes | 624 bytes | 498 bytes |

The 20-record result is also smaller than the current 552-byte IPQ2 result.
On the four-record set, IPQ2 remains smaller at 158 bytes.

## Limits

- Dictionary-backed archives require the exact vocabulary and derivation used
  by the encoder.
- The Brotli CLI writes a temporary 35,984-byte dictionary file for each
  compression or decompression operation.
- The command-line fallback buffers decompressed output before applying the
  256 MiB payload limit.
- Small batches still pay the 17-byte IPQ3 envelope cost.
