import unittest

from horse_profile_fields import (
    canonicalize_row,
    merge_profile_rows,
    parse_profile_html,
)


CURRENT_HTML = """
<table class="horseProfile"><tbody><tr><td>
  <table><tr><td><span class="title_text">齊歡最樂 (J182)</span></td></tr></table>
</td><td>
  <table>
    <tr><td>出生地 / 馬齡</td><td>:</td><td>紐西蘭 / 6</td></tr>
    <tr><td>毛色 / 性別</td><td>:</td><td>棕 / 閹</td></tr>
    <tr><td>今季獎金*</td><td>:</td><td>$0</td></tr>
    <tr><td>總獎金*</td><td>:</td><td>$1,783,775</td></tr>
  </table>
  <table>
    <tr><td>練馬師</td><td>:</td><td><a>伍鵬志</a></td></tr>
    <tr><td>馬主</td><td>:</td><td><a>會友團體</a></td></tr>
    <tr><td>父系</td><td>:</td><td><a>Savabeel</a></td></tr>
    <tr><td>母系</td><td>:</td><td>Candelabra</td></tr>
    <tr><td>外祖父</td><td>:</td><td>Pins</td></tr>
  </table>
</td></tr></tbody></table>
"""


class HorseProfileFieldsTest(unittest.TestCase):
    def test_current_hkjc_labels_are_canonical(self):
        row = parse_profile_html(CURRENT_HTML, "J182")
        self.assertEqual(row["出生地"], "紐西蘭")
        self.assertEqual(row["今季獎金"], "$0")
        self.assertEqual(row["總獎金"], "$1,783,775")
        self.assertEqual(row["練馬師"], "伍鵬志")
        self.assertEqual(row["馬主"], "會友團體")
        self.assertEqual(row["父系"], "Savabeel")
        self.assertEqual(row["母系"], "Candelabra")
        self.assertEqual(row["外祖父"], "Pins")

    def test_historical_starred_columns_are_recovered(self):
        row = canonicalize_row(
            {
                "出生地___馬齡": "澳洲 / 4",
                "今季獎金*": "$12,300",
                "總獎金*": "$98,700",
            }
        )
        self.assertEqual(row["出生地"], "澳洲")
        self.assertEqual(row["今季獎金"], "$12,300")
        self.assertEqual(row["總獎金"], "$98,700")

    def test_public_status_marker_corrects_stale_active_flag(self):
        row = canonicalize_row(
            {
                "name": "仁者荃承 (K496) (已退役)",
                "status": "active",
            }
        )
        self.assertEqual(row["status"], "retired")

    def test_partial_refresh_never_erases_verified_values(self):
        merged = merge_profile_rows(
            {
                "horse_no": "J182",
                "馬主": "會友團體",
                "父系": "Savabeel",
                "profile_last_scraped": "2026-05-21",
            },
            {
                "horse_no": "J182",
                "總獎金": "$1,783,775",
                "profile_last_scraped": "2026-08-19",
            },
        )
        self.assertEqual(merged["馬主"], "會友團體")
        self.assertEqual(merged["父系"], "Savabeel")
        self.assertEqual(merged["總獎金"], "$1,783,775")
        self.assertEqual(merged["profile_last_scraped"], "2026-05-21")
        self.assertEqual(merged["profile_refresh_status"], "partial_merged")


if __name__ == "__main__":
    unittest.main()