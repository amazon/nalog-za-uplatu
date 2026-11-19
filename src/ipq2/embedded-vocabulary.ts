import { COMPILED_VOCABULARY_BASE64 } from "../generated/ipq2-vocabulary.js";
import { parseCompiledVocabulary } from "./vocabulary-format.js";
import { VocabularyError } from "./errors.js";
import { Vocabulary } from "./vocabulary.js";
import { decompressZstdFrame } from "./zstd.js";

const MAX_COMPILED_VOCABULARY_BYTES = 16 * 1024 * 1024;
let cachedVocabulary: Vocabulary | undefined;

function decodeBase64(value: string): Uint8Array {
  if (value.length === 0) {
    throw new VocabularyError(
      "embedded vocabulary is missing; run npm run generate:vocabulary",
    );
  }

  let binary: string;
  try {
    binary = atob(value);
  } catch (cause) {
    throw new VocabularyError(
      "embedded vocabulary is not valid Base64",
      { cause },
    );
  }

  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index);
  }
  return output;
}

export function getEmbeddedVocabulary(): Vocabulary {
  if (cachedVocabulary !== undefined) return cachedVocabulary;

  const compressed = decodeBase64(COMPILED_VOCABULARY_BASE64);
  const compiled = decompressZstdFrame(
    compressed,
    undefined,
    MAX_COMPILED_VOCABULARY_BYTES,
  );
  cachedVocabulary = Vocabulary.fromCompiled(
    parseCompiledVocabulary(compiled),
  );
  return cachedVocabulary;
}
