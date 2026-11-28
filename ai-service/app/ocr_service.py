"""Modul OCR / Multimodal Vision untuk pemindaian foto nota belanja UMKM Samudera Jaya.
Mendukung validasi gambar, output JSON terstruktur (Gemini Vision), throttling, retry, dan fallback Groq Vision.
"""

import asyncio
import base64
import json
import os
import time
from typing import Any, Dict, List
import httpx

from app.nlp_extractor import get_known_ingredients_summary

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

# ponytail: Throttling memakai lock in-memory single-process;
# jika deploy multi-worker/replicated, ganti ke rate limiter terpusat (mis. Redis).
_throttle_lock = asyncio.Lock()
_last_ocr_call_ts = 0.0


class ImageValidationError(ValueError):
    """Error validasi file gambar yang diunggah."""


class OCRNotConfiguredError(RuntimeError):
    """Tidak ada API key Vision provider yang terkonfigurasi."""


class OCRRateLimitError(RuntimeError):
    """Provider Vision mengembalikan HTTP 429 (kuota / rate limit habis)."""


class OCRUpstreamError(RuntimeError):
    """Kegagalan komunikasi atau parsing output dari provider Vision."""


RECEIPT_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "is_receipt": {"type": "BOOLEAN"},
        "reason": {"type": "STRING"},
        "raw_text": {"type": "STRING"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "raw_name": {"type": "STRING"},
                    "quantity": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["raw_name", "quantity", "unit"],
            },
        },
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["is_receipt", "raw_text", "items", "warnings"],
}


def validate_image_upload(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Memvalidasi ukuran, MIME type, dan magic bytes file gambar."""
    if not image_bytes:
        raise ImageValidationError("File gambar kosong.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageValidationError("Ukuran gambar melebihi batas maksimal 5 MB.")

    normalized_mime = (mime_type or "").split(";")[0].strip().lower()
    if normalized_mime == "image/jpg":
        normalized_mime = "image/jpeg"
    if normalized_mime not in ALLOWED_MIME_TYPES:
        raise ImageValidationError("Format gambar harus JPG, PNG, atau WEBP.")

    is_jpeg = image_bytes.startswith(b"\xff\xd8\xff")
    is_png = image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP"

    valid_magic = (
        (normalized_mime == "image/jpeg" and is_jpeg)
        or (normalized_mime == "image/png" and is_png)
        or (normalized_mime == "image/webp" and is_webp)
    )
    if not valid_magic:
        raise ImageValidationError("Isi file gambar tidak sesuai dengan format JPG/PNG/WEBP yang valid.")

    return normalized_mime


def _build_receipt_prompt() -> str:
    known_list = ", ".join(
        f"{entry['name']} ({entry['standard_unit']})" for entry in get_known_ingredients_summary()
    )
    return (
        "Anda adalah asisten OCR inventaris untuk UMKM kuliner Mie Ayam & Bakso Samudera Jaya.\n"
        f"Daftar bahan baku utama UMKM: {known_list}.\n\n"
        "Tugas Anda:\n"
        "1. Tentukan `is_receipt`: true HANYA jika gambar adalah nota belanja bahan makanan/kuliner, bon pasar, "
        "atau catatan belanja bahan baku dapur. Jika gambar bukan nota belanja kuliner (mis. selfie, pemandangan, "
        "nota elektronik/BBM/pakaian, dokumen non-belanja, atau gambar tidak terbaca sama sekali), set `is_receipt: false`.\n"
        "2. Ekstrak seluruh item bahan baku ke array `items` berisi `{raw_name, quantity, unit, confidence}` (0.0 - 1.0).\n"
        "3. ABAIKAN angka harga, subtotal, total pembayaran (Rp), nomor nota, dan tanggal agar tidak tertukar dengan kuantitas.\n"
        "4. Jika tulisan kuantitas atau nama bahan agak buram/ragu, tetap ekstrak estimasi terbaik dan catat di `warnings`.\n"
        "5. Kembalikan JSON valid SAJA tanpa teks tambahan.\n\n"
        "Contoh 1 (Nota Belanja Valid):\n"
        '{"is_receipt": true, "reason": "Nota belanja bahan kuliner", '
        '"raw_text": "Mie basah 5 kg Rp 75.000; Bakso 100 butir Rp 80.000", '
        '"items": [{"raw_name": "mie basah", "quantity": 5, "unit": "kg", "confidence": 0.95}, '
        '{"raw_name": "bakso", "quantity": 100, "unit": "butir", "confidence": 0.93}], "warnings": []}\n\n'
        "Contoh 2 (Bukan Nota Kuliner):\n"
        '{"is_receipt": false, "reason": "Gambar merupakan struk pengisian BBM / bukan bahan makanan", '
        '"raw_text": "", "items": [], "warnings": []}'
    )


def _strip_json_fences(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_ocr_json(raw_text: str) -> Dict[str, Any]:
    cleaned = _strip_json_fences(raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OCRUpstreamError(f"Output OCR tidak berupa JSON valid: {exc}") from exc

    if not isinstance(parsed, dict):
        raise OCRUpstreamError("Struktur output OCR tidak valid.")

    is_receipt = bool(parsed.get("is_receipt", False))
    warnings: List[str] = [str(w).strip() for w in (parsed.get("warnings") or []) if str(w).strip()]
    valid_items: List[Dict[str, Any]] = []

    for row in parsed.get("items") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("raw_name") or "").strip()
        if not name:
            continue
        try:
            qty = float(str(row.get("quantity")).replace(",", "."))
        except (TypeError, ValueError):
            warnings.append(f"Kuantitas item '{name}' pada nota tidak terbaca sebagai angka.")
            continue
        unit = str(row.get("unit") or "pcs").strip().lower()
        try:
            conf = float(row.get("confidence", 0.88))
        except (TypeError, ValueError):
            conf = 0.88
        conf = max(0.0, min(1.0, conf))
        valid_items.append({"raw_name": name, "quantity": qty, "unit": unit, "confidence": conf})

    return {
        "is_receipt": is_receipt,
        "reason": str(parsed.get("reason") or "").strip(),
        "raw_text": str(parsed.get("raw_text") or "").strip(),
        "items": valid_items,
        "warnings": warnings,
    }


async def _throttle_ocr() -> None:
    global _last_ocr_call_ts
    min_interval = float(os.getenv("OCR_MIN_INTERVAL_SECONDS", "0.5") or "0")
    if min_interval <= 0:
        return
    async with _throttle_lock:
        elapsed = time.monotonic() - _last_ocr_call_ts
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_ocr_call_ts = time.monotonic()


async def _request_with_retry(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    max_attempts = 2
    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=25.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)
                    continue
                raise OCRUpstreamError(f"Koneksi ke Vision API gagal/timeout: {exc}") from exc
            except httpx.HTTPError as exc:
                raise OCRUpstreamError(f"Kesalahan HTTP Vision API: {exc}") from exc

            if resp.status_code == 429:
                raise OCRRateLimitError("Kuota sementara Vision API mencapai batas (HTTP 429).")
            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                await asyncio.sleep(1.0)
                continue
            if resp.status_code >= 400:
                raise OCRUpstreamError(f"Vision API mengembalikan HTTP {resp.status_code}.")

            try:
                return resp.json()
            except ValueError as exc:
                raise OCRUpstreamError("Respons Vision API bukan JSON valid.") from exc

    raise OCRUpstreamError(f"Gagal memanggil Vision API: {last_exc}")


async def _call_gemini_vision(image_bytes: bytes, mime_type: str, api_key: str) -> Dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _build_receipt_prompt()},
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": RECEIPT_RESPONSE_SCHEMA,
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    data = await _request_with_retry(url, headers=headers, payload=payload)

    candidates = data.get("candidates", [])
    if not candidates:
        raise OCRUpstreamError("Gemini Vision tidak mengembalikan kandidat jawaban.")
    parts = candidates[0].get("content", {}).get("parts", [])
    raw_text = parts[0].get("text", "") if parts else ""
    if not raw_text.strip():
        raise OCRUpstreamError("Gemini Vision mengembalikan teks kosong.")

    parsed = _parse_ocr_json(raw_text)
    parsed["provider"] = "gemini_vision"
    return parsed


async def _call_groq_vision(image_bytes: bytes, mime_type: str, api_key: str) -> Dict[str, Any]:
    model = (
        os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
        or "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    url = "https://api.groq.com/openai/v1/chat/completions"
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_receipt_prompt()},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = await _request_with_retry(url, headers=headers, payload=payload)

    choices = data.get("choices", [])
    if not choices:
        raise OCRUpstreamError("Groq Vision tidak mengembalikan pilihan jawaban.")
    raw_text = choices[0].get("message", {}).get("content", "") or ""
    if not raw_text.strip():
        raise OCRUpstreamError("Groq Vision mengembalikan teks kosong.")

    parsed = _parse_ocr_json(raw_text)
    parsed["provider"] = "groq_vision"
    return parsed


async def parse_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """Memvalidasi gambar nota dan mengekstrak item terstruktur via Gemini Vision + fallback Groq Vision."""
    clean_mime = validate_image_upload(image_bytes, mime_type)

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not gemini_key and not groq_key:
        raise OCRNotConfiguredError(
            "GEMINI_API_KEY (atau GROQ_API_KEY fallback) belum diisi untuk pemindaian foto nota."
        )

    await _throttle_ocr()

    if gemini_key:
        try:
            return await _call_gemini_vision(image_bytes, clean_mime, gemini_key)
        except (OCRRateLimitError, OCRUpstreamError) as primary_exc:
            if groq_key:
                result = await _call_groq_vision(image_bytes, clean_mime, groq_key)
                result["warnings"].append(
                    f"Gemini Vision dialihkan ke fallback Groq Vision ({primary_exc})."
                )
                return result
            raise

    return await _call_groq_vision(image_bytes, clean_mime, groq_key)
