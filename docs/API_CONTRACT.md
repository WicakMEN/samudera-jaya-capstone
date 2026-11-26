# API Contract — UMKM Samudera Jaya (Tim A26-CS098)

Dokumen ini mendefinisikan kontrak skema REST API antara **Frontend (Vite/React)**, **Backend Utama (Node.js/Express)**, dan **Layanan AI (Python/FastAPI)** agar seluruh anggota tim dapat bekerja paralel menggunakan format payload yang seragam.

---

## Konvensi Umum

- **Base URL Backend (Node.js/Express):** `http://localhost:3000/api/v1` (atau URL deployment Railway/Render)
- **Base URL AI Service (FastAPI):** `http://localhost:8000/api/v1/ai` (atau URL deployment Railway/Render)
- **Content-Type:** `application/json` (kecuali unggah foto nota pada endpoint AI yang mendukung `multipart/form-data`).

### Format Standar Respons Sukses
```json
{
  "success": true,
  "message": "Deskripsi singkat hasil operasi",
  "data": {}
}
```

### Format Standar Respons Error
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Kuantitas tidak boleh bernilai nol atau negatif",
    "details": []
  }
}
```

Kode status HTTP utama: `200 OK`, `201 Created`, `400 Bad Request`, `404 Not Found`, `422 Unprocessable Entity`, `429 Too Many Requests`, `500 Internal Server Error`.

---

## 1. Backend Utama — Node.js / Express (`/api/v1`)

### 1.1 Health Check
- **Endpoint:** `GET /api/v1/health`
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Backend API is running",
  "data": {
    "status": "ok",
    "timestamp": "2026-11-26T12:00:00Z"
  }
}
```

---

### 1.2 Katalog & Daftar Menu
- **Endpoint:** `GET /api/v1/menus`
- **Deskripsi:** Mengambil daftar menu beserta harga dan ketersediaan stok *real-time* (dihitung dari stok bahan baku sesuai resep) untuk Web Katalog publik dan layar Kasir.
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Daftar menu berhasil diambil",
  "data": [
    {
      "id": 1,
      "name": "Mie Ayam Original",
      "category": "Makanan",
      "price": 15000,
      "is_available": true,
      "max_servings_available": 25,
      "image_url": "/images/mie-ayam.jpg"
    },
    {
      "id": 2,
      "name": "Bakso Yamin",
      "category": "Makanan",
      "price": 18000,
      "is_available": true,
      "max_servings_available": 18,
      "image_url": "/images/bakso-yamin.jpg"
    }
  ]
}
```

---

### 1.3 Pesanan Online (Web Katalog -> Antrean Kasir + WhatsApp Click-to-Chat)
- **Endpoint:** `POST /api/v1/orders`
- **Deskripsi:** Menyimpan pesanan baru dari Web Katalog dengan status `"Menunggu Konfirmasi"` dan mengembalikan teks/URL WhatsApp *Click-to-Chat* terformat ke nomor pemilik.
- **Request Body:**
```json
{
  "customer_name": "Budi",
  "notes": "Bakso pisah kuah, tidak pakai seledri",
  "items": [
    { "menu_id": 1, "quantity": 2 },
    { "menu_id": 2, "quantity": 1 }
  ]
}
```
- **Validasi:** `items` tidak boleh kosong; `quantity` harus integer `> 0`.
- **Respons `201 Created`:**
```json
{
  "success": true,
  "message": "Pesanan masuk ke antrean kasir",
  "data": {
    "order_id": 104,
    "order_code": "ORD-20261126-104",
    "status": "Menunggu Konfirmasi",
    "total_amount": 48000,
    "whatsapp_url": "https://wa.me/6281234567890?text=Halo%20Samudera%20Jaya...",
    "created_at": "2026-11-26T12:10:00Z"
  }
}
```

---

### 1.4 Daftar Antrean & Riwayat Pesanan
- **Endpoint:** `GET /api/v1/orders?status=Menunggu Konfirmasi`
- **Deskripsi:** Mengambil daftar pesanan untuk Web Dashboard kasir (bisa difilter berdasarkan `status`: `Menunggu Konfirmasi`, `Selesai`, `Dibatalkan`).
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Daftar pesanan berhasil diambil",
  "data": [
    {
      "order_id": 104,
      "order_code": "ORD-20261126-104",
      "customer_name": "Budi",
      "channel": "online_katalog",
      "status": "Menunggu Konfirmasi",
      "total_amount": 48000,
      "items": [
        { "menu_id": 1, "menu_name": "Mie Ayam Original", "quantity": 2, "subtotal": 30000 },
        { "menu_id": 2, "menu_name": "Bakso Yamin", "quantity": 1, "subtotal": 18000 }
      ],
      "created_at": "2026-11-26T12:10:00Z"
    }
  ]
}
```

---

### 1.5 Konfirmasi Status Pesanan ("Selesai") & Pemotongan Stok Otomatis
- **Endpoint:** `PATCH /api/v1/orders/:id/status`
- **Deskripsi:** Mengubah status pesanan online menjadi `"Selesai"` (atau `"Dibatalkan"`). Jika `"Selesai"`, backend otomatis menambahkan omzet, memotong stok bahan baku sesuai formula resep, dan mengembalikan daftar bahan yang menyentuh batas ROP (`<= ROP`).
- **Request Body:**
```json
{
  "status": "Selesai"
}
```
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Pesanan selesai dan stok bahan baku berhasil dipotong",
  "data": {
    "order_id": 104,
    "status": "Selesai",
    "total_amount": 48000,
    "deducted_ingredients": [
      { "ingredient_id": 1, "name": "Mie Basah", "deducted_qty": 300, "unit": "gram", "remaining_stock": 1200, "rop": 1500, "is_low_stock": true },
      { "ingredient_id": 2, "name": "Bakso", "deducted_qty": 5, "unit": "butir", "remaining_stock": 85, "rop": 30, "is_low_stock": false }
    ],
    "low_stock_alerts": [
      { "ingredient_id": 1, "name": "Mie Basah", "remaining_stock": 1200, "rop": 1500, "unit": "gram" }
    ]
  }
}
```

---

### 1.6 Pencatatan Transaksi Offline Kasir
- **Endpoint:** `POST /api/v1/transactions/offline`
- **Deskripsi:** Kasir mencatat transaksi pembeli makan di tempat secara langsung. Langsung berstatus `"Selesai"`, menambah omzet, memotong stok bahan baku, dan mengecek alert ROP.
- **Request Body:**
```json
{
  "payment_method": "tunai",
  "notes": "Meja 3",
  "items": [
    { "menu_id": 1, "quantity": 3 }
  ]
}
```
- **Validasi:** `items` wajib ada, `quantity > 0`.
- **Respons `201 Created`:**
```json
{
  "success": true,
  "message": "Transaksi offline berhasil disimpan dan stok diperbarui",
  "data": {
    "order_id": 105,
    "order_code": "TRX-20261126-105",
    "channel": "offline_kasir",
    "status": "Selesai",
    "total_amount": 45000,
    "low_stock_alerts": []
  }
}
```

---

### 1.7 Daftar Inventaris Bahan Baku & Status ROP
- **Endpoint:** `GET /api/v1/ingredients`
- **Deskripsi:** Mengambil daftar bahan baku, sisa stok, satuan standar, nilai ROP, dan flag `is_low_stock` (`current_stock <= rop`).
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Data inventaris berhasil diambil",
  "data": [
    {
      "id": 1,
      "name": "Mie Basah",
      "current_stock": 1200,
      "unit": "gram",
      "rop": 1500,
      "is_low_stock": true,
      "updated_at": "2026-11-26T12:15:00Z"
    },
    {
      "id": 2,
      "name": "Bakso",
      "current_stock": 85,
      "unit": "butir",
      "rop": 30,
      "is_low_stock": false,
      "updated_at": "2026-11-26T12:15:00Z"
    }
  ]
}
```

---

### 1.8 Simpan Penambahan Stok (Restock Terkonfirmasi / Manual)
- **Endpoint:** `POST /api/v1/ingredients/restock`
- **Deskripsi:** Menyimpan penambahan stok ke database setelah pemilik mengklik **"Ya, Simpan"** pada kartu konfirmasi Asisten AI Restock atau dari formulir *restock* manual.
- **Request Body:**
```json
{
  "source": "ai_assistant",
  "notes": "Belanja pasar pagi",
  "items": [
    { "ingredient_id": 1, "quantity": 5000, "unit": "gram" },
    { "ingredient_id": 2, "quantity": 100, "unit": "butir" }
  ]
}
```
- **Validasi:** `quantity` harus `> 0` dan tidak melebihi batas maksimal wajar.
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Stok bahan baku berhasil ditambahkan",
  "data": {
    "updated_items": [
      { "ingredient_id": 1, "name": "Mie Basah", "added_qty": 5000, "new_stock": 6200, "unit": "gram", "is_low_stock": false },
      { "ingredient_id": 2, "name": "Bakso", "added_qty": 100, "new_stock": 185, "unit": "butir", "is_low_stock": false }
    ]
  }
}
```

---

### 1.9 Penyesuaian Stok Manual (*Stock Adjustment*)
- **Endpoint:** `PATCH /api/v1/ingredients/:id/adjust`
- **Deskripsi:** Koreksi stok manual oleh pemilik jika terjadi selisih fisik (*human error* / bahan rusak) disertai alasan penyesuaian.
- **Request Body:**
```json
{
  "new_stock": 1000,
  "reason": "Penyesuaian stok fisik sore, ada bahan rusak 200 gram"
}
```
- **Validasi:** `new_stock >= 0`; `reason` wajib diisi.
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Penyesuaian stok berhasil dicatat",
  "data": {
    "ingredient_id": 1,
    "previous_stock": 1200,
    "new_stock": 1000,
    "reason": "Penyesuaian stok fisik sore, ada bahan rusak 200 gram"
  }
}
```

---

### 1.10 Ringkasan Analitik Bisnis & Rekomendasi Belanja (Data Science)
- **Endpoint:** `GET /api/v1/analytics/summary?days=7`
- **Deskripsi:** Mengambil data grafik tren penjualan harian, menu terlaris, dan estimasi kebutuhan belanja stok berikutnya. Jika data transaksi masih kosong, tetap mengembalikan `200 OK` dengan `is_empty: true`.
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Data analitik berhasil diambil",
  "data": {
    "is_empty": false,
    "total_revenue": 2450000,
    "total_orders": 142,
    "daily_sales_trend": [
      { "date": "2026-11-20", "revenue": 320000, "orders": 19 },
      { "date": "2026-11-21", "revenue": 385000, "orders": 22 }
    ],
    "top_menus": [
      { "menu_id": 1, "name": "Mie Ayam Original", "total_sold": 85 },
      { "menu_id": 2, "name": "Bakso Yamin", "total_sold": 57 }
    ],
    "restock_recommendations": [
      {
        "ingredient_id": 1,
        "name": "Mie Basah",
        "current_stock": 1200,
        "rop": 1500,
        "recommended_buy_qty": 5000,
        "unit": "gram",
        "priority": "high"
      }
    ]
  }
}
```

---

### 1.11 Ekspor Laporan Penjualan (Fitur Tambahan)
- **Endpoint:** `GET /api/v1/reports/sales/export?format=csv&start_date=2026-11-01&end_date=2026-11-30`
- **Deskripsi:** Mengunduh rekapitulasi penjualan berkala dalam format `csv` atau `pdf`.
- **Respons `200 OK`:** File stream (`text/csv` atau `application/pdf`) dengan header `Content-Disposition: attachment; filename="laporan-penjualan.csv"`.

---

### 1.12 Autentikasi Kasir & Pemilik (Pemisahan Akses Publik vs Admin)
- **Endpoint:** `POST /api/v1/auth/login`
- **Deskripsi:** Memverifikasi kredensial pemilik/kasir sebelum mengakses rute `/dashboard`.
- **Request Body:**
```json
{
  "username": "admin",
  "password": "samudera2026"
}
```
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "Login berhasil",
  "data": {
    "token": "mock-admin-session-token",
    "user": { "username": "admin", "role": "owner" }
  }
}
```

---

## 2. Layanan AI — Python / FastAPI (`/api/v1/ai`)

### 2.1 Health Check AI Service
- **Endpoint:** `GET /api/v1/ai/health`
- **Respons `200 OK`:**
```json
{
  "success": true,
  "message": "FastAPI AI Restock Service is running",
  "data": {
    "status": "ok",
    "nlp_model_loaded": true,
    "llm_provider": "gemini"
  }
}
```

---

### 2.2 Ekstraksi Input Restock AI (NLP Teks/Suara & OCR Nota Belanja)
- **Endpoint:** `POST /api/v1/ai/restock-parse`
- **Deskripsi:** Memproses input bahasa alami (teks atau hasil *Voice-to-Text*) dan/atau foto nota belanja fisik (OCR/Vision), melakukan klasifikasi *intent* & ekstraksi entitas bahan baku beserta kuantitasnya, lalu mengembalikan struktur data untuk ditampilkan sebagai **kartu konfirmasi interaktif** di dashboard.
- **Catatan Penting:** Endpoint ini **bersifat read-only terhadap database inventaris** (hanya melakukan parsing & validasi *guardrails*; penyimpanan ke database dilakukan oleh frontend ke `POST /api/v1/ingredients/restock` setelah pemilik menekan **"Ya, Simpan"**).

#### Opsi A — Request JSON (Input Teks / Transkrip Suara)
`Content-Type: application/json`
```json
{
  "input_type": "text",
  "text": "beli mie basah 5 kg dan bakso 100 butir"
}
```

#### Opsi B — Request Multipart Form-Data (Unggah Foto Nota Belanja OCR/Vision)
`Content-Type: multipart/form-data`
- `input_type`: `"image"` (atau `"hybrid"` jika disertai catatan teks)
- `image`: file gambar nota belanja (`image/jpeg`, `image/png`, `image/webp`)
- `text`: *(opsional)* catatan tambahan dari pemilik

#### Respons `200 OK` — Input Valid (Siap Ditampilkan ke Kartu Konfirmasi)
```json
{
  "success": true,
  "message": "Ekstraksi restock berhasil",
  "data": {
    "is_valid_context": true,
    "intent": "restock_inventaris",
    "requires_confirmation": true,
    "raw_extracted_text": "beli mie basah 5 kg dan bakso 100 butir",
    "items": [
      {
        "raw_name": "mie basah",
        "matched_ingredient_name": "Mie Basah",
        "quantity": 5,
        "unit": "kg",
        "normalized_quantity": 5000,
        "normalized_unit": "gram",
        "confidence": 0.96
      },
      {
        "raw_name": "bakso",
        "matched_ingredient_name": "Bakso",
        "quantity": 100,
        "unit": "butir",
        "normalized_quantity": 100,
        "normalized_unit": "butir",
        "confidence": 0.98
      }
    ],
    "warnings": [],
    "model_used": "custom_nlp_v1+gemini"
  }
}
```

#### Respons `422 Unprocessable Entity` — Ditolak oleh Guardrails (Di Luar Konteks / Ambigu / Tidak Valid)
Contoh input: `"siapa presiden indonesia sekarang?"` atau `"beli mie basah -5 kg"`.
```json
{
  "success": false,
  "error": {
    "code": "OUT_OF_CONTEXT_OR_INVALID",
    "message": "Input di luar konteks pencatatan stok/belanja bahan baku kuliner atau kuantitas tidak valid. Silakan masukkan rincian belanja bahan baku yang jelas atau gunakan formulir restock manual.",
    "details": {
      "is_valid_context": false,
      "intent": "out_of_scope",
      "requires_manual_fallback": false
    }
  }
}
```
