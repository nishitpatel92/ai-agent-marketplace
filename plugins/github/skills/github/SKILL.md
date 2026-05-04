---
name: github
description: Use when working with GitHub repositories — cloning, creating branches, opening pull requests, monitoring CI checks, requesting reviews, or merging. Covers best practices for `gh` CLI and `git`. Apply this skill any time the task involves a GitHub repo URL, a PR, a branch, or `.github/`.
---

# GitHub workflow skill

Best-practice patterns for `gh` and `git`. Standard flow: **clone → branch → commit → push → PR → checks → review → merge → cleanup**.

Programmatic operations (status checks, watch loops, log extraction) live in `scripts/` so this skill stays short. Invoke them via `python ${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py` (or adapt the path for your framework).

---

## Authentication

`gh` reads `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth login` cached creds. With `GITHUB_TOKEN` set, no `gh auth login` is needed.

For raw `git` over HTTPS, configure a credential helper so the token is fed automatically:

```sh
git config --global credential.https://github.com.helper \
  '!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f'
```

This avoids `fatal: could not read Username for 'https://github.com'`.

**Token type matters for what works:**
- **Classic PAT** (`repo` scope) — full `gh` functionality including `gh pr checks`.
- **Fine-grained PAT** — GitHub blocks reading individual check-run details regardless of permissions granted. `gh pr checks` will fail. Use the scripts (see below); they work with fine-grained PATs.
- **GitHub App** — full access; preferred long-term.

---

## Cloning

```sh
gh repo clone owner/repo                       # default
gh repo clone owner/repo -- --depth=1          # shallow for large repos
gh repo view owner/repo --json defaultBranchRef # check default branch name
```

---

## Branching

Always branch off the latest default branch. Convention: `<type>/<short-kebab>` where type ∈ {feat, fix, refactor, docs, chore, test}.

```sh
git fetch origin
git switch -c feat/short-summary origin/main
```

Never commit on `main` directly for shared repos.

---

## Committing

- One logical change per commit; `git add -p` for selective staging.
- Imperative mood (`Add X`, not `Added X`).
- Match the project's commit style (Conventional Commits if present).
- Subject ≤72 chars; blank line + body for context.
- Scan for secrets before committing: `git diff --cached | grep -iE 'token|secret|password|api_key'`.

---

## Pushing

```sh
git push -u origin <branch>            # first push
git push --force-with-lease            # safer than --force
```

Never `git push --force` to a shared/protected branch. `--force-with-lease` only overwrites if the remote is at the commit you last fetched.

---

## Pull request creation

Use a HEREDOC body so multi-line markdown survives:

```sh
gh pr create --title "Short, action-oriented title" --body "$(cat <<'EOF'
## Summary
- bullet 1
- bullet 2

## Why
brief rationale

## Test plan
- [ ] manual step
- [ ] automated test added at <path>
EOF
)"
```

Use `--draft` for WIP, `--reviewer @user1` to wire reviewers, `--base` for non-default targets.

---

## CI status checks

**Preferred (when `gh` works):**
```sh
gh pr checks <PR>                  # snapshot
gh pr checks <PR> --watch          # blocks until terminal
gh run view <run-id> --log-failed  # logs of a specific failed run
gh run rerun <run-id> --failed     # re-run only failed jobs
```

**Fallback** — when `gh` is unavailable OR the token is a fine-grained PAT (the bundled scripts handle both):

```sh
python ${CLAUDE_PLUGIN_ROOT}/scripts/pr_status.py --repo OWNER/REPO --pr N           # snapshot
python ${CLAUDE_PLUGIN_ROOT}/scripts/pr_status.py --repo OWNER/REPO --pr N --watch   # poll until terminal
python ${CLAUDE_PLUGIN_ROOT}/scripts/pr_logs.py   --repo OWNER/REPO --pr N --out ./logs
```

`pr_status.py` combines three signals (`mergeable_state`, GraphQL `statusCheckRollup.state`, Actions runs by `head_sha`) so the answer is correct regardless of token type. Exit codes: `0=pass, 1=fail, 2=pending, 3=error, 4=watch timeout`. Use `--json` for machine output.

Coverage caveat: the scripts cover GitHub Actions checks. External CI (CircleCI, Buildkite, Codecov via Checks API) is invisible to fine-grained PATs no matter the path — switch to a classic PAT or GitHub App if you need it.

**Never merge a PR with failing required checks.** Fix flaky checks; don't bypass them.

---

## Code review

```sh
gh pr edit 123 --add-reviewer @user
gh pr view 123 --comments
gh api repos/OWNER/REPO/pulls/123/comments \
  --jq '.[] | "\(.path):\(.line) — \(.user.login): \(.body)"'   # inline review comments
```

Address feedback in new commits. Don't force-push to "clean up" review history mid-review — reviewers lose context.

---

## Merging

```sh
gh pr merge <PR> --auto --squash --delete-branch    # most common
gh pr merge <PR> --squash --delete-branch           # merge now
```

Strategy choice (check repo settings: `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed`):
- `--squash` — clean linear history, single commit per PR. Default for feature work.
- `--rebase` — preserves all commits in linear order. Use when each commit is meaningful.
- `--merge` — preserves branch topology. Use only when explicit history matters.

After merge:
```sh
git switch main && git pull --ff-only && git branch -d <branch>
```

---

## Resolving conflicts

```sh
git fetch origin
git switch <branch>
git rebase origin/main           # or `git merge origin/main` if rebase is forbidden
# resolve files, `git add` them
git rebase --continue
git push --force-with-lease
```

---

## Common gotchas

- **Default branch isn't always `main`.** `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`.
- **Rate limits**: 5000 req/hr. Check via `gh api rate_limit`.
- **`Resource not accessible by personal access token`** = the token lacks a permission, not that the API is broken. For fine-grained PATs, also possible the resource is permanently blocked for that token type (e.g., individual check-runs).
- **`gh pr create` from a branch with no upstream** does nothing useful — `git push -u origin <branch>` first.
- **`gh pr merge --auto` requires auto-merge enabled** in repo settings (Settings → General → Pull Requests).
- **Required status checks block merge** even with admin override unless explicitly bypassed. Wait or fix.

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
git add -p && git commit -m "feat: ..."
git push -u origin feat/x

# PR
gh pr create --title "..." --body "..."
python ${CLAUDE_PLUGIN_ROOT}/scripts/pr_status.py --repo owner/repo --pr N --watch
gh pr view --comments

# Merge
gh pr merge <PR> --auto --squash --delete-branch
```
