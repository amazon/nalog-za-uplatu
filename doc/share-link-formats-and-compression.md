# Share Link Formats and Compression Algorithms

This document provides a comprehensive technical specification of the share link formats (`/s/v1/` and `/s/v2/`) and compression algorithms (IPQ1 and IPQ2) used in the Serbian Payment Slip Generator (*Nalog za uplatu* / *QR Uplatnica*).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Share Link Formats](#2-share-link-formats)
   - [2.1 Canonical IPS QR Representation](#21-canonical-ips-qr-representation)
   - [2.2 v1 Share Link (`/s/v1/` — Legacy Sparse Format)](#22-v1-share-link-sv1--legacy-sparse-format)
     - [Sparsification (Field Delta Encoding)](#sparsification-field-delta-encoding)
     - [Encoding Pipeline](#v1-encoding-pipeline)
     - [Decoding & De-sparsification](#v1-decoding--de-sparsification)
   - [2.3 v2 Share Link (`/s/v2/` — IPQ2 Compressed Format)](#23-v2-share-link-sv2--ipq2-compressed-format)
     - [Encoding Pipeline](#v2-encoding-pipeline)
     - [Decoding Pipeline](#v2-decoding-pipeline)
     - [URL Length Comparison & Benchmark](#url-length-comparison--benchmark)
   - [2.4 Base64URL Encoding Standard](#24-base64url-encoding-standard)
3. [Compression Algorithms](#3-compression-algorithms)
   - [3.1 IPQ1 (DEFLATE + Semantic Delta Codec)](#31-ipq1-deflate--semantic-delta-codec)
     - [Wire Envelope](#ipq1-wire-envelope)
     - [Semantic Representation & Field Trits](#ipq1-semantic-representation--field-trits)
     - [Field-Specific Value Encodings](#ipq1-field-specific-value-encodings)
     - [Preset Static DEFLATE Dictionary](#ipq1-preset-static-deflate-dictionary)
   - [3.2 IPQ2 (Zstandard + Domain Vocabulary Tokenization)](#32-ipq2-zstandard--domain-vocabulary-tokenization)
     - [Wire Envelope & Vocabulary Fingerprint](#ipq2-wire-envelope--vocabulary-fingerprint)
     - [Vocabulary Derivation & Raw Dictionary](#ipq2-vocabulary-derivation--raw-dictionary)
     - [Token Table & Word-Boundary Trie Tokenization](#ipq2-token-table--word-boundary-trie-tokenization)
     - [Adaptive Representation Modes](#ipq2-adaptive-representation-modes)
     - [Zstandard Frame Parameters](#ipq2-zstandard-frame-parameters)
   - [3.3 Comparative Summary](#33-comparative-summary)
4. [Browser Implementation Architecture](#4-browser-implementation-architecture)
   - [4.1 Vocabulary Ahead-of-Time (AOT) Compilation](#41-vocabulary-ahead-of-time-aot-compilation)
   - [4.2 Browser Bundle & WebAssembly Zstandard](#42-browser-bundle--webassembly-zstandard)
   - [4.3 Jekyll SPA Fallback Routing](#43-jekyll-spa-fallback-routing)

---

## 1. Overview

The Payment Slip Generator allows users to prepare batches of Serbian payment slips (e.g. for taxes, utilities, membership fees) and share them via a single URL. Sharing payment batches via URL requires balancing two competing constraints:
1. **URL Size & Compatibility**: Browsers, web servers, and chat platforms have practical URL length limitations (typically 2,048 characters for broad reliability). Uncompressed batches of several payment slips easily exceed this when Base64-encoded.
2. **Backward Compatibility & Client Complexity**: Earlier versions of the generator ran purely as static HTML/JS without external compilation or WebAssembly compression libraries.

To solve this, the application supports two link versions:
- **v1 (`/s/v1/`)**: A backward-compatible, text-based delta format ("sparse format") that requires zero external compression dependencies and decodes in plain JavaScript.
- **v2 (`/s/v2/`)**: An opt-in, highly compressed format that encodes a binary **IPQ2** archive inside Base64URL, cutting link lengths by over **60%**.

---

## 2. Share Link Formats

### 2.1 Canonical IPS QR Representation

Both link formats start from and reconstruct the canonical Serbian NBS IPS (Instant Payment System) QR format. Each slip is represented by a pipe-delimited string of key-value pairs (`KEY:value`):

```text
K:PR|V:01|C:1|R:account|N:payer|I:amount|P:receiver|SF:code|S:purpose|RO:reference
```

Canonical field definitions and canonical field order:
| Key | Name | IPS Meaning | Example |
|:---:|:---|:---|:---|
| `K` | Identifier | Fixed value `PR` (Payment Request) | `PR` |
| `V` | Version | Format version `01` | `01` |
| `C` | Character set | `1` (UTF-8) | `1` |
| `R` | Account (*Račun*) | 18-digit recipient bank account | `840000000123456789` |
| `N` | Payer (*Naziv platioca*) | Name and address of the payer | `PETAR PETROVIC` |
| `I` | Amount (*Iznos*) | Currency prefix `RSD` followed by decimal comma | `RSD12500,00` |
| `P` | Recipient (*Primalac*) | Name and address of the recipient | `PORESKA UPRAVA` |
| `SF`| Payment Code (*Šifra*) | 3-digit payment code | `253` |
| `S` | Purpose (*Svrha*) | Purpose of payment | `POREZ NA DOHODAK` |
| `RO`| Reference (*Poziv na broj*) | 2-digit model + reference number | `9712345678901234` |

Multiple slips are concatenated with newline characters (`\n`).

---

### 2.2 v1 Share Link (`/s/v1/` — Legacy Sparse Format)

- **URL Prefix**: `https://<host>/s/v1/<encodedData>`
- **Content**: Base64URL-encoded UTF-8 string of a *sparsified* IPS batch.
- **Dependency**: Built-in browser `atob` and `TextDecoder`.

#### Sparsification (Field Delta Encoding)
In typical multi-slip batches (e.g. paying quarterly taxes or family bills), consecutive slips share many identical fields (same payer `N`, same recipient `P`, same payment code `SF`, same account `R`).

The v1 encoder applies field-level deduplication:
1. Slips are evaluated in sequence.
2. For the **first slip**, all present fields are retained in canonical order (`K`, `V`, `C`, `R`, `N`, `I`, `P`, `SF`, `S`, `RO`).
3. For each **subsequent slip**, each field is compared against the value of the same field in the immediately preceding slip.
4. If the value is identical to the preceding slip's value, the field value is emitted empty (`KEY:`).
5. If the field is newly introduced, changed, or differs from the predecessor, its value is retained (`KEY:value`).

#### Example of Sparsification

**Canonical Batch (2 slips):**
```text
K:PR|V:01|C:1|R:840000000123456789|N:PETAR PETROVIC|I:RSD12000,00|P:PORESKA UPRAVA|SF:253|S:POREZ NA DOHODAK|RO:97112233
K:PR|V:01|C:1|R:840000000123456789|N:PETAR PETROVIC|I:RSD3500,00|P:PORESKA UPRAVA|SF:253|S:ADMINISTRATIVNA TAKSA|RO:97445566
```

**Sparsified Output:**
```text
K:PR|V:01|C:1|R:840000000123456789|N:PETAR PETROVIC|I:RSD12000,00|P:PORESKA UPRAVA|SF:253|S:POREZ NA DOHODAK|RO:97112233
K:|V:|C:|R:|N:|I:RSD3500,00|P:|SF:|S:ADMINISTRATIVNA TAKSA|RO:97445566
```

#### v1 Encoding Pipeline
```
[ Slip Form Models ]
       │
       ▼
[ Canonical IPS Strings (\n separated) ]
       │
       ▼
[ sparsifyIpsBatch() ]
       │
       ▼
[ UTF-8 Encode (Uint8Array) ]
       │
       ▼
[ Base64URL Encode ]
       │
       ▼
[ URL: /s/v1/<base64url> ]
```

#### v1 Decoding & De-sparsification
When a user opens `/s/v1/<encodedData>`:
1. The path regex `/^\/s\/v1\/([A-Za-z0-9_-]+)$/` extracts the payload.
2. Base64URL decoding produces the raw UTF-8 bytes.
3. The string is split into lines by newline `\n`.
4. For each slip:
   - Each field is parsed by locating the first colon separator (`:`).
   - If a field is empty (e.g. `R:`), its value is inherited from `prevFields[key]`.
   - The reconstructed full field map is converted into the application's slip model (formatting account dashes, amounts, and reference models).

---

### 2.3 v2 Share Link (`/s/v2/` — IPQ2 Compressed Format)

- **URL Prefix**: `https://<host>/s/v2/<encodedData>`
- **Content**: Base64URL-encoded binary **IPQ2** archive.
- **Dependency**: Browser IPQ2 WebAssembly/pure-JS bundle (Zstandard + tokenization).

#### v2 Encoding Pipeline
```
[ Slip Form Models ]
       │
       ▼
[ Canonical IPS Batch (UTF-8 String) ]
       │
       ▼
[ IPQ2 compressText() ]
  ├── Mode 0 Candidate: Raw UTF-8 + Zstd (Level 19, Dict)
  ├── Mode 1 Candidate: IPQ1 Semantic Payload + Zstd
  └── Mode 2 Candidate: Tokenized Semantic Payload + Zstd
  └── Select smallest compressed frame
  └── Prepend 13-byte Envelope (Magic + Fingerprint + Mode)
       │
       ▼
[ IPQ2 Binary Archive (Uint8Array) ]
       │
       ▼
[ Base64URL Encode ]
       │
       ▼
[ URL: /s/v2/<base64url> ]
```

#### v2 Decoding Pipeline
When a user opens `/s/v2/<encodedData>`:
1. The path regex `/^\/s\/v2\/([A-Za-z0-9_-]+)$/` extracts the payload.
2. Base64URL decoding produces a `Uint8Array`.
3. The IPQ2 decompressor validates the 13-byte header:
   - Magic must match `IPQ2`.
   - The 8-byte vocabulary fingerprint must match the compiled application dictionary (`0abe2369576c0501`).
   - The representation mode must be 0, 1, or 2.
4. Zstandard decompression unpacks the frame using the pre-compiled dictionary.
5. The decompressed payload is unpacked according to the mode:
   - **Mode 0**: Decoded directly as UTF-8 canonical IPS text.
   - **Mode 1 & 2**: Field trits, move-to-front caches, numbers, and tokens are unpacked into canonical IPS QR records.
6. The resulting canonical lines are passed to `decodeV1()` (which handles standard slip model reconstruction).

#### URL Length Comparison & Benchmark

Testing with a realistic 4-slip municipal tax payment batch (`example.txt`):

| Link Format | Total URL Length | Base64 Payload Length | Reduction |
|:---|:---:|:---:|:---:|
| **v1 (Legacy Sparse)** | 646 chars | 638 chars | Baseline |
| **v2 (IPQ2 Compressed)** | 242 chars | 234 chars | **-404 chars (-62.5%)** |

For 20-slip batches (`example_memberships.txt`):
| Link Format | Total URL Length | Base64 Payload Length | Reduction |
|:---|:---:|:---:|:---:|
| **v1 (Legacy Sparse)** | 2,128 chars | 2,120 chars | Baseline (exceeds safe URL length) |
| **v2 (IPQ2 Compressed)** | 750 chars | 742 chars | **-1,378 chars (-64.8%)** (well within safe limit) |

---

### 2.4 Base64URL Encoding Standard

Both v1 and v2 use URL-safe Base64 as specified in RFC 4648 Section 5:
- Character 62 (`+`) is replaced by minus (`-`).
- Character 63 (`/`) is replaced by underscore (`_`).
- Trailing padding characters (`=`) are stripped during encoding and restored during decoding.

---

## 3. Compression Algorithms

### 3.1 IPQ1 (DEFLATE + Semantic Delta Codec)

IPQ1 was designed as a domain-specific binary compressor for Serbian IPS payment strings (`ipsqr_compress.py`). It strips syntax overhead and models field variations before applying raw DEFLATE with a preset dictionary.

#### IPQ1 Wire Envelope
```text
+-------------------+----------------------+-----------------------------+
| magic: b"IPQ1"    | crc32: u32 (big-end) | raw DEFLATE stream ...      |
| (4 bytes)         | (4 bytes)            | (remaining bytes)           |
+-------------------+----------------------+-----------------------------+
```

#### IPQ1 Semantic Representation & Field Trits
Inside the decompressed payload:
```text
+-------------+------------------+-------------------+
| flags: u8   | count: uvarint   | record[count]     |
+-------------+------------------+-------------------+
```
- **Flags**: Bit 0 = ends with newline; Bit 1 = line endings were CRLF (otherwise LF).
- **Field-State Trits**: Each record begins with a single variable-length integer (`uvarint` / LEB128) representing a 7-trit (base-3) state number for the 7 variable fields in canonical order:
  `R` (0), `N` (1), `I` (2), `P` (3), `SF` (4), `S` (5), `RO` (6).
  $$\text{state} = \sum_{i=0}^6 \text{trit}[i] \times 3^i$$
  - `Trit 0`: Field absent.
  - `Trit 1`: Field identical to previous record (inherited without writing any bytes).
  - `Trit 2`: New field value follows in record body.

#### IPQ1 Field-Specific Value Encodings
1. **Account (`R`)**:
   - First appearance: 18-digit integer stored as 8 bytes big-endian.
   - Subsequent appearances: signed delta from previous account encoded with zigzag + `uvarint`.
2. **Amount (`I`)**:
   - `RSD` and comma stripped; amount converted to integer para (cents) and stored as `uvarint`.
3. **Payment Code (`SF`)**:
   - Stored as an integer via `uvarint` (padded to 3 digits on decode).
4. **Text (`N`, `P`, `S`)**:
   - Each field maintains an independent move-to-front (MTF) cache.
   - Code `0`: New literal (length as `uvarint` followed by UTF-8 bytes); pushed to cache index 0.
   - Code `> 0`: Cache reference at index `code - 1`; entry moved to index 0.
5. **Reference Number (`RO`)**:
   - Tag `0`: 6-bit packed alphanumeric encoding for standard characters (`0-9A-Z`), saving 25% space.
   - Tag `1`: Move-to-front text encoding fallback for references with punctuation or special characters.

#### IPQ1 Preset Static DEFLATE Dictionary
IPQ1 uses raw RFC 1951 DEFLATE initialized with a fixed 386-byte UTF-8 string containing common Serbian administrative and banking terms:
```python
"nalog za uplatu platilac primalac iznos račun primaoca poziv na broj "
"odobrenje svrha plaćanja šifra plaćanja valuta RSD javni prihodi "
"Republika Srbija Republike Srbije ministarstvo uprava porez doprinos "
"osiguranje zdravstveno penzijsko invalidsko nezaposlenost samostalna "
"delatnost porez na prihode doprinos za osiguranje Poreska uprava "
"Republike Srbije Porez na prihode od samostalne delatnosti "
"Doprinos za zdravstveno osiguranje Doprinos za slucaj nezaposlenosti "
"Doprinos za penzijsko i invalidsko osiguranje"
```

---

### 3.2 IPQ2 (Zstandard + Domain Vocabulary Tokenization)

IPQ2 improves upon IPQ1 by moving from DEFLATE to Zstandard (level 19), utilizing a deterministic 32,822-byte raw dictionary derived from `serbian_english_vocabulary.tsv`, tokenizing text at Unicode word boundaries, and adaptively choosing between three representation modes.

#### IPQ2 Wire Envelope & Vocabulary Fingerprint
```text
+----------------+------------------------+-----------+----------------------+
| magic: b"IPQ2" | fingerprint: [8]byte   | mode: u8  | Zstd Frame ...       |
| (4 bytes)      | (8 bytes)              | (1 byte)  | (remaining bytes)    |
+----------------+------------------------+-----------+----------------------+
```
The **fingerprint** is the first 8 bytes of the SHA-256 hash computed over:
- Hash prefix `IPQ2-derived-vocabulary-v2\0`
- 8-byte big-endian length of the raw dictionary + raw dictionary bytes
- Each token length (4-byte big-endian) + token UTF-8 bytes

This ensures that an archive cannot be decoded with a modified or out-of-sync vocabulary.

#### IPQ2 Vocabulary Derivation & Raw Dictionary
The source vocabulary `serbian_english_vocabulary.tsv` contains payment, organizational, geographic, and tax terminology.
From this TSV, the compiler generates:
1. Full values in Serbian Latin and English.
2. Case variants: lowercase, title case, uppercase.
3. Serbian ASCII transliterations (`č, ć -> c`, `š -> s`, `ž -> z`, `đ -> dj`).
4. Priority words boosted to receive 1-byte token IDs (e.g. `za`, `i`, `u`, `na`, `porez`, `racun`, `uplata`, etc.).

The raw dictionary consists of these distinct phrases separated by newlines (`\n`), totaling 32,822 bytes.

#### IPQ2 Token Table & Word-Boundary Trie Tokenization
The token table contains 2,831 terms:
- **Common Tokens (IDs 0–255)**: 256 highest-ranked words, encoded as a single byte.
- **Extended Tokens (IDs 256+)**: Encoded as `uvarint(token_id - 256)`.

During tokenization:
- Longest-prefix matching is performed using a byte trie.
- Boundary condition: Tokens starting or ending with alphanumeric characters are prevented from matching inside unrelated words (word-boundary guard), preventing erroneous sub-word tokenization.

Tokenized text serialization:
- 1 byte `TEXT_TOKENIZED` tag (`1`).
- `uvarint(piece_count)`.
- 2-bit packed piece types (4 pieces per byte):
  - `00` (`PIECE_LITERAL`): Raw byte sequence (`uvarint` length + bytes).
  - `01` (`PIECE_COMMON_TOKEN`): 1-byte token ID.
  - `10` (`PIECE_EXTENDED_TOKEN`): `uvarint(token_id - 256)`.
- Piece payloads in sequence.

#### IPQ2 Adaptive Representation Modes
The compressor builds three candidate representations and selects the one that produces the fewest total bytes after Zstandard compression:
- **Mode 0 (`MODE_RAW_TEXT`)**:
  Raw UTF-8 canonical IPS text compressed against the Zstandard dictionary. Highly effective when global repetitive text dominates.
- **Mode 1 (`MODE_SEMANTIC`)**:
  IPQ1 semantic payload (trits, delta integers, MTF caches) compressed against the Zstandard dictionary.
- **Mode 2 (`MODE_TOKENIZED_SEMANTIC`)**:
  IPQ1 semantic payload where text fields are tokenized using the IPQ2 token table, then compressed against the Zstandard dictionary.

#### IPQ2 Zstandard Frame Parameters
- Compression Level: 19
- Content Size Flag: enabled (stored in frame header)
- Checksum Flag: enabled (4-byte XXH64 content checksum)
- Dict ID Flag: 0 (disabled in Zstd header because the envelope has the stronger 8-byte fingerprint)

---

### 3.3 Comparative Summary

| Feature | IPQ1 | IPQ2 | IPQ2a (Experimental) |
|:---|:---|:---|:---|
| **Magic** | `IPQ1` | `IPQ2` | `IPQ2a` |
| **Primary Codec** | DEFLATE (RFC 1951) | Zstandard (Level 19) | Zstandard (Level 19) |
| **Envelope Header** | 8 bytes (`IPQ1` + CRC32) | 13 bytes (`IPQ2` + Fingerprint + Mode) | 14 bytes (`IPQ2a` + Fingerprint + Mode) |
| **Dictionary Type** | 386 B static text string | 32,822 B raw-content dictionary | 32,822 B raw-content dictionary |
| **Tokenization** | None (MTF text cache only) | 2,831-token trie + boundary check | 2,831-token trie + boundary check |
| **Adaptive Modes** | None (Single mode) | 3 modes (Raw, Semantic, Tokenized) | 5 modes (Adds prefix-inheritance) |
| **Browser Web Support** | Python CLI | TypeScript + `zstdify` WebAssembly | Python CLI |
| **Web Share Link** | Basis for `/s/v1/` sparse model | Powers `/s/v2/` compressed links | — |

---

## 4. Browser Implementation Architecture

The browser integration is implemented in TypeScript within `src/` and bundled into `src/ipq2.js`:

### 4.1 Vocabulary Ahead-of-Time (AOT) Compilation
At build time, `src/build/compile-vocabulary.ts`:
1. Reads `serbian_english_vocabulary.tsv`.
2. Derives the raw dictionary, tokens, and SHA-256 fingerprint.
3. Compresses the serialized structures into a compact Base64 payload.
4. Outputs `src/generated/ipq2-vocabulary.ts`.

This guarantees that zero TSV parsing or dictionary derivation happens at browser runtime.

### 4.2 Browser Bundle & WebAssembly Zstandard
- `src/main.ts` exports `compressText`, `decompressText`, `buildShareUrl`, `parseSharePath`, and `decodeShareData`.
- Bundled using `esbuild` into a standalone ES module `src/ipq2.js`.
- Uses `zstdify` for browser-compatible Zstandard compression and decompression with raw dictionary support.

### 4.3 Jekyll SPA Fallback Routing
GitHub Pages serves the static site using Jekyll. To allow links like `/s/v1/...` and `/s/v2/...` to load seamlessly:
- `src/404.html` or Jekyll rewrite routes serve `src/index.html`.
- On window load, Alpine.js checks `window.location.pathname`.
- `parseSharePath()` detects version 1 or version 2.
- Payment slips are unpacked and automatically populated into the form.

---

## 5. AI Assistant & Agent Direct Generation

Because the v1 link format relies on simple line-based text sparsification and RFC 4648 §5 Base64URL encoding (without binary dictionary compressors), AI models (ChatGPT, Gemini, DeepSeek, Claude) can generate valid share links directly in conversation from user-provided invoices or bills.

For step-by-step agent instructions, transliteration tables, and prompt templates, see [doc/agents.md](agents.md) and [llms.txt](../llms.txt).

