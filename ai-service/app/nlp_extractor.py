"""Ekstraktor entitas bahan baku, kuantitas, dan normalisasi satuan dari teks bahasa alami."""

import re
from typing import Any, Dict, List

# Kamus bahan baku standar UMKM Samudera Jaya (selaras dengan backend/src/data/mockStore.js)
INGREDIENT_ALIASES = {
    "mie basah": {"canonical": "Mie Basah", "standard_unit": "gram"},
    "mie kuning": {"canonical": "Mie Basah", "standard_unit": "gram"},
    "mie ayam": {"canonical": "Mie Basah", "standard_unit": "gram"},
    "mie": {"canonical": "Mie Basah", "standard_unit": "gram"},
    "bakso": {"canonical": "Bakso", "standard_unit": "butir"},
    "pentol": {"canonical": "Bakso", "standard_unit": "butir"},
    "bumbu yamin": {"canonical": "Bumbu Yamin", "standard_unit": "gram"},
    "bumbu": {"canonical": "Bumbu Yamin", "standard_unit": "gram"},
    "kemasan bowl": {"canonical": "Kemasan Bowl", "standard_unit": "pcs"},
    "mangkok": {"canonical": "Kemasan Bowl", "standard_unit": "pcs"},
    "bowl": {"canonical": "Kemasan Bowl", "standard_unit": "pcs"},
    "kemasan": {"canonical": "Kemasan Bowl", "standard_unit": "pcs"},
}

UNIT_CONVERSIONS = {
    "kg": ("gram", 1000.0),
    "kilogram": ("gram", 1000.0),
    "ons": ("gram", 100.0),
    "gram": ("gram", 1.0),
    "gr": ("gram", 1.0),
    "g": ("gram", 1.0),
    "butir": ("butir", 1.0),
    "biji": ("butir", 1.0),
    "pcs": ("pcs", 1.0),
    "buah": ("pcs", 1.0),
    "bungkus": ("pcs", 1.0),
    "pak": ("pcs", 1.0),
}

# Pola: <nama bahan> <angka (boleh desimal/negatif untuk ditangkap guardrails)> <satuan>
ALIASES_PATTERN = "|".join(sorted(INGREDIENT_ALIASES.keys(), key=len, reverse=True))
UNITS_PATTERN = "|".join(sorted(UNIT_CONVERSIONS.keys(), key=len, reverse=True))
ENTITY_REGEX = re.compile(
    rf"\b(?P<name>{ALIASES_PATTERN})\s+(?P<qty>-?\d+(?:[.,]\d+)?)\s*(?P<unit>{UNITS_PATTERN})\b",
    re.IGNORECASE,
)


def extract_restock_items(text: str) -> List[Dict[str, Any]]:
    """Mengekstrak daftar entitas bahan baku dan menormalisasi satuannya."""
    items: List[Dict[str, Any]] = []
    for match in ENTITY_REGEX.finditer(text):
        raw_name = match.group("name").strip().lower()
        qty_str = match.group("qty").replace(",", ".")
        raw_qty = float(qty_str)
        raw_unit = match.group("unit").strip().lower()

        alias_info = INGREDIENT_ALIASES.get(raw_name)
        if not alias_info:
            continue

        norm_unit, multiplier = UNIT_CONVERSIONS.get(raw_unit, (alias_info["standard_unit"], 1.0))
        norm_qty = raw_qty * multiplier
        if norm_qty.is_integer():
            norm_qty = int(norm_qty)
        if raw_qty.is_integer():
            raw_qty = int(raw_qty)

        items.append(
            {
                "raw_name": raw_name,
                "matched_ingredient_name": alias_info["canonical"],
                "quantity": raw_qty,
                "unit": raw_unit,
                "normalized_quantity": norm_qty,
                "normalized_unit": norm_unit,
                "confidence": 0.94,
            }
        )
    return items
