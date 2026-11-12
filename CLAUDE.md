# OCRDocFlow — notes for Claude

SaaS document-processing product by Qumaxa, live at
https://ocrdocflow.qumaxa.com since 2026-09-14. Users upload scanned
invoices/vouchers (PDF/JPG/PNG, ≤10 MB, ≤10 pages); the app OCRs them
(PaddleOCR, English/Arabic), extracts invoice fields with rule-based
logic (vendor, dates, line items, totals, multi-invoice per document),
and lets the team review and export. Org-based multi-tenancy, team
members, usage quotas, a no-login visitor tier, admin panel + audit log,
rate limiting, Stripe subscriptions (starter/professional/business).

## Current honest scope — keep this straight in any copy or decisions
- Billing is wired but in **Stripe test mode**: launched free/beta, not charging.
- OCR runs **synchronously** (no job queue) — not built for many concurrent users.
- Extraction is **rule-based**; no LLM document understanding yet.
- Password reset: emailed single-use link (Resend). Until `RESEND_API_KEY`
  is set on the server the link only goes to the API log (see
  `deploy/DEPLOY.md`, "Password reset email").
- `README.md` is stale and understates scope. Trust the code and
  `deploy/DEPLOY.md`.

## Layout
- `backend/` — FastAPI + SQLAlchemy + Alembic. `app/api/v1/` routes,
  `app/services/` (ocr_service, field_extractor, invoice_validator,
  language_detector, usage_service), `app/models/`, `app/schemas/`.
  Config via `backend/.env` (`DATABASE_URL`, `JWT_SECRET_KEY`, …; see
  `.env.example`). Database is **Neon** managed Postgres; schema snapshot
  in `neon_schema.sql`.
- `frontend/` — React 18 + TypeScript + Vite + Tailwind 3. Pages in
  `src/pages/` (Dashboard, Login, Register, Billing, Team, Admin, Visitor);
  API client in `src/api.ts`. Production build calls same-origin `/api/...`
  (`.env.production` sets `VITE_API_BASE_URL=`).
- `deploy/` — Dockerfile + compose for the API only. It joins the AR
  Console's `deploy_default` Docker network and is fronted by the
  Console's nginx (container name `ocrdocflow-api` is fixed; never rename
  it to `api` — it collides with the Console's service). The built
  `frontend/dist` is mounted into that nginx from `/opt/ocrdocflow`.
- Root `docker-compose.yml` is the **local dev** stack (brings up Postgres
  + API); `deploy/docker-compose.yml` is production.

## Working conventions
- Git remote: `altafhkhan/ocrdocflow`, default branch `main`.
- Never commit `backend/.env` or `frontend/.env*` with real values.
- Admin login on the live app is `altaf.khan@qumaxa.com`.
- Shared droplet, DNS and hosting facts live in
  `D:\Projects\qumaxa\CONTEXT.md` and `D:\Projects\console\deploy\DEPLOY.md`.

## Related projects
- `D:\Projects\console` — AR Automation Console (sibling product; owns the
  shared nginx/certbot setup this app rides on).
- `D:\Projects\qumaxa` — the qumaxa.com marketing site; its
  `/products/ocrdocflow` page must only describe the *current* scope above.
