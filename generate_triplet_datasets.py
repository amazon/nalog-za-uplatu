#!/usr/bin/env python3
"""Generate reproducible small-batch benchmark datasets."""

from __future__ import annotations

import random
from pathlib import Path


ROOT = Path(__file__).parent
OUTPUT_DIRECTORY = ROOT / "benchmark_triplets"
SOURCE_FILES = (ROOT / "example.txt", ROOT / "example_memberships.txt")
SEED = 20260724
DATASET_COUNT = 10
RECORDS_PER_DATASET = 3
DATASET_GROUPS = {
    3: (OUTPUT_DIRECTORY, "triplet"),
    4: (ROOT / "benchmark_quadruplets", "quadruplet"),
    5: (ROOT / "benchmark_quintuplets", "quintuplet"),
    6: (ROOT / "benchmark_sextuplets", "sextuplet"),
}


def generate(
    records_per_dataset: int = RECORDS_PER_DATASET,
    output_directory: Path = OUTPUT_DIRECTORY,
    filename_prefix: str = "triplet",
) -> list[tuple[int, ...]]:
    records: list[bytes] = []
    for path in SOURCE_FILES:
        records.extend(path.read_bytes().splitlines())

    randomizer = random.Random(SEED)
    combinations: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    while len(combinations) < DATASET_COUNT:
        combination = tuple(
            sorted(randomizer.sample(range(len(records)), records_per_dataset))
        )
        if combination not in seen:
            seen.add(combination)
            combinations.append(combination)

    output_directory.mkdir(exist_ok=True)
    for index, combination in enumerate(combinations, start=1):
        selected = (records[record_index] for record_index in combination)
        output = b"\n".join(selected) + b"\n"
        (output_directory / f"{filename_prefix}_{index:02d}.txt").write_bytes(output)
    return combinations


def main() -> None:
    for record_count, (output_directory, filename_prefix) in DATASET_GROUPS.items():
        combinations = generate(record_count, output_directory, filename_prefix)
        print(f"{record_count}-record datasets:")
        for index, combination in enumerate(combinations, start=1):
            record_numbers = ", ".join(str(value + 1) for value in combination)
            print(
                f"  {filename_prefix}_{index:02d}.txt: "
                f"combined records {record_numbers}"
            )


if __name__ == "__main__":
    main()
