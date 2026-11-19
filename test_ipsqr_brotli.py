from __future__ import annotations

import contextlib
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import ipsqr_brotli as ipq3
import ipsqr_compress as ipq1
import ipsqr_zstd as ipq2


ROOT = Path(__file__).parent


@unittest.skipUnless(
    ipq3.available(),
    "Brotli CLI with shared-dictionary support is unavailable",
)
class IPQ3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = ipq2.Vocabulary(ROOT / "serbian_english_vocabulary.tsv")
        cls.shared_dictionary = ipq3.SharedDictionary(cls.vocabulary)

    def archive_for_mode(self, mode: int, source: bytes) -> bytes:
        semantic_payload = ipq1._build_payload(source)
        if mode == ipq3.MODE_RAW_TEXT:
            payload = source
            text_mode = True
            dictionary = None
        elif mode == ipq3.MODE_SEMANTIC:
            payload = semantic_payload
            text_mode = False
            dictionary = None
        elif mode == ipq3.MODE_DICTIONARY_RAW_TEXT:
            payload = source
            text_mode = True
            dictionary = self.shared_dictionary.data
        elif mode == ipq3.MODE_DICTIONARY_SEMANTIC:
            payload = semantic_payload
            text_mode = False
            dictionary = self.shared_dictionary.data
        else:
            raise AssertionError("unsupported test mode")

        frame = ipq3._brotli_compress(
            payload,
            text_mode=text_mode,
            dictionary=dictionary,
        )
        checksum = struct.pack(">I", zlib.crc32(source))
        return (
            ipq3.MAGIC
            + self.shared_dictionary.fingerprint
            + bytes((mode,))
            + checksum
            + frame
        )

    def test_round_trip_benchmark_datasets(self) -> None:
        for filename in ("example.txt", "example_memberships.txt"):
            with self.subTest(filename=filename):
                source = (ROOT / filename).read_bytes()
                archive = ipq3.compress(source, self.vocabulary)
                self.assertEqual(ipq3.decompress(archive, self.vocabulary), source)

    def test_every_representation_mode(self) -> None:
        source = (ROOT / "example_memberships.txt").read_bytes()
        for mode in (
            ipq3.MODE_RAW_TEXT,
            ipq3.MODE_SEMANTIC,
            ipq3.MODE_DICTIONARY_RAW_TEXT,
            ipq3.MODE_DICTIONARY_SEMANTIC,
        ):
            with self.subTest(mode=mode):
                archive = self.archive_for_mode(mode, source)
                self.assertEqual(ipq3.decompress(archive, self.vocabulary), source)

    def test_shared_dictionary_contains_complete_vocabulary(self) -> None:
        self.assertEqual(
            self.shared_dictionary.term_count,
            len(self.vocabulary.terms),
        )
        self.assertEqual(len(self.shared_dictionary.data), 35_984)
        self.assertTrue(
            self.shared_dictionary.data.startswith(ipq3.IPS_FORMAT_DICTIONARY)
        )
        self.assertTrue(
            self.shared_dictionary.data.endswith(self.vocabulary.terms[0] + b"\n")
        )
        for term in self.vocabulary.terms:
            self.assertIn(b"\n" + term + b"\n", self.shared_dictionary.data)

    def test_shared_dictionary_improves_plain_brotli(self) -> None:
        source = (ROOT / "example_memberships.txt").read_bytes()
        plain = ipq3._brotli_compress(source, text_mode=True)
        shared = ipq3._brotli_compress(
            source,
            text_mode=True,
            dictionary=self.shared_dictionary.data,
        )
        self.assertLess(len(shared), len(plain))

    def test_dictionary_frame_requires_dictionary(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = self.archive_for_mode(ipq3.MODE_DICTIONARY_RAW_TEXT, source)
        with self.assertRaisesRegex(ipq1.FormatError, "Brotli"):
            ipq3._brotli_decompress(archive[17:])

    def test_corrupt_envelope(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = bytearray(ipq3.compress(source, self.vocabulary))

        with self.assertRaisesRegex(ipq1.FormatError, "IPQ3"):
            ipq3.decompress(b"IPQ2" + bytes(archive[4:]), self.vocabulary)

        wrong_fingerprint = bytearray(archive)
        wrong_fingerprint[4] ^= 1
        with self.assertRaisesRegex(ipq1.FormatError, "fingerprint"):
            ipq3.decompress(bytes(wrong_fingerprint), self.vocabulary)

        wrong_mode = bytearray(archive)
        wrong_mode[12] = 255
        with self.assertRaisesRegex(ipq1.FormatError, "mode"):
            ipq3.decompress(bytes(wrong_mode), self.vocabulary)

        wrong_checksum = bytearray(archive)
        wrong_checksum[13] ^= 1
        with self.assertRaisesRegex(ipq1.FormatError, "checksum"):
            ipq3.decompress(bytes(wrong_checksum), self.vocabulary)

        with self.assertRaisesRegex(ipq1.FormatError, "Brotli"):
            ipq3.decompress(bytes(archive[:18]), self.vocabulary)

    def test_standalone_cli_round_trip(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "payments.ipq3"
            output_path = Path(directory) / "payments.txt"
            with contextlib.redirect_stdout(io.StringIO()):
                result = ipq3.main(
                    [
                        "compress",
                        str(ROOT / "example.txt"),
                        "-o",
                        str(archive_path),
                    ]
                )
            self.assertEqual(result, 0)
            result = ipq3.main(
                ["decompress", str(archive_path), "-o", str(output_path)]
            )
            self.assertEqual(result, 0)
            self.assertEqual(output_path.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
