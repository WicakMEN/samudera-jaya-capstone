import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ShoppingCart,
  Package,
  Sparkles,
  BarChart3,
  AlertTriangle,
  CheckCircle2,
  Mic,
  Upload,
  Download,
  ArrowLeft,
  SlidersHorizontal,
  LogOut
} from "lucide-react";
import {
  fetchMenus,
  fetchOrders,
  updateOrderStatus,
  createOfflineTransaction,
  fetchIngredients,
  restockIngredients,
  adjustIngredientStock,
  fetchAnalyticsSummary,
  getExportCsvUrl,
  parseRestockAI,
  logoutAdmin
} from "../services/api";

const TABS = [
  { id: "kasir", label: "Kasir & Antrean", icon: ShoppingCart },
  { id: "inventaris", label: "Inventaris & ROP", icon: Package },
  { id: "ai-restock", label: "Asisten AI Restock", icon: Sparkles },
  { id: "analitik", label: "Analitik Bisnis", icon: BarChart3 }
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("kasir");
  const [menus, setMenus] = useState([]);
  const [orders, setOrders] = useState([]);
  const [ingredients, setIngredients] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [banner, setBanner] = useState(null);
  const [lowStockAlerts, setLowStockAlerts] = useState([]);

  // Offline transaction form
  const [offlineMenuId, setOfflineMenuId] = useState("");
  const [offlineQty, setOfflineQty] = useState(1);
  const [offlineNotes, setOfflineNotes] = useState("");

  // Manual restock & adjustment
  const [restockIngId, setRestockIngId] = useState("");
  const [restockQty, setRestockQty] = useState("");
  const [adjustTarget, setAdjustTarget] = useState(null);
  const [adjustStock, setAdjustStock] = useState("");
  const [adjustReason, setAdjustReason] = useState("");

  // AI Restock state
  const [aiText, setAiText] = useState("");
  const [aiImage, setAiImage] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiParsed, setAiParsed] = useState(null);
  const [aiError, setAiError] = useState("");
  const [isListening, setIsListening] = useState(false);

  useEffect(() => {
    refreshAll();
  }, []);

  async function refreshAll() {
    try {
      const [m, o, ing, ana] = await Promise.all([
        fetchMenus(),
        fetchOrders(),
        fetchIngredients(),
        fetchAnalyticsSummary()
      ]);
      setMenus(m);
      setOrders(o);
      setIngredients(ing);
      setAnalytics(ana);
      setLowStockAlerts(ing.filter((i) => i.is_low_stock));
      if (!offlineMenuId && m.length > 0) setOfflineMenuId(String(m[0].id));
      if (!restockIngId && ing.length > 0) setRestockIngId(String(ing[0].id));
    } catch {
      setBanner({ type: "error", text: "Gagal terhubung ke Backend API. Pastikan server Express berjalan di port 3000." });
    }
  }

  async function handleCompleteOrder(orderId) {
    try {
      const res = await updateOrderStatus(orderId, "Selesai");
      setBanner({ type: "success", text: `Pesanan #${orderId} selesai & stok bahan baku otomatis terpotong.` });
      if (res.low_stock_alerts?.length > 0) {
        setLowStockAlerts(res.low_stock_alerts);
      }
      await refreshAll();
    } catch (err) {
      setBanner({ type: "error", text: err.response?.data?.error?.message || "Gagal menyelesaikan pesanan." });
    }
  }

  async function handleOfflineSubmit(e) {
    e.preventDefault();
    const qty = Number(offlineQty);
    if (!offlineMenuId || !Number.isInteger(qty) || qty <= 0) {
      setBanner({ type: "error", text: "Validasi gagal: Pilih menu dan masukkan kuantitas lebih dari 0." });
      return;
    }
    try {
      await createOfflineTransaction({
        payment_method: "tunai",
        notes: offlineNotes,
        items: [{ menu_id: Number(offlineMenuId), quantity: qty }]
      });
      setOfflineQty(1);
      setOfflineNotes("");
      setBanner({ type: "success", text: "Transaksi offline tersimpan & stok bahan baku diperbarui." });
      await refreshAll();
    } catch (err) {
      setBanner({ type: "error", text: err.response?.data?.error?.message || "Gagal menyimpan transaksi." });
    }
  }

  async function handleManualRestock(e) {
    e.preventDefault();
    const qty = Number(restockQty);
    if (!restockIngId || !Number.isFinite(qty) || qty <= 0) {
      setBanner({ type: "error", text: "Validasi gagal: Kuantitas restock harus lebih dari 0." });
      return;
    }
    try {
      await restockIngredients({
        source: "manual_form",
        notes: "Input restock manual",
        items: [{ ingredient_id: Number(restockIngId), quantity: qty }]
      });
      setRestockQty("");
      setBanner({ type: "success", text: "Stok bahan baku berhasil ditambahkan." });
      await refreshAll();
    } catch (err) {
      setBanner({ type: "error", text: err.response?.data?.error?.message || "Gagal menambah stok." });
    }
  }

  async function handleAdjustSubmit(e) {
    e.preventDefault();
    if (!adjustTarget) return;
    try {
      await adjustIngredientStock(adjustTarget.id, {
        new_stock: Number(adjustStock),
        reason: adjustReason
      });
      setAdjustTarget(null);
      setAdjustStock("");
      setAdjustReason("");
      setBanner({ type: "success", text: "Penyesuaian stok manual berhasil dicatat." });
      await refreshAll();
    } catch (err) {
      setBanner({ type: "error", text: err.response?.data?.error?.message || "Gagal menyesuaikan stok." });
    }
  }

  function handleVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setAiError("Browser ini belum mendukung Voice-to-Text (Web Speech API). Silakan ketik manual.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "id-ID";
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setAiText((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.start();
  }

  async function handleAiParse(e) {
    e.preventDefault();
    setAiError("");
    setAiParsed(null);
    if (!aiText.trim() && !aiImage) {
      setAiError("Masukkan teks belanjaan atau unggah foto nota belanja terlebih dahulu.");
      return;
    }
    try {
      setAiLoading(true);
      const data = await parseRestockAI({ text: aiText.trim(), imageFile: aiImage });
      setAiParsed(data);
    } catch (err) {
      if (err.response?.status === 422) {
        setAiError(err.response.data?.error?.message || "Input ditolak oleh guardrails AI.");
      } else {
        setAiError(
          "Layanan AI FastAPI (port 8000) belum aktif atau mengalami gangguan. Gunakan tab Inventaris untuk input restock manual."
        );
      }
    } finally {
      setAiLoading(false);
    }
  }

  async function handleConfirmAiRestock() {
    if (!aiParsed?.items?.length) return;
    try {
      const items = aiParsed.items.map((item) => ({
        name: item.matched_ingredient_name || item.raw_name,
        quantity: Number(item.normalized_quantity ?? item.quantity)
      }));
      await restockIngredients({
        source: "ai_assistant",
        notes: aiParsed.raw_extracted_text || "Restock via Asisten AI",
        items
      });
      setAiParsed(null);
      setAiText("");
      setAiImage(null);
      setBanner({ type: "success", text: "Hasil ekstraksi AI dikonfirmasi & stok berhasil ditambahkan!" });
      await refreshAll();
    } catch (err) {
      setAiError(err.response?.data?.error?.message || "Gagal menyimpan hasil restock AI ke database.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-3.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link to="/" className="p-2 rounded-lg border border-slate-200 hover:bg-slate-100" title="Ke Katalog Publik">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Dashboard Samudera Jaya</h1>
              <p className="text-xs text-slate-500">Kasir, Inventaris ROP, Asisten AI Restock & Analitik</p>
            </div>
          </div>

          <nav className="flex flex-wrap gap-1.5">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition ${
                    active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
            <button
              onClick={() => {
                logoutAdmin();
                navigate("/login", { replace: true });
              }}
              className="px-3 py-2 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 flex items-center gap-1.5 transition"
              title="Keluar dari Dashboard"
            >
              <LogOut className="w-4 h-4" />
              Keluar
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {lowStockAlerts.length > 0 && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-bold">Peringatan Stok Menipis ({"<="} ROP):</p>
              <p className="mt-0.5">
                {lowStockAlerts.map((a) => `${a.name} (${a.current_stock ?? a.remaining_stock} ${a.unit})`).join(", ")}.
                Segera lakukan restock!
              </p>
            </div>
          </div>
        )}

        {banner && (
          <div
            className={`p-3.5 rounded-xl border text-sm flex items-center justify-between ${
              banner.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{banner.text}</span>
            </div>
            <button onClick={() => setBanner(null)} className="text-xs underline">
              Tutup
            </button>
          </div>
        )}

        {activeTab === "kasir" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <section className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <h2 className="font-bold text-base">Antrean Pesanan & Riwayat</h2>
              <div className="space-y-3">
                {orders.map((ord) => (
                  <div key={ord.order_id} className="p-4 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm">{ord.order_code}</span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            ord.status === "Selesai"
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {ord.status}
                        </span>
                        <span className="text-xs text-slate-400">({ord.channel})</span>
                      </div>
                      <p className="text-xs text-slate-600 mt-1">
                        {ord.customer_name} • {ord.items.map((i) => `${i.menu_name} x${i.quantity}`).join(", ")}
                      </p>
                      <p className="text-sm font-semibold text-slate-900 mt-1">
                        Rp{ord.total_amount.toLocaleString("id-ID")}
                      </p>
                    </div>
                    {ord.status === "Menunggu Konfirmasi" && (
                      <button
                        onClick={() => handleCompleteOrder(ord.order_id)}
                        className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
                      >
                        Tandai Selesai
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm h-fit">
              <h2 className="font-bold text-base mb-4">Catat Transaksi Offline</h2>
              <form onSubmit={handleOfflineSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Menu</label>
                  <select
                    value={offlineMenuId}
                    onChange={(e) => setOfflineMenuId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200"
                  >
                    {menus.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} (Rp{m.price.toLocaleString("id-ID")})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Kuantitas</label>
                  <input
                    type="number"
                    min="1"
                    value={offlineQty}
                    onChange={(e) => setOfflineQty(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Catatan</label>
                  <input
                    type="text"
                    value={offlineNotes}
                    onChange={(e) => setOfflineNotes(e.target.value)}
                    placeholder="Contoh: Meja 3"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200"
                  />
                </div>
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800"
                >
                  Simpan Transaksi
                </button>
              </form>
            </section>
          </div>
        )}

        {activeTab === "inventaris" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <section className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm overflow-x-auto">
              <h2 className="font-bold text-base mb-4">Stok Bahan Baku & Reorder Point (ROP)</h2>
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="py-2">Bahan Baku</th>
                    <th className="py-2">Sisa Stok</th>
                    <th className="py-2">Batas ROP</th>
                    <th className="py-2">Status</th>
                    <th className="py-2 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ingredients.map((ing) => (
                    <tr key={ing.id}>
                      <td className="py-3 font-medium">{ing.name}</td>
                      <td className="py-3">
                        {ing.current_stock} {ing.unit}
                      </td>
                      <td className="py-3 text-slate-500">
                        {ing.rop} {ing.unit}
                      </td>
                      <td className="py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            ing.is_low_stock ? "bg-red-100 text-red-700" : "bg-emerald-50 text-emerald-700"
                          }`}
                        >
                          {ing.is_low_stock ? "Stok Tipis" : "Aman"}
                        </span>
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => {
                            setAdjustTarget(ing);
                            setAdjustStock(String(ing.current_stock));
                          }}
                          className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-100"
                        >
                          <SlidersHorizontal className="w-3 h-3" />
                          Adjust
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {adjustTarget && (
                <form onSubmit={handleAdjustSubmit} className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                  <p className="text-sm font-semibold">Penyesuaian Stok Manual: {adjustTarget.name}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <input
                      type="number"
                      min="0"
                      value={adjustStock}
                      onChange={(e) => setAdjustStock(e.target.value)}
                      placeholder="Stok fisik aktual"
                      className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white"
                    />
                    <input
                      type="text"
                      value={adjustReason}
                      onChange={(e) => setAdjustReason(e.target.value)}
                      placeholder="Alasan penyesuaian (wajib)"
                      className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button type="submit" className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-medium">
                      Simpan Penyesuaian
                    </button>
                    <button
                      type="button"
                      onClick={() => setAdjustTarget(null)}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs"
                    >
                      Batal
                    </button>
                  </div>
                </form>
              )}
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm h-fit">
              <h2 className="font-bold text-base mb-1">Restock Manual (Fallback)</h2>
              <p className="text-xs text-slate-500 mb-4">Gunakan form ini jika tidak memakai Asisten AI Restock.</p>
              <form onSubmit={handleManualRestock} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Bahan Baku</label>
                  <select
                    value={restockIngId}
                    onChange={(e) => setRestockIngId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200"
                  >
                    {ingredients.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.name} ({i.unit})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Jumlah Tambahan</label>
                  <input
                    type="number"
                    min="1"
                    value={restockQty}
                    onChange={(e) => setRestockQty(e.target.value)}
                    placeholder="Contoh: 5000"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200"
                  />
                </div>
                <button type="submit" className="w-full py-2.5 rounded-xl bg-amber-500 text-white text-sm font-semibold hover:bg-amber-600">
                  Tambah Stok
                </button>
              </form>
            </section>
          </div>
        )}

        {activeTab === "ai-restock" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <div>
                <h2 className="font-bold text-base">Asisten Cerdas AI Restock (FastAPI)</h2>
                <p className="text-xs text-slate-500">
                  Ketik/bicara belanjaan pasar (misal: &quot;beli mie basah 5 kg dan bakso 100 butir&quot;) atau unggah foto nota belanja.
                </p>
              </div>

              <form onSubmit={handleAiParse} className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-700">Input Bahasa Alami / Suara</label>
                    <button
                      type="button"
                      onClick={handleVoiceInput}
                      className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border ${
                        isListening ? "bg-red-50 border-red-300 text-red-700" : "border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      <Mic className="w-3.5 h-3.5" />
                      {isListening ? "Mendengarkan..." : "Voice-to-Text"}
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={aiText}
                    onChange={(e) => setAiText(e.target.value)}
                    placeholder="Contoh: beli mie basah 5 kg dan bakso 100 butir"
                    className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-medium text-slate-700">Atau Unggah Foto Nota Belanja (OCR)</label>
                  <label className="flex items-center justify-center gap-2 p-4 border border-dashed border-slate-300 rounded-xl cursor-pointer hover:bg-slate-50 text-sm text-slate-600">
                    <Upload className="w-4 h-4" />
                    <span>{aiImage ? aiImage.name : "Pilih foto nota (JPG/PNG)"}</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setAiImage(e.target.files?.[0] || null)}
                      className="hidden"
                    />
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={aiLoading}
                  className="w-full py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {aiLoading ? "Menganalisis..." : "Ekstrak dengan AI"}
                </button>
              </form>

              {aiError && (
                <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">{aiError}</div>
              )}
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <h2 className="font-bold text-base">Kartu Konfirmasi Interaktif (Guardrails)</h2>
              {!aiParsed ? (
                <p className="text-sm text-slate-400 py-12 text-center border border-dashed border-slate-200 rounded-xl">
                  Hasil ekstraksi bahan baku & kuantitas akan muncul di sini untuk Anda periksa sebelum disimpan ke database.
                </p>
              ) : (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900">
                    Intent: <strong>{aiParsed.intent}</strong> • Model: <strong>{aiParsed.model_used}</strong>
                  </div>
                  <ul className="divide-y divide-slate-100 text-sm">
                    {aiParsed.items.map((item, idx) => (
                      <li key={idx} className="py-2.5 flex items-center justify-between">
                        <div>
                          <p className="font-semibold">{item.matched_ingredient_name || item.raw_name}</p>
                          <p className="text-xs text-slate-500">Confidence: {Math.round((item.confidence || 0) * 100)}%</p>
                        </div>
                        <span className="font-bold text-emerald-700">
                          +{item.normalized_quantity ?? item.quantity} {item.normalized_unit ?? item.unit}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2">
                    <button
                      onClick={handleConfirmAiRestock}
                      className="flex-1 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
                    >
                      Ya, Simpan ke Stok
                    </button>
                    <button
                      onClick={() => setAiParsed(null)}
                      className="px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-medium"
                    >
                      Batal
                    </button>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === "analitik" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-lg">Dasbor Analitik Penjualan & Rekomendasi Belanja</h2>
              <a
                href={getExportCsvUrl()}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
              >
                <Download className="w-4 h-4" />
                Ekspor CSV
              </a>
            </div>

            {!analytics || analytics.is_empty ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-500">
                <p className="font-semibold text-slate-700">Belum ada data transaksi selesai</p>
                <p className="text-sm mt-1">
                  Grafik tren penjualan dan menu terlaris akan otomatis muncul setelah ada transaksi yang berstatus Selesai.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                  <p className="text-xs text-slate-500">Total Omzet</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    Rp{analytics.total_revenue.toLocaleString("id-ID")}
                  </p>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                  <p className="text-xs text-slate-500">Total Transaksi Selesai</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{analytics.total_orders}</p>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                  <p className="text-xs text-slate-500">Menu Terlaris</p>
                  <p className="text-lg font-bold text-amber-600 mt-1">
                    {analytics.top_menus[0]?.name || "-"} ({analytics.top_menus[0]?.total_sold || 0} porsi)
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
