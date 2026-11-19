import {
  ByteWriter,
  bytesEqual,
  readU32BE,
  readUvarint,
  toSafeNumber,
  writeU32BE,
  writeUvarint,
} from "./bytes.js";
import { VocabularyError } from "./errors.js";
import { encodeUtf8 } from "./utf8.js";

const COMPILED_MAGIC = encodeUtf8("IPQV1");
const FINGERPRINT_LENGTH = 8;
const MAX_COMPILED_VOCABULARY_BYTES = 16 * 1024 * 1024;
const MAX_TERMS = 1_000_000;

export interface CompiledVocabularyData {
  fingerprint: Uint8Array;
  rawDictionary: Uint8Array;
  terms: readonly Uint8Array[];
}

export function serializeCompiledVocabulary(
  vocabulary: CompiledVocabularyData,
): Uint8Array {
  if (vocabulary.fingerprint.length !== FINGERPRINT_LENGTH) {
    throw new VocabularyError(
      `vocabulary fingerprint must contain ${FINGERPRINT_LENGTH} bytes`,
    );
  }
  if (vocabulary.rawDictionary.length > 0xffff_ffff) {
    throw new VocabularyError("raw dictionary is too large");
  }
  if (vocabulary.terms.length > MAX_TERMS) {
    throw new VocabularyError("vocabulary contains too many terms");
  }

  const output = new ByteWriter();
  output.writeBytes(COMPILED_MAGIC);
  output.writeBytes(vocabulary.fingerprint);
  writeU32BE(output, vocabulary.rawDictionary.length);
  output.writeBytes(vocabulary.rawDictionary);
  writeU32BE(output, vocabulary.terms.length);
  for (const term of vocabulary.terms) {
    writeUvarint(output, term.length);
    output.writeBytes(term);
  }
  return output.toUint8Array();
}

export function parseCompiledVocabulary(
  data: Uint8Array,
): CompiledVocabularyData {
  if (data.length > MAX_COMPILED_VOCABULARY_BYTES) {
    throw new VocabularyError("compiled vocabulary is too large");
  }

  let offset = 0;
  if (
    data.length < COMPILED_MAGIC.length + FINGERPRINT_LENGTH + 8 ||
    !bytesEqual(data.subarray(0, COMPILED_MAGIC.length), COMPILED_MAGIC)
  ) {
    throw new VocabularyError("invalid compiled vocabulary header");
  }
  offset += COMPILED_MAGIC.length;

  const fingerprint = data.slice(offset, offset + FINGERPRINT_LENGTH);
  offset += FINGERPRINT_LENGTH;

  const dictionaryLength = readU32BE(data, offset);
  offset += 4;
  if (offset + dictionaryLength > data.length) {
    throw new VocabularyError("truncated compiled raw dictionary");
  }
  const rawDictionary = data.slice(offset, offset + dictionaryLength);
  offset += dictionaryLength;

  const termCount = readU32BE(data, offset);
  offset += 4;
  if (termCount > MAX_TERMS) {
    throw new VocabularyError("compiled vocabulary contains too many terms");
  }

  const terms: Uint8Array[] = [];
  for (let index = 0; index < termCount; index += 1) {
    let lengthResult;
    try {
      lengthResult = readUvarint(data, offset);
    } catch (cause) {
      throw new VocabularyError(
        "invalid compiled vocabulary term length",
        { cause },
      );
    }
    const length = toSafeNumber(
      lengthResult.value,
      "compiled vocabulary term length",
    );
    offset = lengthResult.offset;
    if (offset + length > data.length) {
      throw new VocabularyError("truncated compiled vocabulary term");
    }
    terms.push(data.slice(offset, offset + length));
    offset += length;
  }

  if (offset !== data.length) {
    throw new VocabularyError("compiled vocabulary has trailing data");
  }

  return { fingerprint, rawDictionary, terms };
}
