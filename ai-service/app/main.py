"""FastAPI AI Restock Service — UMKM Samudera Jaya (Tim A26-CS098).
Menyajikan endpoint /api/v1/ai/health dan /api/v1/ai/restock-parse sesuai docs/API_CONTRACT.md.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.guardrails import is_model_loaded, validate_restock_request
from app.nlp_extractor import extract_restock_items
from app.ocr_service import extract_text_from_receipt

load_dotenv()

app = FastAPI(
    title="Samudera Jaya AI Restock Service",
    version="0.1.0",
    description="Layanan NLP Ekstraksi Entitas & OCR Nota Belanja (Tim A26-CS098)",
)

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/ai/health")
def health_check():
    return {
        "success": True,
        "message": "FastAPI AI Restock Service is running",
        "data": {
            "status": "ok",
            "nlp_model_loaded": is_model_loaded(),
            "llm_provider": "gemini" if os.getenv("GEMINI_API_KEY", "").strip() else "local_nlp_only",
        },
    }


@app.post("/api/v1/ai/restock-parse")
async def restock_parse(request: Request):
    content_type = request.headers.get("content-type", "")
    raw_text = ""
    model_used = "custom_nlp_v1"

    if "multipart/form-data" in content_type:
        form = await request.form()
        raw_text = str(form.get("text") or "").strip()
        image = form.get("image")

        if image is not None and hasattr(image, "read"):
            image_bytes = await image.read()
            if image_bytes:
                try:
                    ocr_text = await extract_text_from_receipt(
                        image_bytes, getattr(image, "content_type", "image/jpeg") or "image/jpeg"
                    )
                except Exception as exc:
                    return JSONResponse(
                        status_code=502,
                        content={
                            "success": False,
                            "error": {
                                "code": "OCR_UPSTREAM_ERROR",
                                "message": f"Gagal memproses foto nota via Vision API: {exc}",
                                "details": {"requires_manual_fallback": True},
                            },
                        },
                    )

                if ocr_text is None:
                    return JSONResponse(
                        status_code=422,
                        content={
                            "success": False,
                            "error": {
                                "code": "OCR_NOT_CONFIGURED",
                                "message": "GEMINI_API_KEY belum diisi untuk pemindaian foto nota. Gunakan input teks atau form restock manual.",
                                "details": {"requires_manual_fallback": True},
                            },
                        },
                    )
                if ocr_text.strip().upper() == "OUT_OF_CONTEXT":
                    return JSONResponse(
                        status_code=422,
                        content={
                            "success": False,
                            "error": {
                                "code": "OUT_OF_CONTEXT_OR_INVALID",
                                "message": "Foto yang diunggah tidak terdeteksi sebagai nota belanja bahan baku kuliner.",
                                "details": {"is_valid_context": False, "intent": "out_of_scope", "requires_manual_fallback": True},
                            },
                        },
                    )
                raw_text = f"{raw_text} {ocr_text}".strip()
                model_used = "custom_nlp_v1+gemini_vision"
    else:
        try:
            body: Optional[dict] = await request.json()
        except Exception:
            body = {}
        raw_text = str((body or {}).get("text") or "").strip()

    extracted_items = extract_restock_items(raw_text)
    is_valid, intent, error_message = validate_restock_request(raw_text, extracted_items)

    if not is_valid:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "OUT_OF_CONTEXT_OR_INVALID",
                    "message": error_message,
                    "details": {
                        "is_valid_context": False,
                        "intent": intent,
                        "requires_manual_fallback": False,
                    },
                },
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
            "warnings": [],
            "model_used": model_used,
        },
    }
