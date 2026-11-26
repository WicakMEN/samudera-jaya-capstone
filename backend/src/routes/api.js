import { Router } from "express";
import {
  menus,
  orders,
  ingredients,
  stockLogs,
  computeMaxServings,
  deductIngredientsForItems
} from "../data/mockStore.js";

const router = Router();
const OWNER_WA = process.env.OWNER_WHATSAPP_NUMBER || "6281234567890";

// 1.1 Health Check
router.get("/health", (_req, res) => {
  res.json({
    success: true,
    message: "Backend API is running (Mock Mode - siap dihubungkan ke PostgreSQL)",
    data: { status: "ok", timestamp: new Date().toISOString() }
  });
});

// 1.2 Daftar Menu & Ketersediaan Real-time
router.get("/menus", (_req, res) => {
  const data = menus.map((m) => {
    const maxServings = computeMaxServings(m.id);
    return {
      ...m,
      is_available: maxServings > 0,
      max_servings_available: maxServings
    };
  });
  res.json({ success: true, message: "Daftar menu berhasil diambil", data });
});

// 1.3 Pesanan Online dari Web Katalog -> Antrean Kasir + WA Click-to-Chat
router.post("/orders", (req, res) => {
  const { customer_name = "Pelanggan", notes = "", items = [] } = req.body || {};

  if (!Array.isArray(items) || items.length === 0) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Item pesanan tidak boleh kosong", details: [] }
    });
  }

  let totalAmount = 0;
  const resolvedItems = [];

  for (const item of items) {
    const qty = Number(item.quantity);
    if (!Number.isInteger(qty) || qty <= 0) {
      return res.status(400).json({
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Kuantitas pesanan harus lebih dari 0", details: [] }
      });
    }
    const menu = menus.find((m) => m.id === Number(item.menu_id));
    if (!menu) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: `Menu ID ${item.menu_id} tidak ditemukan`, details: [] }
      });
    }
    const subtotal = menu.price * qty;
    totalAmount += subtotal;
    resolvedItems.push({ menu_id: menu.id, menu_name: menu.name, quantity: qty, subtotal });
  }

  const nextId = orders.length > 0 ? Math.max(...orders.map((o) => o.order_id)) + 1 : 101;
  const datePart = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const orderCode = `ORD-${datePart}-${nextId}`;

  const newOrder = {
    order_id: nextId,
    order_code: orderCode,
    customer_name: String(customer_name).trim() || "Pelanggan",
    channel: "online_katalog",
    status: "Menunggu Konfirmasi",
    notes: String(notes).trim(),
    total_amount: totalAmount,
    items: resolvedItems,
    created_at: new Date().toISOString()
  };
  orders.unshift(newOrder);

  const itemLines = resolvedItems.map((i) => `- ${i.menu_name} x${i.quantity} (Rp${i.subtotal.toLocaleString("id-ID")})`).join("\n");
  const waText = [
    `Halo Samudera Jaya, saya ingin memesan:`,
    `Kode: ${orderCode}`,
    `Nama: ${newOrder.customer_name}`,
    ``,
    itemLines,
    ``,
    `Total: Rp${totalAmount.toLocaleString("id-ID")}`,
    newOrder.notes ? `Catatan: ${newOrder.notes}` : null
  ]
    .filter(Boolean)
    .join("\n");

  const whatsapp_url = `https://wa.me/${OWNER_WA}?text=${encodeURIComponent(waText)}`;

  return res.status(201).json({
    success: true,
    message: "Pesanan masuk ke antrean kasir",
    data: {
      order_id: newOrder.order_id,
      order_code: newOrder.order_code,
      status: newOrder.status,
      total_amount: newOrder.total_amount,
      whatsapp_url,
      created_at: newOrder.created_at
    }
  });
});

// 1.4 Daftar Antrean & Riwayat Pesanan
router.get("/orders", (req, res) => {
  const { status } = req.query;
  const filtered = status ? orders.filter((o) => o.status === status) : orders;
  res.json({ success: true, message: "Daftar pesanan berhasil diambil", data: filtered });
});

// 1.5 Konfirmasi Status Pesanan ("Selesai" / "Dibatalkan") + Pemotongan Stok Otomatis
router.patch("/orders/:id/status", (req, res) => {
  const orderId = Number(req.params.id);
  const { status } = req.body || {};
  const order = orders.find((o) => o.order_id === orderId);

  if (!order) {
    return res.status(404).json({
      success: false,
      error: { code: "NOT_FOUND", message: "Pesanan tidak ditemukan", details: [] }
    });
  }

  if (!["Selesai", "Dibatalkan"].includes(status)) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Status harus 'Selesai' atau 'Dibatalkan'", details: [] }
    });
  }

  if (order.status === "Selesai") {
    return res.status(400).json({
      success: false,
      error: { code: "ALREADY_COMPLETED", message: "Pesanan sudah berstatus Selesai", details: [] }
    });
  }

  order.status = status;
  let deductionResult = { deducted_ingredients: [], low_stock_alerts: [] };
  if (status === "Selesai") {
    deductionResult = deductIngredientsForItems(order.items);
  }

  return res.json({
    success: true,
    message:
      status === "Selesai"
        ? "Pesanan selesai dan stok bahan baku berhasil dipotong"
        : "Pesanan dibatalkan",
    data: {
      order_id: order.order_id,
      status: order.status,
      total_amount: order.total_amount,
      ...deductionResult
    }
  });
});

// 1.6 Pencatatan Transaksi Offline Kasir
router.post("/transactions/offline", (req, res) => {
  const { payment_method = "tunai", notes = "", items = [] } = req.body || {};

  if (!Array.isArray(items) || items.length === 0) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Item transaksi tidak boleh kosong", details: [] }
    });
  }

  let totalAmount = 0;
  const resolvedItems = [];

  for (const item of items) {
    const qty = Number(item.quantity);
    if (!Number.isInteger(qty) || qty <= 0) {
      return res.status(400).json({
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Kuantitas transaksi harus lebih dari 0", details: [] }
      });
    }
    const menu = menus.find((m) => m.id === Number(item.menu_id));
    if (!menu) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: `Menu ID ${item.menu_id} tidak ditemukan`, details: [] }
      });
    }
    const subtotal = menu.price * qty;
    totalAmount += subtotal;
    resolvedItems.push({ menu_id: menu.id, menu_name: menu.name, quantity: qty, subtotal });
  }

  const nextId = orders.length > 0 ? Math.max(...orders.map((o) => o.order_id)) + 1 : 101;
  const datePart = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const orderCode = `TRX-${datePart}-${nextId}`;

  const newTrx = {
    order_id: nextId,
    order_code: orderCode,
    customer_name: "Pelanggan Kasir",
    channel: "offline_kasir",
    payment_method,
    status: "Selesai",
    notes: String(notes).trim(),
    total_amount: totalAmount,
    items: resolvedItems,
    created_at: new Date().toISOString()
  };
  orders.unshift(newTrx);

  const deductionResult = deductIngredientsForItems(resolvedItems);

  return res.status(201).json({
    success: true,
    message: "Transaksi offline berhasil disimpan dan stok diperbarui",
    data: {
      order_id: newTrx.order_id,
      order_code: newTrx.order_code,
      channel: newTrx.channel,
      status: newTrx.status,
      total_amount: newTrx.total_amount,
      ...deductionResult
    }
  });
});

// 1.7 Daftar Inventaris Bahan Baku & Status ROP
router.get("/ingredients", (_req, res) => {
  const data = ingredients.map((ing) => ({
    ...ing,
    is_low_stock: ing.current_stock <= ing.rop
  }));
  res.json({ success: true, message: "Data inventaris berhasil diambil", data });
});

// 1.8 Simpan Penambahan Stok (Restock Terkonfirmasi / Manual)
router.post("/ingredients/restock", (req, res) => {
  const { source = "manual_form", notes = "", items = [] } = req.body || {};

  if (!Array.isArray(items) || items.length === 0) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Daftar bahan restock tidak boleh kosong", details: [] }
    });
  }

  const updated_items = [];
  for (const item of items) {
    const qty = Number(item.quantity);
    if (!Number.isFinite(qty) || qty <= 0 || qty > 1000000) {
      return res.status(400).json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Kuantitas restock harus lebih dari 0 dan dalam batas wajar",
          details: []
        }
      });
    }

    const ing = ingredients.find(
      (i) => i.id === Number(item.ingredient_id) || i.name.toLowerCase() === String(item.name || "").toLowerCase()
    );
    if (!ing) {
      return res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "Bahan baku tidak ditemukan", details: [] }
      });
    }

    ing.current_stock += qty;
    ing.updated_at = new Date().toISOString();
    stockLogs.push({ type: "restock", source, ingredient_id: ing.id, qty, notes, at: ing.updated_at });

    updated_items.push({
      ingredient_id: ing.id,
      name: ing.name,
      added_qty: qty,
      new_stock: ing.current_stock,
      unit: ing.unit,
      is_low_stock: ing.current_stock <= ing.rop
    });
  }

  return res.json({
    success: true,
    message: "Stok bahan baku berhasil ditambahkan",
    data: { updated_items }
  });
});

// 1.9 Penyesuaian Stok Manual (Stock Adjustment)
router.patch("/ingredients/:id/adjust", (req, res) => {
  const ingId = Number(req.params.id);
  const { new_stock, reason } = req.body || {};
  const ing = ingredients.find((i) => i.id === ingId);

  if (!ing) {
    return res.status(404).json({
      success: false,
      error: { code: "NOT_FOUND", message: "Bahan baku tidak ditemukan", details: [] }
    });
  }

  const parsedStock = Number(new_stock);
  if (!Number.isFinite(parsedStock) || parsedStock < 0) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Stok baru tidak boleh bernilai negatif", details: [] }
    });
  }

  if (!reason || String(reason).trim().length < 3) {
    return res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message: "Alasan penyesuaian stok wajib diisi", details: [] }
    });
  }

  const previous_stock = ing.current_stock;
  ing.current_stock = parsedStock;
  ing.updated_at = new Date().toISOString();
  stockLogs.push({
    type: "adjustment",
    ingredient_id: ing.id,
    previous_stock,
    new_stock: parsedStock,
    reason: String(reason).trim(),
    at: ing.updated_at
  });

  return res.json({
    success: true,
    message: "Penyesuaian stok berhasil dicatat",
    data: {
      ingredient_id: ing.id,
      previous_stock,
      new_stock: ing.current_stock,
      reason: String(reason).trim()
    }
  });
});

// 1.10 Ringkasan Analitik Bisnis & Rekomendasi Belanja
router.get("/analytics/summary", (_req, res) => {
  const completedOrders = orders.filter((o) => o.status === "Selesai");
  if (completedOrders.length === 0) {
    return res.json({
      success: true,
      message: "Belum ada transaksi selesai",
      data: {
        is_empty: true,
        total_revenue: 0,
        total_orders: 0,
        daily_sales_trend: [],
        top_menus: [],
        restock_recommendations: []
      }
    });
  }

  const total_revenue = completedOrders.reduce((acc, o) => acc + o.total_amount, 0);
  const dailyMap = new Map();
  const menuMap = new Map();

  for (const ord of completedOrders) {
    const dateKey = ord.created_at.slice(0, 10);
    const curDay = dailyMap.get(dateKey) || { date: dateKey, revenue: 0, orders: 0 };
    curDay.revenue += ord.total_amount;
    curDay.orders += 1;
    dailyMap.set(dateKey, curDay);

    for (const item of ord.items) {
      const curMenu = menuMap.get(item.menu_id) || {
        menu_id: item.menu_id,
        name: item.menu_name,
        total_sold: 0
      };
      curMenu.total_sold += item.quantity;
      menuMap.set(item.menu_id, curMenu);
    }
  }

  const restock_recommendations = ingredients
    .filter((i) => i.current_stock <= i.rop)
    .map((i) => ({
      ingredient_id: i.id,
      name: i.name,
      current_stock: i.current_stock,
      rop: i.rop,
      recommended_buy_qty: Math.max(i.rop * 2 - i.current_stock, i.rop),
      unit: i.unit,
      priority: i.current_stock <= i.rop * 0.5 ? "high" : "medium"
    }));

  return res.json({
    success: true,
    message: "Data analitik berhasil diambil",
    data: {
      is_empty: false,
      total_revenue,
      total_orders: completedOrders.length,
      daily_sales_trend: Array.from(dailyMap.values()).sort((a, b) => a.date.localeCompare(b.date)),
      top_menus: Array.from(menuMap.values()).sort((a, b) => b.total_sold - a.total_sold),
      restock_recommendations
    }
  });
});

// 1.11 Ekspor Laporan Penjualan CSV
router.get("/reports/sales/export", (_req, res) => {
  const completedOrders = orders.filter((o) => o.status === "Selesai");
  const header = "order_code,channel,total_amount,created_at\n";
  const rows = completedOrders
    .map((o) => `${o.order_code},${o.channel},${o.total_amount},${o.created_at}`)
    .join("\n");

  res.setHeader("Content-Type", "text/csv; charset=utf-8");
  res.setHeader("Content-Disposition", 'attachment; filename="laporan-penjualan-samudera-jaya.csv"');
  res.send(header + rows);
});

// 1.12 Autentikasi Kasir & Pemilik
router.post("/auth/login", (req, res) => {
  const { username = "", password = "" } = req.body || {};
  const validUser = process.env.ADMIN_USERNAME || "admin";
  const validPass = process.env.ADMIN_PASSWORD || "samudera2026";

  if (username.trim() !== validUser || password !== validPass) {
    return res.status(401).json({
      success: false,
      error: {
        code: "INVALID_CREDENTIALS",
        message: "Username atau password salah",
        details: []
      }
    });
  }

  return res.json({
    success: true,
    message: "Login berhasil",
    data: {
      token: "mock-admin-session-token",
      user: { username: validUser, role: "owner" }
    }
  });
});

export default router;
