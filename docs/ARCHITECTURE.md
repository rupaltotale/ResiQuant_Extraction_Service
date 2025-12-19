# ResiQuant Extraction – Architecture

## Overview
- Goal: Extract broker details and property addresses from an uploaded email chain PDF and attachments, returning structured JSON with provenance and per-field confidence.
- Tech:
  - Backend: Flask, OpenAI SDK, pypdf, openpyxl
  - Frontend: Next.js (simple upload UI)
  - Deploy targets: local dev; adaptable to containerization

## Data Flow
1. User uploads `email_pdf` (required) and optional `attachments` to `POST /api/upload`.
2. Backend extracts lightweight previews:
   - PDF: page text via `pypdf` (truncated preview for attachments)
   - XLSX: text via `openpyxl` (limited cells)
3. Backend calls LLM with:
   - Email text (full preview of the email PDF)
   - Attachment summaries (filename, mime, size, short `text_preview`)
   - System+schema instructions to produce strict JSON including:
     - Scalar fields, property address list
     - `field_confidence` per field (score + explanation)
     - `citations` with `{ source, snippet, match }`
4. Response assembled with:
   - Document metadata
   - `llm_parsed` payload
   - `provenance` built from LLM citations; fallback to search if citations absent

## Prompt & Schema
- System: “precise extraction assistant,” domain context for insurance submissions; prefer explicit mentions; avoid guessing.
- Schema highlights (subset):
  - `broker_name | broker_email | brokerage | complete_brokerage_address: string|null`
  - `property_addresses: [string]`
  - `field_confidence.{field}: { score:number, explanation:string }`
  - `field_confidence.property_addresses.per_address: [{ address, score, explanation }]`
  - `citations.{field}: [{ source:'email_pdf'|filename, snippet:string, match:string }]`
- Snippet rules: include the exact `match` and 25–120 chars of surrounding context.

## Validation & Provenance
- Strict JSON: enforced via `response_format={type: 'json_object'}`; fallback JSON salvage using regex if needed.
- Provenance build:
  - Prefer LLM citations (`snippet`, `match`, `source`).
  - Fallback search: page-level for PDFs; text search for previews; generate contextual `snippet` and set `match` to the extracted value.
- UI: Popover shows confidence (score + explanation) and provenance with highlighted `match` in snippet.

## Caching & Idempotency
- In-memory cache `LLM_CACHE` keyed by SHA-256 of: email text, attachment summaries, model, and instructions.
- Avoids duplicate LLM calls; adds `cached: true` in response (if reused).
- Tradeoff: per-process only; not shared across replicas; not persistent.

## Cost & Latency
- Cost drivers: LLM prompt size (email text + attachment previews) and output tokens.
- Latency drivers: PDF/XLSX parsing, network to OpenAI, model latency.
- Current mitigations:
  - Attachment previews truncated (~500 chars) in LLM prompt
  - In-memory caching for identical inputs
- Options to improve:
  - Persisted cache (Redis) keyed by content hash
  - Document chunking + retrieval (RAG) if inputs grow large
  - Smaller/cheaper model with fallback to stronger model when uncertain
  - Streaming UI for upload/parse progress

## Tradeoffs
- JSON enforcement vs. flexibility: strict schema reduces post-processing but can fail on edge outputs (regex salvage applied).
- In-memory cache: simple and fast, but not multi-instance safe.
- Citation reliance: trusts LLM to provide good snippets; fallback search reduces risk but can miss OCR edge cases.
- Minimal parsing: previews only for attachments to control token cost; may reduce recall compared to full-text parsing.

## Extensibility
- Add fields: extend the schema in `backend/app.py` and UI rendering; use `field_confidence` pattern.
- Add per-address provenance: extend citations to include `citations_per_address` keyed by address and render in UI.
- Swap models: set `OPENAI_MODEL` env; prompt is model-agnostic.
