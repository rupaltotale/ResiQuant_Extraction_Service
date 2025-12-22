# Backend (Flask)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
FLASK_APP=app.py FLASK_ENV=development python app.py
```

By default the server runs on http://localhost:5000.

## Testing

Install dev requirements and run pytest from the `backend/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

## Logging

Structured logs are emitted as single-line JSON with safe fields (no PII):

- event: high-level action (e.g., `upload_processed`, `validation_error`, `llm_error`)
- request_id: per-request UUID
- route: endpoint path
- source_hash: SHA-256 of input bytes (email + attachments)
- cache_hit: whether the LLM result was reused
- llm_status: `ok` | `skipped` | `error`
- llm_latency_ms: round-trip time for LLM call
- model: LLM model used
- document_count: number of uploaded documents
- broker_email_hash: SHA-256 of broker email, if present
- error_category: `validation` | `provider` | `timeout` (on failures)
- elapsed_ms: total request processing time

Configure log level via `LOG_LEVEL` (default `INFO`). Secrets must be provided via env (e.g., `OPENAI_API_KEY`) and are never logged.

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
# Optional: choose a model (defaults to gpt-5)
export OPENAI_MODEL="gpt-5"
```

If `OPENAI_API_KEY` is not set, the backend still responds and includes `llm_parsed.status = "skipped"`.

#### Domain Context

The prompt includes domain guidance to improve semantic extraction for insurance submissions:

- Submissions vary by broker; data is often sparse and unstandardized.
- Prefer explicit mentions from documents; avoid guessing.
- Return `null` for fields that are not explicitly supported by evidence.
