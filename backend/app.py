import os
import io
import json
import hashlib
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Model selection for OpenAI
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# External dependencies (installed via requirements.txt)
from openai import OpenAI  # OpenAI SDK
import openpyxl  # XLSX parsing
from pypdf import PdfReader  # PDF text extraction

# Simple in-memory cache to avoid duplicate LLM calls for identical inputs
LLM_CACHE: Dict[str, Dict[str, Any]] = {}


def extract_text_from_pdf(file_stream: io.BytesIO) -> str:
    try:
        reader = PdfReader(file_stream)
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(texts).strip()
    except Exception:
        return ""


def extract_text_from_xlsx(data: bytes, max_cells: int = 2000) -> str:
    try:
        # Load workbook from bytes
        bio = io.BytesIO(data)
        wb = openpyxl.load_workbook(bio, data_only=True, read_only=True)
        lines = []
        count = 0
        for ws in wb.worksheets:
            lines.append(f"# Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                if count >= max_cells:
                    break
                # Join non-empty cell values
                vals = [str(v) for v in row if v is not None]
                if vals:
                    lines.append(", ".join(vals))
                    count += len(vals)
            if count >= max_cells:
                break
        return "\n".join(lines).strip()
    except Exception:
        return ""


def structure_document_json(filename: str, content_type: str, data: bytes) -> Dict[str, Any]:
    size = len(data)
    text_preview = ""

    if content_type.lower() in ("application/pdf",) or filename.lower().endswith(".pdf"):
        text_preview = extract_text_from_pdf(io.BytesIO(data))[:2000]
    elif content_type.lower() in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",) or filename.lower().endswith(".xlsx"):
        text_preview = extract_text_from_xlsx(data)[:2000]
    else:
        # naive text attempt for text-like files
        try:
            text_preview = data.decode("utf-8", errors="ignore")[:2000]
        except Exception:
            text_preview = ""

    return {
        "filename": filename,
        "mime_type": content_type,
        "size_bytes": size,
        "text_preview": text_preview,
        # Placeholder for future field extraction rules/LLM parsing
        "parsed_fields": {}
    }


def call_llm_for_structured_output(email_text: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Call OpenAI to produce a strict JSON extraction of the email thread.
    Returns a dict; if the API key is missing or an error occurs, returns an
    error payload while keeping the route successful.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return {"status": "skipped", "reason": "missing_openai_key"}

    # Summarize attachments for the model
    attachments_summary = [
        {
            "filename": a.get("filename"),
            "mime_type": a.get("mime_type"),
            "size_bytes": a.get("size_bytes"),
            # Include a short preview only if present
            "text_preview": (a.get("text_preview") or "")[:500],
        }
        for a in attachments
    ]

    system_instructions = (
        "You are a precise extraction assistant. "
        "Extract brokerage details and property addresses from the provided email thread text and attachment summaries. "
        "Always return strictly valid JSON that conforms to the schema. No extra text.\n\n"
        "Domain Context: The auto-ingest of insurance submission documents is a process that automates the current "
        "manual process of reading insurance email submissions (and attachments) to extract relevant building attributes "
        "of the properties requesting coverage such as construction class, occupancy type, number of stories, and others. "
        "These attributes are necessary for running a catastrophe model and providing a quote. Every insurance submission is different; "
        "each broker has their own document format and property data is often sparse, unstandardized, and unvetted. "
        "Interpret fields semantically and prefer explicit mentions from the documents. If information is missing or uncertain, return null rather than guessing."
    )

    schema_description = (
        "Return a JSON object with exactly these fields and types:\n"
        "{\n"
        "  \"broker_name\": string|null,\n"
        "  \"broker_email\": string|null,\n"
        "  \"brokerage\": string|null,\n"
        "  \"complete_brokerage_address\": string|null,\n"
        "  \"property_addresses\": [string],\n"
        "  \"confidence_overall\": number,\n"
        "  \"citations\": {\n"
        "    // For each field above, provide an array of citations with source and a contextual snippet, plus the exact matched text\n"
        "    \"broker_name\": [ { \"source\": \"email_pdf\"|string, \"snippet\": string, \"match\": string } ],\n"
        "    \"broker_email\": [ { \"source\": \"email_pdf\"|string, \"snippet\": string, \"match\": string } ],\n"
        "    \"brokerage\": [ { \"source\": \"email_pdf\"|string, \"snippet\": string, \"match\": string } ],\n"
        "    \"complete_brokerage_address\": [ { \"source\": \"email_pdf\"|string, \"snippet\": string, \"match\": string } ],\n"
        "    \"property_addresses\": [ { \"source\": \"email_pdf\"|string, \"snippet\": string, \"match\": string } ]\n"
        "  },\n"
        "  \"field_confidence\": {\n"
        "    // Attach a confidence (0..1) and an explanation for why, per field\n"
        "    \"broker_name\": { \"score\": number, \"explanation\": string },\n"
        "    \"broker_email\": { \"score\": number, \"explanation\": string },\n"
        "    \"brokerage\": { \"score\": number, \"explanation\": string },\n"
        "    \"complete_brokerage_address\": { \"score\": number, \"explanation\": string },\n"
        "    \"property_addresses\": { \"score\": number, \"explanation\": string, \"per_address\": [ { \"address\": string, \"score\": number, \"explanation\": string } ] }\n"
        "  }\n"
        "}\n"
        "Rules:\n"
        "- Use the email thread text primarily; use attachment summaries as secondary hints.\n"
        "- Citations must be snippets that include the exact matched text plus surrounding context (25–120 characters on each side) from the provided texts (email thread or attachment previews).\n"
        "- The \"source\" must be either \"email_pdf\" or the exact attachment filename provided.\n"
        "- If a field is not present, return null (and an empty citation list).\n"
        "- \"property_addresses\" must be a list of unique, human-readable street addresses (one line each).\n"
        "- Set \"confidence_overall\" to reflect your certainty (0..1).\n"
        "- For each field, set \"field_confidence\" with a numeric score and a concise explanation that references specific evidence (e.g., a phrase inside the snippet).\n"
        "- In citations, set \"match\" equal to the exact text you used to identify the field (e.g., the broker name or address).\n"
        "- Do not include commentary, only the JSON object."
    )

    user_prompt = {
        "email_thread_text": email_text,
        "attachments": attachments_summary,
        "instructions": schema_description,
        "domain_context": "Insurance submissions vary widely; data may be sparse/unstandardized. Prefer explicit text; do not infer beyond the documents.",
    }

    # Cache key derived from content + model + instructions to avoid duplicate calls
    cache_key_payload = {
        "email_thread_text": email_text,
        "attachments": attachments_summary,
        "model": OPENAI_MODEL,
        "instructions": schema_description,
    }
    cache_key = hashlib.sha256(json.dumps(cache_key_payload, sort_keys=True).encode("utf-8")).hexdigest()

    cached = LLM_CACHE.get(cache_key)
    if cached and cached.get("status") == "ok":
        # Mark cached result to help clients optionally identify hits
        result = dict(cached)
        result["cached"] = True
        return result

    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
        )
        content = (resp.choices[0].message.content or "{}").strip()
        try:
            parsed = json.loads(content)
        except Exception:
            # Attempt to salvage JSON from content
            import re
            m = re.search(r"\{[\s\S]*\}", content)
            parsed = json.loads(m.group(0)) if m else {"raw": content}
        result = {"status": "ok", "model": OPENAI_MODEL, "data": parsed}
        # Store successful responses in cache
        LLM_CACHE[cache_key] = result
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _make_snippet(text: str, start: int, end: int, context: int = 120) -> str:
    left = max(0, start - context)
    right = min(len(text), end + context)
    snippet = text[left:right].replace("\n", " ")
    if left > 0:
        snippet = "…" + snippet
    if right < len(text):
        snippet = snippet + "…"
    return snippet


def find_in_pdf(data: bytes, term: str, max_hits: int = 1) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        lower_term = term.lower()
        for idx, page in enumerate(reader.pages):
            try:
                txt = (page.extract_text() or "")
            except Exception:
                continue
            lower_txt = txt.lower()
            pos = lower_txt.find(lower_term)
            if pos != -1:
                snippet = _make_snippet(txt, pos, pos + len(term))
                hits.append({"page": idx + 1, "snippet": snippet})
                if len(hits) >= max_hits:
                    break
        return hits
    except Exception:
        return hits


def find_in_text(text: str, term: str) -> Optional[str]:
    lower_txt = (text or "").lower()
    lower_term = term.lower()
    pos = lower_txt.find(lower_term)
    if pos == -1:
        return None
    return _make_snippet(text, pos, pos + len(term))


def compute_provenance(
    email_pdf_bytes: bytes,
    email_pdf_name: str,
    attachments_raw: List[Dict[str, Any]],
    llm_data: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Compute provenance for extracted fields by searching source texts.

    Produces a map of field -> [{ doc, page, snippet }].
    - Searches across the email PDF (page-level) and attachments (PDF page-level or text preview).
    """
    provenance: Dict[str, List[Dict[str, Any]]] = {}

    def add_prov(field: str, doc: str, page: Optional[int], snippet: Optional[str], match: Optional[str] = None):
        if not snippet:
            return
        entry = {
            "doc": doc,
            "page": page,
            "snippet": snippet,
        }
        if isinstance(match, str) and match.strip():
            entry["match"] = match
        provenance.setdefault(field, []).append(entry)

    # Scalar fields
    for field in ["broker_name", "broker_email", "brokerage", "complete_brokerage_address"]:
        val = llm_data.get(field)
        if isinstance(val, str) and val.strip():
            # Search email PDF pages
            for hit in find_in_pdf(email_pdf_bytes, val, max_hits=1):
                add_prov(field, email_pdf_name or "email_pdf", hit.get("page"), hit.get("snippet"), match=val)
            # Search attachments previews and PDFs
            for att in attachments_raw:
                # Try PDF page search if PDF
                if (att.get("mimetype", "").lower() == "application/pdf") or (att.get("filename", "").lower().endswith(".pdf")):
                    for hit in find_in_pdf(att.get("data", b""), val, max_hits=1):
                        add_prov(field, att.get("filename") or "attachment", hit.get("page"), hit.get("snippet"), match=val)
                else:
                    snip = find_in_text(att.get("text_preview", ""), val)
                    if snip:
                        add_prov(field, att.get("filename") or "attachment", None, snip, match=val)

    # List of addresses
    addrs = llm_data.get("property_addresses") or []
    if isinstance(addrs, list):
        for addr in addrs:
            if not isinstance(addr, str) or not addr.strip():
                continue
            field = "property_addresses"
            for hit in find_in_pdf(email_pdf_bytes, addr, max_hits=1):
                add_prov(field, email_pdf_name or "email_pdf", hit.get("page"), hit.get("snippet"), match=addr)
            for att in attachments_raw:
                if (att.get("mimetype", "").lower() == "application/pdf") or (att.get("filename", "").lower().endswith(".pdf")):
                    for hit in find_in_pdf(att.get("data", b""), addr, max_hits=1):
                        add_prov(field, att.get("filename") or "attachment", hit.get("page"), hit.get("snippet"), match=addr)
                else:
                    snip = find_in_text(att.get("text_preview", ""), addr)
                    if snip:
                        add_prov(field, att.get("filename") or "attachment", None, snip, match=addr)

    return provenance


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.post("/api/upload")
def upload() -> Any:
    if not request.files:
        return jsonify({"error": "No files provided"}), 400

    # New contract: one email chain PDF under 'email_pdf', zero or more attachments under 'attachments'
    email_pdf = request.files.get('email_pdf')
    attachments_files = request.files.getlist('attachments')

    # Expect explicit fields only: 'email_pdf' and optional 'attachments'

    if not email_pdf:
        return jsonify({"error": "Missing 'email_pdf' file"}), 400

    # Process email PDF
    email_data = email_pdf.read() or b""
    try:
        email_pdf.seek(0)
    except Exception:
        pass

    email_meta = structure_document_json(email_pdf.filename or "", email_pdf.mimetype or "", email_data)
    email_text = email_meta.get("text_preview", "")

    # Process attachments
    attachments: List[Dict[str, Any]] = []
    # Keep raw data for provenance search (not returned to client)
    attachment_raw: List[Dict[str, Any]] = []
    for f in attachments_files:
        data = f.read() or b""
        try:
            f.seek(0)
        except Exception:
            pass
        meta = structure_document_json(f.filename or "", f.mimetype or "", data)
        attachments.append(meta)
        attachment_raw.append({
            "filename": f.filename or "",
            "mimetype": f.mimetype or "",
            "data": data,
            "text_preview": meta.get("text_preview", ""),
        })

    # Call LLM for structured JSON
    llm = call_llm_for_structured_output(email_text=email_text, attachments=attachments)

    provenance: Dict[str, List[Dict[str, Any]]] = {}
    if llm.get("status") == "ok":
        data_obj = llm.get("data", {})
        citations = data_obj.get("citations", {})
        # Prefer LLM-provided citations (source + contextual snippet)
        if isinstance(citations, dict):
            for field, sources in citations.items():
                if not isinstance(sources, list):
                    continue
                for c in sources:
                    if not isinstance(c, dict):
                        continue
                    doc = c.get("source") or "email_pdf"
                    snippet = c.get("snippet") or c.get("quote") or ""
                    match = c.get("match")
                    if snippet.strip():
                        entry = {
                            "doc": doc,
                            "page": None,
                            "snippet": snippet,
                        }
                        if isinstance(match, str) and match.strip():
                            entry["match"] = match
                        provenance.setdefault(field, []).append(entry)
        # Fallback to computed provenance if citations missing
        if not provenance:
            provenance = compute_provenance(
                email_pdf_bytes=email_data,
                email_pdf_name=email_pdf.filename or "email_pdf",
                attachments_raw=attachment_raw,
                llm_data=data_obj,
            )

    result = {
        "email_document": email_meta,
        "attachments": attachments,
        "document_count": 1 + len(attachments),
        "llm_parsed": llm,
        "provenance": provenance,
    }
    return jsonify(result), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
