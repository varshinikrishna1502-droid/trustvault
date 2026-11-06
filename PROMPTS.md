# PROMPTS.md

## What I reused across the project
- I pasted the full challenge brief at the start, then told the AI: "I only have few days. Explain step by step, simple, and give code and process I can paste and understand."
- I pasted real error text and screenshots back instead of describing them.

## Entry 1 - 2026-11-05 - Plan and design
**Asked:** I pasted the brief and asked for a plan to finish it.
**Produced:** A FastAPI + SQLite plan with one `can_access()` function, per-request permission lookup, and a hash-chained audit log. It said the audit table would be protected because "the app's database user has INSERT only".
**Wrong:** SQLite has no database users, so that protection cannot exist. It also planned 7 days when I had 2.
**Did instead:** Cut scope to the permission model and audit trail, and wrote the limitation down as THREATS.md D4. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/ae2e229

## Entry 2 - 2026-11-06 - Audit trail: role changes were not logged
**Asked:** The admin endpoint to change a user's role.
**Produced:** A working endpoint with no audit entry.
**Wrong:** The brief lists permission changes as audit events. A role change is one and it was silent. I caught it when I compared the endpoints to the requirement list.
**Did instead:** Added a `role_change` log line and the test `test_role_change_is_audited`. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e

## Entry 3 - 2026-11-06 - Authentication: hard-coded fallback secret
**Asked:** Login and token code.
**Produced:** `SECRET = os.environ.get("SECRET_KEY", "change-me-before-deploying")`.
**Wrong:** If I forgot to set the variable on the server, anyone reading my public repo could forge tokens for any user, admin included. pytest also warned that the key was only 26 bytes.
**Did instead:** In production the app now refuses to start without `SECRET_KEY`. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e

## Entry 4 - 2026-11-06 - Audit trail: chain could be rebuilt and could fork
**Asked:** A tamper-evident audit log.
**Produced:** A SHA-256 chain that reads the last row and inserts the next one.
**Wrong:** With plain SHA-256, anyone who can write to the database can recompute the whole chain. Two simultaneous requests could also read the same "last" row and fork the chain. I noticed this while writing THREATS.md.
**Did instead:** Keyed HMAC, a write lock, and a test that rebuilds the chain with plain SHA-256 and expects verification to fail. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/a8588e5

## Entry 5 - 2026-11-06 - A database and cache files went onto a public repo
**Asked:** How to commit and push.
**Produced:** An order of steps where `trustvault.db` and `__pycache__` were committed in the first commit before `.gitignore` was working.
**Wrong:** A database containing user password hashes was on a public repository. I spotted it in the GitHub file list.
**Did instead:** `git rm --cached` for both files, and rewrote `.gitignore` (it had an encoding problem on Windows). Commits: https://github.com/varshinikrishna1502-droid/trustvault/commit/ad8c9ba and https://github.com/varshinikrishna1502-droid/trustvault/commit/1bd9e34

## Entry 6 - 2026-11-06 - Do my tests actually test anything?
**Asked:** A pytest suite (20 tests).
**Check I did:** I replaced the authorisation call in the download endpoint with a plain `db.get(Document, doc_id)` and re-ran.
**Result:** 7 failed, 13 passed. Failing: unshared viewer, other owner, admin, revoke with an already-issued token, deleted document, denied attempts not logged, and a missing document crashed with a 500 instead of a 404. So the tests do depend on the check.
**Then the AI's instruction went wrong:** It told me to put the line back but did not say there were two places with that line. I changed the wrong one, so `get_doc_or_404` called itself. Result: RecursionError and 10 failures. I read the stack trace, saw the function calling itself, and fixed it by hand.
**Did instead:** Restored the check in the right place. All tests pass again. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e