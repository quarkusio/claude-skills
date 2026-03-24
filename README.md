# Claude Skills

Shared [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for Java/Quarkus development.

## Skills

| Skill | Description |
|-------|-------------|
| `/decompile <ClassName>` | Decompile a Java class from Maven dependencies using CFR. Accepts fully qualified or simple class names. |
| `/classpath-search <ClassName>` | Search for a Java class across all Maven JARs. Finds which dependency provides a class, flags version conflicts. |
| `/full-quarkus-build` | Run a full build of the Quarkus project via a subagent. Also triggers from natural language like "do a full build". |
| `/module-build <modules>` | Build one or more Quarkus modules in parallel via subagents. e.g. `/module-build graphql and openapi`. |
| `/diff [args]` | Instantly open a rich, syntax-highlighted git diff in the browser with a collapsible sidebar file tree. Supports unstaged, staged, branch comparisons, commit ranges, and live watch mode. Requires `diff2html-cli` (`npm i -g diff2html-cli`). |

## Setup

### 1. Clone this repo

```bash
git clone https://github.com/quarkusio/claude-skills.git ~/.claude/claude-skills
```

### 2. Symlink the commands and tools

```bash
# Create directories if needed
mkdir -p ~/.claude/commands ~/.claude/tools

# Symlink skills
ln -sf ~/.claude/claude-skills/commands/*.md ~/.claude/commands/

# Symlink tools
ln -sf ~/.claude/claude-skills/tools/* ~/.claude/tools/
chmod +x ~/.claude/tools/build-class-index.sh
```

### 3. Add natural language triggers (optional)

Append the included `CLAUDE.md` to your project's `CLAUDE.md` so that skills trigger automatically from natural language prompts (e.g. "do a full build", "build graphql and openapi"):

```bash
cat ~/.claude/claude-skills/CLAUDE.md >> /path/to/your/project/CLAUDE.md
```

### 4. Use them

```
> /decompile com.fasterxml.jackson.databind.ObjectMapper
> /classpath-search ObjectMapper
> /full-quarkus-build
> /module-build graphql and openapi
> /diff                      # instant unstaged changes
> /diff staged               # staged changes
> /diff branch main          # compare current branch to main
> /diff commit HEAD~3        # last 3 commits
> /diff watch                # live-updating diff (auto-refreshes every 2s)
> /diff watch branch main    # live-updating branch comparison
> build the graphql module   # works if step 3 was done
```

The class index is built automatically on first use and rebuilt if older than 7 days. CFR decompiler is downloaded automatically on first use. Build skills use subagents so your main conversation stays responsive during long builds. The diff skill requires `diff2html-cli` (`npm i -g diff2html-cli`).
