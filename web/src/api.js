// Thin API client. Base URL from env, defaults to the dev proxy (/v1).
const BASE = import.meta.env.VITE_API_BASE || "/v1";

function token() {
  return localStorage.getItem("farmingos_token") || "";
}
export function setToken(t) {
  localStorage.setItem("farmingos_token", t);
}
export function clearToken() {
  localStorage.removeItem("farmingos_token");
}

async function req(path, { method = "GET", body, auth = false, form } = {}) {
  const headers = {};
  if (auth && token()) headers["Authorization"] = `Bearer ${token()}`;
  let payload;
  if (form) {
    payload = form; // FormData; browser sets content-type
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  // auth + onboarding
  requestOtp: (phone) => req("/auth/otp/request", { method: "POST", body: { phone } }),
  onboard: (data) => req("/farmers/onboard", { method: "POST", body: data }),
  staffLogin: (email, password) =>
    req("/auth/staff/login", { method: "POST", body: { email, password } }),
  // reference
  crops: () => req("/crops"),
  markets: () => req("/markets"),
  // conversation
  ingest: (external_user_id, text) =>
    req("/messages:ingest", { method: "POST", body: { channel: "web", external_user_id, text } }),
  cropDiagnose: (farmerId, file, lang) => {
    const fd = new FormData();
    fd.append("image", file);
    fd.append("farmer_id", farmerId);
    fd.append("lang", lang);
    return req("/agents/crop", { method: "POST", form: fd });
  },
  // staff: prices
  prices: (q = "") => req(`/prices${q}`, { auth: true }),
  addPrice: (p) => req("/prices", { method: "POST", body: p, auth: true }),
  bulkPrices: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return req("/prices:bulk", { method: "POST", form: fd, auth: true });
  },
  coverage: () => req("/prices/coverage", { auth: true }),
  // officer
  escalations: (status = "open") => req(`/escalations?status=${status}`, { auth: true }),
  escalationClaim: (id) => req(`/escalations/${id}:claim`, { method: "POST", auth: true }),
  escalationResolve: (id, note) =>
    req(`/escalations/${id}:resolve`, { method: "POST", body: { note }, auth: true }),
  logOutcome: (body) => req("/outcomes", { method: "POST", body, auth: true }),
  // admin / knowledge base
  kbDocs: () => req("/kb/docs", { auth: true }),
  kbCreate: (d) => req("/kb/docs", { method: "POST", body: d, auth: true }),
  kbPatch: (id, d) => req(`/kb/docs/${id}`, { method: "PATCH", body: d, auth: true }),
  kbReindex: (id) => req(`/kb/docs/${id}:reindex`, { method: "POST", auth: true }),
  getSettings: () => req("/admin/settings", { auth: true }),
  patchSettings: (d) => req("/admin/settings", { method: "PATCH", body: d, auth: true }),
  adminFarmers: () => req("/admin/farmers", { auth: true }),
  adminConversations: () => req("/admin/conversations", { auth: true }),
  northstar: () => req("/metrics/northstar", { auth: true }),
  usage: () => req("/metrics/usage", { auth: true }),
  dashboard: () => req("/metrics/dashboard", { auth: true }),
  // PDPA (farmer)
  exportData: () => req("/farmers/me/data", { auth: true }),
  eraseData: () => req("/farmers/me:erase", { method: "POST", auth: true }),
};
