# OnboardAI Frontend

React + TypeScript + Vite dashboard for the existing OnboardAI FastAPI backend.

It is a pure frontend: it calls the existing `/api/*` endpoints and adds no new
backend behavior. The only backend change is additive CORS middleware in
`src/onboardai/api/main.py` so the browser dashboard can reach the API.

## Requirements

- Node.js 18+ (tested with Node 24 and npm 11)
- The OnboardAI backend running on `http://127.0.0.1:8001`

## How to run the frontend

### 1. Start the backend (existing project, unchanged)

```bash
# from the repository root
python -m uvicorn onboardai.api.main:create_app --factory --host 127.0.0.1 --port 8001
```

The backend must be running on port `8001` because the Vite dev server proxies
`/api` requests there.

### 2. Install frontend dependencies

```bash
cd frontend
npm install
```

> Note: if your npm is configured with `omit=dev` (this machine is), run
> `npm install --include=dev` so the build tooling is installed.

### 3. Start the dashboard

```bash
npm run dev
```

Open http://localhost:5173 in your browser.

The Vite dev server proxies every `/api` request to
`http://127.0.0.1:8001`, so no API URL is hardcoded in the browser code.

### Production build

```bash
npm run build        # type-checks and bundles into frontend/dist
npm run preview      # serves the production bundle locally
```

For a production deployment where the dashboard is served from a different
origin than the API, set `VITE_API_BASE_URL` at build time:

```bash
# Windows PowerShell
$env:VITE_API_BASE_URL="http://127.0.0.1:8001"; npm run build
```

The backend already allows the Vite dev/preview origins via CORS
(`localhost:5173`, `127.0.0.1:5173`, `localhost:4173`, `127.0.0.1:4173`).
If you deploy on another origin, add it to `allow_origins` in
`src/onboardai/api/main.py`.

## Static checks

```bash
npm run typecheck    # tsc --noEmit
npm run lint         # eslint (zero warnings required)
npm run build        # tsc && vite build
```

## What the dashboard does

- Shows backend health (mode, embedding model, knowledge base size) in the header.
- Submits a new onboarding case (all fields from `OnboardingRequest`, including
  the three agents to run and an optional start date).
- Shows workflow progress and case status for the active thread.
- Handles the `missing_information` pause (supply `start_date`) and the
  `human_approval` pause (approve/reject with reviewer and comments).
- Renders Training, HR Documents, and IT Provisioning agent results with
  recommendations, risk flags, artifacts, and RAG citations.
- Lists generated draft files and lets you preview their content.
- Shows the audit event trail for the active case.
- Polls the non-mutating `GET /api/cases/{thread_id}` every 15 seconds while a
  case is paused, so the approval screen refreshes without re-running the
  workflow.
- Displays API errors (HTTP status, FastAPI validation details) inline.

## Project layout

```text
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts          # dev proxy -> http://127.0.0.1:8001
├── eslint.config.js
└── src/
    ├── main.tsx
    ├── App.tsx             # dashboard shell + case lifecycle
    ├── styles.css
    ├── api/
    │   ├── client.ts       # fetch wrapper + ApiError
    │   └── types.ts        # mirrors of the backend Pydantic contracts
    └── components/
        ├── ConnectionStatus.tsx
        ├── NewCaseForm.tsx
        ├── CaseDetail.tsx
        ├── CasePanel.tsx   # audit events + case list
        ├── ApprovalStep.tsx
        ├── WorkerResults.tsx
        ├── WorkflowProgress.tsx
        └── ui.tsx          # Panel, Chip, Alert, Spinner, EmptyState
```
