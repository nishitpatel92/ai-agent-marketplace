# ai-agent-marketplace

A growing collection of plugins, skills, and agent definitions intended to be **framework-agnostic**: the same files should be installable in [Claude Code](https://docs.claude.com/en/docs/claude-code), [Hermes](https://hermes-agent.nousresearch.com/), [Codex](https://github.com/openai/codex), and other agentic CLIs that load markdown-with-frontmatter skill definitions.

## Layout

```
ai-agent-marketplace/
├── .claude-plugin/marketplace.json       # Claude Code marketplace manifest
├── plugins/
│   └── <plugin>/
│       ├── .claude-plugin/plugin.json    # plugin manifest (Claude Code)
│       ├── README.md                     # human-readable plugin docs
│       ├── scripts/                      # programmatic complexity lives here
│       └── skills/<skill>/SKILL.md       # what the agent loads
└── README.md
```

## Skill style — thin SKILL, scripts do plumbing

The bar for every plugin in this repo:

> **The skill teaches the agent *what* and *why*. Anything programmatic — multi-step API logic, polling, parsing, archive extraction — lives in `scripts/`.**

Why: skill text is loaded into the agent's context every time it activates. Long curl pipelines, jq incantations, and watch loops bloat the context for no benefit — the agent never improves them, just reads and re-emits them. Pushing them into Python keeps the skill compact and lets a script encapsulate edge cases (token-type fallback, error handling, retry policy) without the agent re-deriving them each turn.

Concrete rules:

1. **`SKILL.md` is intent-first.** Sections describe decisions, conventions, and pitfalls. Commands shown should be one-liners or simple chains the agent can adapt mid-task.
2. **Scripts are stdlib-only Python by default** (no `pip install` step in fresh sandboxes). Shell or other tools when there's a clear win.
3. **Scripts are referenced as `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.<ext>`** in the SKILL.md. For non-Claude frameworks, users adapt the path.
4. **Scripts read auth from env** — `GITHUB_TOKEN`, etc. — and document required permissions in their docstring.
5. **Scripts have machine-friendly output** (`--json`) and **standard exit codes**. The agent should be able to chain them.
6. **The skill's frontmatter `description`** is the activation hook — make it precise. The model uses it to decide when to load this skill.

If you find yourself pasting >5 lines of curl/jq/loop into a SKILL, that's a script.

## Plugins

| Plugin | Description |
|---|---|
| [github](./plugins/github) | `gh`/`git` workflow patterns. Scripts: `pr_status.py` (CI snapshot/watch with token-type-aware fallback), `pr_logs.py` (failed-run log extraction). |

## Installation

### Claude Code

```sh
/plugin marketplace add nishitpatel92/ai-agent-marketplace
/plugin install github@ai-agent-marketplace
```

### Hermes Agent

```sh
hermes skills install \
  https://raw.githubusercontent.com/nishitpatel92/ai-agent-marketplace/main/plugins/github/skills/github/SKILL.md
```

(Or clone and copy `plugins/<plugin>/skills/<skill>/` into `~/.hermes/skills/`. For framework-agnostic skills that depend on bundled scripts, also copy the plugin's `scripts/` dir to a known path and point `${CLAUDE_PLUGIN_ROOT}` at the plugin root.)

### Codex / others

Drop the `SKILL.md` content where the framework expects skill or AGENTS.md instructions. Adjust script paths.

## Contributing

PRs welcome. Bar for adding a plugin:

1. Solves a real, recurring agent task.
2. Skill teaches *patterns*, not framework-specific details.
3. Frontmatter `description` is a precise activation hook.
4. Programmatic complexity is in `scripts/`, not in the SKILL.

## License

MIT (see `LICENSE` once added).
