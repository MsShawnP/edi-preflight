---
description: Append a dated entry to HANDOFF.md and commit as a save point
---

Append an entry to HANDOFF.md in the project root, then commit all
changed files as a save point.

> **Secret redaction (non-negotiable).** Never write a populated
> `DATABASE_URL`, connection string, password, token, or API key into
> HANDOFF.md or the commit message. If a connection string carries an
> embedded `user:password@` credential, redact it to
> `postgresql://…@host/db` (drop the `user:password@` segment) before
> writing it anywhere. This applies to the log entry AND the commit
> message.

## Step 1: Append the log entry

Format:

## YYYY-MM-DD HH:MM

**What changed:** [one line]

**Why:** [one or two lines]

**State:** [what's working, what's broken, what's untouched]

**Next:** [the immediate next action — not a vague goal]

---

Rules for the entry:
- Use the actual current date and time, not a placeholder.
- Append to the bottom of the file. Do not rewrite earlier entries.
- If HANDOFF.md does not exist, create it with a top-level heading
  "# [Project name] — Handoff Log" and then append the first entry.
- Keep each field to the lengths above. If a field needs more space,
  it belongs in DECISIONS.md instead.
- Do not summarize the conversation. Log the change.
- Never paste a populated connection string or password into the entry.
  Redact credentials to `postgresql://…@host/db` (see banner above).

Argument: $ARGUMENTS
- If $ARGUMENTS is empty, infer the entry from the most recent work
  in this session.
- If $ARGUMENTS is provided, treat it as the "What changed" line and
  fill in the rest.

## Step 2: Commit

After the entry is written:

1. Run `git status` to see what's changed.
2. Run `git add -A` to stage all modified and new files.
3. Run `git commit -m "log: <What changed line>"` using the headline
   from the entry as the commit message.
4. Report back the commit hash and the list of files committed.

Rules for the commit:
- Do not push. Local save point only.
- If `git status` shows nothing to commit, report that and skip the
  commit step.
- If the commit fails, report the exact error and stop. Do not
  attempt to fix it automatically.
- Do not amend previous commits. Each /log is its own commit.
- The commit message headline is derived from the "What changed" line —
  if that line would contain a credential, redact it to
  `postgresql://…@host/db` first. Never put a password in the message.

## Step 3: Suggest what's next

After the commit (or skip), add a one-line suggestion based on
context:

- If the user seems to be wrapping up → "Ready to stop? Run /wrap
  to save your session state."
- If there's more work in PLAN.md → "Checkpoint saved. Next task
  in the plan: [task name]."
- If it's been a while since the last /improve → "Checkpoint saved.
  This project is due for a review — /improve audit-only when
  you're ready."
- Otherwise → "Checkpoint saved. Keep going."

Additionally, if the project has a remote and there are 5+ unpushed
commits, add: "You have [N] unpushed commits — consider pushing to
back up your work." Only mention this once per session, not on every
/log.
