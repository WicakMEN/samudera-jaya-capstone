// In-memory mock store sementara sebelum tim FS & DS menghubungkan ke PostgreSQL (Supabase/Neon).
// Struktur data mengikuti docs/API_CONTRACT.md & docs/PROJECT_CONTEXT.md.

export const ingredients = [
  { id: 1, name: "Mie Basah", current_stock: 4500, unit: "gram", rop: 1500, updated_at: new Date().toISOString() },
  { id: 2, name: "Bakso", current_stock: 90, unit: "butir", rop: 30, updated_at: new Date().toISOString() },
  { id: 3, name: "Bumbu Yamin", current_stock: 1800, unit: "gram", rop: 600, updated_at: new Date().toISOString() },
  { id: 4, name: "Kemasan Bowl", current_stock: 22, unit: "pcs", rop: 25, updated_at: new Date().toISOString() }
];

// Formula resep per 1 porsi menu
export const recipes = {
  1: [
    { ingredient_id: 1, qty_per_serving: 150 },
    { ingredient_id: 3, qty_per_serving: 30 },
    { ingredient_id: 4, qty_per_serving: 1 }
  ],
  2: [
    { ingredient_id: 1, qty_per_serving: 150 },
    { ingredient_id: 2, qty_per_serving: 5 },
    { ingredient_id: 3, qty_per_serving: 40 },
    { ingredient_id: 4, qty_per_serving: 1 }
  ],
  3: [
    { ingredient_id: 2, qty_per_serving: 6 },
    { ingredient_id: 4, qty_per_serving: 1 }
  ]
};

export const menus = [
  {
    id: 1,
    name: "Mie Ayam Original",
    category: "Makanan",
    price: 15000,
    description: "Mie basah kenyal dengan topping ayam kecap gurih dan sawi segar.",
    image_url: "https://images.unsplash.com/photo-1585032226651-759b368d7246?auto=format&fit=crop&w=600&q=80"
  },
  {
    id: 2,
    name: "Bakso Yamin Spesial",
    category: "Makanan",
    price: 18000,
    description: "Mie yamin manis gurih dipadukan dengan 5 butir bakso daging sapi.",
    image_url: "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80"
  },
  {
    id: 3,
    name: "Bakso Kuah Polos",
    category: "Makanan",
    price: 14000,
    description: "6 butir bakso daging sapi dengan kuah kaldu hangat.",
    image_url: "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=600&q=80"
  }
];

export const orders = [
  {
    order_id: 101,
    order_code: "ORD-20261126-101",
    customer_name: "Siti Aminah",
    channel: "online_katalog",
    status: "Menunggu Konfirmasi",
    notes: "Pedas sedang",
    total_amount: 33000,
    items: [
      { menu_id: 1, menu_name: "Mie Ayam Original", quantity: 1, subtotal: 15000 },
      { menu_id: 2, menu_name: "Bakso Yamin Spesial", quantity: 1, subtotal: 18000 }
    ],
    created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString()
  },
  {
    order_id: 100,
    order_code: "TRX-20261126-100",
    customer_name: "Pelanggan Kasir",
    channel: "offline_kasir",
    status: "Selesai",
    notes: "Meja 2",
    total_amount: 30000,
    items: [
      { menu_id: 1, menu_name: "Mie Ayam Original", quantity: 2, subtotal: 30000 }
    ],
    created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString()
  }
];

export const stockLogs = [];

export function computeMaxServings(menuId) {
  const recipe = recipes[menuId] || [];
  if (recipe.length === 0) return 0;
  let minServings = Infinity;
  for (const r of recipe) {
    const ing = ingredients.find((i) => i.id === r.ingredient_id);
    if (!ing) return 0;
    const possible = Math.floor(ing.current_stock / r.qty_per_serving);
    if (possible < minServings) minServings = possible;
  }
  return minServings === Infinity ? 0 : minServings;
}

export function deductIngredientsForItems(items) {
  const deducted = [];
  for (const item of items) {
    const recipe = recipes[item.menu_id] || [];
    for (const r of recipe) {
      const ing = ingredients.find((i) => i.id === r.ingredient_id);
      if (!ing) continue;
      const qtyToDeduct = r.qty_per_serving * item.quantity;
      ing.current_stock = Math.max(0, ing.current_stock - qtyToDeduct);
      ing.updated_at = new Date().toISOString();

      const existing = deducted.find((d) => d.ingredient_id === ing.id);
      if (existing) {
        existing.deducted_qty += qtyToDeduct;
        existing.remaining_stock = ing.current_stock;
        existing.is_low_stock = ing.current_stock <= ing.rop;
      } else {
        deducted.push({
          ingredient_id: ing.id,
          name: ing.name,
          deducted_qty: qtyToDeduct,
          unit: ing.unit,
          remaining_stock: ing.current_stock,
          rop: ing.rop,
          is_low_stock: ing.current_stock <= ing.rop
        });
      }
    }
  }
  const low_stock_alerts = deducted.filter((d) => d.is_low_stock);
  return { deducted_ingredients: deducted, low_stock_alerts };
}
