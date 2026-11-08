# TrustVault: write-up

## What I built
A document sharing service where the server decides who can read a file on every request, and every access, including refused attempts, goes into a tamper-evident audit log. It is a FastAPI backend with SQLite (through SQLAlchemy), deployed on Render. There is a small web interface at `/ui` (plain HTML and JavaScript, no framework), and the Swagger UI at `/docs`.

It has three roles (admin, owner, viewer), upload with validation, per-document read or edit grants, revoking, search by name, owner, category and date, an admin view of the audit log, and 23 automated tests. The live URL, demo accounts and the API table (who may call what) are in README.md.

## My permission model
Every document belongs to one owner. Nobody else can reach it unless the owner gives them a grant, either read or edit, by name. There are no groups and no folder inheritance, so one grant covers exactly one document. I chose this because it is the simplest model I could fully check: for any document, the list of people who can reach it is the owner plus the rows in one table.

Every endpoint that touches a document goes through one function, which looks in the database each time. It never trusts the login token for permissions. Only the owner can delete, share or revoke. The admin can see activity and change roles, but cannot read document contents, on purpose. A document someone cannot access and a document that does not exist both return the same 404, so nobody can find out which files exist.

## How revoking works, and what it costs
Permissions are looked up in the database on every request. When an owner revokes a grant, the very next request from that person fails, even with a login token they already hold. The cost is one extra database query on every document request. I accepted that to get instant revocation. A role change also invalidates the user's old tokens.

## How the audit trail is protected
Each row stores a hash of the previous row plus its own fields, computed with a secret key (HMAC). The admin endpoint `/admin/audit/verify` recomputes the chain and reports the first broken row. Without the key, someone who edits the database cannot rebuild a chain that passes. There is no endpoint that changes or deletes audit rows. Refused attempts are logged too, not only successful ones.

## How I used AI
I used AI to write most of the code and to plan the work. PROMPTS.md lists six cases where its output was wrong, each with the commit that fixed it. Several were in access control and the audit trail: the first design relied on an "insert-only database user" that SQLite does not have, the audit chain could be rebuilt by anyone with database access, a role change was not logged, and the token secret had an unsafe default. I also checked that my tests really depend on the access check by removing it and watching tests fail. Some mistakes I found by running things myself. Others the AI pointed out when I asked it to review its own work. PROMPTS.md says which was which.

## What I deliberately did not build
A frontend framework (the `/ui` page is plain HTML and JavaScript), sharing with people outside the company, file versions, restore after delete, retention rules, groups and folders, MFA, password reset, and the AI suggestion feature for sharing. I had two days, and I spent them on the permission check and the audit trail.

## What is unfinished
- No rate limiting on login (THREATS.md B6).
- Failed logins are not written to the audit log (THREATS.md D6).
- Files are not encrypted at rest, and deleted files stay on disk (THREATS.md E3).
- Someone who has both the database and the secret key could forge the audit chain (THREATS.md D3).
- On free hosting the disk can be wiped on redeploy, and the first request after a quiet period can take up to a minute.
- The demo video has no spoken narration. Each scene is labelled with an on-screen caption.

Everything I know is weak is listed in THREATS.md, with the reason I left it.