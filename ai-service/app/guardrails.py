"""Lapisan Guardrails AI untuk menolak input di luar konteks kuliner/inventaris,
serangan prompt injection, chat pesanan pelanggan, serta kuantitas tidak valid.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import joblib

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "intent_classifier.pkl"
_cached_model = None

# Pola defense-in-depth untuk mencegah bypass meski kalimat menyebut kata bahan + angka
NON_RESTOCK_PATTERNS = [
    re.compile(r"\b(?:abaikan\s+(?:semua\s+)?instruksi|ignore\s+(?:all\s+)?(?:previous\s+)?instructions|system\s+prompt|jailbreak)\b", re.IGNORECASE),
    re.compile(r"\b(?:siapa|apa\s+itu|apa\s+perbedaan|bagaimana\s+cara|gimana\s+cara|jelaskan|ceritakan|tuliskan|terjemahkan)\b", re.IGNORECASE),
    re.compile(r"\b(?:buatkan|bikin(?:kan)?)\s+(?:kode|script|puisi|esai|cerita|lagu)\b", re.IGNORECASE),
    re.compile(r"\bberapa\s+(?:kalori|hasil|jarak|harga\s+saham|harga\s+mie|lama\s+merebus|kurs|suhu|dosis)\b", re.IGNORECASE),
    re.compile(r"\bresep\s+(?:cara\s+)?(?:membuat|bikin|masak)\b", re.IGNORECASE),
    re.compile(r"\b(?:rekomendasi\s+(?:film|wisata|hp)|cuaca\s+hari\s+ini|pemenang\s+piala\s+dunia|jadwal\s+pertandingan)\b", re.IGNORECASE),
    re.compile(r"\b(?:mau\s+pes[ae]n|pes[ae]n\s+mie|diantar\s+ke|buka\s+(?:gak|nggak|tidak)|bungkusin|tanpa\s+seledri|pisah\s+kuah|bayar\s+(?:pakai\s+)?qris)\b", re.IGNORECASE),
    re.compile(r"\b(?:bensin|pertamax|solar|semen|pasir|oli\s+motor|pulsa|laptop|sepatu)\b", re.IGNORECASE),
]

# Batas wajar per satuan untuk operasional harian/mingguan UMKM: (hard_max, warn_above)
UNIT_LIMITS: Dict[str, Tuple[float, float]] = {
    "gram": (100_000.0, 25_000.0),  # maks 100 kg, peringatan > 25 kg
    "ml": (50_000.0, 15_000.0),     # maks 50 liter, peringatan > 15 liter
    "butir": (5_000.0, 1_000.0),
    "pcs": (5_000.0, 1_000.0),
    "lembar": (10_000.0, 2_000.0),
    "botol": (500.0, 100.0),
}
DEFAULT_UNIT_LIMIT = (10_000.0, 2_000.0)


def load_intent_model():
    global _cached_model
    if _cached_model is None and MODEL_PATH.exists():
        _cached_model = joblib.load(MODEL_PATH)
    return _cached_model


def reset_model_cache() -> None:
    global _cached_model
    _cached_model = None


def is_model_loaded() -> bool:
    return load_intent_model() is not None


def has_non_restock_pattern(text: str) -> bool:
    clean = (text or "").strip()
    return any(pattern.search(clean) for pattern in NON_RESTOCK_PATTERNS)


def validate_restock_request(
    text: str,
    extracted_items: List[Dict[str, Any]],
    source: str = "text",
) -> Tuple[bool, str, Optional[str], List[str]]:
    """Memvalidasi konteks intent dan batas wajar kuantitas.
    Mengembalikan (is_valid, intent, error_message, warnings).
    """
    clean_text = (text or "").strip()
    warnings: List[str] = []

    if source == "text":
        if not clean_text:
            return (
                False,
                "out_of_scope",
                "Input teks kosong. Masukkan rincian belanja bahan baku atau unggah foto nota.",
                warnings,
            )

        if has_non_restock_pattern(clean_text):
            return (
                False,
                "out_of_scope",
                "Input di luar konteks pencatatan stok/belanja bahan baku kuliner. "
                "Silakan masukkan rincian belanja bahan baku yang jelas atau gunakan formulir restock manual.",
                warnings,
            )

        model = load_intent_model()
        if model is not None:
            predicted_intent = str(model.predict([clean_text])[0])
            if predicted_intent == "out_of_scope":
                return (
                    False,
                    "out_of_scope",
                    "Input di luar konteks pencatatan stok/belanja bahan baku kuliner. "
                    "Silakan masukkan rincian belanja bahan baku yang jelas atau gunakan formulir restock manual.",
                    warnings,
                )

        if len(extracted_items) == 0:
            return (
                False,
                "ambiguous_input",
                "Nama bahan baku atau kuantitas tidak terdeteksi dengan jelas. "
                "Contoh format: 'beli mie basah 5 kg dan bakso 100 butir'.",
                warnings,
            )
    else:
        # Jalur 'ocr' atau 'hybrid' (is_receipt sudah divalidasi oleh Vision API)
        if source == "hybrid" and clean_text and has_non_restock_pattern(clean_text):
            return (
                False,
                "out_of_scope",
                "Catatan teks di luar konteks pencatatan stok/belanja bahan baku kuliner.",
                warnings,
            )

        if len(extracted_items) == 0:
            return (
                False,
                "ambiguous_input",
                "Bahan baku dan kuantitas tidak terbaca jelas dari foto nota. "
                "Silakan foto ulang dengan pencahayaan lebih jelas atau gunakan formulir restock manual.",
                warnings,
            )

    # Validasi kuantitas & ambang batas per satuan untuk seluruh jalur (text, ocr, hybrid)
    for item in extracted_items:
        qty = float(item["normalized_quantity"])
        unit = str(item.get("normalized_unit") or "pcs").lower()
        name = item["matched_ingredient_name"]

        if qty <= 0:
            return (
                False,
                "invalid_quantity",
                f"Kuantitas untuk '{name}' tidak boleh nol atau negatif ({item['quantity']}).",
                warnings,
            )

        hard_max, warn_above = UNIT_LIMITS.get(unit, DEFAULT_UNIT_LIMIT)
        if qty > hard_max:
            return (
                False,
                "invalid_quantity",
                f"Kuantitas untuk '{name}' ({qty:g} {unit}) melebihi batas maksimal wajar ({hard_max:g} {unit}).",
                warnings,
            )

        if qty > warn_above:
            warnings.append(
                f"Kuantitas '{name}' cukup besar ({qty:g} {unit}); pastikan angka sudah sesuai sebelum menyimpan."
            )

    return True, "restock_inventaris", None, warnings
