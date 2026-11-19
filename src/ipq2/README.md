# Browser IPQ2 codec

`src/main.ts` exports a browser-compatible IPQ2 encoder and decoder. The
implementation preserves the Python reference format:

- IPQ1 field-aware semantic encoding and per-field move-to-front caches;
- IPQ2 vocabulary tokenization and all three adaptive modes;
- the `IPQ2` envelope and vocabulary fingerprint;
- raw-content Zstandard dictionaries, content sizes, and checksums; and
- strict size, UTF-8, frame-boundary, and semantic validation.

The vocabulary is compiled by `src/build/compile-vocabulary.ts`. The compiler
derives the dictionary and token table from
`serbian_english_vocabulary.tsv`, serializes them, compresses that serialization
without a dictionary, and writes a Base64 module to
`src/generated/ipq2-vocabulary.ts`. The final browser bundle therefore does not
load the TSV or any adjacent vocabulary asset.

Public API:

```ts
import {
  compress,
  compressText,
  decompress,
  decompressText,
} from "./assets/ipq2.js";
```

All functions are synchronous. Binary functions accept and return
`Uint8Array`. Text helpers encode and decode UTF-8.

## Share links

`src/share-links.ts` exposes the browser share-link formats used by the Alpine
application:

- **`/s/v1/<base64url>` (Legacy Sparse Format)**:
  - Default backward-compatible format.
  - Takes the canonical newline-separated IPS records (`K:PR|V:01|C:1|...`) and runs
    `sparsifyIpsBatch()`, removing field values that duplicate the immediately preceding slip.
  - Converts the resulting sparse string to UTF-8 and encodes it as unpadded Base64URL.
  - Decoded in plain JavaScript without external compression dependencies.

- **`/s/v2/<base64url>` (IPQ2 Compressed Format)**:
  - Enabled when the user selects the **Short link (IPQ2)** checkbox.
  - Calls `compressText()` on the canonical IPS batch, running it through the 3 adaptive
    IPQ2 representation modes (raw UTF-8, IPQ1 semantic payload, and tokenized semantic payload)
    with the 32 KB pre-compiled Zstandard dictionary.
  - Encodes the resulting binary IPQ2 archive (including 13-byte envelope and fingerprint)
    as unpadded Base64URL.
  - Yields a **~63% link length reduction** on 4-slip batches (e.g. 646 down to 242 characters).

Both formats decode into the same canonical IPS batch before the existing form
population logic runs. When v2 is selected, the application compares both URLs
and reports the measured character and percentage savings in the copy toast.

For the detailed specification of wire structures, delta encoding, and compression internals,
see [doc/share-link-formats-and-compression.md](../../doc/share-link-formats-and-compression.md).
