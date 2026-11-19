import {
  ByteWriter,
  bytesEqual,
  readUvarint,
  toSafeNumber,
  writeUvarint,
} from "./bytes.js";
import { FormatError } from "./errors.js";
import { MAX_TEXT_BYTES } from "./ipq1-semantic.js";
import { decodeUtf8, encodeUtf8 } from "./utf8.js";
import { Vocabulary, type TokenPiece } from "./vocabulary.js";

export const COMMON_TOKEN_COUNT = 256;
export const PIECE_LITERAL = 0;
export const PIECE_COMMON_TOKEN = 1;
export const PIECE_EXTENDED_TOKEN = 2;
export const TEXT_RAW = 0;
export const TEXT_TOKENIZED = 1;

function findCached(cache: Uint8Array[], encoded: Uint8Array): number {
  return cache.findIndex((candidate) => bytesEqual(candidate, encoded));
}

function moveToFront<T>(values: T[], index: number): T {
  const [value] = values.splice(index, 1);
  if (value === undefined) {
    throw new RangeError("cache index is outside its range");
  }
  values.unshift(value);
  return value;
}

function pieceType(piece: TokenPiece): number {
  if (piece instanceof Uint8Array) return PIECE_LITERAL;
  return piece < COMMON_TOKEN_COUNT
    ? PIECE_COMMON_TOKEN
    : PIECE_EXTENDED_TOKEN;
}

export function serializeTokenized(
  vocabulary: Vocabulary,
  encoded: Uint8Array,
): Uint8Array {
  const pieces = vocabulary.tokenize(encoded);
  const output = new ByteWriter();
  output.writeByte(TEXT_TOKENIZED);
  writeUvarint(output, pieces.length);

  const pieceTypes = new Uint8Array(Math.ceil(pieces.length / 4));
  pieces.forEach((piece, index) => {
    const typeIndex = index >> 2;
    pieceTypes[typeIndex] =
      pieceTypes[typeIndex]! |
      (pieceType(piece) << ((index & 3) * 2));
  });
  output.writeBytes(pieceTypes);

  for (const piece of pieces) {
    if (piece instanceof Uint8Array) {
      writeUvarint(output, piece.length);
      output.writeBytes(piece);
    } else if (piece < COMMON_TOKEN_COUNT) {
      output.writeByte(piece);
    } else {
      writeUvarint(output, piece - COMMON_TOKEN_COUNT);
    }
  }
  return output.toUint8Array();
}

export function encodeTokenizedText(
  vocabulary: Vocabulary,
  output: ByteWriter,
  value: string,
  cache: Uint8Array[],
): void {
  const encoded = encodeUtf8(value);
  const cacheIndex = findCached(cache, encoded);
  if (cacheIndex >= 0) {
    writeUvarint(output, cacheIndex + 1);
    moveToFront(cache, cacheIndex);
    return;
  }

  writeUvarint(output, 0);

  const raw = new ByteWriter();
  raw.writeByte(TEXT_RAW);
  writeUvarint(raw, encoded.length);
  raw.writeBytes(encoded);
  const rawBytes = raw.toUint8Array();
  const tokenized = serializeTokenized(vocabulary, encoded);
  output.writeBytes(
    tokenized.length < rawBytes.length ? tokenized : rawBytes,
  );
  cache.unshift(encoded);
}

export function decodeTokenizedText(
  vocabulary: Vocabulary,
  data: Uint8Array,
  start: number,
  cache: Uint8Array[],
): { value: string; offset: number } {
  const reference = readUvarint(data, start);
  let offset = reference.offset;
  let encoded: Uint8Array;

  if (reference.value !== 0n) {
    const cacheIndex = toSafeNumber(
      reference.value - 1n,
      "IPQ2 text dictionary reference",
    );
    if (cacheIndex >= cache.length) {
      throw new FormatError(
        "invalid IPQ2 text dictionary reference",
      );
    }
    encoded = moveToFront(cache, cacheIndex);
  } else {
    if (offset >= data.length) {
      throw new FormatError("truncated IPQ2 text representation");
    }
    const representation = data[offset]!;
    offset += 1;

    if (representation === TEXT_RAW) {
      const result = readUvarint(data, offset);
      const length = toSafeNumber(result.value, "IPQ2 text length");
      offset = result.offset;
      if (length > MAX_TEXT_BYTES || offset + length > data.length) {
        throw new FormatError(
          "invalid or truncated IPQ2 text field",
        );
      }
      encoded = data.slice(offset, offset + length);
      offset += length;
    } else if (representation === TEXT_TOKENIZED) {
      const countResult = readUvarint(data, offset);
      const pieceCount = toSafeNumber(
        countResult.value,
        "IPQ2 token piece count",
      );
      offset = countResult.offset;
      if (pieceCount > MAX_TEXT_BYTES) {
        throw new FormatError("IPQ2 text has too many token pieces");
      }

      const pieceTypesLength = Math.ceil(pieceCount / 4);
      if (offset + pieceTypesLength > data.length) {
        throw new FormatError("truncated IPQ2 token piece types");
      }
      const pieceTypes = data.subarray(
        offset,
        offset + pieceTypesLength,
      );
      offset += pieceTypesLength;

      const decoded = new ByteWriter();
      for (let index = 0; index < pieceCount; index += 1) {
        const type =
          (pieceTypes[index >> 2]! >> ((index & 3) * 2)) & 3;
        if (type === PIECE_LITERAL) {
          const result = readUvarint(data, offset);
          const length = toSafeNumber(
            result.value,
            "IPQ2 literal length",
          );
          offset = result.offset;
          if (length > MAX_TEXT_BYTES || offset + length > data.length) {
            throw new FormatError("invalid IPQ2 literal text piece");
          }
          decoded.writeBytes(data.subarray(offset, offset + length));
          offset += length;
        } else if (type === PIECE_COMMON_TOKEN) {
          if (offset >= data.length) {
            throw new FormatError("truncated IPQ2 common token");
          }
          const tokenId = data[offset]!;
          offset += 1;
          if (
            tokenId >=
            Math.min(COMMON_TOKEN_COUNT, vocabulary.terms.length)
          ) {
            throw new FormatError("invalid IPQ2 common token");
          }
          decoded.writeBytes(vocabulary.terms[tokenId]!);
        } else if (type === PIECE_EXTENDED_TOKEN) {
          const result = readUvarint(data, offset);
          const extendedId = toSafeNumber(
            result.value,
            "IPQ2 vocabulary token",
          );
          offset = result.offset;
          const tokenId = COMMON_TOKEN_COUNT + extendedId;
          if (tokenId >= vocabulary.terms.length) {
            throw new FormatError("invalid IPQ2 vocabulary token");
          }
          decoded.writeBytes(vocabulary.terms[tokenId]!);
        } else {
          throw new FormatError("reserved IPQ2 token piece type");
        }

        if (decoded.length > MAX_TEXT_BYTES) {
          throw new FormatError(
            "decoded IPQ2 text field is too large",
          );
        }
      }
      encoded = decoded.toUint8Array();
    } else {
      throw new FormatError("unknown IPQ2 text representation");
    }
    cache.unshift(encoded);
  }

  return {
    value: decodeUtf8(encoded, "IPQ2 text field is not valid UTF-8"),
    offset,
  };
}
