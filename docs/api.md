# API

The backend exposes route groups for authentication, subjects, syllabi, and generation jobs. The current scaffold includes health and placeholder endpoints so the architecture can be wired incrementally without changing the public surface.

## Planned Route Groups

- `GET /api/health`
- `POST /api/auth/login`
- `GET /api/subjects`
- `GET /api/syllabi`
- `POST /api/generation/jobs`
