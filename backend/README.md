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
- `confidence_overall`: number (0.0–1.0)
 - `field_confidence`: object with per-field confidence and explanation
   - `broker_name`: `{ score: number, explanation: string }`
   - `broker_email`: `{ score: number, explanation: string }`
   - `brokerage`: `{ score: number, explanation: string }`
   - `complete_brokerage_address`: `{ score: number, explanation: string }`
   - `property_addresses`: `{ score: number, explanation: string, per_address?: [{ address: string, score: number, explanation: string }] }`
 - `citations`: per-field arrays of evidence with contextual snippets
   - items: `{ source: 'email_pdf' | string, snippet: string, match?: string }`

### Provenance

The response includes a `provenance` object mapping each field to a list of sources:

- `doc`: filename (email PDF or attachment)
- `page`: page number (PDFs only; null for non-PDF)
- `snippet`: contextual text surrounding the match (25–120 chars each side)
- `match` (optional): the exact text matched for the field (used for highlighting)

### LLM Integration

Set the following environment variable before running:

```bash
export OPENAI_API_KEY="sk-..."
# Optional: choose a model
export OPENAI_MODEL="gpt-4o-mini"
```

If `OPENAI_API_KEY` is not set, the backend still responds and includes `llm_parsed.status = "skipped"`.

#### Domain Context

The prompt includes domain guidance to improve semantic extraction for insurance submissions:

- Submissions vary by broker; data is often sparse and unstandardized.
- Prefer explicit mentions from documents; avoid guessing.
- Return `null` for fields that are not explicitly supported by evidence.
