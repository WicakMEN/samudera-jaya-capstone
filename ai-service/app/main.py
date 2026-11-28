"""FastAPI AI Restock Service — UMKM Samudera Jaya (Tim A26-CS098).
Menyajikan endpoint /api/v1/ai/health dan /api/v1/ai/restock-parse sesuai docs/API_CONTRACT.md.
"""

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.guardrails import has_non_restock_pattern, is_model_loaded, validate_restock_request
from app.nlp_extractor import (
    extract_restock_with_warnings,
    get_known_ingredients_summary,
    normalize_item,
)
from app.ocr_service import (
    ImageValidationError,
    OCRNotConfiguredError,
    OCRRateLimitError,
    OCRUpstreamError,
    parse_receipt_image,
)

load_dotenv()

app = FastAPI(
    title="Samudera Jaya AI Restock Service",
    version="0.2.0",
    description="Layanan NLP Ekstraksi Entitas, OCR Nota Belanja (Vision + Fallback), & Guardrails (Tim A26-CS098)",
)

origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message, "details": details or {}}},
    )


def _detect_llm_provider() -> str:
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    has_groq = bool(os.getenv("GROQ_API_KEY", "").strip())
    if has_gemini and has_groq:
        return "gemini+groq"
    if has_gemini:
        return "gemini"
    if has_groq:
        return "groq"
    return "local_nlp_only"


def _merge_warnings(*warning_lists: List[str]) -> List[str]:
    merged: List[str] = []
    for warn_list in warning_lists:
        for warn in warn_list:
            if warn and warn not in merged:
                merged.append(warn)
    return merged


@app.get("/api/v1/ai/health")
def health_check():
    return {
        "success": True,
        "message": "FastAPI AI Restock Service is running",
        "data": {
            "status": "ok",
            "nlp_model_loaded": is_model_loaded(),
            "llm_provider": _detect_llm_provider(),
            "supported_ingredients_count": len(get_known_ingredients_summary()),
        },
    }


@app.post("/api/v1/ai/restock-parse")
async def restock_parse(request: Request):
    content_type = request.headers.get("content-type", "")
    raw_text = ""
    validation_text = ""
    source = "text"
    model_used = "custom_nlp_v2"
    extracted_items: List[Dict[str, Any]] = []
    extraction_warnings: List[str] = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        note_text = str(form.get("text") or "").strip()
        image = form.get("image")

        image_bytes = b""
        if image is not None and hasattr(image, "read"):
            image_bytes = await image.read()

        if image_bytes:
            image_mime = getattr(image, "content_type", "image/jpeg") or "image/jpeg"
            try:
                ocr_result = await parse_receipt_image(image_bytes, image_mime)
            except ImageValidationError as exc:
                return _error_response(
                    422,
                    "INVALID_IMAGE",
                    str(exc),
                    {"is_valid_context": False, "requires_manual_fallback": True},
                )
            except OCRNotConfiguredError as exc:
                return _error_response(
                    422,
                    "OCR_NOT_CONFIGURED",
                    str(exc),
                    {"requires_manual_fallback": True},
                )
            except OCRRateLimitError as exc:
                return _error_response(
                    429,
                    "OCR_RATE_LIMITED",
                    f"{exc} Gunakan input teks lokal atau formulir restock manual.",
                    {"requires_manual_fallback": True},
                )
            except OCRUpstreamError as exc:
                return _error_response(
                    502,
                    "OCR_UPSTREAM_ERROR",
                    f"Gagal memproses foto nota via Vision API: {exc}",
                    {"requires_manual_fallback": True},
                )

            if not ocr_result.get("is_receipt"):
                reason = ocr_result.get("reason") or "Foto yang diunggah tidak terdeteksi sebagai nota belanja bahan baku kuliner."
                return _error_response(
                    422,
                    "OUT_OF_CONTEXT_OR_INVALID",
                    reason,
                    {"is_valid_context": False, "intent": "out_of_scope", "requires_manual_fallback": True},
                )

            extraction_warnings.extend(ocr_result.get("warnings") or [])
            for raw_item in ocr_result.get("items") or []:
                norm_item, item_warns = normalize_item(
                    raw_name=raw_item["raw_name"],
                    raw_qty=raw_item["quantity"],
                    raw_unit=raw_item["unit"],
                    confidence=raw_item.get("confidence", 0.9),
                )
                extracted_items.append(norm_item)
                extraction_warnings.extend(item_warns)

            source = "ocr"
            raw_text = ocr_result.get("raw_text") or ", ".join(
                f"{it['raw_name']} {it['quantity']} {it['unit']}" for it in extracted_items
            )
            model_used = f"custom_nlp_v2+{ocr_result['provider']}"

            if note_text:
                if has_non_restock_pattern(note_text):
                    return _error_response(
                        422,
                        "OUT_OF_CONTEXT_OR_INVALID",
                        "Catatan tambahan di luar konteks pencatatan stok/belanja bahan baku kuliner.",
                        {"is_valid_context": False, "intent": "out_of_scope", "requires_manual_fallback": True},
                    )
                source = "hybrid"
                validation_text = note_text
                note_items, note_warns = extract_restock_with_warnings(note_text)
                existing_keys = {
                    (it["matched_ingredient_name"], it["normalized_quantity"], it["normalized_unit"])
                    for it in extracted_items
                }
                for item in note_items:
                    key = (item["matched_ingredient_name"], item["normalized_quantity"], item["normalized_unit"])
                    if key not in existing_keys:
                        extracted_items.append(item)
                        existing_keys.add(key)
                extraction_warnings.extend(note_warns)
                raw_text = f"{raw_text} | Catatan: {note_text}".strip(" |")
        else:
            raw_text = note_text
            validation_text = note_text
            extracted_items, extraction_warnings = extract_restock_with_warnings(raw_text)
    else:
        try:
            body: Optional[dict] = await request.json()
        except Exception:
            body = {}
        raw_text = str((body or {}).get("text") or "").strip()
        validation_text = raw_text
        extracted_items, extraction_warnings = extract_restock_with_warnings(raw_text)

    is_valid, intent, error_message, guardrail_warnings = validate_restock_request(
        validation_text, extracted_items, source=source
    )

    if not is_valid:
        return _error_response(
            422,
            "OUT_OF_CONTEXT_OR_INVALID",
            error_message or "Input di luar konteks pencatatan stok bahan baku.",
            {
                "is_valid_context": False,
                "intent": intent,
                "requires_manual_fallback": source != "text",
            },
        )

    return {
        "success": True,
        "message": "Ekstraksi restock berhasil",
        "data": {
            "is_valid_context": True,
            "intent": intent,
            "requires_confirmation": True,
            "raw_extracted_text": raw_text,
            "items": extracted_items,
            "warnings": _merge_warnings(extraction_warnings, guardrail_warnings),
            "model_used": model_used,
        },
    }
