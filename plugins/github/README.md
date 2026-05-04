# github

Best-practice patterns for working with GitHub via `gh` CLI and `git`. Covers cloning, branching, committing, pushing, opening PRs, watching CI checks, code review, and merging.

The skill teaches the canonical command for each step (`gh pr merge --auto --squash` rather than handcrafted API calls), the right credential helper for HTTPS git, and common pitfalls — fine-grained PAT permission errors, `--force` vs `--force-with-lease`, default-branch detection, etc.

## Layout

```
plugins/github/
├── .claude-plugin/plugin.json    # Claude Code plugin manifest
├── README.md                     # this file
└── skills/
    └── github/                    # skill root (per agentskills.io spec)
        ├── SKILL.md               # what the agent loads
        └── scripts/
            ├── pr_status.py       # CI status snapshot + watch
            └── pr_logs.py         # extract logs of failed Actions jobs
```

The skill follows the [Agent Skills specification](https://agentskills.io/specification): `SKILL.md` at skill root with required frontmatter (`name` matching the directory, `description`), and `scripts/` colocated with `SKILL.md`. Paths in `SKILL.md` are relative to the skill root.

## Scripts

Both scripts are Python stdlib only — no install step. They read `GITHUB_TOKEN` (or `GH_TOKEN`) from env.

### `pr_status.py`

```sh
python pr_status.py --repo owner/repo --pr 123              # one-shot snapshot
python pr_status.py --repo owner/repo --pr 123 --watch      # poll until terminal
python pr_status.py --repo owner/repo --pr 123 --json       # machine output
```

Combines three signals to be correct across token types:

- **`pull.mergeable_state`** — `clean` / `unstable` / `blocked` / `behind` / `dirty` / `unknown`. Encodes required-check status when branch protection or rulesets are configured.
- **GraphQL `statusCheckRollup.state`** — overall `SUCCESS` / `FAILURE` / `PENDING`. The aggregate field works with fine-grained PATs even though per-check details don't.
- **Actions API workflow runs by `head_sha`** — per-workflow detail (`Actions: Read` permission).

Exit codes: `0=pass, 1=fail, 2=pending, 3=error, 4=watch timeout`.

### `pr_logs.py`

```sh
python pr_logs.py --repo owner/repo --pr 123 --out ./logs
```

Finds the most recent failed Actions runs on the PR's head SHA, prints which jobs and steps failed, and extracts GitHub's log archive into `--out`.

## Why a skill, not a tool

Agentic CLIs already have shell access. They don't need a new tool — they need *guidance* on which commands to reach for and which to avoid (e.g., `--force` to a shared branch, merging with failing required checks). That's what the skill provides.

The bundled scripts handle the cases where shelling out to `gh` doesn't work — minimal sandboxes without `gh`, or fine-grained PATs that GitHub blocks from the per-check API. The scripts let the skill stay short and intent-focused while still being usable in those environments.
