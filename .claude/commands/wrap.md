---
description: End-of-session wrap. Structured summary, updates HANDOFF/FAILURES/DECISIONS, commits with full journal in commit body.
---

End-of-session protocol. Do these in order. Do not skip steps.

> **Secret redaction (non-negotiable, applies to every step).** Never
> write a populated `DATABASE_URL`, connection string, password, token,
> or API key into HANDOFF.md, FAILURES.md, DECISIONS.md, or the commit
> message body. If a connection string with an embedded `user:password@`
> credential appears in the session, redact it to `postgresql://…@host/db`
> (drop the `user:password@` segment) before it goes into any of those
> files or the commit. This includes the full session summary embedded
> in the commit body at Step 6 — redact it there too.

## Step 1: Session summary

Before writing anything to files, produce a structured summary of
this session. Show it to the user for review.

Format:

---
**Session summary — [date, time]**

**Starting point:** Where we began this session. One or two lines.
Pull from the previous HANDOFF.md entry if available.

**What we did:** The work performed this session. Specific, not
"worked on the report." Use bullets if multiple distinct things.

**What worked:** Approaches that succeeded. Why they worked, if
non-obvious.

**What didn't work:** Approaches tried that failed or were abandoned.
Why. What was tried instead. Even small failures count — they're the
highest-value capture.

**Surprises:** Anything unexpected. Code behaving differently than
predicted, results that didn't match assumptions, edge cases
discovered. This is where future-you finds intuition.

**State now:** What's working, what's broken, what's untouched.
Concrete, not vague.

**Tomorrow's starting point:** What the next session should pick up.
Specific enough that fresh-Claude can act on it without asking.

**Process reflection:** One sentence — what would you do differently
about HOW you worked this session? Not what you built, but how you
built it. (e.g., "Should have branched before that refactor" or
"Spent too long on styling before the logic was solid.") Write "n/a"
if nothing comes to mind — don't force it.
---

After producing the summary, ask: "Does this summary match what
actually happened? Anything to add, remove, or correct?"

Wait for confirmation or edits before continuing.

## Step 2: Update HANDOFF.md

Append a new entry to HANDOFF.md based on the confirmed summary.
Format:

## YYYY-MM-DD HH:MM

**Started from:** [Starting point line]

**Did:** [What we did, condensed]

**State:** [State now]

**Next:** [Tomorrow's starting point]

(Keep this entry compact. The full summary is captured in the commit
message; HANDOFF.md is the at-a-glance status.)

Before saving: scan the entry for credentials and redact any to
`postgresql://…@host/db` (see banner).

## Step 3: Update FAILURES.md

For each item in "What didn't work" from the summary, ask the user:
"This failure looks worth capturing in FAILURES.md. Add it?"

If yes, append using the FAILURES.md format. Confirm tags before
saving. A failure often involves a broken connection string or auth
error — redact any credential to `postgresql://…@host/db` before
writing it to FAILURES.md. The failure detail lives in the redacted
form; the password is never the lesson.

If the user says no or skip, move on. Do not push.

## Step 4: Decision check

Review the session for any candidates for DECISIONS.md. A change is
a DECISION (not just a log entry) if any of these apply:

- It establishes a rule that should hold across future sessions
- It rejects an alternative that someone might reasonably try again
- It defines an anti-instruction
- It commits to a convention, format, or standard
- Reversing it later would require explanation

For each candidate, ask the user one at a time. Format:

> This session involved [brief description]. This looks like a
> durable decision because [reason — points to the criteria above].
>
> Add to DECISIONS.md? (yes / no / not yet)
>
> If yes, proposed entry:
>
> ### [date] — [one-line decision]
> - **Why:** [reasoning]
> - **Scope:** [what it applies to]
> - **Do not:** [anti-instruction, if applicable]

Rules:
- Ask one candidate at a time. Do not batch.
- Maximum three candidates per session.
- If the user says "not yet," note this in the HANDOFF entry and
  move on.
- If the user says "no," do not raise this candidate again unless
  the user brings it up.

## Step 5: PLAN.md update

If any tasks in PLAN.md were completed this session, mark them
complete. If the entire current arc is done, ask the user whether
to archive it and start a new arc.

## Step 6: Commit and push

After all file updates are confirmed:

1. Run `git status` to confirm what's changed.
2. Run `git add -A` to stage all modified and new files.
3. Run `git commit` with a multi-line message:

   ```
   wrap: <one-line session headline>

   <full session summary from Step 1>
   ```

   The detailed summary in the commit body means the journal is
   permanently captured in git history, searchable via
   `git log --grep=<term>`, even if HANDOFF.md gets rotated. Because it
   is permanent, redact any credential in the summary to
   `postgresql://…@host/db` BEFORE committing — a password in a commit
   body cannot be removed without rewriting history.

4. Push to remote automatically:
   - Run `git remote -v` to check if a remote exists.
   - If a remote exists, run `git push`. If on a branch that
     doesn't have an upstream yet, use `git push -u origin HEAD`.
   - If no remote exists, skip the push and tell the user:
     > "Committed locally. No remote configured — your work only
     > exists on this machine."

5. Report back the commit hash, files changed, push status, and
   the "Next" line so the user can see what's ready for tomorrow.

## Step 7: Tag suggestion (if applicable)

If this session reached a meaningful milestone (deliverable rendered,
arc completed, version ready to share), suggest a tag name.

Do not create the tag automatically. Suggest it; let the user decide.

## Rules

- Do not skip the user-confirmation step on the summary. The summary
  drives everything else.
- If the user says "skip the summary, just commit," do that — but
  HANDOFF.md still gets a minimal entry.
- Push to remote automatically after commit (handled in Step 6).
- If git operations fail, stop and report the error. Do not attempt
  to fix automatically.

## Step 8: (Removed — push is now part of Step 6)

## Step 9: Next session preview

After the commit, print a short "when you come back" note:

```
---------------------------------------------------
SESSION CLOSED

When you open Claude Code next time, I'll read your
files and pick up from: [Tomorrow's starting point]

Reminder: type / to see your commands.
  /log      — save a checkpoint while working
  /improve  — review and improve the project
  /wrap     — end a session (what you just ran)
  /commands — full command list
---------------------------------------------------
```

If the project is due for a /improve review (check the Improvement
History in PLAN.md), add: "This project is due for a review —
consider running /improve next session."
