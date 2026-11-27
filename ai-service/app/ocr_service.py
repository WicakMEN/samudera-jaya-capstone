"""Modul OCR / Multimodal Vision untuk pemindaian foto nota belanja.
Base hook disiapkan oleh Haryo; integrasi lanjutan & prompt tuning OCR dilanjutkan oleh Faiz.
"""

import base64
import os
from typing import Optional
import httpx


async def extract_text_from_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[str]:
    """Menggunakan Google Gemini Vision API jika GEMINI_API_KEY tersedia."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Ekstrak daftar bahan baku kuliner dan kuantitasnya dari foto nota belanja ini "
                            "dalam satu kalimat bahasa Indonesia singkat, misalnya: "
                            "'beli mie basah 5 kg dan bakso 100 butir'. "
                            "Jika gambar bukan nota belanja bahan makanan, jawab persis: OUT_OF_CONTEXT."
                        )
                    },
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    return parts[0].get("text", "").strip() if parts else None
