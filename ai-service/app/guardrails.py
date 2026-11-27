"""Lapisan Guardrails AI untuk menolak input di luar konteks kuliner/inventaris atau bernilai tidak valid."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "intent_classifier.pkl"
_cached_model = None


def load_intent_model():
    global _cached_model
    if _cached_model is None and MODEL_PATH.exists():
        _cached_model = joblib.load(MODEL_PATH)
    return _cached_model


def is_model_loaded() -> bool:
    return load_intent_model() is not None


def validate_restock_request(text: str, extracted_items: List[Dict[str, Any]]) -> Tuple[bool, str, Optional[str]]:
    """Mengembalikan (is_valid, intent, error_message)."""
    clean_text = (text or "").strip()
    if not clean_text:
        return False, "out_of_scope", "Input teks kosong. Masukkan rincian belanja bahan baku atau unggah foto nota."

    model = load_intent_model()
    predicted_intent = "restock_inventaris"
    if model is not None:
        predicted_intent = str(model.predict([clean_text])[0])

    # Guardrail 1: Jika model mengklasifikasikan out_of_scope dan tidak ada entitas bahan baku valid
    if predicted_intent == "out_of_scope" and len(extracted_items) == 0:
        return (
            False,
            "out_of_scope",
            "Input di luar konteks pencatatan stok/belanja bahan baku kuliner. "
            "Silakan masukkan rincian belanja bahan baku yang jelas atau gunakan formulir restock manual.",
        )

    # Guardrail 2: Jika intent restock tapi tidak ada satupun bahan + kuantitas yang bisa diekstrak
    if len(extracted_items) == 0:
        return (
            False,
            "ambiguous_input",
            "Nama bahan baku atau kuantitas tidak terdeteksi dengan jelas. "
            "Contoh format: 'beli mie basah 5 kg dan bakso 100 butir'.",
        )

    # Guardrail 3: Tolak kuantitas nol, negatif, atau melebihi batas wajar
    for item in extracted_items:
        qty = float(item["normalized_quantity"])
        if qty <= 0:
            return (
                False,
                "invalid_quantity",
                f"Kuantitas untuk '{item['matched_ingredient_name']}' tidak boleh nol atau negatif ({item['quantity']}).",
            )
        if qty > 1_000_000:
            return (
                False,
                "invalid_quantity",
                f"Kuantitas untuk '{item['matched_ingredient_name']}' melebihi batas maksimal wajar.",
            )

    return True, "restock_inventaris", None
