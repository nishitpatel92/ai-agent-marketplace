# ai-agent-marketplace

A growing collection of plugins, skills, and agent definitions intended to be **framework-agnostic**: the same files should be installable in [Claude Code](https://docs.claude.com/en/docs/claude-code), [Hermes](https://hermes-agent.nousresearch.com/), [Codex](https://github.com/openai/codex), and other agentic CLIs that load markdown-with-frontmatter skill definitions.

## What's here

```
ai-agent-marketplace/
├── .claude-plugin/
│   └── marketplace.json          # Claude Code marketplace manifest
├── plugins/
│   └── github/                    # plugin: GitHub workflow patterns
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── README.md
│       └── skills/
│           └── github/
│               └── SKILL.md       # the skill the agent loads
└── README.md
```

Skills are written as standalone markdown files with YAML frontmatter (`name`, `description`). That same file is what Claude Code loads from `skills/<name>/SKILL.md`, what Hermes loads from `~/.hermes/skills/<name>/SKILL.md`, and what most other "agent skill" systems consume. The marketplace and plugin manifests in `.claude-plugin/` are Claude-specific scaffolding around those shared skill files.

## Plugins

| Plugin | Description |
|---|---|
| [github](./plugins/github) | Cloning, branching, PRs, CI checks, code review, merging — `gh` CLI + `git` best practices. |

## Installation

### Claude Code

Add this repo as a marketplace, then install plugins from it:

```sh
/plugin marketplace add nishitpatel92/ai-agent-marketplace
/plugin install github@ai-agent-marketplace
```

### Hermes Agent

Hermes installs skills from URLs to individual `SKILL.md` files. To install a skill from this repo:

```sh
hermes skills install \
  https://raw.githubusercontent.com/nishitpatel92/ai-agent-marketplace/main/plugins/github/skills/github/SKILL.md
```

(Or clone the repo and copy `plugins/<plugin>/skills/<skill>/` into `~/.hermes/skills/`.)

### Codex / others

Most agentic CLIs accept a markdown file with a `description` frontmatter field as a "skill" or "AGENTS.md"-style instruction. Drop the relevant `SKILL.md` content into the framework's known location.

## Contributing

PRs welcome. The bar for adding a plugin:

1. The skill helps with a real, recurring agent task.
2. The skill is written so it works whether or not the host framework gives the agent extra tools — it teaches *patterns*, not framework specifics.
3. The frontmatter `description` is a precise hook so agents know when to load it.

## License

MIT (see `LICENSE` once added).
