import { FormatError } from "./errors.js";

export class ByteWriter {
  private buffer = new Uint8Array(256);
  private used = 0;

  get length(): number {
    return this.used;
  }

  writeByte(value: number): void {
    if (!Number.isInteger(value) || value < 0 || value > 0xff) {
      throw new RangeError(`byte value is outside 0..255: ${value}`);
    }
    this.ensureCapacity(1);
    this.buffer[this.used] = value;
    this.used += 1;
  }

  writeBytes(value: Uint8Array): void {
    this.ensureCapacity(value.length);
    this.buffer.set(value, this.used);
    this.used += value.length;
  }

  toUint8Array(): Uint8Array {
    return this.buffer.slice(0, this.used);
  }

  private ensureCapacity(additional: number): void {
    const required = this.used + additional;
    if (required <= this.buffer.length) return;

    let capacity = this.buffer.length;
    while (capacity < required) {
      capacity = Math.max(capacity * 2, required);
    }

    const replacement = new Uint8Array(capacity);
    replacement.set(this.buffer.subarray(0, this.used));
    this.buffer = replacement;
  }
}

export interface Uvarint {
  value: bigint;
  offset: number;
}

export function writeUvarint(
  output: ByteWriter,
  input: number | bigint,
): void {
  let value = typeof input === "bigint" ? input : BigInt(input);
  if (value < 0n) {
    throw new RangeError("uvarint cannot encode a negative value");
  }

  while (value >= 0x80n) {
    output.writeByte(Number((value & 0x7fn) | 0x80n));
    value >>= 7n;
  }
  output.writeByte(Number(value));
}

export function readUvarint(data: Uint8Array, start: number): Uvarint {
  let offset = start;
  let value = 0n;

  for (let index = 0; index < 10; index += 1) {
    if (offset >= data.length) {
      throw new FormatError("truncated variable-length integer");
    }

    const byte = data[offset]!;
    offset += 1;
    value |= BigInt(byte & 0x7f) << BigInt(index * 7);
    if (byte < 0x80) {
      return { value, offset };
    }
  }

  throw new FormatError("variable-length integer is too large");
}

export function toSafeNumber(value: bigint, description: string): number {
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new FormatError(`${description} is too large`);
  }
  return Number(value);
}

export function concatBytes(parts: readonly Uint8Array[]): Uint8Array {
  const size = parts.reduce((total, part) => total + part.length, 0);
  const output = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    output.set(part, offset);
    offset += part.length;
  }
  return output;
}

export function bytesEqual(
  left: Uint8Array,
  right: Uint8Array,
): boolean {
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return false;
  }
  return true;
}

export function compareBytes(
  left: Uint8Array,
  right: Uint8Array,
): number {
  const shared = Math.min(left.length, right.length);
  for (let index = 0; index < shared; index += 1) {
    const difference = left[index]! - right[index]!;
    if (difference !== 0) return difference;
  }
  return left.length - right.length;
}

export function startsWithBytes(
  data: Uint8Array,
  prefix: Uint8Array,
): boolean {
  if (data.length < prefix.length) return false;
  return bytesEqual(data.subarray(0, prefix.length), prefix);
}

export function writeU32BE(output: ByteWriter, value: number): void {
  if (!Number.isInteger(value) || value < 0 || value > 0xffff_ffff) {
    throw new RangeError("u32 value is outside its range");
  }
  output.writeByte((value >>> 24) & 0xff);
  output.writeByte((value >>> 16) & 0xff);
  output.writeByte((value >>> 8) & 0xff);
  output.writeByte(value & 0xff);
}

export function readU32BE(data: Uint8Array, offset: number): number {
  if (offset + 4 > data.length) {
    throw new FormatError("truncated 32-bit integer");
  }
  return (
    data[offset]! * 0x1000000 +
    (data[offset + 1]! << 16) +
    (data[offset + 2]! << 8) +
    data[offset + 3]!
  );
}

export function writeU64BE(output: ByteWriter, input: bigint): void {
  if (input < 0n || input > 0xffff_ffff_ffff_ffffn) {
    throw new RangeError("u64 value is outside its range");
  }
  for (let shift = 56n; shift >= 0n; shift -= 8n) {
    output.writeByte(Number((input >> shift) & 0xffn));
  }
}

export function readU64BE(data: Uint8Array, offset: number): bigint {
  if (offset + 8 > data.length) {
    throw new FormatError("truncated 64-bit integer");
  }
  let value = 0n;
  for (let index = 0; index < 8; index += 1) {
    value = (value << 8n) | BigInt(data[offset + index]!);
  }
  return value;
}

export function bytesToHex(data: Uint8Array): string {
  let output = "";
  for (const byte of data) {
    output += byte.toString(16).padStart(2, "0");
  }
  return output;
}
