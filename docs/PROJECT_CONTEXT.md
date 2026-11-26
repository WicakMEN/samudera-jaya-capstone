# Project Context — UMKM Samudera Jaya (Tim A26-CS098)

Dokumen ini merupakan pedoman tetap (*system context*) bagi seluruh anggota tim dan AI coding agent di workspace monorepo ini. Seluruh informasi disarikan dari Dokumen Project Plan **Asah 2026 led by Dicoding supported by GoTo**.

---

## 1. Identitas Proyek & Mitra
- **ID Tim Capstone:** `A26-CS098`
- **Mitra UMKM:** Samudera Jaya (Bidang: *Food and Beverage* — menu utama antara lain Mie Ayam dan Bakso Yamin)
- **Pemilik UMKM:** Ibu Sandra Rismayanti
- **Judul Use Case:** Digitalisasi Pencatatan Transaksi dan Pemantauan Stok Bahan Baku pada UMKM Samudera Jaya
- **Periode Pengerjaan:** 20 November – 20 Desember 2026 (4 Minggu)

### Masalah Utama Mitra
1. Pencatatan transaksi manual yang rentan kesalahan hitung dan pencatatan omzet.
2. Pemantauan stok bahan baku sering terlewat hingga kehabisan bahan saat operasional.
3. Kerepotan pemilik usaha saat mencatat barang belanjaan *restock* dari pasar satu per satu ke dalam sistem/buku.

### Perubahan dari Use Case Awal
- Antarmuka AI dialihkan dari *chatbot* pelanggan WhatsApp menjadi **Asisten Cerdas Restock Inventaris (NLP & OCR Nota)** di dashboard pemilik.
- Pemesanan *online* menggunakan **Web Katalog publik** dengan tautan langsung **WhatsApp Click-to-Chat** ke nomor pribadi pemilik demi keamanan nomor pribadi UMKM dan kemudahan *restock* harian.

---

## 2. Arsitektur Sistem & Tech Stack

Sistem dibangun sebagai ekosistem web terpadu dengan arsitektur *monorepo*:

| Komponen | Teknologi | Direktori | Fungsi Utama |
| :--- | :--- | :--- | :--- |
| **Frontend** | Vite + React, Axios | `/frontend` | Web Katalog publik (pelanggan) & Web Dashboard internal (kasir/pemilik), termasuk kartu konfirmasi AI Restock dan grafik analitik. |
| **Backend API** | Node.js + Express (`/api/v1/...`) | `/backend` | REST API transaksi, antrean pesanan, manajemen inventaris, pemotongan stok otomatis berbasis resep, perhitungan alert ROP, dan ekspor laporan. |
| **Database** | PostgreSQL (Supabase / Neon) | — | Penyimpanan data transaksi, daftar menu, resep bahan baku, riwayat stok, dan antrean pesanan. |
| **AI Service** | Python + FastAPI, Scikit-Learn/PyTorch, Google Gemini API | `/ai-service` | Model kustom NLP (klasifikasi *intent* & ekstraksi entitas bahan/kuantitas) + Multimodal LLM/OCR untuk pemindaian foto nota belanja & input teks/suara. |
| **Deployment** | Vercel / Railway / Render | — | Hosting frontend, backend Node.js, dan layanan FastAPI agar dapat diakses daring saat demo dan serah terima. |

---

## 3. Alur Kerja Utama (End-to-End)

1. **Pemesanan Pelanggan (Web Katalog Publik):**
   - Pelanggan melihat daftar menu dan ketersediaan stok secara *real-time*.
   - Pelanggan memilih item dan menekan tombol **"Pesan via WhatsApp"**.
   - **2A:** Sistem mengarahkan pelanggan ke WhatsApp pribadi pemilik (Ibu Sandra Rismayanti) melalui tautan *Click-to-Chat* berisi rincian pesanan terformat.
   - **2B:** Secara bersamaan, pesanan tercatat otomatis ke antrean Web Dashboard kasir dengan status `"Menunggu Konfirmasi"`.

2. **Pemrosesan Kasir & Penjualan (Online & Offline):**
   - **Online:** Setelah sepakat di WhatsApp, pemilik/kasir mengubah status pesanan di Web Dashboard menjadi `"Selesai"`.
   - **Offline:** Kasir mencatat transaksi pembeli makan di tempat secara langsung di layar kasir Web Dashboard.
   - **Otomatisasi Backend & DB:** Saat pesanan berstatus `"Selesai"` atau transaksi offline disimpan, sistem otomatis menambahkan omzet harian dan memotong kuantitas stok bahan baku terkait (misal: mie basah, bakso, bumbu yamin, kemasan) sesuai formula resep.

3. **Peringatan Dini Stok (Reorder Point / ROP):**
   - Setelah pemotongan stok, sistem mengecek apakah `sisa_stok <= ROP`.
   - Jika ya, muncul indikator peringatan visual merah (*alert stok rendah*) di dashboard kasir/pemilik.

4. **Asisten Cerdas AI Restock (FastAPI):**
   - Setelah belanja di pasar, pemilik mengetik/berbicara santai dalam bahasa alami (NLP / *Voice-to-Text*) atau mengunggah foto nota belanja fisik (OCR/Vision) di Web Dashboard.
   - Layanan FastAPI mengekstraksi entitas nama bahan dan kuantitas menjadi **kartu konfirmasi interaktif**.
   - Pemilik memeriksa dan menekan **"Ya, Simpan"** (atau **"Edit"**) sebelum stok benar-benar bertambah di database.

5. **Dasbor Analitik Bisnis (Data Science):**
   - Mengolah riwayat transaksi menjadi grafik tren penjualan harian, pemetaan produk terlaris, dan rekomendasi estimasi kebutuhan belanja bahan baku berikutnya.

---

## 4. Aturan Guardrails AI & Keamanan Operasional

Seluruh pengembangan fitur AI dan validasi input **wajib** mematuhi aturan berikut:

1. **Human-in-the-Loop (Konfirmasi Eksplisit):**
   - Layanan AI **tidak boleh** langsung mengubah stok di database secara sepihak. Hasil ekstraksi NLP/OCR wajib ditampilkan sebagai **kartu konfirmasi interaktif** (`"Ya, Simpan"` / `"Edit"`) agar pemilik memverifikasi nama bahan dan kuantitasnya terlebih dahulu.
2. **Penolakan Di Luar Konteks (*Domain Guardrails*):**
   - Endpoint AI Restock hanya memproses input yang berkaitan dengan belanja/inventaris/bahan baku kuliner. Input ambigu atau pertanyaan di luar konteks kuliner/inventaris (misal: pertanyaan umum/cuaca/coding) wajib ditolak secara eksplisit dengan pesan *guardrails* yang jelas dan tidak menghasilkan perubahan stok.
3. **Validasi Input Ketat (*Anti Human Error*):**
   - Menolak nilai kuantitas/harga kosong, nol, atau negatif (`<= 0`), menerapkan batas maksimal wajar, serta menyediakan fitur koreksi stok manual (*stock adjustment*) dengan kolom alasan penyesuaian.
4. **Resiliensi & Fallback:**
   - Menerapkan *request throttling* dan *prompt* ringkas untuk menghemat kuota *free tier* Google Gemini API, menggunakan model lokal kustom (FastAPI) untuk ekstraksi teks dasar, serta menyiapkan *fallback* (Groq/Llama 3, OpenAI API, atau *rule-based*) dan **formulir input restock manual** di dashboard jika layanan AI mengalami gangguan atau foto nota buram.
5. **Privasi Data:**
   - Data historis yang digunakan untuk analitik dan pelatihan model hanya berupa data transaksi anonim (tanggal, menu, kuantitas) tanpa mencatat identitas atau data pribadi pelanggan.
6. **Empty State Handling:**
   - Dasbor analitik tidak boleh *crash* saat data riwayat transaksi masih kosong (awal penggunaan); wajib menampilkan status *empty state* yang informatif.

---

## 5. Ruang Lingkup di Luar Pengerjaan (Out of Scope)
- Payment gateway otomatis.
- Bot otomatis di WhatsApp pribadi pemilik.
- Integrasi kurir pihak ketiga.
- Aplikasi mobile native (Android/iOS).

---

## 6. Pembagian Tugas Anggota Tim

| Nama & ID | Peran | Tanggung Jawab Utama | Fitur Tambahan / Khusus |
| :--- | :--- | :--- | :--- |
| **Muhammad Rafie Afkar Yunansyah** (`FS299B6Y1231`) | AI Full-Stack Developer | Pengembangan Web Dashboard Kasir, Web Katalog Publik (WhatsApp Click-to-Chat), & Antarmuka Manajemen (validasi form & *stock adjustment*). | — |
| **Mochamad Fahrul Rizqi** (`FS313B6Y1001`) | AI Full-Stack Developer | Pembangunan REST API Backend (Node.js/Express), Basis Data (PostgreSQL), Logika Pemotongan Stok otomatis & Alert ROP. | Ekspor Laporan Penjualan (CSV/PDF) bersama tim AI untuk integrasi. |
| **Haryo Wicaksono** (`AE299B6Y0723`) | Next-Gen AI Engineer | Pelatihan Model Kustom Ekstraksi & Klasifikasi Restock AI (membandingkan min. 2 model) + Serving FastAPI (*Main Quest*), mitigasi *rate limit*. | Input Suara (*Voice-to-Text*) Restock di dashboard. |
| **Muhammad Faiz Adya** (`AE012B6Y1134`) | Next-Gen AI Engineer | Asisten Cerdas Input Restock berbasis Multimodal LLM & OCR Nota Belanja di dashboard dengan *guardrails* ketat. | Integrasi kartu konfirmasi interaktif NLP/OCR. |
| **I Gede Putu Oka Pramana Putra** (`DS232B6Y0749`) | Data Science Specialist | Pembersihan & eksplorasi data historis, asistensi skema basis data, *data dictionary*, pengecekan *class imbalance* & *train/test split* dataset AI. | Standarisasi satuan bahan (gram, porsi, dll.) & imputasi data. |
| **Titi Alfiana Pramesti** (`DS466B6X1729`) | Data Science Specialist | Analisis tren penjualan, pemodelan rekomendasi estimasi kebutuhan belanja stok (ROP), serta **Koordinator Pengujian Sistem (QA)**. | Pengelolaan *QA Test Log* (Google Sheets), GitHub Issues, & *re-testing*. |

---

## 7. Jadwal Pengerjaan & Pengujian

- **Minggu 1 (20 – 27 Nov 2026):** Skema DB & rancangan API, *wireframe* & prototipe frontend, pembersihan data historis, pelatihan model restock awal & setup FastAPI.
- **Minggu 2 (28 Nov – 5 Des 2026):** Logika potong stok & ROP di backend, integrasi Web Katalog (WA Click-to-Chat) & Dashboard, model analitik tren penjualan, integrasi LLM & OCR di FastAPI, **Checkpoint 2**.
- **Minggu 3 (6 – 13 Des 2026):** Integrasi grafik tren & rekomendasi ke dashboard, pemasangan alert visual stok tipis, uji coba *end-to-end* MVP, pengujian *boundary* & input salah oleh QA, draf *user manual*.
- **Minggu 4 (14 – 20 Des 2026):** Pengujian menyeluruh (*black-box*, respons AI, performa web), *bug fixing*, finalisasi *Project Brief* (PDF), *manual guide*, video demo 10 menit, dan serah terima ke UMKM Samudera Jaya (**Checkpoint 3**).

### Hasil Akhir yang Dikumpulkan
1. Web Katalog publik & Web Dashboard ter-deploy.
2. REST API FastAPI Asisten Restock AI.
3. Repositori GitHub yang rapi.
4. Project Brief (PDF), panduan penggunaan (*manual guide*), dan video demo (10 menit).
