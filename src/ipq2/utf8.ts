import { FormatError } from "./errors.js";

const encoder = new TextEncoder();

export function encodeUtf8(value: string): Uint8Array {
  return encoder.encode(value);
}

export function decodeUtf8(
  value: Uint8Array,
  errorMessage = "input is not valid UTF-8",
): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(value);
  } catch (cause) {
    throw new FormatError(errorMessage, { cause });
  }
}
