// API configuration.
//   - In production (single-container deploy) the FastAPI server also serves
//     this bundle, so API_BASE is "" → calls go to the same origin.
//   - For local dev against a separate backend, set VITE_API_BASE
//     (e.g. http://localhost:8000) in frontend/.env.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export const API = {
  auth: {
    register: `${API_BASE}/auth/register`,
    login: `${API_BASE}/auth/login`,
  },
  characters: {
    list: `${API_BASE}/characters`,
    create: `${API_BASE}/characters`,
    generate: `${API_BASE}/characters/generate`,
    promote: `${API_BASE}/characters/promote`,
  },
  script: {
    create: `${API_BASE}/create-script`,
  },
  video: {
    make: `${API_BASE}/make-video`,
    jobs: `${API_BASE}/jobs`,
    list: `${API_BASE}/videos`,
  },
  voice: {
    clone: `${API_BASE}/clone-voice`,
  },
};

export function getJobUrl(jobId: string): string {
  return `${API.video.jobs}/${jobId}`;
}

export function getStaticUrl(path: string): string {
  return `${API_BASE}/static/${path}`;
}
