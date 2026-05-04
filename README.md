# ai-agent-marketplace

A growing collection of skills (and eventually agents and commands) intended to be **framework-agnostic**: the same files should be installable in [Claude Code](https://docs.claude.com/en/docs/claude-code), [Hermes](https://hermes-agent.nousresearch.com/), [Codex](https://github.com/openai/codex), and other agentic CLIs that load markdown-with-frontmatter skill definitions.

## Layout

```
ai-agent-marketplace/
├── .claude-plugin/marketplace.json       # Claude Code marketplace manifest
├── skills/
│   └── <skill>/                          # skill root — agentskills.io spec
│       ├── SKILL.md                      # required: frontmatter + body
│       ├── scripts/                      # optional: programmatic complexity
│       ├── references/                   # optional: detail loaded on demand
│       └── assets/                       # optional: static resources
└── README.md
```

Every skill conforms to the [Agent Skills specification](https://agentskills.io/specification): the skill is a directory containing `SKILL.md` with required frontmatter (`name`, `description`); the `name` matches the parent directory; and `scripts/` / `references/` / `assets/` colocate with `SKILL.md` and are referenced by paths relative to the skill root.

The `.claude-plugin/marketplace.json` at the repo root is Claude Code-specific scaffolding — it makes the skills discoverable by the Claude marketplace. Other frameworks (Hermes skills, Codex, etc.) ignore it and work directly off the skill directories under `skills/`.

## Skills

| Skill | Description |
|---|---|
| [github](./skills/github) | `gh`/`git` workflow patterns. Scripts: `pr_status.py` (CI snapshot/watch with token-type-aware logic), `pr_logs.py` (failed-run log extraction). |

## Installation

The right install command depends on which framework you're using **and** whether the skill has scripts. The github skill below has scripts, so the URL-only install in hermes is *not* sufficient — see the caveat there.

### Claude Code

```sh
/plugin marketplace add nishitpatel92/ai-agent-marketplace
/plugin install github@ai-agent-marketplace
```

The whole skill directory (including `scripts/`) is copied locally on install.

### Hermes Agent

**Recommended — full skill including `scripts/`:**

```sh
hermes skills install nishitpatel92/ai-agent-marketplace/skills/github
```

Hermes' GitHub source walks the directory tree and pulls every file under `skills/github/`, so scripts work.

**Limited — single-file install:**

```sh
hermes skills install \
  https://raw.githubusercontent.com/nishitpatel92/ai-agent-marketplace/main/skills/github/SKILL.md
```

> ⚠️ This URL-based path **only fetches `SKILL.md`** — Hermes' own docs say *"multi-file skills with `references/` or `scripts/` subfolders need a manifest we can't discover from a bare URL."* The skill's `gh pr checks` happy path still works, but the fine-grained-PAT fallback (which calls `python scripts/pr_status.py …`) will fail with "No such file or directory." Use the GitHub-source install above unless you specifically need a single-file copy.

### Codex / others

Drop the `SKILL.md` content where the framework expects skill or `AGENTS.md`-style instructions. For multi-file skills with `scripts/`, also clone the relevant skill directory and adjust paths so the agent can resolve `scripts/<name>.py` correctly.

## Skill style — thin SKILL, scripts do plumbing

In addition to the spec, this repo enforces one editorial rule:

> **The skill teaches the agent *what* and *why*. Anything programmatic — multi-step API logic, polling, parsing, archive extraction — lives in `scripts/`.**

Why: skill text is loaded into the agent's context every time it activates. Long curl pipelines, jq incantations, and watch loops bloat the context for no benefit — the agent never improves them, just reads and re-emits them. Pushing them into Python keeps the skill compact and lets a script encapsulate edge cases (token-type fallback, error handling, retry policy) without the agent re-deriving them each turn. (This aligns with the spec's "progressive disclosure" guidance: keep `SKILL.md` itself small; defer detail to scripts and `references/`.)

Concrete rules:

1. **`SKILL.md` is intent-first.** Sections describe decisions, conventions, and pitfalls. Commands shown should be one-liners or simple chains the agent can adapt mid-task.
2. **Scripts are stdlib-only Python by default** (no `pip install` step in fresh sandboxes). Shell or other tools when there's a clear win.
3. **Scripts are referenced via paths relative to the skill root** (e.g. `scripts/pr_status.py`), per the spec.
4. **Scripts read auth from env** — `GITHUB_TOKEN`, etc. — and document required permissions in their docstring.
5. **Scripts have machine-friendly output** (`--json`) and **standard exit codes**. The agent should be able to chain them.
6. **The skill's frontmatter `description`** is the activation hook — make it precise. The model uses it to decide when to load this skill.
7. **Declare `compatibility`** in the frontmatter when the skill needs specific tooling (`gh`, `jq`, Python version, network access, etc.).
8. **The skill's happy path should not require scripts.** Scripts are for fallback / advanced cases. That way a single-file install (e.g. Hermes URL install) still gets useful behavior.

If you find yourself pasting >5 lines of curl/jq/loop into a SKILL, that's a script.

## Contributing

PRs welcome. Bar for adding a skill:

1. Solves a real, recurring agent task.
2. Conforms to https://agentskills.io/specification (validate with `skills-ref validate ./skills/<name>` if you have it installed).
3. Frontmatter `description` is a precise activation hook.
4. Programmatic complexity is in `scripts/`, not in the SKILL.
5. Skill works (degraded but useful) even when only `SKILL.md` is available, for compatibility with single-file installers.

## License

MIT (see `LICENSE` once added).
