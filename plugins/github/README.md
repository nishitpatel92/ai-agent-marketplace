# github

Best-practice patterns for working with GitHub via the `gh` CLI and `git`. Covers cloning, branching, committing, pushing, opening PRs, watching CI checks, code review, and merging.

The skill teaches the agent the canonical command for each step (e.g. `gh pr merge --auto --squash` rather than handcrafted API calls), the right credential helper for HTTPS git, and the common pitfalls — fine-grained PAT permission errors, `--force` vs `--force-with-lease`, default-branch detection, etc.

## What's inside

- [`skills/github/SKILL.md`](./skills/github/SKILL.md) — the skill the agent loads when GitHub work is in scope.

## When the skill activates

Anytime the agent is asked to clone a GitHub repo, open or update a PR, react to CI status, or merge — basically anything where the answer involves `gh` or a remote on `github.com`.

## Why a skill, not a tool

Agentic CLIs already have shell access. They don't need a new tool — they need *guidance* on which commands to reach for and which to avoid (e.g., `--force` to a shared branch, committing without `--force-with-lease`, merging with failing required checks). That's what this skill provides.
