import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:3000/api/v1";
const AI_BASE_URL = import.meta.env.VITE_AI_BASE_URL || "http://localhost:8000/api/v1/ai";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000
});

export const aiClient = axios.create({
  baseURL: AI_BASE_URL,
  timeout: 20000
});

const TOKEN_KEY = "sj_admin_token";

export const loginAdmin = async (credentials) => {
  const res = await apiClient.post("/auth/login", credentials);
  const { token, user } = res.data.data;
  localStorage.setItem(TOKEN_KEY, token);
  return { token, user };
};

export const logoutAdmin = () => {
  localStorage.removeItem(TOKEN_KEY);
};

export const isAdminAuthenticated = () => Boolean(localStorage.getItem(TOKEN_KEY));

export const fetchMenus = async () => {
  const res = await apiClient.get("/menus");
  return res.data.data;
};

export const createOrder = async (payload) => {
  const res = await apiClient.post("/orders", payload);
  return res.data.data;
};

export const fetchOrders = async (status) => {
  const res = await apiClient.get("/orders", { params: status ? { status } : {} });
  return res.data.data;
};

export const updateOrderStatus = async (orderId, status) => {
  const res = await apiClient.patch(`/orders/${orderId}/status`, { status });
  return res.data.data;
};

export const createOfflineTransaction = async (payload) => {
  const res = await apiClient.post("/transactions/offline", payload);
  return res.data.data;
};

export const fetchIngredients = async () => {
  const res = await apiClient.get("/ingredients");
  return res.data.data;
};

export const restockIngredients = async (payload) => {
  const res = await apiClient.post("/ingredients/restock", payload);
  return res.data.data;
};

export const adjustIngredientStock = async (id, payload) => {
  const res = await apiClient.patch(`/ingredients/${id}/adjust`, payload);
  return res.data.data;
};

export const fetchAnalyticsSummary = async (days = 7) => {
  const res = await apiClient.get("/analytics/summary", { params: { days } });
  return res.data.data;
};

export const getExportCsvUrl = () => `${API_BASE_URL}/reports/sales/export?format=csv`;

export const parseRestockAI = async ({ text, imageFile }) => {
  if (imageFile) {
    const formData = new FormData();
    formData.append("input_type", text ? "hybrid" : "image");
    formData.append("image", imageFile);
    if (text) formData.append("text", text);
    const res = await aiClient.post("/restock-parse", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return res.data.data;
  }

  const res = await aiClient.post("/restock-parse", {
    input_type: "text",
    text
  });
  return res.data.data;
};
