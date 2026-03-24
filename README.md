# Quarkus Development Skills

> **Note**: This is a work in progress. Skill names and functionality will change as we iterate on them. The initial set is more to give ideas of what could be possible.

Coding agent skills to use for developing on Quarkus itself NOT Quarkus users, see quarkusio/skills repo for those. These are intended to "standard" skills and thus works with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Codex](https://github.com/pchaganti/bx-step-agent), and other AI coding assistants supporting the [skills](https://agentskills.io/home) format.


## Quick Start

**Install all skills:**
```bash
npx skills install github:quarkusio/quarkusdev-skills
```

**Or install individual skills:**
```bash
npx skills install github:quarkusio/quarkusdev-skills/skills/java-decompile
npx skills install github:quarkusio/quarkusdev-skills/skills/java-classpath-search
npx skills install github:quarkusio/quarkusdev-skills/skills/git-diff-browser
# ... etc
```

**Install dependencies:**
```bash
# Required for java-decompile
curl -Ls https://sh.jbang.dev | bash -s - app setup

# Required for git-diff-browser
npm install -g diff2html-cli
```

**Setup cache directory:**
```bash
mkdir -p ~/.cache/quarkusdev-skills
```

See [Platform Setup](#platform-setup) for other platforms (Gemini CLI, Codex).

## Skills

| Skill | Description | Platforms |
|-------|-------------|-----------|
| `java-decompile` | Decompile Java classes from Maven dependencies using Vineflower. View library source code, method signatures, and implementation details. | All |
| `java-classpath-search` | Search for Java classes across all Maven JARs. Find which dependency provides a class, detect version conflicts. | All |
| `quarkus-full-build` | Run a full build of the Quarkus project via a subagent. Optimized with parallel compilation and test skipping. | All |
| `quarkus-module-build` | Build specific Quarkus modules in parallel via subagents. Fast iteration on individual extensions. | All |
| `git-diff-browser` | Rich, syntax-highlighted git diffs in browser. Supports unstaged, staged, branch comparisons, and live watch mode. | All |

## Platform Setup

### Claude Code

Claude Code uses the skills format natively.

#### Option 1: Install with npx (Recommended)

**Install all skills:**
```bash
npx skills install github:quarkusio/quarkusdev-skills
```

**Install individual skills:**
```bash
# Java decompiler
npx skills install github:quarkusio/quarkusdev-skills/skills/java-decompile

# Classpath search
npx skills install github:quarkusio/quarkusdev-skills/skills/java-classpath-search

# Quarkus full build
npx skills install github:quarkusio/quarkusdev-skills/skills/quarkus-full-build

# Quarkus module build
npx skills install github:quarkusio/quarkusdev-skills/skills/quarkus-module-build

# Git diff browser
npx skills install github:quarkusio/quarkusdev-skills/skills/git-diff-browser
```

**Post-installation:**
```bash
# Install diff2html (required for git-diff-browser)
npm install -g diff2html-cli

# Create cache directory for generated artifacts
mkdir -p ~/.cache/quarkusdev-skills
```

**Managing skills:**
```bash
# List installed skills
npx skills list

# Update all skills from this repo
npx skills update quarkusio-quarkusdev-skills

# Uninstall all skills
npx skills uninstall quarkusio-quarkusdev-skills

# Uninstall individual skill
npx skills uninstall java-decompile
```

#### Option 2: Manual Installation

**1. Clone this repo:**
```bash
git clone https://github.com/quarkusio/quarkusdev-skills.git ~/.claude/skills/quarkus
```

**2. Setup cache directory:**
```bash
# Create cache directory for generated artifacts
mkdir -p ~/.cache/quarkusdev-skills
```

**3. Add natural language triggers (optional):**

Append the included `CLAUDE.md` to your project's `CLAUDE.md`:
```bash
cat ~/.claude/skills/quarkus/CLAUDE.md >> /path/to/your/project/CLAUDE.md
```

**4. Install diff2html (required for git-diff-browser):**
```bash
npm install -g diff2html-cli
```

#### Usage

```
> Use the java-decompile skill to decompile ObjectMapper
> /quarkus-full-build
> Show me a diff in the browser
```

Skills auto-discover from `~/.claude/skills/` and your project's `skills/` directory.

## Skill Details

### java-decompile

Decompile Java classes from project dependencies to view source code.

**Features:**
- Uses Vineflower decompiler via jbang (auto-downloads on first use)
- Supports fully qualified or simple class names
- Falls back to javap if jbang unavailable
- Searches Maven local repo and project build output

**Example:**
```
> Decompile com.fasterxml.jackson.databind.ObjectMapper
> What does the RestClient class do?
```

### java-classpath-search

Find which JAR contains a Java class.

**Features:**
- Pre-built index for instant search (<1 second)
- Auto-rebuilds index if older than 7 days
- Detects version conflicts
- Extracts Maven coordinates from JAR paths

**Example:**
```
> Which JAR has ObjectMapper?
> Find all JARs containing GraphQLService
```

### quarkus-full-build

Run a complete Quarkus build with optimized flags.

**Features:**
- Parallel compilation (16 threads per core)
- Skips tests and non-essential checks
- Runs in subagent to keep main conversation responsive
- Typical build time: 5-15 minutes

**Example:**
```
> Do a full build
> Rebuild everything
```

### quarkus-module-build

Build specific Quarkus modules in parallel.

**Features:**
- Accepts multiple modules (e.g., "graphql and openapi")
- Builds in parallel via subagents
- Auto-finds module paths in Quarkus structure
- Reports per-module success/failure

**Example:**
```
> Build the graphql module
> Compile openapi and rest
```

### git-diff-browser

Display rich git diffs in your browser.

**Features:**
- Syntax highlighting via diff2html
- Collapsible file tree sidebar
- Live watch mode (auto-refresh every 2s)
- Optional AI-generated summaries
- Supports unstaged, staged, branch comparisons, commit ranges

**Example:**
```
> Show me the diff
> Compare to main branch
> Watch the diff (live mode)
```

## Dependencies

**Required:**
- Java 8+ (for decompilation and builds)
- Maven 3+ (for builds and classpath)
- Git (for diff viewing)
- Python 3 (for diff-view.py)
- jbang (for java-decompile) - Install: `curl -Ls https://sh.jbang.dev | bash -s - app setup`

**Optional:**
- `diff2html-cli` (npm install -g diff2html-cli) - Required for git-diff-browser

## Publishing & Metadata

This repository includes metadata for the Claude Code plugin marketplace:

### .claude-plugin/marketplace.json

Describes this skill package for Claude Code plugin marketplaces. Contains:
- Package metadata (name, version, description)
- All 5 skills with their descriptions and paths
- Tool definitions and dependencies
- Installation instructions
- Platform support information

**Location:** `.claude-plugin/marketplace.json` (follows Claude Code plugin convention)

**Usage:** The `npx skills` CLI reads this file to enable one-click installation and display package information in plugin marketplaces.

## Contributing

Contributions welcome! These skills are designed to be platform-agnostic.

**Adding a new skill:**

1. Create `skills/<skill-name>/SKILL.md` following the format
2. Add YAML frontmatter with `name` and `description`
3. Use platform-agnostic tool references
4. Test on at least 2 platforms
5. Update this README
6. Add skill entry to `.claude-plugin/marketplace.json`

## License

Apache 2.0 - See LICENSE file

## Links

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- [Codex](https://github.com/pchaganti/bx-step-agent)
- [Quarkus](https://quarkus.io)
- [CFR Decompiler](https://github.com/leibnitz27/cfr)
- [diff2html](https://github.com/rtfpessoa/diff2html)
