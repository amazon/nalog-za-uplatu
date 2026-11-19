import { readFileSync } from "node:fs";

import { describe, expect, test } from "vitest";

import {
  IPQ2_SHARE_VERSION,
  LEGACY_SHARE_VERSION,
  buildCompressedShareUrl,
  buildLegacyShareUrl,
  decodeShareData,
  parseSharePath,
  sparsifyIpsBatch,
} from "../share-links.js";

const origin = "https://payments.example";
const example = readFileSync("example.txt", "utf8").replace(/\n$/u, "");
const memberships = readFileSync(
  "example_memberships.txt",
  "utf8",
).replace(/\n$/u, "");

function decodeUrl(url: string): string {
  const path = new URL(url).pathname;
  const parsed = parseSharePath(path);
  if (parsed === null) throw new Error("share URL did not parse");
  return decodeShareData(parsed.version, parsed.encodedData);
}

describe("share links", () => {
  test("keeps v1 sparse links backward compatible", () => {
    const url = buildLegacyShareUrl(origin, example);
    expect(url).toContain("/s/v1/");
    expect(decodeUrl(url)).toBe(sparsifyIpsBatch(example));
  });

  test("round-trips canonical IPS data through v2 IPQ2 links", () => {
    const url = buildCompressedShareUrl(origin, example);
    expect(url).toContain("/s/v2/");
    expect(decodeUrl(url)).toBe(example);
  });

  test.each([
    ["tax example", example],
    ["memberships example", memberships],
  ])("produces a shorter v2 link for %s", (_name, batch) => {
    const legacy = buildLegacyShareUrl(origin, batch);
    const compressed = buildCompressedShareUrl(origin, batch);
    expect(compressed.length).toBeLessThan(legacy.length);
  });

  test("parses supported version numbers without silently accepting others", () => {
    expect(parseSharePath("/s/v1/QQ")).toEqual({
      version: LEGACY_SHARE_VERSION,
      encodedData: "QQ",
    });
    expect(parseSharePath("/repo-subpath/s/v1/QQ")).toEqual({
      version: LEGACY_SHARE_VERSION,
      encodedData: "QQ",
    });
    expect(parseSharePath("/s/v2/QQ")).toEqual({
      version: IPQ2_SHARE_VERSION,
      encodedData: "QQ",
    });
    expect(parseSharePath("/repo-subpath/s/v2/QQ")).toEqual({
      version: IPQ2_SHARE_VERSION,
      encodedData: "QQ",
    });
    expect(() => decodeShareData(99, "QQ")).toThrow(
      /unsupported share URL version/u,
    );
  });
});
