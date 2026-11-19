from __future__ import annotations

import contextlib
import gzip
import io
import unittest
from pathlib import Path

import ipsqr_compress as ipq1
import ipsqr_zstd as ipq2


ROOT = Path(__file__).parent


class IPQ2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = ipq2.Vocabulary(ROOT / "serbian_english_vocabulary.tsv")

    def archive_for_mode(self, mode: int, source: bytes) -> bytes:
        if mode == ipq2.MODE_RAW_TEXT:
            payload = source
        elif mode == ipq2.MODE_SEMANTIC:
            payload = ipq1._build_payload(source)
        elif mode == ipq2.MODE_TOKENIZED_SEMANTIC:
            encoder = lambda output, value, cache: ipq2._encode_text(  # noqa: E731
                self.vocabulary, output, value, cache
            )
            payload = ipq1._build_payload(source, text_encoder=encoder)
        else:
            raise AssertionError("unsupported test mode")
        frame = ipq2._zstd_compress(payload, self.vocabulary.raw_dictionary)
        return (
            ipq2.MAGIC
            + self.vocabulary.fingerprint
            + bytes((mode,))
            + frame
        )

    def test_round_trip_benchmark_datasets(self) -> None:
        for filename in ("example.txt", "example_memberships.txt"):
            with self.subTest(filename=filename):
                source = (ROOT / filename).read_bytes()
                archive = ipq2.compress(source, self.vocabulary)
                self.assertEqual(ipq2.decompress(archive, self.vocabulary), source)

    def test_priority_words_have_one_byte_token_ids(self) -> None:
        for word in ("za", "račun", "racun", "porez", "doprinos"):
            with self.subTest(word=word):
                token_id = self.vocabulary.terms.index(word.encode("utf-8"))
                self.assertLess(token_id, ipq2.COMMON_TOKEN_COUNT)

    def test_all_256_common_token_ids_use_one_payload_byte(self) -> None:
        common = self.vocabulary.terms[: ipq2.COMMON_TOKEN_COUNT]
        self.assertEqual(len(common), len(set(common)))
        self.assertTrue(
            all(term.decode("utf-8") == term.decode("utf-8").lower() for term in common)
        )
        for token_id in (0, 255):
            with self.subTest(token_id=token_id):
                term = self.vocabulary.terms[token_id]
                encoded = ipq2._serialize_tokenized(self.vocabulary, term)
                self.assertEqual(
                    encoded,
                    bytes(
                        (
                            ipq2.TEXT_TOKENIZED,
                            1,
                            ipq2.PIECE_COMMON_TOKEN,
                            token_id,
                        )
                    ),
                )
                decoded, offset = ipq2._decode_text(
                    self.vocabulary, b"\0" + encoded, 0, []
                )
                self.assertEqual(decoded.encode("utf-8"), term)
                self.assertEqual(offset, len(encoded) + 1)

    def test_first_extended_token_uses_extended_piece_type(self) -> None:
        term = self.vocabulary.terms[ipq2.COMMON_TOKEN_COUNT]
        encoded = ipq2._serialize_tokenized(self.vocabulary, term)
        self.assertEqual(
            encoded,
            bytes(
                (
                    ipq2.TEXT_TOKENIZED,
                    1,
                    ipq2.PIECE_EXTENDED_TOKEN,
                    0,
                )
            ),
        )
        decoded, offset = ipq2._decode_text(
            self.vocabulary, b"\0" + encoded, 0, []
        )
        self.assertEqual(decoded.encode("utf-8"), term)
        self.assertEqual(offset, len(encoded) + 1)

    def test_case_and_serbian_ascii_variants_are_in_raw_dictionary(self) -> None:
        variants = (
            "članarina",
            "Članarina",
            "ČLANARINA",
            "clanarina",
            "Clanarina",
            "CLANARINA",
            "Niš",
            "Nis",
            "NIŠ",
            "NIS",
        )
        dictionary_lines = set(self.vocabulary.raw_dictionary.decode().splitlines())
        self.assertTrue(set(variants).issubset(dictionary_lines))

    def test_short_tokens_respect_word_boundaries(self) -> None:
        self.assertEqual(self.vocabulary.tokenize(b"Teniski"), [b"Teniski"])
        self.assertEqual(self.vocabulary.tokenize(b"redovni"), [b"redovni"])
        self.assertEqual(self.vocabulary.tokenize(b"izraz"), [b"izraz"])
        pieces = self.vocabulary.tokenize("za porez".encode())
        self.assertEqual(
            pieces,
            [
                self.vocabulary.terms.index(b"za"),
                b" ",
                self.vocabulary.terms.index(b"porez"),
            ],
        )

    def test_every_representation_mode(self) -> None:
        source = (ROOT / "example_memberships.txt").read_bytes()
        for mode in (
            ipq2.MODE_RAW_TEXT,
            ipq2.MODE_SEMANTIC,
            ipq2.MODE_TOKENIZED_SEMANTIC,
        ):
            with self.subTest(mode=mode):
                archive = self.archive_for_mode(mode, source)
                self.assertEqual(ipq2.decompress(archive, self.vocabulary), source)

    def test_line_endings_and_empty_input(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        cases = (b"", source.rstrip(b"\n"), source.replace(b"\n", b"\r\n"))
        for case in cases:
            with self.subTest(size=len(case)):
                archive = ipq2.compress(case, self.vocabulary)
                self.assertEqual(ipq2.decompress(archive, self.vocabulary), case)

    def test_vocabulary_fingerprint_mismatch(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = bytearray(ipq2.compress(source, self.vocabulary))
        archive[4] ^= 1
        with self.assertRaisesRegex(ipq1.FormatError, "fingerprint mismatch"):
            ipq2.decompress(bytes(archive), self.vocabulary)

    def test_corrupt_frame(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = bytearray(ipq2.compress(source, self.vocabulary))
        archive[-1] ^= 1
        with self.assertRaisesRegex(ipq1.FormatError, "Zstandard"):
            ipq2.decompress(bytes(archive), self.vocabulary)

    def test_unknown_mode(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = bytearray(self.archive_for_mode(ipq2.MODE_RAW_TEXT, source))
        archive[12] = 255
        with self.assertRaisesRegex(ipq1.FormatError, "unknown IPQ2"):
            ipq2.decompress(bytes(archive), self.vocabulary)

    def test_adaptive_compression_improves_held_out_corpus(self) -> None:
        source = (ROOT / "example_memberships.txt").read_bytes()
        archive = ipq2.compress(source, self.vocabulary)
        gzipped = gzip.compress(source, compresslevel=9, mtime=0)
        self.assertLess(len(archive), len(gzipped))
        self.assertLess(len(archive), len(ipq1.compress(source)))

    def test_benchmark_reports_brotli_ipq2a_and_ipq3(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = ipq2.main(["bench", str(ROOT / "example.txt")])
        self.assertEqual(result, 0)
        self.assertIn("brotli-11:", output.getvalue())
        self.assertIn("IPQ2a:", output.getvalue())
        self.assertIn("IPQ3:", output.getvalue())
        self.assertIn("IPQ3/brotli-11:", output.getvalue())

    def test_ipq1_remains_compatible(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = ipq1.compress(source)
        self.assertEqual(len(archive), 128)
        self.assertEqual(ipq1.decompress(archive), source)


if __name__ == "__main__":
    unittest.main()
