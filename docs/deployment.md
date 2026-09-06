# ExamCraft AI Deployment Guide

This guide deploys:

- Frontend to Vercel
- FastAPI backend to Render
- PostgreSQL through a managed provider such as Supabase
- MongoDB for academic/content data
- Brevo for password-reset email delivery
- NVIDIA API for question generation

Deploy the backend before the frontend because the frontend needs the final
Render API URL.

## 1. Pre-deployment checks

From the repository root:

```powershell
git status
```

Verify that real environment files are not tracked:

```powershell
git ls-files .env backend/.env frontend/.env.local
```

This command should return no real environment files. `.env.example` and
`backend/.env.example` are safe templates and may remain tracked.

Run the backend tests:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Expected result:

```text
295 passed
```

Verify the migration graph:

```powershell
..\.venv\Scripts\python.exe -m alembic heads
```

Expected result:

```text
0007_productivity_template_owner (head)
```

There must be exactly one Alembic head.

Never commit:

- `.env`
- `backend/.env`
- `frontend/.env.local`
- PostgreSQL or MongoDB credentials
- `SECRET_KEY`
- `NVIDIA_API_KEY`
- `BREVO_API_KEY`
- `ADMIN_PASSWORD`

## 2. Prepare production databases

### PostgreSQL

Create a dedicated production PostgreSQL database. Do not use the local
development database.

The backend uses async SQLAlchemy. The URL should normally use the
`postgresql+asyncpg://` scheme:

```text
postgresql+asyncpg://USER:PASSWORD:HOST:PORT/DATABASE
```

Use the exact connection URL supplied by the PostgreSQL provider and URL-encode
special characters in the password when necessary.

The Render service must be allowed to connect to the database. Do not drop,
reset, or recreate the database during deployment.

### MongoDB

Create a production MongoDB database and user. Allow the Render service to
connect to the cluster. Do not use:

```text
mongodb://localhost:27017
```

Keep the MongoDB URI and credentials only in Render.

## 3. Create the Render backend service

1. Open Render and choose **New → Web Service**.
2. Connect the GitHub repository.
3. Select the ExamCraft repository.
4. Use these settings:

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Root Directory | `backend` |
| Python version | `3.12` |
| Build Command | `pip install .` |
| Pre-Deploy Command | `alembic upgrade head` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

Use the native Python runtime. If Docker is used instead, ensure the container
also listens on Render's `$PORT`; do not assume port `8000` is the public port.

After creation, Render will provide a URL similar to:

```text
https://examcraft-backend.onrender.com
```

Save this URL for the Vercel configuration.

## 4. Configure Render environment variables

Add the following under the Render service's **Environment** settings. Replace
every placeholder with a real production value.

### Application and authentication

```env
APP_ENV=production
SECRET_KEY=<new-long-random-production-secret>
JWT_REFRESH_EXPIRE=604800
```

Generate a new production `SECRET_KEY`; do not reuse the development secret.
`604800` is seven days in seconds.

### PostgreSQL

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

### MongoDB

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/<database>
MONGODB_DATABASE=<production-database-name>
```

### Administrator account

```env
ADMIN_EMAIL=<production-admin-email>
ADMIN_PASSWORD=<strong-production-admin-password>
```

Do not use test passwords or demo credentials in production.

### CORS

Initially use the final Vercel origin:

```env
CORS_ORIGINS=https://<project>.vercel.app
```

If a custom domain is also used:

```env
CORS_ORIGINS=https://<project>.vercel.app,https://<custom-domain>
```

Use origins only. Do not include `/login`, `/api`, or another path. Do not use
`*` for production CORS.

### NVIDIA generation

```env
NVIDIA_API_KEY=<nvidia-api-key>
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b
LLM_TIMEOUT=90
LLM_MAX_RETRIES=3
LLM_STUB=false
```

Never expose `NVIDIA_API_KEY` to Vercel or browser code.

### Email provider (password-reset OTP)

The email provider is selected with `EMAIL_PROVIDER`. The backend default is
`resend`; Brevo is also implemented and can be selected explicitly.

Resend (default):

```env
EMAIL_PROVIDER=resend
RESEND_API_KEY=<resend-api-key>
RESEND_FROM_EMAIL=onboarding@resend.dev
RESEND_FROM_NAME=ExamCraft AI
```

Brevo (alternative):

```env
EMAIL_PROVIDER=brevo
BREVO_API_KEY=<brevo-api-key>
BREVO_FROM_EMAIL=<verified-brevo-sender>
BREVO_FROM_NAME=ExamCraft AI
```

With Resend, `RESEND_FROM_EMAIL` must be a sender verified in the Resend
account (`onboarding@resend.dev` is for testing only). With Brevo,
`BREVO_FROM_EMAIL` must be a sender verified or permitted by the Brevo
account. Do not invent a sender address. Never expose `RESEND_API_KEY` or
`BREVO_API_KEY` to the frontend.

### Password reset and uploads

```env
OTP_EXPIRE_MINUTES=5
OTP_MAX_ATTEMPTS=5
OTP_RESEND_COOLDOWN_SECONDS=60
RESET_TOKEN_EXPIRE_MINUTES=10
MAX_UPLOAD_SIZE=52428800
```

Do not enable TEST mode or test email outbox behavior in production. The
production value must remain:

```env
APP_ENV=production
```

## 5. Run the Render migration

Use this exact Render pre-deploy command:

```bash
alembic upgrade head
```

This applies the current migration chain through:

```text
0007_productivity_template_owner
```

Never run these against production:

```bash
alembic downgrade base
dropdb
```

Do not delete users, papers, templates, audit logs, or other production data.

## 6. Deploy and verify Render

1. Save the Render settings.
2. Start the deployment.
3. Review the deploy logs.
4. Confirm dependency installation succeeds.
5. Confirm `alembic upgrade head` succeeds.
6. Confirm Uvicorn starts on `$PORT`.
7. Open:

```text
https://<render-service>.onrender.com/health
```

Expected response:

```json
{"status":"ok"}
```

Also verify the API documentation:

```text
https://<render-service>.onrender.com/docs
```

If the health check fails, confirm the start command uses `$PORT`, not a
hard-coded port.

## 7. Create the Vercel frontend project

1. Open Vercel and choose **Add New → Project**.
2. Import the same GitHub repository.
3. Configure:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Install Command | `npm install` |
| Build Command | `npm run build` |
| Output Directory | Default |
| Node.js version | 20 or newer |

The root directory must be `frontend`, not the repository root.

## 8. Configure Vercel environment variables

Add this variable for the Vercel Production environment:

```env
NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com
```

The value should be the Render origin without a trailing `/api`. The frontend
adds API paths itself, for example:

```text
https://<render-service>.onrender.com/api/auth/login
```

If Preview deployments are used, configure a suitable Preview value as well.

Do not add any backend secrets to Vercel. In particular, never add:

```text
SECRET_KEY
DATABASE_URL
MONGODB_URI
NVIDIA_API_KEY
BREVO_API_KEY
ADMIN_PASSWORD
```

Only public frontend configuration should use the `NEXT_PUBLIC_` prefix.

## 9. Deploy and verify Vercel

1. Save the Vercel variable.
2. Deploy the project.
3. Wait for `npm run build` to complete.
4. Open the generated Vercel URL:

```text
https://<project>.vercel.app
```

In browser developer tools, verify that API requests target the Render URL and
never `localhost` or `127.0.0.1`.

## 10. Finalize CORS

After Vercel provides the final production URL, set the exact URL in Render:

```env
CORS_ORIGINS=https://<actual-project>.vercel.app
```

Include the custom domain as a second comma-separated origin if applicable.
Save the variable and restart/redeploy the Render service.

## 11. Production smoke tests

### Authentication

- Open the Vercel login page.
- Log in with an active production account.
- Confirm no password hash is returned.
- Refresh the browser and confirm the session remains valid.
- Log out and confirm protected pages are no longer accessible.

### Password reset

- Open **Forgot Password**.
- Submit a real production email address.
- Confirm Brevo delivers the message.
- Enter the OTP.
- Reset the password.
- Log in with the new password.

Never print or store the OTP, reset token, password, or provider API key in
logs or screenshots.

### RBAC and ownership

- Confirm an admin can access authorized admin resources.
- Confirm faculty can access their own resources.
- Confirm faculty cannot access another faculty member's paper.
- Confirm unauthenticated requests receive `401`.
- Confirm unauthorized role requests receive `403`.

### Generation

- Create a valid paper configuration.
- Start generation.
- Confirm job progress is visible.
- Confirm the job reaches `completed`.
- Confirm failed jobs reach `failed`.
- Confirm retry/resume does not duplicate questions.

### Review and export

- Open the generated paper.
- Edit a question and verify the authenticated user is recorded.
- Approve the paper with an authorized account.
- Export PDF and DOCX where available.
- Verify export audit records contain the authenticated user.
- Confirm another faculty member cannot export the paper.

## 12. Troubleshooting

### Render cannot install dependencies

Check that:

- Root Directory is `backend`.
- Python is 3.12.
- Build Command is `pip install .`.

### Migration fails

Check that:

- `DATABASE_URL` is correct.
- PostgreSQL accepts connections from Render.
- The database user can create/update tables.
- Render runs the command from `backend`.
- There is exactly one Alembic head.

Run only:

```bash
alembic upgrade head
```

### CORS errors

Confirm `CORS_ORIGINS` contains the exact HTTPS Vercel origin, without a path:

```text
https://examcraft.vercel.app
```

Not:

```text
https://examcraft.vercel.app/login
```

### Frontend still calls localhost

Check that Vercel has:

```env
NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com
```

Then redeploy. Next.js environment values are applied during the production
build.

### Authentication or refresh fails

Confirm:

- Render's `SECRET_KEY` is stable between deploys.
- Both services use HTTPS.
- The Vercel origin is allowed by CORS.
- `JWT_REFRESH_EXPIRE` is configured.
- Browser storage/cookies are not blocked.

## 13. Deployment checklist

### Render

- [ ] Root directory is `backend`
- [ ] Python 3.12 is selected
- [ ] Build command is `pip install .`
- [ ] Pre-deploy command is `alembic upgrade head`
- [ ] Start command uses `$PORT`
- [ ] `/health` returns `{"status":"ok"}`
- [ ] `APP_ENV=production`
- [ ] Production `SECRET_KEY` is configured
- [ ] PostgreSQL and MongoDB are configured
- [ ] NVIDIA configuration is configured
- [ ] Brevo configuration is configured
- [ ] CORS contains the final Vercel origin
- [ ] Test outbox is disabled
- [ ] Alembic has one head

### Vercel

- [ ] Root directory is `frontend`
- [ ] Framework is Next.js
- [ ] Build command is `npm run build`
- [ ] `NEXT_PUBLIC_API_BASE_URL` points to Render
- [ ] No backend secrets are configured
- [ ] Production build succeeds
- [ ] Branding/static assets load

### Functional checks

- [ ] Landing page
- [ ] Login and logout
- [ ] Access-token refresh
- [ ] Forgot password and OTP
- [ ] Password reset
- [ ] Faculty permissions
- [ ] Admin permissions
- [ ] Generation and retry/resume
- [ ] Review and approval
- [ ] PDF/DOCX export
- [ ] Ownership restrictions
- [ ] Light and dark themes
- [ ] Mobile layout
