import { ByteWriter } from "./bytes.js";
import { FormatError } from "./errors.js";

const ZSTD_MAGIC = 0xfd2fb528;
const DICTIONARY_ID_SIZES = [0, 1, 2, 4] as const;

function readU24LE(data: Uint8Array, offset: number): number {
  return (
    data[offset]! |
    (data[offset + 1]! << 8) |
    (data[offset + 2]! << 16)
  );
}

function readU32LE(data: Uint8Array, offset: number): number {
  return (
    data[offset]! +
    data[offset + 1]! * 0x100 +
    data[offset + 2]! * 0x10000 +
    data[offset + 3]! * 0x1000000
  );
}

function readContentSize(
  data: Uint8Array,
  offset: number,
  length: number,
): number {
  if (length === 1) return data[offset]!;
  if (length === 2) {
    return 256 + data[offset]! + data[offset + 1]! * 0x100;
  }
  if (length === 4) return readU32LE(data, offset);
  if (length === 8) {
    const value =
      BigInt(readU32LE(data, offset)) |
      (BigInt(readU32LE(data, offset + 4)) << 32n);
    if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
      throw new FormatError(
        "Zstandard content size exceeds the safe integer range",
      );
    }
    return Number(value);
  }
  throw new FormatError("invalid Zstandard content size");
}

function writeU32LE(output: ByteWriter, value: number): void {
  output.writeByte(value & 0xff);
  output.writeByte((value >>> 8) & 0xff);
  output.writeByte((value >>> 16) & 0xff);
  output.writeByte((value >>> 24) & 0xff);
}

function windowDescriptorFor(minimumSize: number): number {
  for (let descriptor = 0; descriptor <= 0xff; descriptor += 1) {
    const exponent = descriptor >>> 3;
    const mantissa = descriptor & 7;
    const base = 2 ** (10 + exponent);
    const size = base + (base / 8) * mantissa;
    if (size >= minimumSize) return descriptor;
  }
  throw new FormatError("required Zstandard window is too large");
}

function requireBytes(
  data: Uint8Array,
  offset: number,
  count: number,
  message: string,
): void {
  if (offset + count > data.length) {
    throw new FormatError(message);
  }
}

export function singleZstdFrameLength(frame: Uint8Array): number {
  requireBytes(frame, 0, 5, "truncated Zstandard frame header");
  if (readU32LE(frame, 0) !== ZSTD_MAGIC) {
    throw new FormatError("invalid Zstandard frame magic");
  }

  let offset = 4;
  const descriptor = frame[offset]!;
  offset += 1;
  if ((descriptor & 0x18) !== 0) {
    throw new FormatError("invalid Zstandard frame descriptor");
  }

  const contentSizeFlag = descriptor >>> 6;
  const singleSegment = (descriptor & 0x20) !== 0;
  const hasChecksum = (descriptor & 0x04) !== 0;
  const dictionaryIdFlag = descriptor & 0x03;

  if (!singleSegment) {
    requireBytes(frame, offset, 1, "truncated Zstandard window descriptor");
    offset += 1;
  }

  offset += DICTIONARY_ID_SIZES[dictionaryIdFlag]!;
  const contentSizeLength =
    contentSizeFlag === 0
      ? singleSegment
        ? 1
        : 0
      : contentSizeFlag === 1
        ? 2
        : contentSizeFlag === 2
          ? 4
          : 8;
  requireBytes(
    frame,
    offset,
    contentSizeLength,
    "truncated Zstandard frame content size",
  );
  offset += contentSizeLength;

  while (true) {
    requireBytes(frame, offset, 3, "truncated Zstandard block header");
    const header = readU24LE(frame, offset);
    offset += 3;

    const lastBlock = (header & 1) !== 0;
    const blockType = (header >>> 1) & 3;
    const blockSize = header >>> 3;
    if (blockType === 3) {
      throw new FormatError("reserved Zstandard block type");
    }

    const storedSize = blockType === 1 ? 1 : blockSize;
    requireBytes(frame, offset, storedSize, "truncated Zstandard block");
    offset += storedSize;
    if (lastBlock) break;
  }

  if (hasChecksum) {
    requireBytes(frame, offset, 4, "truncated Zstandard checksum");
    offset += 4;
  }
  return offset;
}

/**
 * zstdify 1.4 constrains dictionary lookbacks to a single-segment frame's
 * content-size window. RFC 8878 permits raw dictionary history beyond that
 * tiny window, and official libzstd emits such frames for small IPQ2 payloads.
 *
 * Re-expressing the same frame as a non-single-segment frame with a sufficient
 * window changes only the frame header. Blocks and the content checksum remain
 * untouched. The returned bytes are used only as decoder input; archive bytes
 * are never rewritten.
 */
export function widenZstdFrameWindow(
  frame: Uint8Array,
  minimumWindowSize: number,
): Uint8Array {
  requireBytes(frame, 0, 5, "truncated Zstandard frame header");
  const descriptor = frame[4]!;
  const singleSegment = (descriptor & 0x20) !== 0;
  if (!singleSegment) return frame;

  const contentSizeFlag = descriptor >>> 6;
  const dictionaryIdLength = DICTIONARY_ID_SIZES[descriptor & 3]!;
  const contentSizeLength =
    contentSizeFlag === 0
      ? 1
      : contentSizeFlag === 1
        ? 2
        : contentSizeFlag === 2
          ? 4
          : 8;
  const dictionaryIdOffset = 5;
  const contentSizeOffset = dictionaryIdOffset + dictionaryIdLength;
  requireBytes(
    frame,
    contentSizeOffset,
    contentSizeLength,
    "truncated Zstandard frame content size",
  );
  const contentSize = readContentSize(
    frame,
    contentSizeOffset,
    contentSizeLength,
  );
  if (contentSize >= minimumWindowSize) return frame;

  let newContentSizeFlag: number;
  if (contentSize < 256) newContentSizeFlag = 0;
  else if (contentSize <= 65_791) newContentSizeFlag = 1;
  else if (contentSize <= 0xffff_ffff) newContentSizeFlag = 2;
  else newContentSizeFlag = 3;

  const output = new ByteWriter();
  output.writeBytes(frame.subarray(0, 4));
  output.writeByte(
    (descriptor & 0x1f) | (newContentSizeFlag << 6),
  );
  output.writeByte(
    windowDescriptorFor(Math.max(minimumWindowSize, contentSize)),
  );
  output.writeBytes(
    frame.subarray(
      dictionaryIdOffset,
      dictionaryIdOffset + dictionaryIdLength,
    ),
  );

  if (newContentSizeFlag === 1) {
    const encoded = contentSize - 256;
    output.writeByte(encoded & 0xff);
    output.writeByte((encoded >>> 8) & 0xff);
  } else if (newContentSizeFlag === 2) {
    writeU32LE(output, contentSize);
  } else if (newContentSizeFlag === 3) {
    let remaining = BigInt(contentSize);
    for (let index = 0; index < 8; index += 1) {
      output.writeByte(Number(remaining & 0xffn));
      remaining >>= 8n;
    }
  }

  output.writeBytes(
    frame.subarray(contentSizeOffset + contentSizeLength),
  );
  return output.toUint8Array();
}
