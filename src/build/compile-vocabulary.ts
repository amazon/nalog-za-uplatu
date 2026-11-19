import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { compress } from "zstdify/compress";

import {
  ByteWriter,
  bytesToHex,
  compareBytes,
  writeU32BE,
  writeU64BE,
} from "../ipq2/bytes.js";
import { VocabularyError } from "../ipq2/errors.js";
import { encodeUtf8 } from "../ipq2/utf8.js";
import {
  serializeCompiledVocabulary,
  type CompiledVocabularyData,
} from "../ipq2/vocabulary-format.js";
import { PRIORITY_WORDS } from "./priority-words.js";

const COMMON_TOKEN_COUNT = 256;
const FINGERPRINT_MARKER = encodeUtf8(
  "IPQ2-derived-vocabulary-v2\0",
);
const WORD_RE = /\p{L}+/gu;
const SERBIAN_ASCII = new Map<string, string>([
  ["č", "c"],
  ["ć", "c"],
  ["š", "s"],
  ["ž", "z"],
  ["đ", "dj"],
  ["Č", "C"],
  ["Ć", "C"],
  ["Š", "S"],
  ["Ž", "Z"],
  ["Đ", "DJ"],
]);

interface VocabularyRow {
  category: string;
  serbian: string;
  english: string;
}

interface RankedTerm {
  text: string;
  bytes: Uint8Array;
  score: number;
}

function serbianAscii(value: string): string {
  let output = "";
  for (const character of value) {
    output += SERBIAN_ASCII.get(character) ?? character;
  }
  return output;
}

function firstCapital(value: string): string {
  const characters = [...value];
  if (characters.length === 0) return value;
  return characters[0]!.toUpperCase() + characters.slice(1).join("");
}

function textVariants(value: string): string[] {
  const variants: string[] = [];
  const seen = new Set<string>();
  const add = (candidate: string): void => {
    if (!seen.has(candidate)) {
      seen.add(candidate);
      variants.push(candidate);
    }
  };

  add(value);
  add(value.toLowerCase());
  add(firstCapital(value));
  add(value.toUpperCase());
  for (const candidate of [...variants]) {
    add(serbianAscii(candidate));
  }
  return variants;
}

function parseRows(tsv: string): VocabularyRow[] {
  const lines = tsv.replace(/\r\n/gu, "\n").split("\n");
  if (lines.at(-1) === "") lines.pop();
  if (lines.length === 0) {
    throw new VocabularyError("vocabulary contains no entries");
  }

  const headers = lines[0]!.split("\t");
  const categoryIndex = headers.indexOf("category");
  const serbianIndex = headers.indexOf("sr_latn");
  const englishIndex = headers.indexOf("en");
  if (
    categoryIndex < 0 ||
    serbianIndex < 0 ||
    englishIndex < 0
  ) {
    throw new VocabularyError(
      "vocabulary must contain category, sr_latn, and en columns",
    );
  }

  const rows = lines.slice(1).map((line, index) => {
    const columns = line.split("\t");
    const category = (columns[categoryIndex] ?? "").trim();
    const serbian = (columns[serbianIndex] ?? "").trim();
    const english = (columns[englishIndex] ?? "").trim();
    if (!category || !serbian || !english) {
      throw new VocabularyError(
        `vocabulary line ${index + 2} has an empty required value`,
      );
    }
    return { category, serbian, english };
  });
  if (rows.length === 0) {
    throw new VocabularyError("vocabulary contains no entries");
  }
  return rows;
}

function buildRawDictionary(rows: readonly VocabularyRow[]): Uint8Array {
  const values: string[] = [];
  const seen = new Set<string>();
  const add = (value: string): void => {
    if (!seen.has(value)) {
      seen.add(value);
      values.push(value);
    }
  };

  for (const row of rows) {
    for (const value of [row.serbian, row.english]) {
      for (const variant of textVariants(value)) add(variant);
    }
  }
  for (const word of PRIORITY_WORDS) {
    for (const variant of textVariants(word)) add(variant);
  }
  return encodeUtf8(`${values.join("\n")}\n`);
}

function categoryWeight(category: string): number {
  if (category.startsWith("payment.")) return 8;
  if (category.startsWith("organization.")) return 6;
  if (category.startsWith("geo.")) return 4;
  return 2;
}

function buildTerms(rows: readonly VocabularyRow[]): Uint8Array[] {
  const scores = new Map<string, number>();
  const words = new Set<string>();
  const addScore = (term: string, value: number): void => {
    scores.set(term, (scores.get(term) ?? 0) + value);
  };

  for (const row of rows) {
    const weight = categoryWeight(row.category);
    for (const [columnWeight, value] of [
      [2, row.serbian],
      [1, row.english],
    ] as const) {
      const baseWeight = weight * columnWeight;
      for (const variant of textVariants(value)) {
        const encoded = encodeUtf8(variant);
        addScore(
          variant,
          baseWeight * Math.max(2, Math.floor(encoded.length / 4)),
        );
      }

      for (const spelling of new Set([value, serbianAscii(value)])) {
        for (const match of spelling.matchAll(WORD_RE)) {
          const word = match[0].toLowerCase();
          words.add(word);
          addScore(word, baseWeight);
        }
      }
    }
  }

  const priorityBoost = 1_000_000;
  PRIORITY_WORDS.forEach((word, rank) => {
    words.add(word);
    addScore(word, priorityBoost - rank);
  });

  const ranked = (terms: Iterable<string>): RankedTerm[] =>
    [...terms]
      .map((text) => ({
        text,
        bytes: encodeUtf8(text),
        score: scores.get(text) ?? 0,
      }))
      .sort(
        (left, right) =>
          right.score - left.score ||
          right.bytes.length - left.bytes.length ||
          compareBytes(left.bytes, right.bytes),
      );

  const common = ranked(words);
  if (common.length < COMMON_TOKEN_COUNT) {
    throw new VocabularyError(
      `vocabulary has fewer than ${COMMON_TOKEN_COUNT} distinct words`,
    );
  }
  const commonTerms = common.slice(0, COMMON_TOKEN_COUNT);
  const commonSet = new Set(commonTerms.map((term) => term.text));
  const extended = ranked(
    [...scores.keys()].filter((term) => !commonSet.has(term)),
  );
  return [...commonTerms, ...extended].map((term) => term.bytes);
}

function fingerprint(
  rawDictionary: Uint8Array,
  terms: readonly Uint8Array[],
): Uint8Array {
  const digest = createHash("sha256");
  digest.update(FINGERPRINT_MARKER);

  const length = new ByteWriter();
  writeU64BE(length, BigInt(rawDictionary.length));
  digest.update(length.toUint8Array());
  digest.update(rawDictionary);

  for (const term of terms) {
    const termLength = new ByteWriter();
    writeU32BE(termLength, term.length);
    digest.update(termLength.toUint8Array());
    digest.update(term);
  }
  return new Uint8Array(digest.digest().subarray(0, 8));
}

function createGeneratedSource(
  base64: string,
  vocabulary: CompiledVocabularyData,
  entryCount: number,
  compiledBytes: number,
): string {
  return `// Generated by src/build/compile-vocabulary.ts. Do not edit.
export const COMPILED_VOCABULARY_BASE64 = ${JSON.stringify(base64)};
export const COMPILED_VOCABULARY_METADATA = ${JSON.stringify(
    {
      fingerprint: bytesToHex(vocabulary.fingerprint),
      entryCount,
      dictionaryBytes: vocabulary.rawDictionary.length,
      termCount: vocabulary.terms.length,
      compiledBytes,
    },
    null,
    2,
  )} as const;
`;
}

async function main(): Promise<void> {
  const projectRoot = process.cwd();
  const inputPath = resolve(
    projectRoot,
    "serbian_english_vocabulary.tsv",
  );
  const outputPath = resolve(
    projectRoot,
    "src/generated/ipq2-vocabulary.ts",
  );

  const rows = parseRows(await readFile(inputPath, "utf8"));
  const rawDictionary = buildRawDictionary(rows);
  const terms = buildTerms(rows);
  const vocabulary: CompiledVocabularyData = {
    fingerprint: fingerprint(rawDictionary, terms),
    rawDictionary,
    terms,
  };
  const compiled = serializeCompiledVocabulary(vocabulary);
  const compressed = compress(compiled, {
    level: 9,
    checksum: true,
    noDictId: true,
  });
  const base64 = Buffer.from(compressed).toString("base64");

  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(
    outputPath,
    createGeneratedSource(
      base64,
      vocabulary,
      rows.length,
      compiled.length,
    ),
    "utf8",
  );

  process.stdout.write(
    [
      `Generated ${outputPath}`,
      `fingerprint=${bytesToHex(vocabulary.fingerprint)}`,
      `dictionary=${rawDictionary.length}`,
      `terms=${terms.length}`,
      `compiled=${compiled.length}`,
      `compressed=${compressed.length}`,
    ].join(" "),
  );
  process.stdout.write("\n");
}

await main();
