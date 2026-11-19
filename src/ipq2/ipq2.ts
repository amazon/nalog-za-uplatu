import {
  concatBytes,
  bytesEqual,
  startsWithBytes,
} from "./bytes.js";
import { FormatError } from "./errors.js";
import { buildPayload, restorePayload } from "./ipq1-semantic.js";
import {
  decodeTokenizedText,
  encodeTokenizedText,
} from "./tokenized-text.js";
import type { Vocabulary } from "./vocabulary.js";
import {
  compressZstdFrame,
  decompressZstdFrame,
} from "./zstd.js";

const MAGIC = new TextEncoder().encode("IPQ2");
const ENVELOPE_LENGTH = 13;
const MIN_ARCHIVE_LENGTH = 19;

export const MODE_RAW_TEXT = 0;
export const MODE_SEMANTIC = 1;
export const MODE_TOKENIZED_SEMANTIC = 2;
export type RepresentationMode =
  | typeof MODE_RAW_TEXT
  | typeof MODE_SEMANTIC
  | typeof MODE_TOKENIZED_SEMANTIC;

function representationPayload(
  data: Uint8Array,
  vocabulary: Vocabulary,
  mode: RepresentationMode,
): Uint8Array {
  if (mode === MODE_RAW_TEXT) return data;
  if (mode === MODE_SEMANTIC) return buildPayload(data);
  return buildPayload(data, (output, value, cache) => {
    encodeTokenizedText(vocabulary, output, value, cache);
  });
}

export function compressWithMode(
  data: Uint8Array,
  vocabulary: Vocabulary,
  mode: RepresentationMode,
): Uint8Array {
  const payload = representationPayload(data, vocabulary, mode);
  const frame = compressZstdFrame(
    payload,
    vocabulary.rawDictionary,
  );
  return concatBytes([
    MAGIC,
    vocabulary.fingerprint,
    new Uint8Array([mode]),
    frame,
  ]);
}

export function compress(
  data: Uint8Array,
  vocabulary: Vocabulary,
): Uint8Array {
  // Constructing both semantic candidates validates the source even when the
  // raw representation eventually produces the smallest Zstandard frame.
  const modes: RepresentationMode[] = [
    MODE_RAW_TEXT,
    MODE_SEMANTIC,
    MODE_TOKENIZED_SEMANTIC,
  ];
  const candidates = modes.map((mode) => {
    const payload = representationPayload(data, vocabulary, mode);
    return {
      mode,
      frame: compressZstdFrame(payload, vocabulary.rawDictionary),
    };
  });

  candidates.sort(
    (left, right) =>
      left.frame.length - right.frame.length || left.mode - right.mode,
  );
  const winner = candidates[0]!;
  return concatBytes([
    MAGIC,
    vocabulary.fingerprint,
    new Uint8Array([winner.mode]),
    winner.frame,
  ]);
}

export function decompress(
  archive: Uint8Array,
  vocabulary: Vocabulary,
): Uint8Array {
  if (
    archive.length < MIN_ARCHIVE_LENGTH ||
    !startsWithBytes(archive, MAGIC)
  ) {
    throw new FormatError("not an IPQ2 archive");
  }
  if (
    !bytesEqual(
      archive.subarray(MAGIC.length, MAGIC.length + 8),
      vocabulary.fingerprint,
    )
  ) {
    throw new FormatError("IPQ2 vocabulary fingerprint mismatch");
  }

  const mode = archive[12]!;
  const payload = decompressZstdFrame(
    archive.subarray(ENVELOPE_LENGTH),
    vocabulary.rawDictionary,
  );

  if (mode === MODE_RAW_TEXT) return payload;
  if (mode === MODE_SEMANTIC) return restorePayload(payload);
  if (mode !== MODE_TOKENIZED_SEMANTIC) {
    throw new FormatError(
      `unknown IPQ2 representation mode ${mode}`,
    );
  }
  return restorePayload(payload, (data, offset, cache) =>
    decodeTokenizedText(vocabulary, data, offset, cache),
  );
}
