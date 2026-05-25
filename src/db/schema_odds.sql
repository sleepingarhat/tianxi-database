-- Odds snapshot schema — minimal subset used by Capy Odds workflow.
-- Synced from .elo-pipeline/src/db/schema.sql (odds_snapshots block).
-- Restored after commit 8070415 ("drop ... unused schema_odds") deleted it;
-- turns out capy_odds.yml still references this path and has been failing
-- with ENOENT on every cron since then (76+ hours of stale odds as of
-- 2026-05-25). File is intentionally small — only odds tables — because the
-- workflow creates a fresh scratch DB on each run and only needs odds tables.

CREATE TABLE IF NOT EXISTS odds_snapshots (
  id TEXT PRIMARY KEY,
  race_id TEXT NOT NULL REFERENCES races(id),
  horse_id TEXT NOT NULL REFERENCES horses(id),
  timestamp TEXT NOT NULL,
  win_odds REAL,
  place_odds REAL,
  pool_investment REAL,
  odds_type TEXT DEFAULT 'live'       -- 'opening' / 'live' / 'final'
);

CREATE INDEX IF NOT EXISTS idx_odds_race ON odds_snapshots(race_id);
CREATE INDEX IF NOT EXISTS idx_odds_horse ON odds_snapshots(horse_id, race_id);
CREATE INDEX IF NOT EXISTS idx_odds_timestamp ON odds_snapshots(timestamp);
