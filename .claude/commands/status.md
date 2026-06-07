---
description: Session-start ritual — show phase, last results, decisions, recent metrics, git state.
allowed-tools: Bash(git:*), Bash(tail:*), Read
---
Perform the TensorTile session-start ritual and give me a tight situation report.

Current repo state:
- Branch / status: !`git -C "$CLAUDE_PROJECT_DIR" status -sb 2>/dev/null | head -5`
- Recent commits: !`git -C "$CLAUDE_PROJECT_DIR" log --oneline -5 2>/dev/null`
- Last METRICS rows: !`tail -n 6 "$CLAUDE_PROJECT_DIR/METRICS.md" 2>/dev/null`

Now:
1. Read `STATUS.md` (current phase, last results, next actions) and the latest `DECISIONS.md`
   entries.
2. Summarize in ≤10 lines: **current phase**, last measured results, open risks, and the
   single proposed next action. Evidence over adjectives.
3. Note whether we are mid-phase or waiting on an operator gate. Do **not** start the next phase
   unless I have said "continue."
