---
description: Show a rich, syntax-highlighted git diff in the browser. Use when the user wants to view changes, review a diff, compare branches, or see what changed in recent commits. Supports unstaged changes, staged changes, branch comparisons, and commit ranges. Also supports watch mode for live-updating diffs.
---

Show a rich, syntax-highlighted git diff in the browser for: $ARGUMENTS

## Instructions

### Fast mode (default)

For instant results, run the all-in-one script directly. No need to read files or generate JSON — the script handles everything (git diff, diff2html, sidebar enrichment, browser open).

| User says | Command |
|---|---|
| *(empty / no args)* | `python3 ~/.claude/tools/diff-view.py` |
| `staged` | `python3 ~/.claude/tools/diff-view.py --staged` |
| `branch <name>` | `python3 ~/.claude/tools/diff-view.py --branch <name>` |
| `commit HEAD~N` | `python3 ~/.claude/tools/diff-view.py --commit HEAD~N` |
| `commit <sha>` | `python3 ~/.claude/tools/diff-view.py --commit <sha>` |
| `watch` | `python3 ~/.claude/tools/diff-view.py --watch` |
| `watch branch main` | `python3 ~/.claude/tools/diff-view.py --watch --branch main` |
| `watch staged` | `python3 ~/.claude/tools/diff-view.py --watch --staged` |

The sidebar will show a mechanical summary (file count and total changes). This is instant.

### Watch mode

When the user says `watch`, `/diff watch`, or asks for a live diff:

1. Start the watch server in the background:
```bash
python3 ~/.claude/tools/diff-view.py --watch [args] &
```

2. The script prints the server URL and PID. Note the URL (e.g. `http://127.0.0.1:12345`).

3. The page updates in-place via DOM patching (no full reload, scroll preserved).

4. The server auto-stops when the Claude session exits.

5. After starting the watch server, spawn a subagent to generate the AI summary asynchronously:
   - The subagent should read the diff (`git diff` with appropriate args)
   - Write a concise 2-4 sentence summary explaining the intent of the changes
   - POST it to the server: `curl -s -X POST http://127.0.0.1:<port>/api/summary -H 'Content-Type: application/json' -d '{"summary":"<the summary>"}'`
   - The summary will appear in the sidebar without a page reload, replacing the "Generating summary..." placeholder

### AI summary for non-watch mode

For static diffs, add the `--summary` flag:

1. Run `git diff` (with appropriate args) and read the output
2. Write a concise 2-4 sentence summary explaining the intent of the changes
3. Pass it to the script:
```bash
python3 ~/.claude/tools/diff-view.py --summary "Your AI summary here" [other args]
```

### Examples

- `/diff` — instant unstaged changes
- `/diff staged` — instant staged changes
- `/diff branch main` — compare current branch to main
- `/diff commit HEAD~3` — last 3 commits
- `/diff watch` — live-updating unstaged diff with async AI summary
- `/diff watch branch main` — live-updating branch comparison
