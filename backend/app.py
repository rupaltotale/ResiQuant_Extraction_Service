import os
import io
import json
from typing import List, Dict, Any
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
        "Always return strictly valid JSON that conforms to the schema. No extra text."
    )

    schema_description = (
        "Return a JSON object with exactly these fields and types:\n"
        "{\n"
        "  \"broker_name\": string|null,\n"
        "  \"broker_email\": string|null,\n"
        "  \"brokerage\": string|null,\n"
        "  \"complete_brokerage_address\": string|null,\n"
        "  \"property_addresses\": [string]\n"
        "}\n"
        "Rules:\n"
        "- Use the email thread text primarily; use attachment summaries as secondary hints.\n"
        "- If a field is not present, return null.\n"
        "- \"property_addresses\" must be a list of unique, human-readable street addresses (one line each).\n"
        "- Do not include commentary, only the JSON object."
    )

    user_prompt = {
        "email_thread_text": email_text,
        "attachments": attachments_summary,
        "instructions": schema_description,
    }

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
        return {"status": "ok", "model": OPENAI_MODEL, "data": parsed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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

    # Backward compatibility: if only 'files' provided, treat the first as email, rest as attachments
    if not email_pdf and not attachments_files:
        files_fallback = request.files.getlist('files')
        if files_fallback:
            email_pdf = files_fallback[0]
            attachments_files = files_fallback[1:]

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
    for f in attachments_files:
        data = f.read() or b""
        try:
            f.seek(0)
        except Exception:
            pass
        attachments.append(structure_document_json(f.filename or "", f.mimetype or "", data))

    # Call LLM for structured JSON
    llm = call_llm_for_structured_output(email_text=email_text, attachments=attachments)

    result = {
        "email_document": email_meta,
        "attachments": attachments,
        "document_count": 1 + len(attachments),
        "llm_parsed": llm,
    }
    return jsonify(result), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
