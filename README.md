# Resiquant App

Simple Flask backend + Next.js frontend to upload documents with an email and receive structured JSON output.

## Backend (Flask)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on http://localhost:5000.

## Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:3000.

Set `NEXT_PUBLIC_BACKEND_URL` in `frontend/.env.local` if backend differs from default.
