# Samudera Jaya Capstone — Sistem Digitalisasi Transaksi, Stok, & AI Restock

Repositori *monorepo* proyek Capstone **Asah 2026 led by Dicoding supported by GoTo** oleh **Tim A26-CS098** untuk mitra **UMKM Samudera Jaya** (*Food & Beverage* — Mie Ayam & Bakso Yamin).

---

## 1. Deskripsi Proyek & Permasalahan yang Diselesaikan

- **Pengguna Sasaran:**
  1. **Pelanggan UMKM Samudera Jaya:** Memesan menu secara *online* melalui Web Katalog Publik.
  2. **Pemilik & Kasir (Ibu Sandra Rismayanti):** Mengelola pesanan *online/offline*, memantau stok bahan baku, mencatat *restock* belanja pasar, dan meninjau analitik penjualan melalui Web Dashboard Internal.
- **Kondisi Sebelum Solusi:** Pencatatan transaksi dilakukan secara manual (rentan kesalahan hitung omzet), pemantauan stok bahan baku sering terlewat hingga kehabisan bahan saat operasional, dan pencatatan belanja *restock* pasar harus diinput satu per satu ke buku/formulir.
- **Solusi yang Dikembangkan:**
  1. **Web Katalog Publik (`/`):** Menampilkan menu & ketersediaan porsi *real-time*, terhubung langsung ke WhatsApp pemilik via **Click-to-Chat** sekaligus memasukkan pesanan ke antrean kasir.
  2. **Web Dashboard Internal (`/login` $\rightarrow$ `/dashboard`):** Dilindungi autentikasi admin/kasir untuk konfirmasi pesanan *online* (`Selesai`), pencatatan transaksi *offline*, pemotongan stok bahan baku otomatis sesuai resep, dan peringatan dini saat stok menyentuh batas *Reorder Point* (`<= ROP`).
  3. **Asisten Cerdas AI Restock (FastAPI):** Memproses input bahasa alami (teks/*Voice-to-Text*) dan foto nota belanja (OCR/Vision) menjadi kartu konfirmasi interaktif dengan *guardrails* ketat (*Human-in-the-Loop*).
  4. **Dasbor Analitik Data Science:** Visualisasi tren penjualan harian, menu terlaris, dan rekomendasi estimasi kebutuhan belanja bahan baku berikutnya.

---

## 2. Dokumentasi Referensi Tim

- **[docs/PROJECT_CONTEXT.md](./docs/PROJECT_CONTEXT.md):** Konteks proyek, arsitektur sistem, aturan *guardrails* AI, pembagian tugas 6 anggota tim, jadwal, dan rencana QA.
- **[docs/API_CONTRACT.md](./docs/API_CONTRACT.md):** Kontrak skema REST API Node.js/Express (`/api/v1/*`) dan layanan AI FastAPI (`POST /api/v1/ai/restock-parse`) beserta contoh payload JSON.
- **[docs/SRS_DAN_DESAIN_SISTEM_A26-CS098.pdf](./docs/SRS_DAN_DESAIN_SISTEM_A26-CS098.pdf):** Dokumen SRS lengkap berisi diagram arsitektur, alur *end-to-end*, ERD basis data, kebutuhan fungsional/non-fungsional, dan peta branch tim.

---

## 3. Struktur Folder Monorepo

```text
samudera-jaya-capstone/
├── docs/
│   ├── PROJECT_CONTEXT.md                   # Pedoman konteks & guardrails tim
│   ├── API_CONTRACT.md                      # Kontrak skema REST API & AI Service
│   └── SRS_DAN_DESAIN_SISTEM_A26-CS098.pdf  # Lembar SRS, diagram arsitektur, & ERD
├── frontend/                                # Web Katalog Publik & Dashboard (Vite + React + Tailwind)
│   ├── src/pages/                           # CatalogPage.jsx, LoginPage.jsx, DashboardPage.jsx
│   ├── src/services/api.js                  # Klien Axios ke Backend & AI Service
│   └── .env.example
├── backend/                                 # REST API Utama (Node.js + Express)
│   ├── src/data/mockStore.js                # Mock store sementara (siap migrasi PostgreSQL)
│   ├── src/routes/api.js                    # Endpoint /api/v1/*
│   ├── src/server.js
│   └── .env.example
├── ai-service/                              # Layanan AI Restock & Data Science (Python + FastAPI)
│   ├── app/
│   │   ├── main.py                          # Server FastAPI (/api/v1/ai/health & /restock-parse)
│   │   ├── nlp_extractor.py                 # Ekstraktor entitas bahan baku & normalisasi satuan
│   │   ├── guardrails.py                    # Validasi domain & kuantitas (tolak 422)
│   │   └── ocr_service.py                   # Hook Gemini Vision API untuk OCR nota belanja
│   ├── data/
│   │   └── restock_intent_dataset.csv       # Dataset awal klasifikasi intent (restock vs out_of_scope)
│   ├── models/                              # Artefak model (*.pkl, *.pt di-ignore Git)
│   │   └── model_comparison.json            # Rekap metrik perbandingan model
│   ├── notebooks/
│   │   └── train_and_compare.py             # Script training & perbandingan 3 model NLP
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

---

## 4. Setup Environment & Cara Menjalankan Aplikasi

Pastikan **Node.js (v20/v22+)** dan **Python (3.10+)** sudah terpasang. Jangan pernah melakukan *commit* file `.env` ke Git.

### A. Backend (`/backend` — Port `3000`)
```bash
cd backend
cp .env.example .env   # Di Windows PowerShell: copy .env.example .env
npm install
npm run dev
```
Endpoint aktif di `http://localhost:3000/api/v1/health`.

### B. Frontend (`/frontend` — Port `5173`)
```bash
cd frontend
cp .env.example .env   # Opsional jika pakai port default
npm install
npm run dev
```
- **Web Katalog Publik:** `http://localhost:5173/`
- **Login Dashboard Internal:** `http://localhost:5173/login` *(demo lokal: username `admin`, password `samudera2026`)*

### C. AI Service (`/ai-service` — Port `8000`)
```bash
cd ai-service
cp .env.example .env   # Isi GEMINI_API_KEY jika mengaktifkan OCR foto nota
python -m venv .venv
# Aktifkan venv:
# Windows: .\.venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python notebooks/train_and_compare.py
uvicorn app.main:app --reload --port 8000
```
Dokumentasi interaktif Swagger tersedia di `http://localhost:8000/docs`.

---

## 5. Model AI, Dataset, & Evaluasi (Main Quest & Side Quest)

### Sumber Dataset & Preprocessing
- **Sumber Data:** Dataset awal (`ai-service/data/restock_intent_dataset.csv`, 44 sampel berlabel `restock_inventaris` dan `out_of_scope`) disusun sebagai data sintetis representatif berdasarkan daftar bahan baku UMKM Samudera Jaya (*Mie Basah*, *Bakso*, *Bumbu Yamin*, *Kemasan Bowl*) serta kalimat jebakan di luar konteks. *(Catatan: Data historis operasional UMKM digunakan secara anonim tanpa identitas pelanggan).*
- **Preprocessing:** Lowercasing, ekstraksi fitur `TfidfVectorizer(ngram_range=(1, 2))`, dan pemisahan data terstratifikasi (`train_test_split` 75% latih / 25% uji).

### Perbandingan Model Klasifikasi Intent (Baseline)
Hasil pelatihan menggunakan `ai-service/notebooks/train_and_compare.py`:

| Model | Accuracy | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **TF-IDF + LinearSVC** *(Terpilih)* | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| TF-IDF + LogisticRegression | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| TF-IDF + MultinomialNB | 0.9091 | 0.8333 | 1.0000 | 0.9091 |

- **Alasan Pemilihan:** `TF-IDF + LinearSVC` dipilih karena ringan, cepat saat *inference* di FastAPI, serta mencapai F1-score `1.0000` pada *baseline split* awal untuk membedakan perintah *restock* dari input di luar konteks.
- **Tindak Lanjut Tim AI & DS:** Perluasan dataset/augmentasi, *hyperparameter tuning*, integrasi penuh OCR Gemini Vision (`ocr_service.py`), serta rekap uji penolakan minimal 10 pertanyaan di luar konteks akan diperbarui di bagian ini.
- **Tautan Model ML (Google Drive):** *[Akan diisi tautan folder Google Drive model final dengan akses viewer untuk `capstone@student.devacademy.id` sebelum pengumpulan akhir]*.

---

## 6. Panduan Alur Git Branching Tim

Seluruh anggota bekerja paralel dari `main` sesuai pembagian pada **SRS**:

| Branch | Fokus Pengerjaan | Penanggung Jawab |
| :--- | :--- | :--- |
| `main` | Kode stabil siap integrasi & demo (*protected*, merge via Pull Request). | Seluruh Tim |
| `feat/frontend-dashboard` | Web Katalog (WA Click-to-Chat), Dashboard Kasir, validasi form, grafik analitik, & alert ROP (`/frontend`). | Muhammad Rafie Afkar Yunansyah |
| `feat/backend-api` | Migrasi PostgreSQL, transaksi potong stok resep, ROP alert, proxy AI, & ekspor CSV/PDF (`/backend`). | Mochamad Fahrul Rizqi |
| `feat/ds-analytics-rop` | Pembersihan data, *data dictionary*, *train/test split*, rumus ROP & tren, serta QA Test Log (`/ai-service/data`, `/ai-service/notebooks`). | I Gede Putu Oka P. P. & Titi Alfiana Pramesti |
| `feat/ai-restock-fastapi` | Model NLP kustom, server FastAPI, OCR nota belanja (Gemini Vision + *fallback*), & *guardrails* lanjutan (`/ai-service/app`, `/ai-service/models`). | Haryo Wicaksono & Muhammad Faiz Adya |

### Aturan Kerja Git
1. **Sinkronisasi sebelum mulai:** `git checkout main && git pull origin main`, lalu masuk ke branch masing-masing (`git checkout <branch>`).
2. **Jangan commit langsung ke `main`** selama pengembangan fitur; gunakan **Pull Request (PR)** untuk *merge* ke `main`.
3. **Pastikan `.env`, `node_modules/`, `dist/`, `.venv/`, `__pycache__/`, dan `*.pkl`/`*.pt` tidak ter-commit.**
