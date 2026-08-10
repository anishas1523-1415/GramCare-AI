# E2E smoke suite

Login → dashboard → one core action, for Patient, Doctor, and Hospital. Exists
because the real bugs found in this app during manual testing — silent 403s,
missing profile pages, a role missing from the registration dropdown — were
never reachable by the backend's pytest suite, since none of them were API
bugs. They were "the frontend never calls the endpoint, or mishandles the
response" bugs, which only a real browser driving a real login flow can catch.

## Running locally

1. Start the backend against a real (SQLite or Postgres) database with
   migrations applied:
   ```
   cd apps/backend_service
   alembic upgrade head
   uvicorn main:app --port 8000
   ```
2. Seed the fixed test accounts (idempotent — safe to re-run):
   ```
   cd apps/backend_service
   python scripts/seed_e2e_users.py
   ```
3. From `apps/web_portal`, with `NEXT_PUBLIC_API_URL` pointed at that backend:
   ```
   npm run test:e2e
   ```
   Playwright builds and starts `web_portal` itself (see `playwright.config.ts`)
   and reuses an already-running dev server if you have one on port 3000.

## What this suite is not

Not a replacement for the backend's pytest suite (business logic, auth
edge cases, data integrity) or for manually testing anything visual/animated.
It's specifically the "does the button that's supposed to be there exist,
and does clicking it not blow up" layer.
