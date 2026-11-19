import { compress as compressZstd } from "zstdify/compress";
import { decompress as decompressZstd } from "zstdify/decompress";

import { FormatError } from "./errors.js";
import {
  singleZstdFrameLength,
  widenZstdFrameWindow,
} from "./zstd-frame.js";

export const MAX_SEMANTIC_PAYLOAD = 256 * 1024 * 1024;

export function compressZstdFrame(
  data: Uint8Array,
  dictionary?: Uint8Array,
): Uint8Array {
  try {
    return compressZstd(data, {
      // zstdify currently clamps levels above 9. Compression level is not
      // part of the IPQ2 wire format; checksum and raw-dictionary use are.
      level: 19,
      checksum: true,
      ...(dictionary === undefined ? {} : { dictionary }),
      noDictId: true,
    });
  } catch (cause) {
    const detail = cause instanceof Error ? cause.message : String(cause);
    throw new FormatError(`Zstandard compression failed: ${detail}`, {
      cause,
    });
  }
}

export function decompressZstdFrame(
  frame: Uint8Array,
  dictionary?: Uint8Array,
  maxSize = MAX_SEMANTIC_PAYLOAD,
): Uint8Array {
  try {
    if (singleZstdFrameLength(frame) !== frame.length) {
      throw new FormatError(
        "truncated frame or trailing IPQ2 archive data",
      );
    }

    const decoderFrame =
      dictionary === undefined
        ? frame
        : widenZstdFrameWindow(frame, dictionary.length);
    const payload = decompressZstd(decoderFrame, {
      ...(dictionary === undefined ? {} : { dictionary }),
      maxSize: maxSize + 1,
      validateChecksum: true,
    });
    if (payload.length > maxSize) {
      throw new FormatError("IPQ2 semantic payload is too large");
    }
    return payload;
  } catch (cause) {
    if (cause instanceof FormatError) throw cause;
    const detail = cause instanceof Error ? cause.message : String(cause);
    throw new FormatError(`invalid Zstandard frame: ${detail}`, {
      cause,
    });
  }
}
