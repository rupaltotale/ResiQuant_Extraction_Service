import io
import json
from typing import Any


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, payload: dict):
        content = json.dumps(payload)
        self.choices = [_Choice(content)]


class _ChatCompletions:
    def __init__(self, payload: dict | Exception):
        self._payload_or_exc = payload

    def create(self, *args: Any, **kwargs: Any):
        if isinstance(self._payload_or_exc, Exception):
            raise self._payload_or_exc
        return _Resp(self._payload_or_exc)


class _Chat:
    def __init__(self, payload: dict | Exception):
        self.completions = _ChatCompletions(payload)


class _DummyOpenAI:
    def __init__(self, payload: dict | Exception):
        self.chat = _Chat(payload)


def _multipart_file(data: bytes, filename: str, mimetype: str):
    return (io.BytesIO(data), filename, mimetype)


def test_upload_llm_mock_success(client, monkeypatch):
    # Arrange a deterministic LLM response with citations
    llm_payload = {
        "broker_name": "John Smith",
        "broker_email": "john.smith@acmebrokerage.com",
        "brokerage": "Acme Brokerage",
        "complete_brokerage_address": "123 Broad St, Floor 5, New York, NY 10001",
        "property_addresses": [
            "10 Market St, San Francisco, CA 94103",
            "25 Pine Ave, Miami, FL 33101",
        ],
        "confidence_overall": 0.82,
        "citations": {
            "broker_name": [
                {
                    "source": "email_pdf",
                    "snippet": "...Regards, John Smith — Acme Brokerage...",
                    "match": "John Smith",
                }
            ],
            "broker_email": [
                {
                    "source": "email_pdf",
                    "snippet": "...contact me at john.smith@acmebrokerage.com for details...",
                    "match": "john.smith@acmebrokerage.com",
                }
            ],
            "brokerage": [
                {
                    "source": "email_pdf",
                    "snippet": "...John Smith, Acme Brokerage, 123 Broad St...",
                    "match": "Acme Brokerage",
                }
            ],
            "complete_brokerage_address": [
                {
                    "source": "email_pdf",
                    "snippet": "...Acme Brokerage, 123 Broad St, Floor 5, New York, NY 10001...",
                    "match": "123 Broad St, Floor 5, New York, NY 10001",
                }
            ],
            "property_addresses": [
                {
                    "source": "properties.csv",
                    "snippet": "...10 Market St, San Francisco, CA 94103, wood frame...",
                    "match": "10 Market St, San Francisco, CA 94103",
                },
                {
                    "source": "properties.csv",
                    "snippet": "...25 Pine Ave, Miami, FL 33101, masonry...",
                    "match": "25 Pine Ave, Miami, FL 33101",
                },
            ],
        },
        "field_confidence": {
            "broker_name": {"score": 0.9, "explanation": "Signature line contains full name."},
            "broker_email": {"score": 0.95, "explanation": "Explicit email provided."},
            "brokerage": {"score": 0.85, "explanation": "Appears next to name in signature."},
            "complete_brokerage_address": {"score": 0.8, "explanation": "Full address listed."},
            "property_addresses": {
                "score": 0.75,
                "explanation": "Addresses present in attachment rows.",
                "per_address": [
                    {"address": "10 Market St, San Francisco, CA 94103", "score": 0.78, "explanation": "Found in properties.csv."},
                    {"address": "25 Pine Ave, Miami, FL 33101", "score": 0.72, "explanation": "Found in properties.csv."},
                ],
            },
        },
    }

    import app as app_module

    # Patch the OpenAI constructor used inside the module to return our dummy
    monkeypatch.setattr(app_module, "OpenAI", lambda: _DummyOpenAI(llm_payload))

    # Build a minimal multipart request
    email_text = (
        b"Subject: Property Submission\n"
        b"Hello,\nPlease see the attached properties for quote.\n"
        b"Regards, John Smith\nAcme Brokerage\n"
        b"Contact: john.smith@acmebrokerage.com\n"
    )
    email_file = _multipart_file(email_text, "email.txt", "text/plain")

    # Attachment as CSV-ish text so preview includes addresses
    prop_csv = (
        b"address,construction\n"
        b"10 Market St, San Francisco, CA 94103,wood\n"
        b"25 Pine Ave, Miami, FL 33101,masonry\n"
    )
    props_file = _multipart_file(prop_csv, "properties.csv", "text/csv")

    data = {
        "email_pdf": email_file,
        "attachments": [props_file],
    }

    resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    body = resp.get_json()
    assert body["llm_parsed"]["status"] == "ok"
    assert body["llm_parsed"]["data"]["broker_name"] == "John Smith"
    assert body["email_document"]["filename"] == "email.txt"
    assert body["document_count"] == 2

    # Provenance should mirror the LLM citations (preferred path)
    prov = body["provenance"]
    assert "broker_name" in prov and prov["broker_name"][0]["doc"] == "email_pdf"
    assert all(entry.get("page") is None for entries in prov.values() for entry in entries)
    assert any(e.get("doc") == "properties.csv" for e in prov["property_addresses"])  # from attachment


def test_upload_llm_mock_error_path(client, monkeypatch):
    # Simulate OpenAI SDK raising an exception
    exc = RuntimeError("provider down")
    import app as app_module
    monkeypatch.setattr(app_module, "OpenAI", lambda: _DummyOpenAI(exc))

    email_file = _multipart_file(b"Test email body", "email.txt", "text/plain")
    resp = client.post(
        "/api/upload",
        data={"email_pdf": email_file},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["llm_parsed"]["status"] == "error"
    assert "message" in body["llm_parsed"]


def test_upload_missing_email_pdf(client):
    resp = client.post(
        "/api/upload",
        data={},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error")
