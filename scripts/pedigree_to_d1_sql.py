"""
data/pedigree/horse_pedigree.csv → D1 upsert SQL

Writes one .sql file (chunked) that:
  1. creates horse_pedigree if missing (horse_id = 'horse_'+code, matching
     race_results.horse_id so the LGB feature join works directly)
  2. upserts every pedigree row (COALESCE — never overwrites a value with NULL)
  3. backfills horses.sire / dam / dam_sire for the canonical horses rows

Usage:
  python scripts/pedigree_to_d1_sql.py --out /tmp/pedigree-sql [--chunk 400]
Then:
  wrangler d1 execute tianxi-db --remote --file=/tmp/pedigree-sql/000.sql
"""

import argparse
import csv
import os

CSV_PATH = os.path.join("data", "pedigree", "horse_pedigree.csv")

DDL = """CREATE TABLE IF NOT EXISTS horse_pedigree (
  horse_id TEXT PRIMARY KEY,
  code     TEXT,
  sire     TEXT,
  dam      TEXT,
  dam_sire TEXT,
  half_siblings TEXT,
  country_of_origin TEXT,
  import_type TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pedigree_sire ON horse_pedigree(sire);
CREATE INDEX IF NOT EXISTS idx_pedigree_damsire ON horse_pedigree(dam_sire);
"""


def q(v: str | None) -> str:
    if v is None or str(v).strip() == "":
        return "NULL"
    return "'" + str(v).strip().replace("'", "''") + "'"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=CSV_PATH)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk", type=int, default=400)
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("code") or "").strip()]
    if not rows:
        raise SystemExit("no pedigree rows")

    os.makedirs(args.out, exist_ok=True)
    for old in os.listdir(args.out):
        if old.endswith(".sql"):
            os.remove(os.path.join(args.out, old))

    stmts: list[str] = []
    for r in rows:
        code = r["code"].strip()
        hid = (r.get("horse_id") or f"horse_{code}").strip()
        vals = (
            q(hid), q(code), q(r.get("sire")), q(r.get("dam")), q(r.get("dam_sire")),
            q(r.get("half_siblings")), q(r.get("country_of_origin")), q(r.get("import_type")),
            q(r.get("scraped_at")),
        )
        stmts.append(
            "INSERT INTO horse_pedigree (horse_id, code, sire, dam, dam_sire, half_siblings, "
            "country_of_origin, import_type, updated_at) VALUES ("
            + ", ".join(vals)
            + ") ON CONFLICT(horse_id) DO UPDATE SET "
            "sire=COALESCE(excluded.sire, horse_pedigree.sire), "
            "dam=COALESCE(excluded.dam, horse_pedigree.dam), "
            "dam_sire=COALESCE(excluded.dam_sire, horse_pedigree.dam_sire), "
            "half_siblings=COALESCE(excluded.half_siblings, horse_pedigree.half_siblings), "
            "country_of_origin=COALESCE(excluded.country_of_origin, horse_pedigree.country_of_origin), "
            "import_type=COALESCE(excluded.import_type, horse_pedigree.import_type), "
            "updated_at=excluded.updated_at;"
        )

    # Backfill the canonical horses table from the pedigree map.
    stmts.append(
        "UPDATE horses SET "
        "sire = COALESCE(sire, (SELECT p.sire FROM horse_pedigree p WHERE p.horse_id = horses.id)), "
        "dam = COALESCE(dam, (SELECT p.dam FROM horse_pedigree p WHERE p.horse_id = horses.id)), "
        "dam_sire = COALESCE(dam_sire, (SELECT p.dam_sire FROM horse_pedigree p WHERE p.horse_id = horses.id)) "
        "WHERE EXISTS (SELECT 1 FROM horse_pedigree p WHERE p.horse_id = horses.id);"
    )

    files = 0
    body: list[str] = [DDL]
    count = 0
    for s in stmts:
        body.append(s)
        count += 1
        if count >= args.chunk:
            path = os.path.join(args.out, f"{files:03d}.sql")
            open(path, "w", encoding="utf-8").write("\n".join(body) + "\n")
            files += 1
            body, count = [DDL], 0
    if body:
        path = os.path.join(args.out, f"{files:03d}.sql")
        open(path, "w", encoding="utf-8").write("\n".join(body) + "\n")
        files += 1

    print(f"rows={len(rows)} statements={len(stmts)} files={files} → {args.out}")


if __name__ == "__main__":
    main()
