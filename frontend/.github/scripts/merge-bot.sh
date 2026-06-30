#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Merge Bot — keep every active claude/** branch in sync with main.
#
# Runs on each push to main. For every recent claude/** branch it merges main
# in; clean merges are pushed so branches never drift. Real conflicts are handed
# to the AI resolver (ai-merge-resolve.py, free-tier Gemini). If the AI fully
# resolves them the merge is pushed; otherwise the merge is aborted and a single
# tracking issue is opened for a human.
#
# Why: the deploy pipeline auto-merges a claude/** push into main. A branch that
# has drifted far behind main conflicts and silently blocks its own deploy. This
# bot keeps drift near-zero so that almost never happens.
#
# Pushes use GITHUB_TOKEN, which (by GitHub design) does NOT re-trigger
# workflows — so syncing a branch never kicks off a deploy or loops the bot.
#
# Env: GEMINI_API_KEY (or GOOGLE_API_KEY), GITHUB_TOKEN, GITHUB_REPOSITORY,
#      MERGE_BOT_MAX_AGE_DAYS (optional, default 30 — skip abandoned branches).
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY required}"
API="https://api.github.com/repos/$REPO"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_AGE_DAYS="${MERGE_BOT_MAX_AGE_DAYS:-30}"
NOW="$(date +%s)"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git fetch origin --prune --quiet

# Open one tracking issue per branch (deduped against existing open issues).
open_issue() {
  local branch="$1" files="$2" existing body
  existing="$(curl -sS -H "Authorization: token $GITHUB_TOKEN" \
    "$API/issues?state=open&labels=merge-conflict&per_page=100" \
    | jq -r --arg b "$branch" '[.[] | select(.title | contains($b))] | length')"
  if [ "${existing:-0}" != "0" ]; then
    echo "  (tracking issue already open for $branch — not duplicating)"
    return
  fi
  body="$(printf 'The merge bot could not auto-resolve conflicts merging `main` into `%s`.\n\n**Conflicted files:**\n```\n%s\n```\n\nResolve locally:\n```\ngit checkout %s\ngit merge main   # fix the conflicts\ngit push\n```\n\nWorkflow run: %s/%s/actions/runs/%s' \
    "$branch" "$files" "$branch" "${GITHUB_SERVER_URL:-https://github.com}" "$REPO" "${GITHUB_RUN_ID:-0}")"
  curl -sS -X POST -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" "$API/issues" \
    -d "$(jq -nc --arg t "🤖 Merge bot: $branch needs manual conflict resolution" \
                 --arg b "$body" \
                 '{title:$t, body:$b, labels:["merge-conflict","automated"]}')" >/dev/null \
    && echo "  opened tracking issue for $branch"
}

mapfile -t BRANCHES < <(git for-each-ref --format='%(refname:short)' refs/remotes/origin/claude \
                          | sed 's#^origin/##')
if [ "${#BRANCHES[@]}" -eq 0 ]; then
  echo "No claude/** branches to sync."
  exit 0
fi

failures=0
for B in "${BRANCHES[@]}"; do
  echo "::group::$B"

  ts="$(git log -1 --format=%ct "origin/$B" 2>/dev/null || echo 0)"
  age_days=$(( (NOW - ts) / 86400 ))
  if [ "$age_days" -gt "$MAX_AGE_DAYS" ]; then
    echo "  stale (${age_days}d > ${MAX_AGE_DAYS}d) — skipping"
    echo "::endgroup::"; continue
  fi

  git checkout -B "$B" "origin/$B" >/dev/null 2>&1

  if git merge --no-edit origin/main >/dev/null 2>&1; then
    echo "  ✓ in sync with main"
  else
    CONFLICTS="$(git diff --name-only --diff-filter=U)"
    echo "  conflicts:"; echo "$CONFLICTS" | sed 's/^/    /'
    if python3 "$SCRIPT_DIR/ai-merge-resolve.py" $CONFLICTS; then
      git add -A
      if git grep -nE '^(<<<<<<<|=======|>>>>>>>)' -- $CONFLICTS >/dev/null 2>&1; then
        echo "  ::error::conflict markers remain after AI pass"
        git merge --abort || true
        open_issue "$B" "$CONFLICTS"; failures=$((failures+1))
        echo "::endgroup::"; continue
      fi
      git commit --no-edit -m "Merge main into $B (AI-resolved conflicts)" >/dev/null
      echo "  🤖 AI-resolved the conflict"
    else
      git merge --abort || true
      open_issue "$B" "$CONFLICTS"; failures=$((failures+1))
      echo "::endgroup::"; continue
    fi
  fi

  git push origin "$B" >/dev/null 2>&1 && echo "  pushed $B" || echo "  nothing to push"
  echo "::endgroup::"
done

echo "Merge bot done. Unresolved branches: $failures"
# Non-zero exit surfaces the run as failed in the Actions tab when something
# needs a human, without blocking any deploy (this is a standalone workflow).
[ "$failures" -eq 0 ]
