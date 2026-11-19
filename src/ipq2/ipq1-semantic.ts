import {
  ByteWriter,
  bytesEqual,
  readU64BE,
  readUvarint,
  toSafeNumber,
  writeU64BE,
  writeUvarint,
} from "./bytes.js";
import { FormatError } from "./errors.js";
import { decodeUtf8, encodeUtf8 } from "./utf8.js";

export const FIXED_PREFIX = "K:PR|V:01|C:1|";
export const FIELD_NAMES = ["R", "N", "I", "P", "SF", "S", "RO"] as const;
export const MAX_RECORDS = 1_000_000;
export const MAX_TEXT_BYTES = 1_000_000;

const TEXT_FIELDS = new Set<FieldName>(["N", "P", "S"]);
const TEXT_CACHE_FIELDS = ["N", "P", "S", "RO"] as const;
const FLAG_FINAL_NEWLINE = 1;
const FLAG_CRLF = 2;
const ACCOUNT_RE = /^[0-9]{18}$/u;
const AMOUNT_RE = /^RSD(0|[1-9][0-9]*),([0-9]{2})$/u;
const PAYMENT_CODE_RE = /^[0-9]{3}$/u;
const REFERENCE_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const REFERENCE_INDEX = new Map(
  [...REFERENCE_ALPHABET].map((character, index) => [character, index]),
);

export type FieldName = (typeof FIELD_NAMES)[number];
export type RecordValues = readonly (string | null)[];
export type TextCache = Map<FieldName, Uint8Array[]>;
export type TextEncoder = (
  output: ByteWriter,
  value: string,
  cache: Uint8Array[],
) => void;
export type TextDecoder = (
  data: Uint8Array,
  offset: number,
  cache: Uint8Array[],
) => { value: string; offset: number };

function zigzagEncode(value: bigint): bigint {
  return value >= 0n ? value * 2n : -value * 2n - 1n;
}

function zigzagDecode(value: bigint): bigint {
  return value % 2n === 0n ? value / 2n : -(value / 2n + 1n);
}

function containsByte(data: Uint8Array, byte: number): boolean {
  return data.indexOf(byte) >= 0;
}

function endsWithBytes(data: Uint8Array, suffix: Uint8Array): boolean {
  return (
    data.length >= suffix.length &&
    bytesEqual(data.subarray(data.length - suffix.length), suffix)
  );
}

function splitInput(data: Uint8Array): {
  lines: string[];
  flags: number;
} {
  if (data.length === 0) return { lines: [], flags: 0 };

  let separator: Uint8Array;
  let separatorText: string;
  let flags: number;

  if (containsByte(data, 0x0d)) {
    for (let index = 0; index < data.length; index += 1) {
      if (data[index] === 0x0d) {
        if (data[index + 1] !== 0x0a) {
          throw new FormatError("mixed or unsupported line endings");
        }
        index += 1;
      } else if (data[index] === 0x0a) {
        throw new FormatError("mixed or unsupported line endings");
      }
    }
    separator = new Uint8Array([0x0d, 0x0a]);
    separatorText = "\r\n";
    flags = FLAG_CRLF;
  } else {
    separator = new Uint8Array([0x0a]);
    separatorText = "\n";
    flags = 0;
  }

  let content = data;
  if (endsWithBytes(content, separator)) {
    flags |= FLAG_FINAL_NEWLINE;
    content = content.subarray(0, content.length - separator.length);
  }

  if (content.length === 0) return { lines: [], flags };
  const text = decodeUtf8(content);
  const lines = text.split(separatorText);
  if (lines.some((line) => line.length === 0)) {
    throw new FormatError("blank lines are not supported");
  }
  return { lines, flags };
}

function parseRecord(line: string, lineNumber: number): RecordValues {
  if (!line.startsWith(FIXED_PREFIX)) {
    throw new FormatError(
      `line ${lineNumber}: expected fixed prefix ${JSON.stringify(FIXED_PREFIX)}`,
    );
  }

  const parsed = new Map<FieldName, string>();
  const order: FieldName[] = [];
  for (const part of line.slice(FIXED_PREFIX.length).split("|")) {
    const separator = part.indexOf(":");
    if (separator < 0) {
      throw new FormatError(
        `line ${lineNumber}: malformed field ${JSON.stringify(part)}`,
      );
    }

    const name = part.slice(0, separator);
    const value = part.slice(separator + 1);
    if (!FIELD_NAMES.includes(name as FieldName)) {
      throw new FormatError(
        `line ${lineNumber}: unsupported field ${JSON.stringify(name)}`,
      );
    }

    const field = name as FieldName;
    if (parsed.has(field)) {
      throw new FormatError(
        `line ${lineNumber}: duplicate field ${JSON.stringify(name)}`,
      );
    }
    parsed.set(field, value);
    order.push(field);
  }

  const expectedOrder = FIELD_NAMES.filter((name) => parsed.has(name));
  if (
    order.length !== expectedOrder.length ||
    order.some((name, index) => name !== expectedOrder[index])
  ) {
    throw new FormatError(
      `line ${lineNumber}: fields are not in IPS canonical order`,
    );
  }
  if (parsed.size === 0) {
    throw new FormatError(
      `line ${lineNumber}: record has no variable fields`,
    );
  }

  const account = parsed.get("R");
  if (account !== undefined && !ACCOUNT_RE.test(account)) {
    throw new FormatError(
      `line ${lineNumber}: R must contain exactly 18 digits`,
    );
  }

  const amount = parsed.get("I");
  if (amount !== undefined && !AMOUNT_RE.test(amount)) {
    throw new FormatError(
      `line ${lineNumber}: unsupported I amount ${JSON.stringify(amount)}`,
    );
  }

  const paymentCode = parsed.get("SF");
  if (paymentCode !== undefined && !PAYMENT_CODE_RE.test(paymentCode)) {
    throw new FormatError(
      `line ${lineNumber}: SF must contain exactly 3 digits`,
    );
  }

  return FIELD_NAMES.map((name) => parsed.get(name) ?? null);
}

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

export function encodeCachedText(
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
  writeUvarint(output, encoded.length);
  output.writeBytes(encoded);
  cache.unshift(encoded);
}

export function decodeCachedText(
  data: Uint8Array,
  start: number,
  cache: Uint8Array[],
): { value: string; offset: number } {
  const reference = readUvarint(data, start);
  let encoded: Uint8Array;
  let offset = reference.offset;

  if (reference.value !== 0n) {
    const cacheIndex = toSafeNumber(
      reference.value - 1n,
      "text dictionary reference",
    );
    if (cacheIndex >= cache.length) {
      throw new FormatError("invalid text dictionary reference");
    }
    encoded = moveToFront(cache, cacheIndex);
  } else {
    const result = readUvarint(data, offset);
    const length = toSafeNumber(result.value, "text field length");
    offset = result.offset;
    if (length > MAX_TEXT_BYTES || offset + length > data.length) {
      throw new FormatError("invalid or truncated text field");
    }
    encoded = data.slice(offset, offset + length);
    offset += length;
    cache.unshift(encoded);
  }

  return {
    value: decodeUtf8(encoded, "compressed text field is not valid UTF-8"),
    offset,
  };
}

function packReference(value: string): Uint8Array | null {
  const output = new ByteWriter();
  let accumulator = 0;
  let bits = 0;

  for (const character of value) {
    const symbol = REFERENCE_INDEX.get(character);
    if (symbol === undefined) return null;

    accumulator = accumulator * 64 + symbol;
    bits += 6;
    while (bits >= 8) {
      bits -= 8;
      output.writeByte(Math.floor(accumulator / 2 ** bits) & 0xff);
      accumulator &= bits === 0 ? 0 : 2 ** bits - 1;
    }
  }

  if (bits > 0) {
    output.writeByte((accumulator * 2 ** (8 - bits)) & 0xff);
  }
  return output.toUint8Array();
}

function unpackReference(packed: Uint8Array, length: number): string {
  const symbols: string[] = [];
  let accumulator = 0;
  let bits = 0;

  for (const byte of packed) {
    accumulator = accumulator * 256 + byte;
    bits += 8;
    while (bits >= 6 && symbols.length < length) {
      bits -= 6;
      const index = Math.floor(accumulator / 2 ** bits) & 0x3f;
      if (index >= REFERENCE_ALPHABET.length) {
        throw new FormatError("invalid packed RO character");
      }
      symbols.push(REFERENCE_ALPHABET[index]!);
      accumulator &= bits === 0 ? 0 : 2 ** bits - 1;
    }
  }

  if (symbols.length !== length) {
    throw new FormatError("truncated packed RO field");
  }
  return symbols.join("");
}

function createTextCache(): TextCache {
  return new Map(TEXT_CACHE_FIELDS.map((field) => [field, []]));
}

function cacheFor(cache: TextCache, field: FieldName): Uint8Array[] {
  const values = cache.get(field);
  if (values === undefined) {
    throw new Error(`missing text cache for ${field}`);
  }
  return values;
}

function encodeValue(
  output: ByteWriter,
  field: FieldName,
  value: string,
  previous: string | null,
  textCache: TextCache,
  textEncoder: TextEncoder,
): void {
  if (field === "R") {
    const number = BigInt(value);
    if (previous === null) {
      writeU64BE(output, number);
    } else {
      writeUvarint(output, zigzagEncode(number - BigInt(previous)));
    }
    return;
  }

  if (field === "I") {
    const match = AMOUNT_RE.exec(value);
    if (match === null) throw new Error("validated amount did not match");
    const cents = BigInt(match[1]!) * 100n + BigInt(match[2]!);
    writeUvarint(output, cents);
    return;
  }

  if (field === "SF") {
    writeUvarint(output, BigInt(value));
    return;
  }

  if (field === "RO") {
    const packed = packReference(value);
    if (packed !== null) {
      output.writeByte(0);
      writeUvarint(output, [...value].length);
      output.writeBytes(packed);
    } else {
      output.writeByte(1);
      textEncoder(output, value, cacheFor(textCache, field));
    }
    return;
  }

  if (TEXT_FIELDS.has(field)) {
    textEncoder(output, value, cacheFor(textCache, field));
    return;
  }

  throw new Error(`no encoder for ${field}`);
}

function decodeValue(
  data: Uint8Array,
  start: number,
  field: FieldName,
  previous: string | null,
  textCache: TextCache,
  textDecoder: TextDecoder,
): { value: string; offset: number } {
  let offset = start;

  if (field === "R") {
    let number: bigint;
    if (previous === null) {
      if (offset + 8 > data.length) {
        throw new FormatError("truncated R field");
      }
      number = readU64BE(data, offset);
      offset += 8;
    } else {
      const delta = readUvarint(data, offset);
      number = BigInt(previous) + zigzagDecode(delta.value);
      offset = delta.offset;
    }

    if (number < 0n || number >= 10n ** 18n) {
      throw new FormatError(
        "decoded R field is outside the 18-digit range",
      );
    }
    return { value: number.toString().padStart(18, "0"), offset };
  }

  if (field === "I") {
    const result = readUvarint(data, offset);
    const whole = result.value / 100n;
    const fraction = (result.value % 100n).toString().padStart(2, "0");
    return { value: `RSD${whole},${fraction}`, offset: result.offset };
  }

  if (field === "SF") {
    const result = readUvarint(data, offset);
    if (result.value > 999n) {
      throw new FormatError(
        "decoded SF field is outside the 3-digit range",
      );
    }
    return {
      value: result.value.toString().padStart(3, "0"),
      offset: result.offset,
    };
  }

  if (field === "RO") {
    if (offset >= data.length) {
      throw new FormatError("truncated RO field");
    }
    const encoding = data[offset]!;
    offset += 1;
    if (encoding === 0) {
      const result = readUvarint(data, offset);
      const length = toSafeNumber(result.value, "packed RO length");
      offset = result.offset;
      const packedLength = Math.floor((length * 6 + 7) / 8);
      if (length > MAX_TEXT_BYTES || offset + packedLength > data.length) {
        throw new FormatError("invalid or truncated packed RO field");
      }
      return {
        value: unpackReference(
          data.subarray(offset, offset + packedLength),
          length,
        ),
        offset: offset + packedLength,
      };
    }
    if (encoding === 1) {
      return textDecoder(data, offset, cacheFor(textCache, field));
    }
    throw new FormatError("unknown RO field encoding");
  }

  if (TEXT_FIELDS.has(field)) {
    return textDecoder(data, offset, cacheFor(textCache, field));
  }
  throw new Error(`no decoder for ${field}`);
}

export function buildPayload(
  data: Uint8Array,
  textEncoder: TextEncoder = encodeCachedText,
): Uint8Array {
  const { lines, flags } = splitInput(data);
  if (lines.length > MAX_RECORDS) {
    throw new FormatError(`input has more than ${MAX_RECORDS} records`);
  }
  const records = lines.map((line, index) => parseRecord(line, index + 1));

  const output = new ByteWriter();
  output.writeByte(flags);
  writeUvarint(output, records.length);

  let previous: RecordValues = FIELD_NAMES.map(() => null);
  const textCache = createTextCache();
  for (const record of records) {
    let status = 0;
    let multiplier = 1;
    for (let index = 0; index < FIELD_NAMES.length; index += 1) {
      const value = record[index]!;
      const oldValue = previous[index]!;
      const trit = value === null ? 0 : value === oldValue ? 1 : 2;
      status += trit * multiplier;
      multiplier *= 3;
    }
    writeUvarint(output, status);

    for (let index = 0; index < FIELD_NAMES.length; index += 1) {
      const value = record[index]!;
      const oldValue = previous[index]!;
      if (value !== null && value !== oldValue) {
        encodeValue(
          output,
          FIELD_NAMES[index]!,
          value,
          oldValue,
          textCache,
          textEncoder,
        );
      }
    }
    previous = record;
  }

  return output.toUint8Array();
}

export function restorePayload(
  payload: Uint8Array,
  textDecoder: TextDecoder = decodeCachedText,
): Uint8Array {
  if (payload.length === 0) {
    throw new FormatError("compressed payload is empty");
  }

  const flags = payload[0]!;
  if ((flags & ~(FLAG_FINAL_NEWLINE | FLAG_CRLF)) !== 0) {
    throw new FormatError("compressed payload uses unknown flags");
  }

  let offset = 1;
  const countResult = readUvarint(payload, offset);
  const recordCount = toSafeNumber(countResult.value, "record count");
  offset = countResult.offset;
  if (recordCount > MAX_RECORDS) {
    throw new FormatError(
      `archive has more than ${MAX_RECORDS} records`,
    );
  }

  let previous: RecordValues = FIELD_NAMES.map(() => null);
  const textCache = createTextCache();
  const lines: string[] = [];
  const powersOfThree = FIELD_NAMES.map((_, index) => 3 ** index);

  for (let recordIndex = 0; recordIndex < recordCount; recordIndex += 1) {
    const statusResult = readUvarint(payload, offset);
    const status = toSafeNumber(statusResult.value, "field-state value");
    offset = statusResult.offset;
    if (status >= 3 ** FIELD_NAMES.length) {
      throw new FormatError("record has an invalid field-state value");
    }

    const values: (string | null)[] = [];
    for (let index = 0; index < FIELD_NAMES.length; index += 1) {
      const field = FIELD_NAMES[index]!;
      const trit = Math.floor(status / powersOfThree[index]!) % 3;
      const oldValue = previous[index]!;
      let value: string | null;
      if (trit === 0) {
        value = null;
      } else if (trit === 1) {
        if (oldValue === null) {
          throw new FormatError(
            `record inherits absent ${field} field`,
          );
        }
        value = oldValue;
      } else {
        const result = decodeValue(
          payload,
          offset,
          field,
          oldValue,
          textCache,
          textDecoder,
        );
        value = result.value;
        offset = result.offset;
      }
      values.push(value);
    }

    const fields = FIELD_NAMES.flatMap((name, index) => {
      const value = values[index];
      return value === null ? [] : [`${name}:${value}`];
    });
    if (fields.length === 0) {
      throw new FormatError("decoded record has no variable fields");
    }
    lines.push(FIXED_PREFIX + fields.join("|"));
    previous = values;
  }

  if (offset !== payload.length) {
    throw new FormatError("compressed payload has trailing data");
  }

  const separator = (flags & FLAG_CRLF) !== 0 ? "\r\n" : "\n";
  let text = lines.join(separator);
  if ((flags & FLAG_FINAL_NEWLINE) !== 0) text += separator;
  return encodeUtf8(text);
}
