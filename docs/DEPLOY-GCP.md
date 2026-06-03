# Deploying Mind Video to Google Cloud Run

Mind Video ships as a **single container**: a multi-stage build compiles the
React frontend (`frontend/`) to static files, then a Python image runs the
FastAPI backend (`server/`) which serves **both** the API and the built UI on
one port. One URL, one origin, no CORS to manage.

```
┌─────────────────────────── container ───────────────────────────┐
│  uvicorn server:app  (port $PORT, default 8080)                  │
│    ├─ /                → frontend/dist/index.html (React SPA)     │
│    ├─ /assets/*        → hashed JS/CSS/img bundle                 │
│    ├─ /characters …    → JSON API                                │
│    ├─ /static/*        → character images & rendered videos      │
│    └─ /make-video      → shells out to make_episode.py (ffmpeg)   │
└──────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (node → vite build; python + ffmpeg → runtime) |
| `.dockerignore` | Keeps `node_modules`, venv, secrets, generated media out of the context |
| `deploy/setup.sh` | One-time: enable APIs, create Artifact Registry repo + Secret Manager secrets |
| `deploy/deploy.sh` | Build via Cloud Build + deploy to Cloud Run |
| `cloudbuild.yaml` | Same flow as a Cloud Build config (for CI triggers) |

## One-time setup

```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>

# Enables APIs, creates the 'mind-video' Artifact Registry repo, and loads
# FAL_KEY / ELEVENLABS_API_KEY / GOOGLE_API_KEY into Secret Manager.
# Reads the keys from your local .env if present.
./deploy/setup.sh
```

## Deploy

```bash
./deploy/deploy.sh
# prints the public https URL when finished
```

Or via Cloud Build (e.g. from a push trigger):

```bash
gcloud builds submit --config cloudbuild.yaml
```

## Why the Cloud Run flags matter

The deploy uses these flags (in both `deploy.sh` and `cloudbuild.yaml`):

| Flag | Reason |
|------|--------|
| `--no-cpu-throttling` | A render runs as a background subprocess **after** the `/make-video` request returns. Without always-allocated CPU, Cloud Run throttles the instance between requests and the render stalls. |
| `--min-instances=1` | Keeps that instance (and its in-memory job registry) alive so `/jobs/{id}` polling resolves. |
| `--max-instances=1` | Job state and rendered files live in **one process / one filesystem**. A second instance wouldn't see them. |
| `--timeout=3600` | Renders can take several minutes; the default 5-min request timeout is fine for `/make-video` (returns immediately) but generous here for safety. |
| `--cpu=2 --memory=2Gi` | ffmpeg encode + Python pipeline headroom. |

> **Cost note:** `--min-instances=1` + `--no-cpu-throttling` means one always-on
> instance (you pay even when idle). That is the price of the current in-memory
> job model. To scale horizontally later, move job state to Supabase/Firestore
> and rendered media to GCS, then drop these flags.

## Secrets / API keys

Keys are bound from **Secret Manager** at deploy time (never baked into the
image). The render path reads `FAL_KEY` (falls back to `FAL_API_KEY`),
`ELEVENLABS_API_KEY`, and `GOOGLE_API_KEY`. To rotate a key:

```bash
printf '%s' "$NEW_KEY" | gcloud secrets versions add FAL_KEY --data-file=-
gcloud run services update mind-video --region me-west1   # picks up :latest
```

## Statefulness caveats (current limitations)

The container's filesystem is **ephemeral** — it resets on every redeploy or
instance restart:

- **`users.json`** (registered accounts) is lost on restart.
- **`server/episodes/<slug>/`** rendered videos and **newly created characters**
  under `server/characters/` are lost on restart.

For anything beyond a demo, persist these to GCS / Supabase. This is tracked as
follow-up work, not a deploy blocker.

## Local sanity check (same image GCP runs)

```bash
docker build -t mind-video .
docker run -p 8080:8080 --env-file .env mind-video
# open http://localhost:8080  — health at http://localhost:8080/healthz
```

## Image-size optimization (optional)

The runtime image is ~1.3 GB because `server/requirements.txt` includes the
old Streamlit UI plus test/type tooling (`streamlit`, `pandas`, `pyarrow`,
`pytest*`, `mypy`) that the FastAPI server doesn't import. The image works as
is. To slim it, split a `requirements-prod.txt` without those packages and
point the Dockerfile at it.
