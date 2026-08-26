# AI-Based Question Paper Generation System Using Bloom's Taxonomy

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

## Setup

1. Copy `.env.example` to `.env` and fill in secrets.
2. Paste the NVIDIA API key into `NVIDIA_API_KEY` in the backend environment file only.
3. Start PostgreSQL, backend, and frontend with Docker.
4. Run migrations before generating papers.

## Environment Variables

- `DATABASE_URL`
- `MONGODB_URI`
- `MONGODB_DATABASE`
- `NVIDIA_API_KEY`
- `NVIDIA_BASE_URL`
- `NVIDIA_MODEL`
- `APP_ENV`
- `SECRET_KEY`
- `MAX_UPLOAD_SIZE`
- `LLM_TIMEOUT`
- `LLM_MAX_RETRIES`

MongoDB is reserved for future document/session storage and can be pointed at a local or managed instance through the backend environment.
The NVIDIA API key must stay in the backend environment. Do not add it to the frontend.

## Security Notes

- The NVIDIA API key never reaches the browser.
- Uploaded files are validated by MIME type, extension, and size.
- Validation happens in the backend before any paper can be approved or exported.
- Audit logs track major actions without secrets.

## Current Status

The repository is scaffolded with the core project architecture, schema layer, and app shells. Next steps are to finish backend route wiring, generation workflows, validation logic, export pipelines, and tests.
The backend now also includes a thin repository layer for future persistence work and a reserved MongoDB connection path for non-relational storage.
