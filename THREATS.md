# THREATS.md

Status: **Closed** = fixed and tested. **Partly** = reduced, a gap remains. **Accepted** = knowingly left, reason given.

## A. Access to documents

| # | Threat | What I did | Status | Test |
|---|--------|-----------|--------|------|
| A1 | Guessing document IDs (IDOR) | Every document endpoint (download, edit, delete, share, revoke) goes through one function, `get_doc_or_404`, which calls `can_access`. "Not found" and "not allowed" both return the same 404, so existence is not leaked. | Closed | test_unshared_viewer_cannot_read_edit_delete_share, test_nonexistent_and_forbidden_look_the_same |
| A2 | "The button is hidden" protection | No client-side checks at all. The server decides on every request. | Closed | all of the above |
| A3 | One owner reaching another owner's files | Ownership is checked by `owner_id`, not by role. | Closed | test_other_owner_cannot_reach_my_document |
| A4 | Admin reading document contents | Admin has no implicit document access. Admin sees activity through the audit log only. | Closed | test_admin_cannot_read_document_content |
| A5 | Search and list leaking other people's files | List and search are filtered in SQL to documents the user owns or holds an active grant for. The q, owner, category and date filters only narrow that set. | Closed | test_list_and_search_hide_unshared_documents |
| A6 | A "read" grant growing into edit, delete or share | Delete and share are owner-only. Edit needs an "edit" grant. | Closed | test_read_grant_allows_read_but_not_edit_delete_share, test_edit_grant_allows_edit_but_not_delete |
| A7 | Revoked user keeps working with a token issued earlier | Permissions are read from the database on every request, never stored in the token. Revoke sets `revoked_at` and the next request fails. | Closed | test_revoke_stops_an_already_issued_token |
| A8 | Deleted document still reachable | Soft delete. `can_access` refuses deleted documents even for people who were granted access. | Closed for access. The file stays on disk (see E3) | test_deleted_document_is_unreachable_even_when_shared |
| A9 | Unauthenticated access | All document and admin routes need a valid bearer token. | Closed | test_no_token_is_rejected |
| A10 | A demoted owner keeps their own files | Ownership belongs to the document, not the role label. If an owner is changed to viewer, they can still manage documents they uploaded. I found this myself and left it: there is no ownership transfer feature. The role change is audited. | Accepted | none |
| A11 | Revoke racing an in-flight download | Access is checked once, then the file is streamed. A download that already started can finish. | Accepted (tiny window, small files) | none |

## B. Identity and sessions

| # | Threat | What I did | Status | Test |
|---|--------|-----------|--------|------|
| B1 | User makes themselves admin at signup | Signup ignores any role in the request. Role is always "viewer". Only an admin can change roles. | Closed | test_signup_cannot_choose_a_role |
| B2 | Non-admin calling admin endpoints | `require_role("admin")` on every admin route. Uploading needs the owner role. | Closed | test_viewer_cannot_upload_or_use_admin_endpoints |
| B3 | Forged tokens | Algorithm is pinned to HS256 on decode. In production the app refuses to start without `SECRET_KEY`. No test for the algorithm pinning (checked by reading the code). | Closed | none |
| B4 | Old token after a privilege change | Each user has `token_version`. A role change bumps it and old tokens stop working. | Closed | test_role_change_kills_old_tokens |
| B5 | Stolen token | Tokens last 15 minutes. There is no logout or "sign out everywhere" endpoint, so a stolen token works until it expires. | Partly | none |
| B6 | Password guessing | **No rate limiting or lockout.** Passwords are bcrypt-hashed (8 to 64 characters). I ran out of time. Next step: per-IP and per-account limits. | Accepted (known gap) | none |
| B7 | Finding out which emails exist | Login and signup give generic messages. But the share endpoint says "Invalid user" for an unknown email, and login is slightly faster for unknown emails. | Partly | none |
| B8 | Seed credentials are public | They are in the README so reviewers can log in. A real deployment must not seed them. | Accepted | none |

## C. Uploads

| # | Threat | What I did | Status | Test |
|---|--------|-----------|--------|------|
| C1 | Path traversal in the file name | The name is reduced to its base name for display. The file on disk has a random UUID name, so user input is never part of a path. | Closed | test_path_traversal_filename_is_neutralised |
| C2 | Script-bearing or executable uploads (html, svg, exe) | Extension allowlist (pdf, png, jpg, txt). Downloads are sent as `application/octet-stream` with `nosniff`, so the browser never renders them. | Closed | test_bad_file_types_are_rejected |
| C3 | Fake extension (text renamed to .pdf) | Magic-byte check per type. | Closed | test_bad_file_types_are_rejected |
| C4 | Huge uploads | 5 MB cap and a bounded read. No per-user quota, so one owner could fill the disk with many files. | Partly | test_too_large_file_is_rejected |
| C5 | Malware inside a valid PDF or image | No virus scanning. | Accepted | none |

## D. Audit trail

| # | Threat | What I did | Status | Test |
|---|--------|-----------|--------|------|
| D1 | Editing or deleting audit rows through the app | No endpoint exists that changes or deletes audit rows. | Closed | none (absence of a route, checked in /docs) |
| D2 | Editing rows directly in the database | Each row's hash covers the previous hash and is an HMAC keyed with a server secret. `/admin/audit/verify` finds the first broken row. Rebuilding the chain with plain SHA-256 is detected. | Partly (see D3, D4) | test_audit_chain_detects_tampering, test_audit_chain_cannot_be_rebuilt_without_the_key |
| D3 | Attacker who has the database AND the secret key | They can forge a valid chain. Also, deleting the newest rows cannot be detected from inside the chain. A fix would be publishing the latest hash somewhere outside the server on a schedule. | Accepted | none |
| D4 | Database-level "insert only" | SQLite has no database users or permissions, so the app cannot run with an insert-only account. With Postgres I would do this. | Accepted | none |
| D5 | Missing events | Uploads, downloads, edits, deletes, grants, revokes, role changes and **refused** attempts are logged. | Closed | test_denied_attempts_are_recorded, test_grant_and_revoke_are_recorded, test_role_change_is_audited |
| D6 | Failed logins and requests with no token | **Not logged.** For an investigation this is a gap. | Accepted (known gap) | none |
| D7 | Action succeeds but the log write fails or the process dies in between | The log is written after the action, so a crash in between leaves an action with no record. | Accepted | none |
| D8 | Two simultaneous requests forking the chain | Log writes are serialised with a lock. This only protects one process. With several workers it would need a database lock. I run one worker. | Partly | none |

## E. Platform

| # | Threat | What I did | Status | Test |
|---|--------|-----------|--------|------|
| E1 | SQL injection | All queries use the SQLAlchemy ORM with bound parameters. | Closed | none |
| E2 | Traffic interception | TLS is provided by the host. The app adds no HSTS or other security headers. | Partly | none |
| E3 | Files at rest | Not encrypted. Deleted documents stay on disk (soft delete). Anyone with disk access can read them. | Accepted | none |
| E4 | /docs visible on the live site | Left on because it is the API documentation the brief asks for. | Accepted | none |
| E5 | Data lost on redeploy | Free hosting disks can be wiped. An availability problem, not a confidentiality one. | Accepted | none |

## Not built, on purpose
A frontend (Swagger UI is the interface), sharing with people outside the company, file versions, restore after delete, retention rules, groups and folders (permissions are per document), MFA, password reset, AI sharing suggestions. I spent the two days on making the permission check and the audit trail hold.