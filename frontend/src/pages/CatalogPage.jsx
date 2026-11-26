import { useEffect, useState } from "react";
import { ShoppingBag, MessageCircle, Plus, Minus, Store, CheckCircle2, AlertCircle } from "lucide-react";
import { fetchMenus, createOrder } from "../services/api";

export default function CatalogPage() {
  const [menus, setMenus] = useState([]);
  const [cart, setCart] = useState({});
  const [customerName, setCustomerName] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [orderResult, setOrderResult] = useState(null);

  useEffect(() => {
    loadMenus();
  }, []);

  async function loadMenus() {
    try {
      setLoading(true);
      const data = await fetchMenus();
      setMenus(data);
    } catch {
      setError("Gagal memuat daftar menu. Pastikan server backend berjalan.");
    } finally {
      setLoading(false);
    }
  }

  function updateQty(menuId, delta, maxAvailable) {
    setCart((prev) => {
      const current = prev[menuId] || 0;
      const next = Math.max(0, Math.min(maxAvailable, current + delta));
      if (next === 0) {
        const copy = { ...prev };
        delete copy[menuId];
        return copy;
      }
      return { ...prev, [menuId]: next };
    });
  }

  const cartItems = Object.entries(cart).map(([menuId, quantity]) => {
    const menu = menus.find((m) => m.id === Number(menuId));
    return { menu, quantity };
  });

  const totalAmount = cartItems.reduce((sum, item) => sum + (item.menu?.price || 0) * item.quantity, 0);

  async function handleCheckout(e) {
    e.preventDefault();
    setError("");
    if (cartItems.length === 0) {
      setError("Pilih minimal 1 menu sebelum memesan.");
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        customer_name: customerName.trim() || "Pelanggan",
        notes: notes.trim(),
        items: cartItems.map((i) => ({ menu_id: i.menu.id, quantity: i.quantity }))
      };
      const result = await createOrder(payload);
      setOrderResult(result);
      setCart({});
      setCustomerName("");
      setNotes("");
    } catch (err) {
      setError(err.response?.data?.error?.message || "Gagal membuat pesanan.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center font-bold">
              <Store className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Samudera Jaya</h1>
              <p className="text-xs text-slate-500">Mie Ayam & Bakso Yamin — Katalog Pemesanan Online</p>
            </div>
          </div>
          <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            Buka Hari Ini
          </span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <section className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-bold text-slate-900">Daftar Menu</h2>

          {error && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[1, 2, 3].map((n) => (
                <div key={n} className="h-64 rounded-2xl bg-slate-200 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {menus.map((menu) => {
                const qty = cart[menu.id] || 0;
                return (
                  <div
                    key={menu.id}
                    className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm flex flex-col"
                  >
                    <img src={menu.image_url} alt={menu.name} className="h-40 w-full object-cover" />
                    <div className="p-4 flex-1 flex flex-col justify-between gap-3">
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="font-semibold text-slate-900">{menu.name}</h3>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              menu.is_available
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-red-50 text-red-700"
                            }`}
                          >
                            {menu.is_available ? `Stok: ${menu.max_servings_available}` : "Habis"}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">{menu.description}</p>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                        <span className="font-bold text-amber-600">
                          Rp{menu.price.toLocaleString("id-ID")}
                        </span>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => updateQty(menu.id, -1, menu.max_servings_available)}
                            disabled={qty === 0}
                            className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center hover:bg-slate-100 disabled:opacity-40"
                          >
                            <Minus className="w-4 h-4" />
                          </button>
                          <span className="w-6 text-center text-sm font-semibold">{qty}</span>
                          <button
                            type="button"
                            onClick={() => updateQty(menu.id, 1, menu.max_servings_available)}
                            disabled={!menu.is_available || qty >= menu.max_servings_available}
                            className="w-8 h-8 rounded-lg bg-amber-500 text-white flex items-center justify-center hover:bg-amber-600 disabled:opacity-40"
                          >
                            <Plus className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm sticky top-24">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingBag className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-bold">Ringkasan Pesanan</h2>
            </div>

            {orderResult && (
              <div className="mb-4 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Pesanan {orderResult.order_code} tercatat!
                </div>
                <p className="text-xs text-emerald-800">
                  Klik tombol di bawah untuk mengirim rincian pesanan ke WhatsApp pemilik agar segera diproses.
                </p>
                <a
                  href={orderResult.whatsapp_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
                >
                  <MessageCircle className="w-4 h-4" />
                  Lanjut ke WhatsApp Pemilik
                </a>
              </div>
            )}

            <form onSubmit={handleCheckout} className="space-y-4">
              {cartItems.length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center border border-dashed border-slate-200 rounded-xl">
                  Belum ada menu yang dipilih.
                </p>
              ) : (
                <ul className="divide-y divide-slate-100 text-sm">
                  {cartItems.map(({ menu, quantity }) => (
                    <li key={menu.id} className="py-2 flex justify-between">
                      <span>
                        {menu.name} <span className="text-slate-400">x{quantity}</span>
                      </span>
                      <span className="font-medium">
                        Rp{(menu.price * quantity).toLocaleString("id-ID")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="flex justify-between font-bold text-base pt-2 border-t border-slate-200">
                <span>Total</span>
                <span className="text-amber-600">Rp{totalAmount.toLocaleString("id-ID")}</span>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-700">Nama Pemesan</label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="Contoh: Budi"
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-700">Catatan (Opsional)</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Contoh: Tidak pakai seledri"
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting || cartItems.length === 0}
                className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 text-white font-semibold text-sm hover:bg-emerald-700 disabled:opacity-50 flex items-center justify-center gap-2 transition"
              >
                <MessageCircle className="w-4 h-4" />
                {submitting ? "Memproses..." : "Pesan via WhatsApp"}
              </button>
            </form>
          </div>
        </aside>
      </main>
    </div>
  );
}
