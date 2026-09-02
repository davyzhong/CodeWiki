#!/usr/bin/env bash
# Production verification loop for CodeWiki.
#
# One command that runs every verification stage the current environment
# allows, in dependency order, and fails closed:
#   1. full offline test suite (twice by default; identical counts required)
#   2. bytecode compilation of src/ only
#   3. git diff --check
#   4. dependency audit via uvx pip-audit
#   5. live smoke (auto-detected; requires codewiki 0.6.x on PATH,
#      KNOWLEDGE_EXTRACTION_MODEL, KNOWLEDGE_LIVE_REPOSITORY)
#
# Toggles:
#   VERIFY_FAST=1     run the suite once instead of twice
#   REQUIRE_LIVE=1    fail instead of skipping when the live stage cannot run
#
# The Mimosa deep scan is an IDE-tool step and stays outside this script;
# run it from the agent toolbelt before promoting a release.
# Compatible with bash 3.2 (macOS system bash).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-$ROOT/.venv/bin/python}"
FAILURES=""
suite_result=MISSING
compile_result=MISSING
diff_result=MISSING
audit_result=MISSING
live_result=MISSING

fail() { FAILURES="$FAILURES $1"; }

header() { printf '\n===== %s =====\n' "$1"; }

header "stage 1/5: offline suite"
suite_runs=2
if [ "${VERIFY_FAST:-0}" = "1" ]; then suite_runs=1; fi
first=""
second=""
run_no=0
normalize() {
  # "752 passed, 1 skipped in 12.3s (0:00:12)" -> "752 passed, 1 skipped"
  printf '%s' "$1" | sed -E 's/ in [0-9]+(\.[0-9]+)?s( \([0-9:]+\))?$/ /' | sed -E 's/[[:space:]]+$//'
}
for expected in $(seq 1 "$suite_runs"); do
  run_no=$((run_no + 1))
  out="$("$PY" -m pytest 2>&1 | tail -1)"
  echo "run $run_no: $out"
  if [ "$run_no" -eq 1 ]; then first="$(normalize "$out")"; else second="$(normalize "$out")"; fi
done
case "$first" in
  *" passed"*)
    if [ "$suite_runs" -eq 2 ] && [ "$second" != "$first" ]; then
      suite_result="FAIL: non-deterministic ('$second' != '$first')"
      fail suite
    else
      suite_result="PASS ($first; runs=$suite_runs)"
    fi
    ;;
  *)
    suite_result="FAIL: unexpected summary '$first'"
    fail suite
    ;;
esac

header "stage 2/5: compileall src"
if "$PY" -m compileall -q src/knowledge_compiler; then
  compile_result="PASS"
else
  compile_result="FAIL: bytecode compilation failed"
  fail compileall
fi

header "stage 3/5: git diff --check"
diff_out="$(git diff --check 2>&1)"
if [ -z "$diff_out" ]; then
  diff_result="PASS"
else
  diff_result="FAIL: $diff_out"
  fail diff-check
fi

header "stage 4/5: dependency audit"
if command -v uvx >/dev/null 2>&1; then
  site_dir="$("$PY" - <<'EOF'
import sysconfig
print(sysconfig.get_paths()["purelib"])
EOF
)"
  audit_out="$(uvx pip-audit --path "$site_dir" --progress-spinner off 2>&1)"
  echo "$audit_out" | tail -3
  case "$audit_out" in
    *"No known vulnerabilities found"*) audit_result="PASS" ;;
    *) audit_result="FAIL: $audit_out"; fail pip-audit ;;
  esac
else
  audit_result="SKIP (uvx not available)"
  if [ "${REQUIRE_LIVE:-0}" = "1" ]; then fail pip-audit; fi
fi

header "stage 5/5: live smoke"
live_ready=1
reasons=""
command -v codewiki >/dev/null 2>&1 || { live_ready=0; reasons="$reasons codewiki-not-on-PATH;"; }
[ -n "${KNOWLEDGE_EXTRACTION_MODEL:-}" ] || { live_ready=0; reasons="$reasons KNOWLEDGE_EXTRACTION_MODEL-unset;"; }
[ -n "${KNOWLEDGE_LIVE_REPOSITORY:-}" ] || { live_ready=0; reasons="$reasons KNOWLEDGE_LIVE_REPOSITORY-unset;"; }
if [ "$live_ready" -eq 1 ]; then
  if KNOWLEDGE_RUN_LIVE=1 "$PY" -m pytest tests/integration/test_live_primary_build.py -q; then
    live_result="PASS"
  else
    live_result="FAIL: opt-in live build failed"
    fail live-smoke
  fi
else
  live_result="SKIP ($reasons)"
  echo "$live_result"
  if [ "${REQUIRE_LIVE:-0}" = "1" ]; then fail live-smoke; fi
fi

header "summary"
printf '%-12s %s\n' "suite" "$suite_result"
printf '%-12s %s\n' "compileall" "$compile_result"
printf '%-12s %s\n' "diff-check" "$diff_result"
printf '%-12s %s\n' "pip-audit" "$audit_result"
printf '%-12s %s\n' "live-smoke" "$live_result"
if [ -n "$FAILURES" ]; then
  echo
  echo "VERIFY: FAILED ($FAILURES )"
  exit 1
fi
echo
echo "VERIFY: PASS"
