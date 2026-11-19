import { decodeUtf8, encodeUtf8 } from "./utf8.js";
import {
  compress as compressWithVocabulary,
  decompress as decompressWithVocabulary,
} from "./ipq2.js";
import { getEmbeddedVocabulary } from "./embedded-vocabulary.js";

export { FormatError, VocabularyError } from "./errors.js";
export { getEmbeddedVocabulary } from "./embedded-vocabulary.js";
export {
  MODE_RAW_TEXT,
  MODE_SEMANTIC,
  MODE_TOKENIZED_SEMANTIC,
  compressWithMode,
  type RepresentationMode,
} from "./ipq2.js";
export { Vocabulary, type TokenPiece } from "./vocabulary.js";

export function compress(data: Uint8Array): Uint8Array {
  return compressWithVocabulary(data, getEmbeddedVocabulary());
}

export function decompress(archive: Uint8Array): Uint8Array {
  return decompressWithVocabulary(archive, getEmbeddedVocabulary());
}

export function compressText(text: string): Uint8Array {
  return compress(encodeUtf8(text));
}

export function decompressText(archive: Uint8Array): string {
  return decodeUtf8(
    decompress(archive),
    "decompressed IPQ2 data is not valid UTF-8",
  );
}
