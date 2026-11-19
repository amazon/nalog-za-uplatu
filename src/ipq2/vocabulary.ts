import { bytesEqual } from "./bytes.js";
import type { CompiledVocabularyData } from "./vocabulary-format.js";
import { decodeUtf8, encodeUtf8 } from "./utf8.js";

export type TokenPiece = number | Uint8Array;

interface TrieNode {
  readonly children: Map<number, TrieNode>;
  tokenId?: number;
}

const ALPHANUMERIC_RE = /^[\p{L}\p{N}]$/u;

function isAlphanumeric(character: string): boolean {
  return ALPHANUMERIC_RE.test(character);
}

function createTrie(terms: readonly Uint8Array[]): TrieNode {
  const root: TrieNode = { children: new Map() };
  terms.forEach((term, tokenId) => {
    let node = root;
    for (const byte of term) {
      let child = node.children.get(byte);
      if (child === undefined) {
        child = { children: new Map() };
        node.children.set(byte, child);
      }
      node = child;
    }
    node.tokenId = tokenId;
  });
  return root;
}

function createTermWordEdges(
  terms: readonly Uint8Array[],
): Uint8Array {
  const edges = new Uint8Array(terms.length);
  terms.forEach((term, index) => {
    const characters = [
      ...decodeUtf8(term, "vocabulary term is not valid UTF-8"),
    ];
    const first = characters[0];
    const last = characters.at(-1);
    if (first !== undefined && isAlphanumeric(first)) {
      edges[index] = edges[index]! | 1;
    }
    if (last !== undefined && isAlphanumeric(last)) {
      edges[index] = edges[index]! | 2;
    }
  });
  return edges;
}

export class Vocabulary {
  readonly fingerprint: Uint8Array;
  readonly rawDictionary: Uint8Array;
  readonly terms: readonly Uint8Array[];

  private readonly trie: TrieNode;
  private readonly termWordEdges: Uint8Array;

  private constructor(data: CompiledVocabularyData) {
    this.fingerprint = data.fingerprint.slice();
    this.rawDictionary = data.rawDictionary.slice();
    this.terms = data.terms.map((term) => term.slice());
    this.trie = createTrie(this.terms);
    this.termWordEdges = createTermWordEdges(this.terms);
  }

  static fromCompiled(data: CompiledVocabularyData): Vocabulary {
    return new Vocabulary(data);
  }

  findTerm(value: string): number {
    const encoded = encodeUtf8(value);
    return this.terms.findIndex((term) => bytesEqual(term, encoded));
  }

  tokenize(data: Uint8Array): TokenPiece[] {
    const text = decodeUtf8(data);
    const wordBefore = new Uint8Array(data.length + 1);
    const wordAfter = new Uint8Array(data.length + 1);

    let byteOffset = 0;
    let previousIsWord = false;
    for (const character of text) {
      const characterIsWord = isAlphanumeric(character);
      wordBefore[byteOffset] = previousIsWord ? 1 : 0;
      wordAfter[byteOffset] = characterIsWord ? 1 : 0;
      byteOffset += encodeUtf8(character).length;
      previousIsWord = characterIsWord;
    }
    wordBefore[byteOffset] = previousIsWord ? 1 : 0;
    wordAfter[byteOffset] = 0;

    const pieces: TokenPiece[] = [];
    let offset = 0;
    let literalStart = 0;

    while (offset < data.length) {
      let node = this.trie;
      let cursor = offset;
      let bestToken: number | undefined;
      let bestEnd = offset;

      while (cursor < data.length) {
        const child = node.children.get(data[cursor]!);
        if (child === undefined) break;
        node = child;
        cursor += 1;

        const tokenId = node.tokenId;
        if (tokenId !== undefined) {
          const edges = this.termWordEdges[tokenId]!;
          const startsInsideWord =
            (edges & 1) !== 0 && wordBefore[offset] !== 0;
          const endsInsideWord =
            (edges & 2) !== 0 && wordAfter[cursor] !== 0;
          if (!startsInsideWord && !endsInsideWord) {
            bestToken = tokenId;
            bestEnd = cursor;
          }
        }
      }

      if (bestToken === undefined) {
        offset += 1;
        continue;
      }

      if (literalStart < offset) {
        pieces.push(data.slice(literalStart, offset));
      }
      pieces.push(bestToken);
      offset = bestEnd;
      literalStart = offset;
    }

    if (literalStart < data.length) {
      pieces.push(data.slice(literalStart));
    }
    return pieces;
  }
}
