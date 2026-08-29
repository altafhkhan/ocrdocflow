# OCRDocFlow — Phase 1 (Foundation)

This is the starting skeleton of OCRDocFlow: login, register, and file upload.
No OCR yet — that's Phase 2, next step.

## What's inside

```
ocrdocflow/
├── backend/     FastAPI app (Python) - handles login, upload, database
└── frontend/    React + TypeScript app - the screen you see in the browser
```

## Step 1 — Install the free tools (one-time setup)

1. **Docker Desktop** → https://www.docker.com/products/docker-desktop/
   (This runs the database and backend for you — no manual Postgres install needed.)
2. **Node.js 20+** → https://nodejs.org (for the frontend)

## Step 2 — Set up your secrets

```
cd backend
cp .env.example .env
```

Open `.env` in a text editor and replace `JWT_SECRET_KEY` with a random value.
You can generate one by running:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

(If you don't have Python installed yet, any long random string works for now —
just don't use the placeholder in real production.)

## Step 3 — Start the backend + database

```
docker compose up --build
```

Leave this running. Your API is now live at: http://localhost:8000
You can see the interactive API docs at: http://localhost:8000/docs

## Step 4 — Start the frontend

Open a **new** terminal window (keep Step 3 running):

```
cd frontend
npm install
npm run dev
```

Open your browser to: http://localhost:5173

## Step 5 — Try it out

1. Click "Register" and create an account.
2. Log in.
3. Upload one of your sample invoices (PDF, JPG, or PNG, under 10 MB).
4. You'll see it appear in your document list with status "uploaded".

That's it for Phase 1! The file is safely stored, but nothing reads its
content yet — that's exactly what we build next in Phase 2 (PaddleOCR).

## Troubleshooting

- **"Could not connect to database"** — make sure `docker compose up` is still
  running in its own terminal.
- **CORS error in browser console** — make sure the backend is running on
  port 8000 and frontend on port 5173 (the defaults above).
- **Port already in use** — something else on your computer is using that
  port. Close it, or ask me and I'll show you how to change the port.

## Phase 2 — OCR (reading the documents)

This adds PaddleOCR so uploaded documents actually get read.

### First-time setup

1. Rebuild the containers (this one will take a while — PaddleOCR is a big
   package, and it also downloads language model files the first time it
   runs, roughly 100-200 MB per language):
   ```
   docker compose up --build -d
   ```
2. Watch the logs to see progress and confirm it started cleanly:
   ```
   docker compose logs -f backend
   ```
   Look for `Application startup complete`. Press `Ctrl+C` to stop watching
   (this does not stop the containers).

### Using it

1. On the Dashboard, pick the document's language (English or Arabic) from
   the dropdown **before** uploading.
2. Upload a PDF or image. The upload button will show "Working on it..."
   while OCR runs — for now this happens synchronously (during the request),
   which is simple and fine for testing one document at a time.
3. Once status shows **done**, click **View Text** to see what was extracted.
4. If status shows **failed**, click **View Text** to see the error message.

### What to expect

- **Typed/printed invoices** (like the QUMAXA template) — should read quite
  well.
- **Arabic text** — PaddleOCR supports Arabic, but accuracy varies more than
  English; we'll tune this as we test your real samples.
- **Handwritten invoices** — this is the hardest case for any free OCR tool.
  Expect partial or rough results, not perfection — that's normal, not a bug.

## What's NOT built yet (on purpose — later phases)

- Extracting specific fields like vendor, total, date (Phase 3/4 — next)
- Background job queue for OCR (currently runs synchronously - fine for
  testing, not for many users at once)
- Multi-user companies / billing / plans (Phase 5 — deferred per your decision)
- Multi-language OCR AI model (deferred — starting with rule-based extraction)
