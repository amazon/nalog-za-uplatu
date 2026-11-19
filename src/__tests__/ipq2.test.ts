import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

import { describe, expect, test } from "vitest";

import { bytesEqual, bytesToHex } from "../ipq2/bytes.js";
import { getEmbeddedVocabulary } from "../ipq2/embedded-vocabulary.js";
import { FormatError } from "../ipq2/errors.js";
import { buildPayload, restorePayload } from "../ipq2/ipq1-semantic.js";
import {
  MODE_RAW_TEXT,
  MODE_SEMANTIC,
  MODE_TOKENIZED_SEMANTIC,
  compress,
  compressWithMode,
  decompress,
  type RepresentationMode,
} from "../ipq2/ipq2.js";
import {
  COMMON_TOKEN_COUNT,
  PIECE_COMMON_TOKEN,
  PIECE_EXTENDED_TOKEN,
  TEXT_TOKENIZED,
  serializeTokenized,
} from "../ipq2/tokenized-text.js";
import { decodeUtf8, encodeUtf8 } from "../ipq2/utf8.js";

const vocabulary = getEmbeddedVocabulary();
const examples = ["example.txt", "example_memberships.txt"].map((path) => ({
  path,
  data: new Uint8Array(readFileSync(path)),
}));

describe("compiled IPQ2 vocabulary", () => {
  test("matches the Python reference metadata", () => {
    expect(bytesToHex(vocabulary.fingerprint)).toBe("0abe2369576c0501");
    expect(vocabulary.rawDictionary.length).toBe(32_822);
    expect(vocabulary.terms.length).toBe(2_831);
  });

  test("keeps priority terms in the common token range", () => {
    for (const word of ["za", "račun", "racun", "porez", "doprinos"]) {
      expect(vocabulary.findTerm(word)).toBeGreaterThanOrEqual(0);
      expect(vocabulary.findTerm(word)).toBeLessThan(COMMON_TOKEN_COUNT);
    }
  });

  test("uses the exact common and extended token encodings", () => {
    for (const tokenId of [0, 255]) {
      const encoded = serializeTokenized(
        vocabulary,
        vocabulary.terms[tokenId]!,
      );
      expect([...encoded]).toEqual([
        TEXT_TOKENIZED,
        1,
        PIECE_COMMON_TOKEN,
        tokenId,
      ]);
    }

    const encoded = serializeTokenized(
      vocabulary,
      vocabulary.terms[COMMON_TOKEN_COUNT]!,
    );
    expect([...encoded]).toEqual([
      TEXT_TOKENIZED,
      1,
      PIECE_EXTENDED_TOKEN,
      0,
    ]);
  });

  test("respects Unicode word boundaries", () => {
    expect(vocabulary.tokenize(encodeUtf8("Teniski"))).toEqual([
      encodeUtf8("Teniski"),
    ]);
    expect(vocabulary.tokenize(encodeUtf8("redovni"))).toEqual([
      encodeUtf8("redovni"),
    ]);
    expect(vocabulary.tokenize(encodeUtf8("izraz"))).toEqual([
      encodeUtf8("izraz"),
    ]);
    expect(vocabulary.tokenize(encodeUtf8("za porez"))).toEqual([
      vocabulary.findTerm("za"),
      encodeUtf8(" "),
      vocabulary.findTerm("porez"),
    ]);
  });
});

describe("IPQ1 semantic payload", () => {
  test("round-trips examples, empty input, LF, and CRLF", () => {
    const cases = [
      new Uint8Array(),
      ...examples.map(({ data }) => data),
      examples[0]!.data.subarray(0, examples[0]!.data.length - 1),
      encodeUtf8(decodeUtf8(examples[0]!.data).replaceAll("\n", "\r\n")),
    ];

    for (const data of cases) {
      expect(bytesEqual(restorePayload(buildPayload(data)), data)).toBe(true);
    }
  });
});

describe("IPQ2 archive", () => {
  test("round-trips every representation mode", () => {
    const modes: RepresentationMode[] = [
      MODE_RAW_TEXT,
      MODE_SEMANTIC,
      MODE_TOKENIZED_SEMANTIC,
    ];
    for (const { data } of examples) {
      for (const mode of modes) {
        const archive = compressWithMode(data, vocabulary, mode);
        expect(bytesEqual(decompress(archive, vocabulary), data)).toBe(true);
      }
    }
  });

  test("round-trips adaptively", () => {
    for (const { data } of examples) {
      expect(bytesEqual(decompress(compress(data, vocabulary), vocabulary), data))
        .toBe(true);
    }
  });

  test("rejects fingerprint mismatches and trailing frame data", () => {
    const archive = compress(examples[0]!.data, vocabulary);

    const wrongFingerprint = archive.slice();
    wrongFingerprint[4] = wrongFingerprint[4]! ^ 1;
    expect(() => decompress(wrongFingerprint, vocabulary)).toThrow(
      /fingerprint mismatch/u,
    );

    const trailing = new Uint8Array(archive.length + 1);
    trailing.set(archive);
    trailing[trailing.length - 1] = 1;
    expect(() => decompress(trailing, vocabulary)).toThrow(
      /trailing IPQ2 archive data/u,
    );
  });

  test("rejects corrupt checksummed frames", () => {
    const archive = compress(examples[0]!.data, vocabulary);
    const corrupt = archive.slice();
    corrupt[corrupt.length - 1] = corrupt[corrupt.length - 1]! ^ 1;
    expect(() => decompress(corrupt, vocabulary)).toThrow(FormatError);
  });
});

const pythonProbe = spawnSync(
  "python3",
  [
    "-c",
    [
      "from pathlib import Path",
      "import ipsqr_zstd as m",
      "v=m.Vocabulary(Path('serbian_english_vocabulary.tsv'))",
      "m._zstd_compress(b'probe', v.raw_dictionary)",
    ].join(";"),
  ],
  { cwd: process.cwd() },
);
const hasPythonReference = pythonProbe.status === 0;

describe.runIf(hasPythonReference)("Python interoperability", () => {
  const pythonArchive = `
import sys
from pathlib import Path
import ipsqr_compress as ipq1
import ipsqr_zstd as ipq2

mode = int(sys.argv[1])
source = sys.stdin.buffer.read()
vocabulary = ipq2.Vocabulary(Path("serbian_english_vocabulary.tsv"))
if mode == ipq2.MODE_RAW_TEXT:
    payload = source
elif mode == ipq2.MODE_SEMANTIC:
    payload = ipq1._build_payload(source)
else:
    encoder = lambda output, value, cache: ipq2._encode_text(
        vocabulary, output, value, cache
    )
    payload = ipq1._build_payload(source, text_encoder=encoder)
frame = ipq2._zstd_compress(payload, vocabulary.raw_dictionary)
sys.stdout.buffer.write(
    ipq2.MAGIC + vocabulary.fingerprint + bytes((mode,)) + frame
)
`;

  const pythonDecompress = `
import sys
from pathlib import Path
import ipsqr_zstd as ipq2
vocabulary = ipq2.Vocabulary(Path("serbian_english_vocabulary.tsv"))
sys.stdout.buffer.write(
    ipq2.decompress(sys.stdin.buffer.read(), vocabulary)
)
`;

  test("decodes Python archives in every mode", () => {
    const source = examples[0]!.data;
    for (const mode of [
      MODE_RAW_TEXT,
      MODE_SEMANTIC,
      MODE_TOKENIZED_SEMANTIC,
    ]) {
      const result = spawnSync("python3", ["-c", pythonArchive, `${mode}`], {
        cwd: process.cwd(),
        input: source,
      });
      expect(result.status, result.stderr.toString()).toBe(0);
      expect(
        bytesEqual(
          decompress(new Uint8Array(result.stdout), vocabulary),
          source,
        ),
      ).toBe(true);
    }
  });

  test("Python decodes TypeScript archives in every mode", () => {
    const source = examples[0]!.data;
    for (const mode of [
      MODE_RAW_TEXT,
      MODE_SEMANTIC,
      MODE_TOKENIZED_SEMANTIC,
    ] as const) {
      const result = spawnSync("python3", ["-c", pythonDecompress], {
        cwd: process.cwd(),
        input: compressWithMode(source, vocabulary, mode),
      });
      expect(result.status, result.stderr.toString()).toBe(0);
      expect(bytesEqual(new Uint8Array(result.stdout), source)).toBe(true);
    }
  });
});
