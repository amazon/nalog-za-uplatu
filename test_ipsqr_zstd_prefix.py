from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import ipsqr_compress as ipq1
import ipsqr_zstd as ipq2
import ipsqr_zstd_prefix as ipq2a


ROOT = Path(__file__).parent


class IPQ2aTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = ipq2.Vocabulary(ROOT / "serbian_english_vocabulary.tsv")

    def archive_for_mode(self, mode: int, source: bytes) -> bytes:
        encoder = lambda output, value, cache: ipq2._encode_text(  # noqa: E731
            self.vocabulary, output, value, cache
        )
        if mode == ipq2a.MODE_RAW_TEXT:
            payload = source
        elif mode == ipq2a.MODE_SEMANTIC:
            payload = ipq1._build_payload(source)
        elif mode == ipq2a.MODE_TOKENIZED_SEMANTIC:
            payload = ipq1._build_payload(source, text_encoder=encoder)
        elif mode == ipq2a.MODE_PREFIX_SEMANTIC:
            payload = ipq2a._build_prefix_payload(source)
        elif mode == ipq2a.MODE_TOKENIZED_PREFIX_SEMANTIC:
            payload = ipq2a._build_prefix_payload(source, text_encoder=encoder)
        else:
            raise AssertionError("unsupported test mode")
        frame = ipq2._zstd_compress(payload, self.vocabulary.raw_dictionary)
        return (
            ipq2a.MAGIC
            + self.vocabulary.fingerprint
            + bytes((mode,))
            + frame
        )

    def test_round_trip_representative_datasets(self) -> None:
        paths = [
            ROOT / "example.txt",
            ROOT / "example_memberships.txt",
            ROOT / "benchmark_triplets" / "triplet_01.txt",
            ROOT / "benchmark_quadruplets" / "quadruplet_01.txt",
            ROOT / "benchmark_quintuplets" / "quintuplet_01.txt",
            ROOT / "benchmark_sextuplets" / "sextuplet_01.txt",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_bytes()
                archive = ipq2a.compress(source, self.vocabulary)
                self.assertEqual(
                    ipq2a.decompress(archive, self.vocabulary),
                    source,
                )

    def test_every_representation_mode(self) -> None:
        source = (ROOT / "example_memberships.txt").read_bytes()
        for mode in (
            ipq2a.MODE_RAW_TEXT,
            ipq2a.MODE_SEMANTIC,
            ipq2a.MODE_TOKENIZED_SEMANTIC,
            ipq2a.MODE_PREFIX_SEMANTIC,
            ipq2a.MODE_TOKENIZED_PREFIX_SEMANTIC,
        ):
            with self.subTest(mode=mode):
                archive = self.archive_for_mode(mode, source)
                self.assertEqual(
                    ipq2a.decompress(archive, self.vocabulary),
                    source,
                )

    def test_example_uses_shorter_prefix_records(self) -> None:
        lines = (ROOT / "example.txt").read_bytes().decode("utf-8").splitlines()
        first = ipq2a._to_prefix_order(ipq1._parse_record(lines[0], 1))
        second = ipq2a._to_prefix_order(ipq1._parse_record(lines[1], 2))
        empty_cache = {field: [] for field in (*ipq1.TEXT_FIELDS, "RO")}

        first_prefix = ipq2a._prefix_record(
            first,
            (None,) * len(ipq2a.PREFIX_FIELD_NAMES),
            empty_cache,
            ipq1._encode_cached_text,
        )
        self.assertIsNotNone(first_prefix)
        assert first_prefix is not None
        self.assertEqual(first_prefix[0][0], 7)

        second_prefix = ipq2a._prefix_record(
            second,
            first,
            first_prefix[1],
            ipq1._encode_cached_text,
        )
        second_general = ipq2a._general_record(
            second,
            first,
            first_prefix[1],
            ipq1._encode_cached_text,
        )
        self.assertIsNotNone(second_prefix)
        assert second_prefix is not None
        self.assertEqual(second_prefix[0][0], 3)
        self.assertLess(len(second_prefix[0]), len(second_general[0]))

    def test_optional_field_hole_uses_general_record(self) -> None:
        line = (
            ROOT / "example_memberships.txt"
        ).read_bytes().decode("utf-8").splitlines()[0]
        record = ipq2a._to_prefix_order(ipq1._parse_record(line, 1))
        empty_cache = {field: [] for field in (*ipq1.TEXT_FIELDS, "RO")}
        self.assertIsNone(
            ipq2a._prefix_record(
                record,
                (None,) * len(ipq2a.PREFIX_FIELD_NAMES),
                empty_cache,
                ipq1._encode_cached_text,
            )
        )

        payload = ipq2a._build_prefix_payload((line + "\n").encode("utf-8"))
        _, offset = ipq1._read_uvarint(payload, 1)
        control, _ = ipq1._read_uvarint(payload, offset)
        self.assertGreaterEqual(control, ipq2a.GENERAL_STATUS_OFFSET)

    def test_example_improves_ipq2(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = ipq2a.compress(source, self.vocabulary)
        self.assertEqual(archive[13], ipq2a.MODE_PREFIX_SEMANTIC)
        self.assertLess(len(archive), len(ipq2.compress(source, self.vocabulary)))

    def test_corrupt_envelope(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        archive = bytearray(ipq2a.compress(source, self.vocabulary))

        with self.assertRaisesRegex(ipq1.FormatError, "IPQ2a"):
            ipq2a.decompress(b"IPQ2b" + bytes(archive[5:]), self.vocabulary)

        wrong_fingerprint = bytearray(archive)
        wrong_fingerprint[5] ^= 1
        with self.assertRaisesRegex(ipq1.FormatError, "fingerprint"):
            ipq2a.decompress(bytes(wrong_fingerprint), self.vocabulary)

        wrong_mode = bytearray(archive)
        wrong_mode[13] = 255
        with self.assertRaisesRegex(ipq1.FormatError, "mode"):
            ipq2a.decompress(bytes(wrong_mode), self.vocabulary)

        with self.assertRaises(ipq1.FormatError):
            ipq2a.decompress(bytes(archive[:15]), self.vocabulary)

    def test_standalone_cli_round_trip(self) -> None:
        source = (ROOT / "example.txt").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "payments.ipq2a"
            output_path = Path(directory) / "payments.txt"
            with contextlib.redirect_stdout(io.StringIO()):
                result = ipq2a.main(
                    [
                        "compress",
                        str(ROOT / "example.txt"),
                        "-o",
                        str(archive_path),
                    ]
                )
            self.assertEqual(result, 0)
            result = ipq2a.main(
                ["decompress", str(archive_path), "-o", str(output_path)]
            )
            self.assertEqual(result, 0)
            self.assertEqual(output_path.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
