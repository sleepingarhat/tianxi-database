#!/usr/bin/env bash
# fixture_guard.sh — fixture-aware scheduling check for GHA workflows.
#
# Usage:
#   scripts/fixture_guard.sh --window N --direction DIR
#
# --window     integer number of days (inclusive)
# --direction  past | future | any
#
# Writes run=true or run=false to $GITHUB_OUTPUT.
# Fail-open: if fixture cache is missing or unreadable, run=true.
#
# Exit 0 always (caller gates subsequent steps via `if: steps.guard.outputs.run == 'true'`).

set -eu

WINDOW=1
DIRECTION=any

while [ "$#" -gt 0 ]; do
  case "$1" in
    --window) WINDOW="$2"; shift 2 ;;
    --direction) DIRECTION="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

FIXTURES="data/fixtures/fixtures.csv"

emit_run() {
  local val="$1"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "run=$val" >> "$GITHUB_OUTPUT"
  fi
  echo "guard: run=$val"
}

if [ ! -f "$FIXTURES" ]; then
  echo "fixture cache missing — fail-open"
  emit_run true
  exit 0
fi

TODAY=$(TZ=Asia/Hong_Kong date +%Y-%m-%d)

# Build the list of candidate dates based on window + direction
CANDIDATES=""
case "$DIRECTION" in
  past)
    for i in $(seq 1 "$WINDOW"); do
      CANDIDATES+=" $(TZ=Asia/Hong_Kong date -d "$TODAY -${i} day" +%Y-%m-%d)"
    done
    ;;
  future)
    for i in $(seq 1 "$WINDOW"); do
      CANDIDATES+=" $(TZ=Asia/Hong_Kong date -d "$TODAY +${i} day" +%Y-%m-%d)"
    done
    ;;
  any)
    CANDIDATES=" $TODAY"
    for i in $(seq 1 "$WINDOW"); do
      CANDIDATES+=" $(TZ=Asia/Hong_Kong date -d "$TODAY -${i} day" +%Y-%m-%d)"
      CANDIDATES+=" $(TZ=Asia/Hong_Kong date -d "$TODAY +${i} day" +%Y-%m-%d)"
    done
    ;;
  *)
    echo "invalid --direction: $DIRECTION" >&2
    emit_run true
    exit 0
    ;;
esac

echo "Checking fixture for today=$TODAY, direction=$DIRECTION, window=$WINDOW"
echo "Candidates:$CANDIDATES"

for d in $CANDIDATES; do
  if grep -q "^$d," "$FIXTURES"; then
    echo "match: $d is a race day"
    emit_run true
    exit 0
  fi
done

echo "no race day within window — skipping"
emit_run false
