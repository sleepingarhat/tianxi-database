#!/usr/bin/env python3
"""Build data/index.json manifest for tianxi-database.

Scans the repo's data artefacts and emits a single JSON file that frontends
and third-party consumers can fetch to discover what data exists, where it
lives, and how fresh it is. This is the SSOT companion to DATA_NOTES.md
(which documents per-column schemas).

Run locally:
    python3 tools/build_manifest.py

Run in CI: wired via .github/workflows/capy_manifest.yml, triggered after
any push that touches data/ or horses/ or jockeys/ or trainers/ or trials/
or entries/.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "index.json"
SCHEMA_VERSION = "1.0.0"
REPO_SLUG = "sleepingarhat/tianxi-database"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_SLUG}/main"

RACE_KINDS = ("results", "commentary", "dividends", "sectional", "video")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def git_head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def count_csv_rows(path: Path) -> int:
    """Row count excluding header. Returns -1 on error."""
    try:
        with path.open("rb") as fh:
            total = sum(1 for _ in fh)
        return max(total - 1, 0)
    except Exception:
        return -1


def scan_race_artefacts() -> dict[str, Any]:
    """Scan data/YYYY/{kind}_{date}.csv."""
    by_kind: dict[str, list[str]] = defaultdict(list)
    date_set: set[str] = set()
    year_set: set[int] = set()

    data_root = REPO_ROOT / "data"
    if not data_root.exists():
        return {"kinds": list(RACE_KINDS), "count_by_kind": {}, "distinct_race_days": 0}

    for year_dir in sorted(data_root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = int(year_dir.name)
        year_set.add(year)
        for f in year_dir.iterdir():
            if not f.name.endswith(".csv"):
                continue
            for kind in RACE_KINDS:
                if f.name.startswith(f"{kind}_"):
                    by_kind[kind].append(f.name)
                    m = DATE_RE.search(f.name)
                    if m:
                        date_set.add(m.group(1))
                    break

    dates_sorted = sorted(date_set)
    return {
        "kinds": list(RACE_KINDS),
        "path_template": "data/{year}/{kind}_{date}.csv",
        "raw_url_template": f"{RAW_BASE}/data/{{year}}/{{kind}}_{{date}}.csv",
        "count_by_kind": {k: len(by_kind[k]) for k in RACE_KINDS},
        "distinct_race_days": len(date_set),
        "date_range": {
            "start": dates_sorted[0] if dates_sorted else None,
            "end": dates_sorted[-1] if dates_sorted else None,
        },
        "season_years": sorted(year_set),
        "example": {
            "results": f"data/{dates_sorted[-1][:4]}/results_{dates_sorted[-1]}.csv"
            if dates_sorted
            else None,
        },
    }


def scan_fixtures() -> dict[str, Any]:
    fx_dir = REPO_ROOT / "data" / "fixtures"
    if not fx_dir.exists():
        return {"master": None, "seasons": {}, "row_count": 0}
    seasons: dict[str, str] = {}
    master = None
    total_rows = 0
    for f in sorted(fx_dir.iterdir()):
        if not f.name.endswith(".csv"):
            continue
        rel = f.relative_to(REPO_ROOT).as_posix()
        if f.name == "fixtures.csv":
            master = rel
            total_rows = count_csv_rows(f)
        else:
            m = re.match(r"(\d{4})_fixtures\.csv", f.name)
            if m:
                seasons[m.group(1)] = rel
    return {
        "master": master,
        "seasons": seasons,
        "row_count": total_rows,
        "docs": "DATA_NOTES.md#fixtures",
    }


def scan_horses() -> dict[str, Any]:
    profiles = REPO_ROOT / "horses" / "profiles" / "horse_profiles.csv"
    form_dir = REPO_ROOT / "horses" / "form_records"
    form_files = (
        sorted(p.name for p in form_dir.iterdir() if p.name.endswith(".csv"))
        if form_dir.exists()
        else []
    )
    return {
        "profiles": {
            "path": "horses/profiles/horse_profiles.csv" if profiles.exists() else None,
            "row_count": count_csv_rows(profiles) if profiles.exists() else -1,
        },
        "form_records": {
            "dir": "horses/form_records/",
            "path_template": "horses/form_records/form_{horse_id}.csv",
            "count": len(form_files),
            "sample": form_files[:3],
        },
    }


def scan_jockeys() -> dict[str, Any]:
    profiles = REPO_ROOT / "jockeys" / "jockey_profiles.csv"
    rec_dir = REPO_ROOT / "jockeys" / "records"
    rec_files = (
        sorted(p.name for p in rec_dir.iterdir() if p.name.endswith(".csv"))
        if rec_dir.exists()
        else []
    )
    return {
        "profiles": {
            "path": "jockeys/jockey_profiles.csv" if profiles.exists() else None,
            "row_count": count_csv_rows(profiles) if profiles.exists() else -1,
        },
        "records": {
            "dir": "jockeys/records/",
            "path_template": "jockeys/records/jockey_{code}.csv",
            "count": len(rec_files),
            "sample": rec_files[:3],
        },
    }


def scan_trainers() -> dict[str, Any]:
    profiles = REPO_ROOT / "trainers" / "trainer_profiles.csv"
    return {
        "profiles": {
            "path": "trainers/trainer_profiles.csv" if profiles.exists() else None,
            "row_count": count_csv_rows(profiles) if profiles.exists() else -1,
        },
        "records": {
            "status": "missing",
            "severity": "D1-high",
            "note": "trainers/records/ directory absent; see plan.md D1",
        },
    }


def scan_trials() -> dict[str, Any]:
    base = REPO_ROOT / "trials"
    results = base / "trial_results.csv"
    sessions = base / "trial_sessions.csv"
    return {
        "results": {
            "path": "trials/trial_results.csv" if results.exists() else None,
            "row_count": count_csv_rows(results) if results.exists() else -1,
        },
        "sessions": {
            "path": "trials/trial_sessions.csv" if sessions.exists() else None,
            "row_count": count_csv_rows(sessions) if sessions.exists() else -1,
        },
        "note": "HKJC retains ~176 days only; pre-2025-03-13 irrecoverable",
    }


def scan_entries() -> dict[str, Any]:
    base = REPO_ROOT / "entries"
    if not base.exists():
        return {}
    files = sorted(p.name for p in base.iterdir() if p.name.endswith(".txt"))
    dated = [f for f in files if re.match(r"entries_\d{4}-\d{2}-\d{2}\.txt", f)]
    latest = dated[-1] if dated else None
    return {
        "format": "txt",
        "path_template": "entries/entries_{date}.txt",
        "today_pointer": "entries/today_entries.txt"
        if (base / "today_entries.txt").exists()
        else None,
        "count": len(dated),
        "latest": latest,
        "note": "TXT (not CSV); space-delimited; race_number=0 means meeting-level batch",
    }


def scan_integrity() -> dict[str, Any]:
    latest = REPO_ROOT / "audit_reports" / "integrity_latest.json"
    if not latest.exists():
        return {"status": "no_report"}
    try:
        data = json.loads(latest.read_text())
    except Exception:
        return {"status": "parse_error"}
    return {
        "latest_report": "audit_reports/integrity_latest.json",
        "raw_url": f"{RAW_BASE}/audit_reports/integrity_latest.json",
        "scan_date": data.get("scan_date"),
        "overall_severity": data.get("overall_severity"),
        "critical_gap_count": data.get("critical_gap_count"),
        "warn_gap_count": data.get("warn_gap_count"),
        "recommendation": data.get("recommendation"),
    }


def scan_elo() -> dict[str, Any]:
    return {
        "storage": "github-actions-artifact",
        "workflow": ".github/workflows/elo-v11.yml",
        "artifact_name_pattern": "elo-v11-bulk-db-{run_id}",
        "format": "sqlite (gzipped)",
        "axes": ["overall", "turf_sprint", "turf_mile", "turf_middle", "turf_staying"],
        "retention_days": 14,
        "note": "Download via GitHub API; not in repo tree",
    }


def scan_news() -> dict[str, Any]:
    base = REPO_ROOT / "data" / "news"
    if not base.exists():
        return {
            "status": "not_implemented",
            "scraperTodo": True,
            "planned_path_template": "data/news/{YYYY-MM}/news_items.csv",
            "planned_image_dir": "data/news/images/",
            "owner": "tools/NewsScraper.py (D1 roadmap)",
        }
    months = sorted(
        p.name for p in base.iterdir() if p.is_dir() and re.match(r"\d{4}-\d{2}", p.name)
    )
    return {
        "status": "live",
        "months": months,
        "path_template": "data/news/{month}/news_items.csv",
        "image_dir": "data/news/images/",
    }


def build_summary(
    race: dict, fixtures: dict, horses: dict, jockeys: dict, trainers: dict
) -> dict:
    return {
        "race_days": race.get("distinct_race_days", 0),
        "race_artefact_files": sum(race.get("count_by_kind", {}).values()),
        "fixtures_rows": fixtures.get("row_count", 0),
        "horse_form_files": horses.get("form_records", {}).get("count", 0),
        "horse_profile_rows": horses.get("profiles", {}).get("row_count", 0),
        "jockey_record_files": jockeys.get("records", {}).get("count", 0),
        "jockey_profile_rows": jockeys.get("profiles", {}).get("row_count", 0),
        "trainer_profile_rows": trainers.get("profiles", {}).get("row_count", 0),
        "season_years": race.get("season_years", []),
    }


def main() -> int:
    race = scan_race_artefacts()
    fixtures = scan_fixtures()
    horses = scan_horses()
    jockeys = scan_jockeys()
    trainers = scan_trainers()
    trials = scan_trials()
    entries = scan_entries()
    integrity = scan_integrity()
    elo = scan_elo()
    news = scan_news()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "tools/build_manifest.py",
        "git_head": git_head_sha(),
        "repo": REPO_SLUG,
        "branch": "main",
        "base_url": {
            "raw": RAW_BASE,
            "api": f"https://api.github.com/repos/{REPO_SLUG}",
        },
        "docs": {
            "schema": "DATA_NOTES.md",
            "plan": "plan.md",
            "readme": "README.md",
        },
        "summary": build_summary(race, fixtures, horses, jockeys, trainers),
        "artefacts": {
            "race_day": race,
            "fixtures": fixtures,
            "horses": horses,
            "jockeys": jockeys,
            "trainers": trainers,
            "trials": trials,
            "entries": entries,
            "news": news,
            "elo": elo,
        },
        "integrity": integrity,
        "policy": {
            "odds_weighting": "disabled (beta=0 hardcoded in win-probability model)",
            "public_hit_rate_display": "blocked until system-wide >80% sustained",
            "data_independence": "factors are pure physics only; no derived-consensus signals",
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"[manifest] wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"[manifest] summary: {json.dumps(manifest['summary'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
