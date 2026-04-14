# Deploying AuditIQ to Railway

One service, one public URL. Railway builds the React frontend and starts
the FastAPI server automatically.

---

## Before you deploy — do this locally first

### 1. Run the RAG ingestion (one time only)
```bash
cd audit-app/backend
pip install -r requirements.txt
python scripts/ingest.py
```
This creates `backend/data/bm25_index.json` and `backend/data/chunks.json`.
**Commit these files** — Railway will load them at startup without re-ingesting.

### 2. Verify the app runs locally
```bash
# Terminal 1 — backend
cd audit-app/backend
set ANTHROPIC_API_KEY=sk-ant-api03-...   # Windows
# export ANTHROPIC_API_KEY=sk-ant-...   # Mac/Linux
uvicorn main:app --reload

# Terminal 2 — frontend dev (optional check)
cd audit-app/frontend
npm run dev
```

---

## Deploy to Railway

### Step 1 — Push your project to GitHub

```bash
cd audit-app
git init
git add .
git commit -m "Initial AuditIQ commit"
```

Create a new repo on github.com, then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/auditiq.git
git push -u origin main
```

> ⚠️ Make sure `backend/.env` is in `.gitignore` (it is by default).
> Never push your API key to GitHub.

---

### Step 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) and sign up / log in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `auditiq` repository
4. Railway will detect the `nixpacks.toml` and start building automatically

---

### Step 3 — Set your environment variable

In Railway dashboard:
1. Click your service → **Variables** tab
2. Click **New Variable**
3. Add:
   ```
   ANTHROPIC_API_KEY = sk-ant-api03-your-key-here
   ```
4. Click **Deploy** to redeploy with the key

> Railway injects this as a real environment variable — no `.env` file needed.

---

### Step 4 — Get your public URL

1. In Railway dashboard, click your service → **Settings** tab
2. Under **Networking**, click **Generate Domain**
3. Your app is live at something like: `https://auditiq-production.up.railway.app`

---

## What happens during Railway build

```
1. nixpacks installs Python 3.11 + Node 20
2. pip install -r backend/requirements.txt
3. cd frontend && npm install
4. cd frontend && npm run build   → creates frontend/dist/
5. START: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

FastAPI then serves:
- `GET /`          → React app (frontend/dist/index.html)
- `GET /assets/*`  → JS, CSS, images
- `GET /api/*`     → API endpoints
- `POST /api/chat` → Multi-agent RAG chat

---

## Updating the app

Any `git push` to your main branch triggers a new Railway deployment automatically.

To update the RAG index (e.g. new PDF):
```bash
# locally
python backend/scripts/ingest.py --pdf path/to/new-standard.pdf
git add backend/data/
git commit -m "Update RAG index"
git push
```

---

## Costs

Railway pricing (as of 2025):
- **Hobby plan**: $5/month — always-on, 8GB RAM, plenty for this app
- **Free trial**: $5 credit to get started
- Claude API calls are billed separately by Anthropic

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails at `npm run build` | Check frontend/package.json has correct vite version |
| `ANTHROPIC_API_KEY not set` | Add the variable in Railway → Variables tab |
| App loads but chat returns 401 | Your API key is invalid — check console.anthropic.com |
| RAG shows "No PDF indexed" | Commit `backend/data/bm25_index.json` and `chunks.json` |
| Slow cold start | Normal on first request — Railway keeps it warm on Hobby plan |
