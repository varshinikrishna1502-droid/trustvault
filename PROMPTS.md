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
**Wrong:** The brief lists permission changes as audit events, and a role change is one. The AI's code did not log it. The AI pointed this out itself when I asked what else was missing after the tests passed. I had not noticed.
**Did instead:** Added a `role_change` log line and the test `test_role_change_is_audited`, then ran the suite. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e

## Entry 3 - 2026-11-06 - Authentication: hard-coded fallback secret
**Asked:** Login and token code.
**Produced:** `SECRET = os.environ.get("SECRET_KEY", "change-me-before-deploying")`.
**Wrong:** If the variable is not set on the server, anyone reading the public repo could forge tokens for any user, admin included. pytest warned that the key was only 26 bytes. I pasted that warning into the chat and asked if it mattered. The AI explained that it came from this fallback.
**Did instead:** In production the app now refuses to start without `SECRET_KEY`. I set a long random key on Render. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e

## Entry 4 - 2026-11-06 - Audit trail: chain could be rebuilt and could fork
**Asked:** A tamper-evident audit log.
**Produced:** A SHA-256 chain that reads the last row and inserts the next one.
**Wrong:** With plain SHA-256, anyone who can write to the database can recompute the whole chain, so tampering would go unnoticed. Two simultaneous requests could also fork the chain. This came up when I asked the AI to help me write an honest THREATS.md and it reviewed its own design. I did not spot it myself.
**Did instead:** Keyed HMAC, a write lock, and a test that rebuilds the chain with plain SHA-256 and expects verification to fail. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/a8588e5

## Entry 5 - 2026-11-06 - A database and cache files went onto a public repo
**Asked:** How to commit and push.
**Produced:** Steps where `trustvault.db` and `__pycache__` were committed in the first commit, before `.gitignore` was working.
**Wrong:** A database containing user password hashes was on a public repository. I sent the AI a screenshot of the GitHub file list and asked if it looked right. It spotted the two files.
**Did instead:** `git rm --cached` for both files, and rewrote `.gitignore` (it had an encoding problem on Windows). Commits: https://github.com/varshinikrishna1502-droid/trustvault/commit/ad8c9ba and https://github.com/varshinikrishna1502-droid/trustvault/commit/1bd9e34

## Entry 6 - 2026-11-06 - Do my tests actually test anything?
**Asked:** A pytest suite (20 tests).
**Check I did:** I replaced the authorisation call in the download endpoint with a plain `db.get(Document, doc_id)` and re-ran the suite. 7 tests failed, 13 passed. So the tests do depend on the check.
**Then the AI's instruction went wrong:** It told me to put the line back but did not say the same line existed in two places. I edited the wrong one, so `get_doc_or_404` called itself. I ran the suite again and got a RecursionError and 10 failures. I pasted the output into the chat and the AI explained which line was wrong.
**Did instead:** Restored the check in the right place. All tests pass again. Commit: https://github.com/varshinikrishna1502-droid/trustvault/commit/608d13e