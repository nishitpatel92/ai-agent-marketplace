---
name: github
description: Use when working with GitHub repositories — cloning, creating branches, opening pull requests, monitoring CI checks, requesting reviews, or merging. Covers best practices for `gh` CLI and `git` together. Apply this skill any time the task involves a GitHub repo URL, a PR, a branch, or anything in `.github/`.
---

# GitHub workflow skill

Best-practice patterns for `gh` CLI and `git`. Use these in order: **clone → branch → commit → push → PR → checks → review → merge → cleanup**.

The `gh` CLI handles auth (via `GITHUB_TOKEN` env var or stored login) and unifies operations that would otherwise need separate API calls. Prefer `gh` over raw `curl` to the API when an equivalent subcommand exists.

---

## Authentication

`gh` reads credentials in this order: `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth login` cached creds. If you have a token in env, you don't need to log in:

```sh
gh auth status               # confirm auth
gh api user --jq .login      # who am I?
```

For raw `git` over HTTPS, configure a credential helper that emits the token rather than putting it in URLs:

```sh
git config --global credential.https://github.com.helper \
  '!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f'
```

This avoids the failure mode `fatal: could not read Username for 'https://github.com'`.

---

## Cloning

Use `gh repo clone` — it picks the right protocol, respects auth, and works for repos you have access to without futzing with URLs:

```sh
gh repo clone owner/repo           # default location
gh repo clone owner/repo path/     # specify directory
gh repo clone owner/repo -- --depth=1 --filter=blob:none   # shallow + partial for large repos
```

For just-the-files inspection without auth setup:

```sh
gh repo view owner/repo --json defaultBranchRef,description
gh repo view owner/repo --web        # open in browser
```

---

## Branching

Always work on a feature branch off the latest default branch. Convention:

```
<type>/<short-kebab-summary>

Examples:
  feat/add-user-search
  fix/login-token-refresh
  docs/clarify-deploy-steps
  refactor/extract-auth-middleware
```

```sh
git fetch origin
git switch -c feat/short-summary origin/main    # branch from up-to-date main
```

Never commit on `main` directly for shared repos.

---

## Committing

- One logical change per commit. Use `git add -p` to stage hunks selectively when changes are mixed.
- Imperative mood: `Add feature X`, not `Added feature X` or `Adds feature X`.
- If the project follows Conventional Commits, match it (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`).
- Subject line ≤72 chars. Add a blank line + body if more context helps.
- **Never commit secrets.** Before staging, scan: `git diff --cached | grep -iE 'token|secret|password|api_key|aws_'`.
- Verify what's staged: `git status` then `git diff --cached`.

```sh
git add -p
git commit -m "fix(auth): refresh token before expiry, not after"
```

---

## Pushing

```sh
git push -u origin feat/short-summary    # first push, sets upstream
git push                                  # subsequent
git push --force-with-lease               # safer force-push (fails if remote moved)
```

**Never use `git push --force` to a shared/protected branch.** `--force-with-lease` only overwrites if the remote is at the commit you last fetched — fails if someone else pushed in the meantime.

---

## Pull request creation

Use `gh pr create` with a HEREDOC for the body so multi-line markdown stays intact:

```sh
gh pr create --title "Short, action-oriented title" --body "$(cat <<'EOF'
## Summary
- Bullet 1
- Bullet 2

## Why
Brief rationale: what problem this solves, what alternative was rejected.

## Test plan
- [ ] Manual verification step
- [ ] Automated test added at <path>
EOF
)"
```

Conventions:
- Title under ~70 chars; details go in the body.
- Use `--draft` for WIP — converts later with `gh pr ready`.
- `--base` to target a non-default branch.
- `--reviewer @user1,@user2 --assignee @me` to wire ownership.

---

## Watching CI checks

After pushing or opening the PR, the agent should wait for CI before declaring success.

### Preferred: `gh pr checks`

```sh
gh pr checks                    # one-shot snapshot
gh pr checks --watch            # blocks until all checks resolve
gh pr view --json statusCheckRollup \
  --jq '.statusCheckRollup[] | "\(.name): \(.conclusion // .status)"'
```

For a specific failed run, get logs:

```sh
gh run list --branch feat/short-summary --limit 5
gh run view <run-id> --log-failed
gh run rerun <run-id> --failed   # re-run only failed jobs without pushing
```

### Fallback: when `gh pr checks` doesn't work

`gh pr checks` can fail for two non-obvious reasons:

1. **`gh` not installed** in the current environment (minimal sandbox, CI image, etc.)
2. **The token is a fine-grained PAT.** GitHub deliberately blocks fine-grained PATs from reading individual check-run details — both via `GET /repos/.../check-runs` (REST) and via `statusCheckRollup.contexts.nodes[].name` (GraphQL). `gh pr checks` walks those nodes, hits the FORBIDDEN, and bails with `Resource not accessible by personal access token`. No permission grant fixes this; the limitation is by token type. To use `gh pr checks` natively, the credentials must be a classic PAT (with `repo` scope) or a GitHub App.

When either applies, fall back to three direct API calls — together they answer everything `gh pr checks` would.

**1. Aggregate "did CI pass?" — `statusCheckRollup.state`** (works with fine-grained PATs):

```sh
curl -sH "Authorization: bearer $GITHUB_TOKEN" -H 'Content-Type: application/json' \
  https://api.github.com/graphql -d "{
    \"query\":\"query { repository(owner:\\\"$OWNER\\\",name:\\\"$REPO\\\") {
      pullRequest(number:$PR) {
        commits(last:1) { nodes { commit { statusCheckRollup { state } } } }
      } } }\"
  }" | jq -r '.data.repository.pullRequest.commits.nodes[0].commit.statusCheckRollup.state'
# → SUCCESS | FAILURE | PENDING | ERROR
```

**2. Mergeable state — `pull.mergeable_state`** (gives required-check awareness when the repo has branch protection):

```sh
curl -sH "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/pulls/$PR" \
  | jq -r '.mergeable_state'
# → clean   = required checks pass + branch up-to-date + reviews ok → ready to merge
# → unstable = optional checks failed but mergeable
# → blocked = something required is blocking
# → behind  = needs rebase against base
# → dirty   = merge conflicts
# → unknown = GitHub still computing (retry) or PR closed
```

`mergeable_state` only encodes required-check status when the repo has branch protection or rulesets configured — those are Pro+ features for private repos. Public repos get them free. If neither is configured, GitHub treats every check as optional, and the signal degrades to "is the PR open and conflict-free."

**3. Per-workflow detail — Actions API** (works with `Actions: Read`):

```sh
SHA=$(curl -sH "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$OWNER/$REPO/pulls/$PR" | jq -r .head.sha)

# Snapshot
curl -sH "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?head_sha=$SHA" \
  | jq -r '.workflow_runs[] | "\(.name): \(.status) \(.conclusion // "")"'

# Drill into a failed run's jobs and steps
curl -sH "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID/jobs" \
  | jq -r '.jobs[] | "\(.name): \(.conclusion)" + (
      [.steps[]? | select(.conclusion == "failure") | "  failed step: " + .name] | join("\n")
    )'

# Failed-job logs (returns redirect to a zipped log file)
curl -sLH "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/jobs/$JOB_ID/logs" -o job-logs.zip
```

Note: `head_sha` must be the **full 40-char SHA** — abbreviated SHAs silently return empty results.

**4. Watch loop — poll until terminal state** (replaces `gh pr checks --watch`):

```sh
SHA=$(curl -sH "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$OWNER/$REPO/pulls/$PR" | jq -r .head.sha)
while :; do
  R=$(curl -sH "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$OWNER/$REPO/actions/runs?head_sha=$SHA")
  PENDING=$(jq '[.workflow_runs[] | select(.status != "completed")] | length' <<<"$R")
  TOTAL=$(jq '.total_count' <<<"$R")
  FAILED=$(jq '[.workflow_runs[] | select(.conclusion=="failure" or .conclusion=="cancelled")] | length' <<<"$R")
  printf "%s  %d/%d done, %d failed\n" "$(date +%T)" $((TOTAL-PENDING)) "$TOTAL" "$FAILED"
  [ "$PENDING" = "0" ] && break
  sleep 30
done
[ "$FAILED" = "0" ] && echo "all green" || echo "CI failed"
```

This Actions-API path covers GitHub Actions checks only. External CI providers (CircleCI, Buildkite, Codecov) write to the Checks API, not the Actions API — those *will* be invisible to a fine-grained PAT, regardless of fallback. For Actions-only repos (the common case), coverage is complete.

### Don't merge a PR with failing required checks

If a check is consistently flaky, fix it or mark it non-required — don't bypass it.

---

## Code review

Request reviewers on creation (`--reviewer`) or after:

```sh
gh pr edit 123 --add-reviewer @user
```

Read review comments programmatically (the agent often misses inline comments left on the diff):

```sh
gh api repos/OWNER/REPO/pulls/123/comments --jq '.[] | "\(.path):\(.line) — \(.user.login): \(.body)"'
gh pr view 123 --comments
```

Address feedback in new commits and push — don't force-push to "clean up" review history; reviewers lose their context.

---

## Merging

Prefer `--squash` for a clean linear history. Use `--auto` to set the PR to merge automatically once required checks pass:

```sh
# Merge now, squash, delete branch
gh pr merge 123 --squash --delete-branch

# Auto-merge as soon as checks pass (most useful pattern)
gh pr merge 123 --auto --squash --delete-branch
```

Strategy choice (use whichever the repo prefers — check `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed`):
- `--squash` — best for feature branches with messy in-progress commits. Single tidy commit on `main`.
- `--rebase` — preserves all commits as a linear sequence. Useful when each commit is meaningful and you want bisectability.
- `--merge` — preserves the branch topology. Use only when explicit branch history matters (e.g., release branches).

After merge:

```sh
git switch main
git pull --ff-only
git branch -d feat/short-summary    # local cleanup; -D if not yet merged locally but already merged upstream
```

---

## Resolving conflicts

When `gh pr merge` reports merge conflicts, resolve locally:

```sh
git fetch origin
git switch feat/short-summary
git rebase origin/main           # or `git merge origin/main` if rebase is forbidden
# resolve files, `git add` them
git rebase --continue
git push --force-with-lease      # force only safe with lease, never plain --force
```

---

## Common gotchas

- **Default branch isn't always `main`.** `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`.
- **Rate limits**: 5000 req/hr authenticated. Check before bulk ops: `gh api rate_limit`.
- **Fine-grained PATs** need explicit per-permission and per-repo scopes. `Resource not accessible by personal access token` means your token is missing a permission, not that the API is wrong.
- **`gh pr create` from a detached HEAD or a branch with no upstream** silently does nothing useful — push the branch first (`git push -u origin <branch>`), then create the PR.
- **`gh pr merge --auto` requires "auto-merge" enabled** on the repo settings. If it errors, tell the user to enable it under Settings → General → Pull Requests.
- **Required status checks block merge** even with admin override unless explicitly bypassed. Wait or fix; don't bypass.

---

## Quick reference

```sh
# Auth
gh auth status

# Repo
gh repo clone owner/repo
gh repo view owner/repo

# Branch + commit
git switch -c feat/x origin/main
git add -p && git commit -m "feat: …"
git push -u origin feat/x

# PR
gh pr create --title "…" --body "…"
gh pr checks --watch
gh pr view --comments

# Merge
gh pr merge --auto --squash --delete-branch
```
