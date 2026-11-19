import { compressText, decompressText } from "./ipq2/index.js";
import { decodeUtf8, encodeUtf8 } from "./ipq2/utf8.js";

export const LEGACY_SHARE_VERSION = 1;
export const IPQ2_SHARE_VERSION = 2;

export type ShareLinkFormat = "legacy" | "ipq2";

export interface ParsedSharePath {
  version: number;
  encodedData: string;
}

const FIELD_ORDER = [
  "K",
  "V",
  "C",
  "R",
  "N",
  "I",
  "P",
  "SF",
  "S",
  "RO",
] as const;

function parseIpsFields(line: string): Map<string, string> {
  const fields = new Map<string, string>();
  for (const field of line.split("|")) {
    const separator = field.indexOf(":");
    if (separator > 0) {
      fields.set(
        field.slice(0, separator),
        field.slice(separator + 1),
      );
    }
  }
  return fields;
}

export function sparsifyIpsBatch(canonicalBatch: string): string {
  const lines = canonicalBatch
    .split("\n")
    .filter((line) => line.length > 0);
  const parsed = lines.map(parseIpsFields);

  return parsed
    .map((fields, index) => {
      const previous = index > 0 ? parsed[index - 1]! : undefined;
      const sparseFields: string[] = [];
      for (const key of FIELD_ORDER) {
        const value = fields.get(key) ?? "";
        const previousValue = previous?.get(key) ?? "";
        const output =
          previous !== undefined && value === previousValue ? "" : value;
        if (fields.has(key) || output.length > 0) {
          sparseFields.push(`${key}:${output}`);
        }
      }
      return sparseFields.join("|");
    })
    .join("\n");
}

export function encodeBase64Url(data: Uint8Array): string {
  const chunkSize = 0x8000;
  let binary = "";
  for (let offset = 0; offset < data.length; offset += chunkSize) {
    const chunk = data.subarray(offset, offset + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/u, "");
}

export function decodeBase64Url(encoded: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]+$/u.test(encoded)) {
    throw new Error("share payload is not valid Base64URL");
  }

  let base64 = encoded.replaceAll("-", "+").replaceAll("_", "/");
  const remainder = base64.length % 4;
  if (remainder !== 0) base64 += "=".repeat(4 - remainder);

  let binary: string;
  try {
    binary = atob(base64);
  } catch (cause) {
    throw new Error("share payload is not valid Base64URL", { cause });
  }

  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index);
  }
  return output;
}

function sharePrefix(origin: string, version: number): string {
  return `${origin.replace(/\/+$/u, "")}/s/v${version}/`;
}

export function buildLegacyShareUrl(
  origin: string,
  canonicalBatch: string,
): string {
  const sparse = sparsifyIpsBatch(canonicalBatch);
  return (
    sharePrefix(origin, LEGACY_SHARE_VERSION) +
    encodeBase64Url(encodeUtf8(sparse))
  );
}

export function buildCompressedShareUrl(
  origin: string,
  canonicalBatch: string,
): string {
  return (
    sharePrefix(origin, IPQ2_SHARE_VERSION) +
    encodeBase64Url(compressText(canonicalBatch))
  );
}

export function buildShareUrl(
  origin: string,
  format: ShareLinkFormat,
  canonicalBatch: string,
): string {
  return format === "ipq2"
    ? buildCompressedShareUrl(origin, canonicalBatch)
    : buildLegacyShareUrl(origin, canonicalBatch);
}

export function parseSharePath(path: string): ParsedSharePath | null {
  const match = /(?:^|\/)s\/v(\d+)\/([A-Za-z0-9_-]+)$/u.exec(path);
  if (match === null) return null;
  return {
    version: Number(match[1]),
    encodedData: match[2]!,
  };
}

export function decodeShareData(
  version: number,
  encodedData: string,
): string {
  const data = decodeBase64Url(encodedData);
  if (version === LEGACY_SHARE_VERSION) {
    return decodeUtf8(data, "legacy share data is not valid UTF-8");
  }
  if (version === IPQ2_SHARE_VERSION) {
    return decompressText(data);
  }
  throw new Error(`unsupported share URL version: v${version}`);
}
