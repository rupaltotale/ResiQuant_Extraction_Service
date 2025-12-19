# Backend (Flask)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
FLASK_APP=app.py FLASK_ENV=development python app.py
```

By default the server runs on http://localhost:5000.

## API

- `GET /health` → `{ "status": "ok" }`
- `POST /api/upload` (multipart form)
  - fields:
    - `email_pdf`: single file (email chain PDF, PDF required)
    - `attachments`: zero or more files (supporting docs, supports PDF, XLSX, and text-like files)
  - response: structured JSON with metadata and LLM-parsed fields

### LLM Output Schema

The `llm_parsed.data` object follows this schema:

- `broker_name`: string|null
- `broker_email`: string|null
- `brokerage`: string|null
- `complete_brokerage_address`: string|null
- `property_addresses`: array of strings (unique, one-line addresses)

### LLM Integration

Set the following environment variable before running:

```bash
export OPENAI_API_KEY="sk-..."
# Optional: choose a model
export OPENAI_MODEL="gpt-4o-mini"
```

If `OPENAI_API_KEY` is not set, the backend still responds and includes `llm_parsed.status = "skipped"`.
