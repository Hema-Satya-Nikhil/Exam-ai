# ExamCraft AI

[![CI](https://github.com/Hema-Satya-Nikhil/Exam-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Hema-Satya-Nikhil/Exam-ai/actions/workflows/ci.yml)

A production-oriented monorepo for generating academic question papers with deterministic backend rules, versioned blueprints, structured NVIDIA LLM integration, review workflows, and auditable exports.

## Architecture

- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui, React Hook Form, Zod, TanStack Query
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL
- Backend data access: SQLAlchemy repositories with room for MongoDB-backed document/session storage
- LLM: NVIDIA OpenAI-compatible API via a dedicated provider abstraction
- Export: deterministic PDF and DOCX generation from validated paper JSON

## Repository Layout

- `frontend/` - premium faculty UI
- `backend/` - API, services, schemas, models, validators, and document generation
- `docs/` - architecture and workflow documentation
- `docker-compose.yml` - local stack with Postgres, backend, and frontend

## Local Development

1. Copy `.env.example` to `.env` (root) and fill in secrets; copy
   `frontend/.env.example` to `frontend/.env.local` for the frontend API URL.
2. Backend (canonical environment is the repository-root `.venv`):
   `uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/`.
3. Frontend: `npm run dev` from `frontend/` (http://localhost:3000).
4. Run migrations before generating papers: `alembic upgrade head` from `backend/`.

Alternatively, start PostgreSQL, backend, and frontend with Docker via
`docker-compose.yml`.

## Browser E2E (frontend)

The Review workflow has a committed Playwright suite (`frontend/e2e/review.spec.ts`)
that drives the real UI: FINAL CHECK states, Part A / Part B rendering, the OR
divider, validation-gated export, regeneration, lock/unlock, and reload
persistence.

1. Start the backend (`uvicorn app.main:app --port 8000` from `backend/`) and
   the frontend (`npm run dev` from `frontend/`).
2. Seed one completed composite paper (runs a real generation, ~2 min):
   `npm run e2e:seed`
3. Run the suite with the printed id:
   `E2E_PAPER_ID=<id> npm run e2e`

Without `E2E_PAPER_ID` the paper-dependent specs skip with a clear message, so
`npm run e2e` is safe to run at any time. First run also needs
`npx playwright install chromium`.

## Environment Variables

Backend (root `.env`, loaded by `backend/app/core/config.py`):

- `DATABASE_URL`, `MONGODB_URI`, `MONGODB_DATABASE`
- `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`
- `SECRET_KEY`, `APP_ENV`, `MAX_UPLOAD_SIZE`
- `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `GENERATION_CONCURRENCY`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` (bootstrap admin seed only)
- `CORS_ORIGINS` (additional allowed frontend origins)
- `EMAIL_PROVIDER` (`resend` default | `brevo`) plus the matching
  `RESEND_*` or `BREVO_*` credentials
- `OTP_EXPIRE_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`,
  `RESET_TOKEN_EXPIRE_MINUTES`

Frontend (`frontend/.env.local`):

- `NEXT_PUBLIC_API_BASE_URL` — required for production builds

MongoDB is reserved for future document/session storage and can be pointed at a local or managed instance through the backend environment.
The NVIDIA API key and email provider credentials must stay in the backend environment. Do not add them to the frontend.

## Testing

- Backend: `pytest -q` from `backend/`
- Frontend: `npm test -- --ci --runInBand`, `npx tsc --noEmit`, `npx eslint .`,
  `npm run build` from `frontend/`
- Browser E2E: see the Playwright section below; CI runs all of the above on
  every push/PR to `main` (`.github/workflows/ci.yml`)

## Production Deployment

See [`docs/deployment.md`](docs/deployment.md) for the full Vercel (frontend)
+ Render (backend) + managed PostgreSQL/MongoDB guide, including environment
variables, migrations, and the pre-deployment checklist.

## Security Notes

- The NVIDIA API key never reaches the browser.
- Uploaded files are validated by MIME type, extension, and size.
- Validation happens in the backend before any paper can be approved or exported.
- Audit logs track major actions without secrets.

## Product Features

- Two-part institutional exams (Part A short answer + Part B main paper with
  explicit OR/choice groups) with atomic, checkpointed, resumable generation
- Syllabus ingestion from PDF/DOCX/images (OCR) with atomic topic extraction
  and faculty confirmation
- Deterministic blueprint + question validation (marks, units, Bloom,
  duplicates, syllabus scope) enforced by the backend
- Faculty review workspace: edit, regenerate with instructions, lock/unlock,
  final validation, and validation-gated PDF/DOCX export with audit logging
- Admin People & Access: faculty approval, admin-access requests, protected
  Main Admin, and an audit trail
- Secure forgot-password flow with hashed, expiring, attempt-limited OTPs and
  single-use reset authorization
