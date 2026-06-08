#!/usr/bin/env bash
#
# One-time GCP setup: enable APIs, create the Artifact Registry repo, and load
# the three API keys into Secret Manager. Re-running is safe (idempotent).
#
# Reads keys from your local .env if present, otherwise from the environment.
#
# Usage:
#   gcloud config set project <YOUR_PROJECT_ID>
#   ./deploy/setup.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-me-west1}"
REPO="${AR_REPO:-mind-video}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: no GCP project. Run: gcloud config set project <ID>" >&2
  exit 1
fi

echo "==> Enabling APIs (run, build, artifactregistry, secretmanager)..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

echo "==> Ensuring Artifact Registry repo '${REPO}' exists in ${REGION}..."
gcloud artifacts repositories describe "${REPO}" --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${REPO}" \
       --repository-format=docker \
       --location="${REGION}" \
       --description="Mind Video container images"

# Pull keys from .env if it exists (so they aren't typed on the command line).
ENV_FILE="$(dirname "$0")/../.env"
if [[ -f "${ENV_FILE}" ]]; then
  echo "==> Loading keys from ${ENV_FILE}"
  set -a; source "${ENV_FILE}"; set +a
fi

put_secret() {
  local name="$1" value="$2"
  if [[ -z "${value}" ]]; then
    echo "    skip ${name} (no value set)"
    return
  fi
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=-
    echo "    updated ${name}"
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=-
    echo "    created ${name}"
  fi
}

echo "==> Loading secrets into Secret Manager..."
put_secret FAL_KEY            "${FAL_KEY:-}"
put_secret ELEVENLABS_API_KEY "${ELEVENLABS_API_KEY:-}"
put_secret GOOGLE_API_KEY     "${GOOGLE_API_KEY:-}"

# Dedicated, minimal runtime service account for Cloud Run. We do NOT use the
# default compute SA: it only exists if the Compute Engine API is enabled and
# it carries broad Editor rights. This SA only gets to read the three secrets.
RUNTIME_SA="${RUNTIME_SA_NAME:-mind-video-run}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "==> Ensuring runtime service account ${RUNTIME_SA} exists..."
gcloud iam service-accounts describe "${RUNTIME_SA}" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "${RUNTIME_SA_NAME:-mind-video-run}" \
       --display-name="Mind Video Cloud Run runtime"

echo "==> Granting ${RUNTIME_SA} secretAccessor..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

echo "==> Setup complete. Next: ./deploy/deploy.sh"
