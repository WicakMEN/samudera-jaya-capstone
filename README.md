# Samudera Jaya Capstone — Sistem Digitalisasi Transaksi, Stok, & AI Restock

Repositori *monorepo* proyek Capstone **Asah 2026 led by Dicoding supported by GoTo** oleh **Tim A26-CS098** untuk mitra **UMKM Samudera Jaya** (Food & Beverage).

## Deskripsi Proyek

Sistem ini memodernisasi operasional UMKM Samudera Jaya melalui ekosistem web terpadu yang mencakup:
1. **Web Katalog Publik:** Pelanggan melihat menu & ketersediaan stok *real-time*, lalu memesan langsung via **WhatsApp Click-to-Chat** ke pemilik sembari mencatat pesanan ke antrean kasir.
2. **Web Dashboard Kasir & Inventaris:** Mencatat transaksi *offline* maupun mengonfirmasi pesanan *online* (`"Selesai"`), yang otomatis menghitung omzet, memotong stok bahan baku sesuai resep, dan memunculkan *alert* saat stok menyentuh batas *Reorder Point* (`<= ROP`).
3. **Asisten Cerdas AI Restock (FastAPI):** Pemilik dapat memperbarui stok belanja pasar melalui input bahasa alami (teks/suara) atau foto nota belanja (OCR/Vision) yang diubah menjadi kartu konfirmasi interaktif dengan *guardrails* ketat.
4. **Dasbor Analitik Data Science:** Visualisasi tren penjualan harian, menu terlaris, dan rekomendasi estimasi kebutuhan belanja bahan baku berikutnya.

---

## Dokumentasi Referensi Tim
- **[docs/PROJECT_CONTEXT.md](./docs/PROJECT_CONTEXT.md):** Konteks proyek, arsitektur sistem, alur kerja utama, aturan *guardrails* AI, pembagian tugas tim, jadwal pengerjaan, dan rencana pengujian.
- **[docs/API_CONTRACT.md](./docs/API_CONTRACT.md):** Kontrak skema endpoint REST API utama (Node.js/Express) dan layanan AI (`POST /api/v1/ai/restock-parse` di FastAPI) beserta contoh payload JSON.

---

## Struktur Folder Monorepo

```text
samudera-jaya-capstone/
├── docs/
│   ├── PROJECT_CONTEXT.md       # Pedoman konteks proyek & aturan guardrails
│   └── API_CONTRACT.md          # Kontrak skema REST API & AI Service
├── frontend/                    # Web Katalog Publik & Web Dashboard (Vite + React + Axios)
├── backend/                     # REST API Utama & Logika Stok/ROP (Node.js + Express)
├── ai-service/                  # Layanan AI Restock (Python + FastAPI)
│   ├── app/                     # Source code FastAPI, endpoint, & inference pipeline
│   ├── data/                    # Dataset bersih, data dictionary, & contoh nota
│   ├── models/                  # Artefak model terlatih (di-ignore Git: *.pkl, *.pt)
│   └── notebooks/               # Eksplorasi data (EDA), eksperimen model, & analisis ROP
├── .gitignore
└── README.md
```

---

## Panduan Alur Git Branching Tim

Agar seluruh anggota tim dapat bekerja secara paralel tanpa saling menimpa kode, gunakan struktur *branch* berikut:

| Branch | Fokus Pengerjaan | Penanggung Jawab Utama |
| :--- | :--- | :--- |
| `main` | Kode stabil siap demo/rilis (*protected*, hanya menerima merge via Pull Request). | Seluruh Tim (Review Bersama) |
| `feat/frontend-dashboard` | Web Katalog publik (WA Click-to-Chat), Web Dashboard kasir, kartu konfirmasi AI, & grafik analitik (`/frontend`). | Muhammad Rafie Afkar Yunansyah |
| `feat/backend-api` | REST API Express, skema PostgreSQL, logika pemotongan stok resep, ROP alert, & ekspor laporan (`/backend`). | Mochamad Fahrul Rizqi |
| `feat/ds-analytics-rop` | Pembersihan data historis, *data dictionary*, pemodelan tren penjualan & kalkulasi ROP (`/ai-service/data`, `/ai-service/notebooks`). | I Gede Putu Oka Pramana Putra & Titi Alfiana Pramesti |
| `feat/ai-restock-fastapi` | Model kustom NLP ekstraksi entitas, integrasi Multimodal LLM/OCR nota, & serving FastAPI (`/ai-service/app`, `/ai-service/models`). | Haryo Wicaksono & Muhammad Faiz Adya |

### Aturan Kerja Git
1. **Selalu sinkronisasi sebelum mulai bekerja:**
   ```bash
   git checkout main
   git pull origin main
   git checkout <nama-branch-fitur>
   git merge main
   ```
2. **Jangan commit langsung ke `main`.** Setiap perubahan pada branch fitur digabungkan ke `main` melalui **Pull Request (PR)** dengan minimal 1 *reviewer* dari anggota tim lain.
3. **Pastikan `.env`, `node_modules/`, `dist/`, `__pycache__/`, dan file model besar (`*.pkl`, `*.pt`) tidak ikut ter-commit** (sudah diatur di `.gitignore`).
4. **Gunakan pesan commit yang jelas**, misalnya:
   - `feat(backend): add automatic ingredient deduction on order completion`
   - `feat(ai): implement restock-parse endpoint with domain guardrails`
   - `docs(api): update restock-parse response schema`
