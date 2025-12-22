# ResiQuant Extraction – Runbook

## Prerequisites
- Python 3.10+
- Node.js 18+
- Environment:
  - `OPENAI_API_KEY` (required for LLM parsing)
  - `OPENAI_MODEL` (optional, defaults to `gpt-4o-mini`)

## Start / Stop
Backend:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
# optional
export OPENAI_MODEL="gpt-5"
python app.py
```
Frontend:
```bash
cd frontend
npm install
export NEXT_PUBLIC_BACKEND_URL="http://localhost:5000"
npm run dev
```

## Key Rotation
- Rotate by updating `OPENAI_API_KEY` where set (env var, secret store, or deployment config) and restart backend.
- Verify with `GET /health` and a small test upload.

## Model Tuning / Selection
- Default model is `gpt-5`. Change `OPENAI_MODEL` env to try different models (e.g., speed/cost tradeoffs).
- If switching to a weaker model, consider increasing snippet context and adjusting prompts (see below).

Temperature notes:
- Some models (e.g., `gpt-5`) only support the default temperature. The backend automatically omits the `temperature` parameter for such models.

## Prompt Tuning
- The prompt and schema live in `backend/app.py` inside `call_llm_for_structured_output()`:
  - `system_instructions`
  - `schema_description`
- Common tweaks:
  - Tighten address rules (e.g., require city+state) to reduce false positives.
  - Adjust snippet context guidance (e.g., 25–120 chars sides) if snippets feel too short/long.
  - Emphasize "return null rather than guess" for specific fields.

## Debug Bad Parses
1. Reproduce: Use the same `email_pdf` and `attachments` in the frontend and capture the Raw Response.
2. Check `llm_parsed.status`:
   - `skipped`: missing API key; set `OPENAI_API_KEY` and retry.
   - `error`: inspect `llm_parsed.message` for SDK/network issues.
3. Inspect `data.field_confidence` explanations – low scores often indicate ambiguous sources.
4. Inspect `citations` and `provenance`:
   - Confirm `source` and `snippet` include the expected `match`.
   - If LLM citations are empty, the backend uses fallback search; consider increasing snippet context.
5. Attachment previews are truncated (~500 chars). If evidence is missing, consider allowing larger previews or richer parsing for that file type.
6. Prompt tune (above) and re-test.

## Caching
- In-memory cache (`LLM_CACHE`) keyed by SHA-256 of inputs + model + instructions.
- To clear: restart the backend process.
- For multi-instance deployments: use Redis or another centralized cache keyed by the same hash payload.

## Logging & Observability
- Current code returns detailed JSON to the client (Raw Response in UI).
- Add server logs (info/warn/error) around LLM calls and parsing if needed – e.g., log cache hits and response sizes.

## Rate Limiting & Retries
- OpenAI SDK backoff is minimal. For production, wrap calls with retries and exponential backoff, plus request timeouts.
- Consider a queue for large batches.

## Common Issues
- HTTP client error referencing `proxies`: pin `httpx==0.27.2` (already in requirements).
- No text in PDFs: some PDFs are scanned; integrate OCR (e.g., Tesseract) if needed.
- Overly long snippets: reduce context in `_make_snippet()`.
- Missing provenance: ensure citations contract `{source,snippet,match}` is still respected by the model after prompt edits.
