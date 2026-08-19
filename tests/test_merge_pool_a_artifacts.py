import csv
import os
import tempfile
import unittest
from pathlib import Path

from scripts.merge_pool_a_artifacts import main


class MergePoolAArtifactsTest(unittest.TestCase):
    def test_new_partial_shard_cannot_erase_verified_profile_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = root / "artifacts"
            older = artifacts / "older" / "horses" / "profiles"
            newer = artifacts / "newer" / "horses" / "profiles"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)

            fields = [
                "horse_no",
                "name",
                "status",
                "profile_last_scraped",
                "profile_checked_at",
                "總獎金",
                "馬主",
                "父系",
            ]
            self._write(
                older / "horse_profiles.csv",
                fields,
                {
                    "horse_no": "J182",
                    "name": "齊歡最樂 (J182)",
                    "status": "active",
                    "profile_last_scraped": "2026-08-18",
                    "profile_checked_at": "2026-08-18T01:00:00+00:00",
                    "總獎金": "$1,700,000",
                    "馬主": "會友團體",
                    "父系": "Savabeel",
                },
            )
            self._write(
                newer / "horse_profiles.csv",
                fields,
                {
                    "horse_no": "J182",
                    "name": "齊歡最樂 (J182)",
                    "status": "active",
                    "profile_last_scraped": "2026-08-19",
                    "profile_checked_at": "2026-08-19T01:00:00+00:00",
                    "總獎金": "$1,783,775",
                    "馬主": "",
                    "父系": "",
                },
            )

            previous = Path.cwd()
            try:
                os.chdir(root)
                self.assertEqual(main(str(artifacts)), 0)
            finally:
                os.chdir(previous)

            with (root / "horses/profiles/horse_profiles.csv").open(
                encoding="utf-8-sig",
                newline="",
            ) as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["總獎金"], "$1,783,775")
            self.assertEqual(row["馬主"], "會友團體")
            self.assertEqual(row["父系"], "Savabeel")
            self.assertEqual(row["profile_refresh_status"], "partial_merged")
            self.assertEqual(row["profile_last_scraped"], "2026-08-18")
            self.assertEqual(
                row["profile_checked_at"],
                "2026-08-19T01:00:00+00:00",
            )

    @staticmethod
    def _write(path: Path, fields: list[str], row: dict[str, str]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerow(row)


if __name__ == "__main__":
    unittest.main()