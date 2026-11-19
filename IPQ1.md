# IPQ1 format

IPQ1 is a compact binary archive for a batch of Serbian IPS QR payment
strings. It is specialized for canonical `K:PR`, `V:01`, `C:1` payment
records and is not a general-purpose text compressor.

The reference implementation is [`ipsqr_compress.py`](ipsqr_compress.py).

## Design goals

IPS payment batches contain structure that a general-purpose compressor must
learn again for every file:

- the `K:PR|V:01|C:1|` prefix is fixed;
- field keys and field order are defined by the IPS format;
- names, payment codes, payer data, and references often repeat;
- accounts and amounts are decimal representations of integers; and
- Serbian tax and payment-purpose vocabulary is predictable.

IPQ1 removes or encodes that structure before applying DEFLATE. Current
benchmark results use Python's `gzip.compress(..., compresslevel=9, mtime=0)`:

| Dataset | Records | Input | gzip-9 | IPQ1 | IPQ1/gzip-9 |
|---------|--------:|------:|-------:|-----:|-------------:|
| [`example.txt`](example.txt) | 4 | 723 B | 283 B | 128 B | 45.2% |
| [`example_memberships.txt`](example_memberships.txt) | 20 | 2,428 B | 695 B | 698 B | 100.4% |

The four-record tax dataset is strongly represented in the preset vocabulary.
The broader membership dataset is a held-out example and shows that the
current dictionary does not provide a general 50% guarantee.

## Input model

The input is UTF-8 text with one IPS QR string per line. An accepted record has
this logical form:

```text
K:PR|V:01|C:1|R:...|N:...|I:...|P:...|SF:...|S:...|RO:...
```

The first three fields must be exactly `K:PR|V:01|C:1|`. The remaining fields
are represented internally in this canonical order:

| Index | Field | IPQ1 representation |
|------:|-------|---------------------|
| 0 | `R` | 18-digit account as an integer or account delta |
| 1 | `N` | UTF-8 text with a per-field move-to-front cache |
| 2 | `I` | RSD amount as integer para (cents) |
| 3 | `P` | UTF-8 text with a per-field move-to-front cache |
| 4 | `SF` | three-digit payment code as an integer |
| 5 | `S` | UTF-8 text with a per-field move-to-front cache |
| 6 | `RO` | six-bit reference or cached UTF-8 text |

Fields may be absent, but fields that are present must occur in the order
above. Duplicate and unknown fields are rejected. A record with no variable
fields is rejected.

The current encoder additionally requires:

- `R` to contain exactly 18 ASCII digits;
- `I` to match `RSD(0|[1-9][0-9]*),[0-9]{2}`; and
- `SF` to contain exactly three ASCII digits.

All records must use either LF or CRLF consistently. Blank lines, bare CR, and
mixed line endings are rejected. The line-ending style and presence of the
final newline are preserved exactly.

## Archive envelope

An IPQ1 file has three parts:

| Offset | Size | Description |
|-------:|-----:|-------------|
| 0 | 4 bytes | ASCII magic and version, `IPQ1` |
| 4 | 4 bytes | CRC-32 of the uncompressed semantic payload, big-endian |
| 8 | remaining bytes | Raw DEFLATE stream containing the semantic payload |

The DEFLATE stream uses RFC 1951 without a zlib or gzip wrapper. It is decoded
with the preset dictionary specified below. The CRC is the standard zlib
CRC-32 and is an integrity check, not a cryptographic authenticator.

The encoder currently uses DEFLATE level 9, memory level 9, and the default
strategy. These settings affect compressed size but are not format
requirements. A decoder only needs raw DEFLATE support and the exact preset
dictionary.

## Integer encoding

Most integers use unsigned LEB128, called `uvarint` in the implementation.
Each byte carries seven low-order data bits. Bit 7 is set when another byte
follows. Groups are emitted least significant first.

For example, decimal 300 is encoded as `AC 02`.

Signed account deltas use zigzag encoding followed by `uvarint`:

```text
zigzag(n) = 2 * n          when n >= 0
zigzag(n) = -2 * n - 1     when n < 0
```

Consequently, deltas `0`, `-1`, `1`, `-2`, and `2` become unsigned values
`0`, `1`, `2`, `3`, and `4`.

## Semantic payload

After raw DEFLATE decompression, the payload is:

```text
+-------------+------------------+-------------------+
| flags: u8   | count: uvarint   | record[count]     |
+-------------+------------------+-------------------+
```

The flags byte is defined as follows:

| Bit | Meaning when set |
|----:|------------------|
| 0 | Original input ended with a line separator |
| 1 | Line separator was CRLF; otherwise it was LF |
| 2-7 | Reserved; a decoder must reject them when set |

Empty input is represented by flags `0` and record count `0`.

### Record state

Each record starts with one `uvarint` field-state number. Its seven base-3
digits correspond to `R`, `N`, `I`, `P`, `SF`, `S`, and `RO`, in that order:

| Trit | Meaning |
|-----:|---------|
| 0 | Field is absent in this record |
| 1 | Field is identical to the immediately preceding record |
| 2 | A new field value follows in the record body |

The state number is calculated as:

```text
state = sum(trit[i] * 3**i for i in range(7))
```

Its maximum valid value is `3**7 - 1`, or 2186, so every state occupies at
most two bytes. Trit 1 is invalid when the preceding record does not contain
that field.

Values for all trit-2 fields follow the state number in canonical field order.
There are no textual field names or separators in the record body.

For a first record containing all seven fields, every trit is 2. Its state is
2186 and its `uvarint` bytes are `8A 11`. In the sample batch, later records
change only `R`, `I`, and `S`; the other fields are inherited without storing
their values again.

## Field encodings

### Account (`R`)

If the preceding record has no `R` value, the 18-digit decimal account is
converted to an unsigned integer and stored as exactly eight bytes,
big-endian. Leading zeroes are restored by formatting the result to 18 digits.

If the preceding record has an `R` value, IPQ1 stores:

```text
uvarint(zigzag(current_account - previous_account))
```

This is effective for batches whose destination accounts are numerically
close. There is no account encoding tag; the previous field state determines
whether the value is full-width or a delta.

### Amount (`I`)

The `RSD` prefix and decimal comma are implicit. The amount is converted to
integer para and stored as a `uvarint`:

```text
RSD44700,00 -> 4_470_000 -> uvarint(4_470_000)
```

The decoder restores the `RSD` prefix, decimal comma, and exactly two decimal
digits.

### Payment code (`SF`)

The three decimal digits are converted to an integer and stored as a
`uvarint`. The decoder pads the result to three digits. Values above 999 are
invalid.

### Text (`N`, `P`, and `S`)

Each text field has an independent move-to-front cache of previously emitted
UTF-8 byte strings. An encoded text value starts with a `uvarint` code:

```text
code = 0:  byte_length: uvarint, followed by byte_length UTF-8 bytes
code > 0:  cache entry at zero-based index code - 1
```

A literal is inserted at the front of its field's cache. A cache reference is
moved to the front after use. Encoder and decoder perform the same operation,
so the cache itself is never written to the archive.

An unchanged value is represented by record-state trit 1 and does not touch
the cache. The cache is useful when values recur after intervening records.

### Reference (`RO`)

`RO` begins with a one-byte encoding tag.

Tag `0` is used when every character belongs to this alphabet:

```text
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ
```

It is followed by the character count as a `uvarint`, then one six-bit
alphabet index per character. Six-bit groups are concatenated most significant
bit first and the last byte is padded with zero bits on the right. The encoded
byte count is `ceil(character_count * 6 / 8)`.

Tag `1` uses the move-to-front text encoding described above, with a separate
cache for `RO`. This fallback preserves references containing characters
outside the six-bit alphabet.

## Preset DEFLATE dictionary

The dictionary is not stored in each archive. It is part of the IPQ1 format,
and changing it requires a new format version and magic. Its exact bytes are
the UTF-8 encoding of the following Python string concatenation:

```python
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
```

A preset dictionary matters most for short batches: gzip cannot learn useful
domain phrases until they have already occurred in the input. Common phrases
near the end of this dictionary receive priority from DEFLATE's limited
history window.

## Compression process

The reference compressor performs these steps:

1. Detect and preserve LF/CRLF style and final-newline state.
2. Decode UTF-8 and parse each canonical IPS record.
3. Remove `K:PR|V:01|C:1|` and all remaining textual field keys.
4. Produce the field-state number and specialized values for every record.
5. Compute CRC-32 over the complete semantic payload.
6. Compress the semantic payload with raw DEFLATE and the preset dictionary.
7. Emit `IPQ1`, the big-endian checksum, and the DEFLATE bytes.

Decompression reverses these steps. Field keys are restored from their
positions, and `K:PR|V:01|C:1|` is inserted before every record.

## Decoder validation

The reference decoder rejects:

- the wrong magic or an archive too short to contain an IPQ1 envelope;
- malformed or truncated DEFLATE data;
- bytes after the end of the DEFLATE stream;
- a semantic-payload CRC mismatch;
- unknown flags;
- truncated or excessively large variable-length integers;
- more than 1,000,000 records;
- field-state values greater than 2186;
- inheritance from an absent field;
- invalid UTF-8 or text literals larger than 1,000,000 bytes;
- malformed packed references or payment codes; and
- unused bytes after the final semantic record.

CRC-32 detects accidental corruption but provides no protection against a
maliciously modified archive. IPQ1 does not provide authentication,
encryption, or signatures.

## Compatibility and limitations

- IPQ1 archives require the exact static dictionary associated with `IPQ1`.
- The format accepts only the fixed `PR/01/1` prefix and canonical variable
  field order implemented by the reference codec.
- Numeric reconstruction is lossless only because the encoder rejects
  non-canonical account, amount, and payment-code spellings.
- The Python implementation reads and decompresses the complete archive in
  memory. Its post-decompression limits are validation limits, not protection
  against a DEFLATE decompression bomb.
- Compression gains depend on batch similarity. IPQ1 is intended for related
  IPS payment records and may not beat a general-purpose compressor on
  unrelated or highly diverse data.

## Relationship to Web Share Links and IPQ2

- **Legacy Web Share Links (`/s/v1/`)**: The static web application's `/s/v1/` links share IPQ1's concept of field inheritance between successive payment records, but in a simplified text-based "sparse" format encoded directly with Base64URL rather than binary DEFLATE.
- **Foundation for IPQ2 and `/s/v2/`**: IPQ1's semantic record layout (7-trit field-state numbers, zigzag delta accounts, integer para amounts, and move-to-front text caches) is preserved intact as the semantic core of [IPQ2](IPQ2.md) (Mode 1 and Mode 2), which is used in compressed `/s/v2/` web share links.

For full details on web share link formats and compression algorithms, see [doc/share-link-formats-and-compression.md](doc/share-link-formats-and-compression.md).

## Command-line interface

```bash
./ipsqr_compress.py compress payments.txt -o payments.ipq
./ipsqr_compress.py decompress payments.ipq -o restored.txt
./ipsqr_compress.py bench payments.txt
```

Use `-` or omit a path to read from standard input or write to standard output.
Compressed output is binary.
