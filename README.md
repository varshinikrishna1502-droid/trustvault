# TrustVault

Secure document sharing where the wrong person cannot read a file, and every access, including refused attempts, is recorded in a tamper-evident audit trail.

**Live URL:**  https://trustvault-8eso.onrender.com (API documentation and the interface are at `/docs`)

**Demo video:** https://drive.google.com/file/d/16H6a7HC-j2VQBAx2-WP0NWvQJbSO01q7/view?usp=sharing

Free hosting: the first load can take up to a minute while the server wakes up.

## Demo accounts
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@trustvault.com | Admin@12345 |
| Owner | owner@trustvault.com | Owner@12345 |
| Viewer | viewer@trustvault.com | Viewer@12345 |

How to use it: open `/docs`, call `POST /auth/login`, copy the `access_token`, click **Authorize**, paste it. Tokens last 15 minutes.

## Roles
- **Admin**: reads the audit log, verifies its integrity, changes user roles. Has no access to document contents.
- **Owner**: uploads documents, shares them (read or edit) with named users, revokes access, deletes their own documents.
- **Viewer**: sees and opens only documents explicitly shared with them. Cannot upload.

New signups are always viewers. Only an admin can change a role.

## Permission model
Per-document grants. A document is reachable only by (1) its owner, or (2) a user with an active grant (`read` or `edit`). Every document endpoint calls one function, `get_doc_or_404` (documents.py), which calls `can_access` (access.py). A forbidden document and a non-existent document both return the same 404. Permissions are read from the database on every request, so revoking works on the very next request, even for a token issued earlier. Delete and share are owner-only. Admin has no document access.

## Run locally
    python -m venv .venv
    .venv\Scripts\activate          (Windows)   or   source .venv/bin/activate
    pip install -r requirements.txt
    python -m uvicorn main:app --reload

Open http://127.0.0.1:8000/docs. Tables are created and the three demo users are seeded automatically on first start.

## Run the tests
    python -m pytest -v

The tests use a temporary database and upload folder, never the real ones.

## Deploy (Render, from a clean clone)
1. Push this repository to GitHub.
2. On render.com: New, Web Service, connect the repository.
3. Runtime: Python. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment variables: `APP_ENV=production` and `SECRET_KEY=<a long random string>`
6. Deploy. On first start the tables are created and the demo users are seeded.

## Configuration
| Variable | Purpose |
|----------|---------|
| SECRET_KEY | Signs login tokens. Required when APP_ENV=production: the app refuses to start without it. |
| APP_ENV | Set to `production` on the server. |
| AUDIT_KEY | Optional separate key for the audit hash chain. Defaults to SECRET_KEY. |
| DATABASE_URL | Defaults to `sqlite:///trustvault.db`. |
| UPLOAD_DIR | Defaults to `uploads`. |

## Database
SQLAlchemy models are in `models.py`. Tables are created on startup. Tables: `users`, `documents`, `permissions`, `audit_log`. `schema.sql` holds the same schema as SQL; `make_schema.py` regenerates it.

## API: who may call what
| Method | Path | Who |
|--------|------|-----|
| GET | / and /health | anyone |
| POST | /auth/signup | anyone (always creates a viewer) |
| POST | /auth/login | anyone |
| GET | /auth/me | any logged-in user |
| PUT | /admin/users/{user_id}/role | admin |
| POST | /documents | owner role (upload) |
| GET | /documents | any logged-in user; returns only documents they own or hold a grant for. Filters: q, category, owner, date_from, date_to |
| GET | /documents/{id}/download | document owner, or a user with a read or edit grant |
| PUT | /documents/{id} | document owner, or a user with an edit grant |
| DELETE | /documents/{id} | document owner only |
| POST | /documents/{id}/share | document owner only |
| DELETE | /documents/{id}/share/{user_id} | document owner only |
| GET | /admin/audit | admin |
| GET | /admin/audit/verify | admin |

## Audit trail
Logged: uploads, downloads, edits, deletes, grants, revokes, role changes, and refused attempts. Each row's hash is an HMAC over the previous row's hash plus its own fields, so changing or rebuilding history makes `/admin/audit/verify` report a broken chain.

## Other files
- `THREATS.md`: threats, what was done about each, what was knowingly accepted
- `PROMPTS.md`: how AI was used and where it was wrong
- `test_access.py`, `conftest.py`: automated tests
- `WRITEUP.md`: what I built, what I did not, permission model, how I used AI, what is unfinished

## Not built
Frontend (Swagger UI is used), sharing with people outside the company, versions, restore, retention, groups and folders, MFA, password reset, AI sharing suggestions. Known gaps (no login rate limiting, failed logins not logged) are listed in THREATS.md.