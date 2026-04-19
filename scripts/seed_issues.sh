#!/usr/bin/env bash
# Seed PLANNED_FEATURE_ROADMAP_2026.md entries as GitHub issues.
#
# Usage:
#   scripts/seed_issues.sh OWNER/REPO
#
# Reads every line of the form `| TBD-NN | <title> | <tier> | <notes> |`,
# creates a GitHub issue per row using `gh issue create`, and rewrites
# `PLANNED_FEATURE_ROADMAP_2026.md` in place to replace `TBD-NN` with the
# real `#NUM` GitHub returned. Idempotent: rows already replaced are skipped.

set -euo pipefail

REPO="${1:-}"
if [[ -z "${REPO}" ]]; then
  echo "usage: $0 OWNER/REPO" >&2
  exit 2
fi

ROADMAP="$(dirname "$0")/../PLANNED_FEATURE_ROADMAP_2026.md"
[[ -f "${ROADMAP}" ]] || { echo "missing ${ROADMAP}" >&2; exit 1; }

command -v gh >/dev/null || { echo "gh CLI is required" >&2; exit 1; }

label_for_tier() {
  case "$1" in
    MVP)         echo "tier:mvp" ;;
    Post-MVP)    echo "tier:post-mvp" ;;
    Cloud)       echo "tier:cloud" ;;
    Enterprise)  echo "tier:enterprise" ;;
    *)           echo "tier:research" ;;
  esac
}

ensure_label() {
  local label="$1"
  gh -R "${REPO}" label create "${label}" --color "ededed" 2>/dev/null || true
}

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

while IFS= read -r line; do
  if [[ "${line}" =~ ^\|[[:space:]]*TBD-([0-9]+)[[:space:]]*\|[[:space:]]*(.+)[[:space:]]*\|[[:space:]]*([A-Za-z\-]+)[[:space:]]*\|[[:space:]]*(.*)[[:space:]]*\|$ ]]; then
    placeholder="TBD-${BASH_REMATCH[1]}"
    title="${BASH_REMATCH[2]}"
    tier="${BASH_REMATCH[3]}"
    notes="${BASH_REMATCH[4]}"
    label="$(label_for_tier "${tier}")"
    ensure_label "${label}"
    body="Tier: ${tier}

${notes}

(Auto-seeded from PLANNED_FEATURE_ROADMAP_2026.md.)"
    issue_url="$(gh -R "${REPO}" issue create --title "${title}" --label "${label}" --body "${body}")"
    issue_num="$(basename "${issue_url}")"
    echo "  → #${issue_num}  ${title}"
    line="${line//${placeholder}/#${issue_num}}"
  fi
  printf '%s\n' "${line}" >> "${tmp}"
done < "${ROADMAP}"

mv "${tmp}" "${ROADMAP}"
trap - EXIT
echo "done."
