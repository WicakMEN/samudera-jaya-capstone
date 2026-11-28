"""Ekstraktor entitas bahan baku, kuantitas, dan normalisasi satuan dari teks maupun output OCR."""

import re
from typing import Any, Dict, List, Optional, Tuple

# ponytail: Daftar bahan aktif di backend/src/data/mockStore.js masih hardcoded 4 item;
# ganti ke cache GET /api/v1/ingredients setelah backend migrasi ke PostgreSQL.
BACKEND_REGISTERED_INGREDIENTS = {"Mie Basah", "Bakso", "Bumbu Yamin", "Kemasan Bowl"}

# Kamus bahan baku standar UMKM Samudera Jaya (Mock Store + Dataset Dummy Drive + Menu Real UMKM)
INGREDIENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "Mie Basah": {
        "standard_unit": "gram",
        "aliases": ["mie basah mentah", "mie basah", "mie mentah", "mie kuning", "mi basah", "mi kuning", "mie"],
    },
    "Bakso": {
        "standard_unit": "butir",
        "aliases": ["bakso halus sapi", "bakso sapi", "bakso halus", "pentol bakso", "bakso", "baso", "pentol"],
    },
    "Bumbu Yamin": {
        "standard_unit": "gram",
        "aliases": ["bumbu yamin", "bumbu mie", "bumbu"],
    },
    "Kemasan Bowl": {
        "standard_unit": "pcs",
        "aliases": [
            "kantong & cup takeaway",
            "kantong dan cup takeaway",
            "cup takeaway",
            "kantong takeaway",
            "kantong plastik",
            "kemasan bowl",
            "mangkok kemasan",
            "mangkok",
            "bowl",
            "kemasan",
            "cup",
        ],
    },
    "Daging Ayam": {
        "standard_unit": "gram",
        "aliases": [
            "daging ayam olahan",
            "daging ayam",
            "ayam olahan",
            "ayam fillet",
            "fillet ayam",
            "dada ayam",
            "paha ayam",
            "ayam suwir",
        ],
    },
    "Ceker Ayam": {
        "standard_unit": "gram",
        "aliases": ["ceker ayam", "ceker"],
    },
    "Telur": {
        "standard_unit": "butir",
        "aliases": ["telur ayam", "telor ayam", "telur", "telor"],
    },
    "Kulit Pangsit": {
        "standard_unit": "lembar",
        "aliases": ["kulit pangsit", "pangsit mentah"],
    },
    "Sawi Hijau": {
        "standard_unit": "gram",
        "aliases": ["sawi hijau", "sayur sawi", "caisim", "cesim", "sawi"],
    },
    "Minyak Bawang": {
        "standard_unit": "ml",
        "aliases": ["minyak bawang & bumbu", "minyak bawang dan bumbu", "minyak bawang", "minyak ayam"],
    },
    "Kecap Manis": {
        "standard_unit": "botol",
        "aliases": ["kecap manis", "kecap"],
    },
    "Teh Botol Sosro": {
        "standard_unit": "botol",
        "aliases": ["teh botol sosro", "teh botol"],
    },
    "Air Mineral": {
        "standard_unit": "botol",
        "aliases": ["air mineral 600ml", "air mineral", "aqua"],
    },
}

INGREDIENT_ALIASES: Dict[str, Dict[str, str]] = {
    alias: {"canonical": canonical, "standard_unit": meta["standard_unit"]}
    for canonical, meta in INGREDIENT_CATALOG.items()
    for alias in meta["aliases"]
}

UNIT_CONVERSIONS: Dict[str, Tuple[str, float]] = {
    "kg": ("gram", 1000.0),
    "kilogram": ("gram", 1000.0),
    "ons": ("gram", 100.0),
    "gram": ("gram", 1.0),
    "gr": ("gram", 1.0),
    "g": ("gram", 1.0),
    "liter": ("ml", 1000.0),
    "ltr": ("ml", 1000.0),
    "l": ("ml", 1000.0),
    "ml": ("ml", 1.0),
    "mililiter": ("ml", 1.0),
    "butir": ("butir", 1.0),
    "biji": ("butir", 1.0),
    "lembar": ("lembar", 1.0),
    "lbr": ("lembar", 1.0),
    "botol": ("botol", 1.0),
    "btl": ("botol", 1.0),
    "pcs": ("pcs", 1.0),
    "buah": ("pcs", 1.0),
    "bungkus": ("pcs", 1.0),
    "bks": ("pcs", 1.0),
}

SPECIAL_UNITS = {"lusin", "kodi", "porsi", "rak", "tray", "pak", "pack", "ikat", "dus", "karton", "bal", "ball", "plastik"}
ALL_UNITS = sorted(set(UNIT_CONVERSIONS.keys()) | SPECIAL_UNITS, key=len, reverse=True)
UNITS_PATTERN = "|".join(re.escape(u) for u in ALL_UNITS)

# Guard agar kata 'mie'/'bakso' tidak menangkap nama menu pesanan pelanggan ('mie ayam', 'mie yamin', 'bakso kuah')
ALIAS_LOOKAHEADS = {
    "mie": r"mie(?!\s+(?:ayam|yamin|bakso|baso|kuah)\b)",
    "bakso": r"bakso(?!\s+kuah\b)",
    "baso": r"baso(?!\s+kuah\b)",
}


def _alias_to_regex(alias: str) -> str:
    return ALIAS_LOOKAHEADS.get(alias, re.escape(alias))


ALIASES_PATTERN = "|".join(_alias_to_regex(a) for a in sorted(INGREDIENT_ALIASES.keys(), key=len, reverse=True))

NAME_FIRST_REGEX = re.compile(
    rf"\b(?P<name>{ALIASES_PATTERN})(?:\s+(?:sebanyak|seberat|sejumlah))?(?:\s*[:=]\s*|\s+-\s+|\s+)(?P<qty>-?\d+(?:[.,]\d+)?)\s*(?P<unit>{UNITS_PATTERN})\b",
    re.IGNORECASE,
)

QTY_FIRST_REGEX = re.compile(
    rf"(?<!\w)(?P<qty>-?\d+(?:[.,]\d+)?)\s*(?P<unit>{UNITS_PATTERN})\s+(?:bahan\s+)?(?P<name>{ALIASES_PATTERN})\b",
    re.IGNORECASE,
)

PRICE_PATTERNS = [
    re.compile(r"\brp\.?\s*\d+(?:[.,]\d+)*", re.IGNORECASE),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:rb|ribu|jt|juta|rupiah)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:[.,]\d+)?k\b", re.IGNORECASE),
]

FRACTION_UNIT_LOOKAHEAD = r"(?=\s*(?:kg|kilogram|ons|liter|ltr|l|lusin|kodi)\b)"
FRACTION_PATTERNS = [
    (re.compile(rf"\btiga\s+setengah{FRACTION_UNIT_LOOKAHEAD}", re.IGNORECASE), "3.5"),
    (re.compile(rf"\bdua\s+setengah{FRACTION_UNIT_LOOKAHEAD}", re.IGNORECASE), "2.5"),
    (re.compile(rf"\bsatu\s+setengah{FRACTION_UNIT_LOOKAHEAD}", re.IGNORECASE), "1.5"),
    (re.compile(rf"\bsetengah{FRACTION_UNIT_LOOKAHEAD}", re.IGNORECASE), "0.5"),
    (re.compile(rf"\bseperempat{FRACTION_UNIT_LOOKAHEAD}", re.IGNORECASE), "0.25"),
]


def get_known_ingredients_summary() -> List[Dict[str, str]]:
    """Ringkasan bahan baku standar untuk diinjeksikan ke prompt OCR Vision."""
    return [
        {"name": canonical, "standard_unit": meta["standard_unit"]}
        for canonical, meta in INGREDIENT_CATALOG.items()
    ]


def _strip_prices(text: str) -> str:
    cleaned = text
    for pat in PRICE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    return cleaned


def _normalize_fractions(text: str) -> str:
    cleaned = text
    for pat, replacement in FRACTION_PATTERNS:
        cleaned = pat.sub(replacement, cleaned)
    return cleaned


def _resolve_alias(raw_name: str) -> Optional[Dict[str, str]]:
    lowered = raw_name.strip().lower()
    if lowered in INGREDIENT_ALIASES:
        return INGREDIENT_ALIASES[lowered]

    # Fallback untuk hasil OCR seperti "Bakso Sapi Halus Cap Bola"
    for alias in sorted(INGREDIENT_ALIASES.keys(), key=len, reverse=True):
        pattern = rf"\b{_alias_to_regex(alias)}\b"
        if re.search(pattern, lowered):
            return INGREDIENT_ALIASES[alias]
    return None


def _clean_number(val: float) -> float | int:
    return int(val) if float(val).is_integer() else round(float(val), 4)


def normalize_item(
    raw_name: str,
    raw_qty: float,
    raw_unit: str,
    confidence: float = 0.94,
) -> Tuple[Dict[str, Any], List[str]]:
    """Menormalisasi satu item bahan & kuantitas (dipakai bersama oleh jalur NLP teks dan OCR Vision)."""
    warnings: List[str] = []
    clean_name = " ".join((raw_name or "").strip().split())
    clean_unit = (raw_unit or "").strip().lower() or "pcs"

    alias_info = _resolve_alias(clean_name)
    if alias_info:
        canonical = alias_info["canonical"]
        standard_unit: Optional[str] = alias_info["standard_unit"]
        eff_conf = round(float(confidence), 2)
    else:
        canonical = clean_name.title()
        standard_unit = None
        eff_conf = round(min(float(confidence), 0.75), 2)
        warnings.append(
            f"Bahan '{canonical}' belum ada di kamus standar Samudera Jaya; periksa atau edit sebelum menyimpan."
        )

    if clean_unit in UNIT_CONVERSIONS:
        norm_unit, multiplier = UNIT_CONVERSIONS[clean_unit]
    elif clean_unit == "lusin":
        norm_unit, multiplier = (standard_unit or "pcs", 12.0)
    elif clean_unit == "kodi":
        norm_unit, multiplier = (standard_unit or "pcs", 20.0)
    elif clean_unit == "porsi" and canonical == "Mie Basah":
        norm_unit, multiplier = ("gram", 150.0)
    elif clean_unit in {"rak", "tray"} and canonical == "Telur":
        norm_unit, multiplier = ("butir", 30.0)
    else:
        norm_unit, multiplier = (clean_unit, 1.0)

    if standard_unit and norm_unit != standard_unit:
        warnings.append(
            f"Satuan '{clean_unit}' untuk '{canonical}' belum dikonversi otomatis ke satuan standar '{standard_unit}'; periksa sebelum menyimpan."
        )

    if alias_info and canonical not in BACKEND_REGISTERED_INGREDIENTS:
        warnings.append(
            f"Bahan '{canonical}' belum terdaftar di backend mockStore saat ini; pastikan sudah ditambahkan di tabel ingredients sebelum disimpan."
        )

    norm_qty = float(raw_qty) * multiplier
    return (
        {
            "raw_name": clean_name.lower(),
            "matched_ingredient_name": canonical,
            "quantity": _clean_number(float(raw_qty)),
            "unit": clean_unit,
            "normalized_quantity": _clean_number(norm_qty),
            "normalized_unit": norm_unit,
            "confidence": eff_conf,
        },
        warnings,
    )


def _overlaps(span: Tuple[int, int], occupied: List[Tuple[int, int]]) -> bool:
    return any(span[0] < end and span[1] > start for start, end in occupied)


def extract_restock_with_warnings(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Mengekstrak daftar entitas bahan baku (dua arah urutan kata) beserta peringatan normalisasi."""
    prepared = _normalize_fractions(_strip_prices(text or ""))
    matches: List[Tuple[int, Dict[str, Any], List[str]]] = []
    occupied_spans: List[Tuple[int, int]] = []

    for match in NAME_FIRST_REGEX.finditer(prepared):
        occupied_spans.append(match.span())
        raw_qty = float(match.group("qty").replace(",", "."))
        item, item_warnings = normalize_item(
            raw_name=match.group("name"),
            raw_qty=raw_qty,
            raw_unit=match.group("unit"),
            confidence=0.94,
        )
        matches.append((match.start(), item, item_warnings))

    for match in QTY_FIRST_REGEX.finditer(prepared):
        if _overlaps(match.span(), occupied_spans):
            continue
        occupied_spans.append(match.span())
        raw_qty = float(match.group("qty").replace(",", "."))
        item, item_warnings = normalize_item(
            raw_name=match.group("name"),
            raw_qty=raw_qty,
            raw_unit=match.group("unit"),
            confidence=0.93,
        )
        matches.append((match.start(), item, item_warnings))

    matches.sort(key=lambda entry: entry[0])
    items = [entry[1] for entry in matches]
    warnings: List[str] = []
    for entry in matches:
        for warn in entry[2]:
            if warn not in warnings:
                warnings.append(warn)
    return items, warnings


def extract_restock_items(text: str) -> List[Dict[str, Any]]:
    """Wrapper kompatibilitas untuk mengembalikan daftar item saja."""
    return extract_restock_with_warnings(text)[0]
