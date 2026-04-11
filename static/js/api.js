/**
 * api.js — Tất cả các lời gọi tới Flask backend
 * Tự động đính kèm JWT token từ localStorage vào mọi request.
 */

const API = (() => {

  function getToken() {
    return localStorage.getItem("dn_token") || "";
  }

  async function request(method, path, body = null) {
    const headers = { "Content-Type": "application/json" };
    const token   = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body !== null) opts.body = JSON.stringify(body);

    const res = await fetch(path, opts);

    // Token hết hạn / chưa login → redirect về login
    if (res.status === 401) {
      localStorage.removeItem("dn_token");
      localStorage.removeItem("dn_user");
      window.location.href = "/login";
      return;
    }

    // ── Safe JSON parse ──────────────────────────────────────────
    // Không gọi .json() mù quáng — Flask debug page / nginx error đều là HTML
    // Nếu không phải JSON → đọc text để hiện error rõ ràng
    const contentType = res.headers.get("Content-Type") || "";
    let data = null;

    if (contentType.includes("application/json")) {
      data = await res.json();
    } else if (res.status !== 204) {
      const text = await res.text();
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      return null;
    }

    if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
    return data;
  }

  return {
    // ── Auth ───────────────────────────────────────────────────
    logout() {
      return fetch("/api/auth/logout", {
        method:  "POST",
        headers: { "Authorization": `Bearer ${getToken()}` },
      }).finally(() => {
        localStorage.removeItem("dn_token");
        localStorage.removeItem("dn_user");
        window.location.href = "/login";
      });
    },

    getMe() {
      return request("GET", "/api/auth/me");
    },

    // ── Notes ──────────────────────────────────────────────────
    getNotes(params = {}) {
      const qs = new URLSearchParams();
      if (params.q)     qs.set("q", params.q);
      if (params.topic) qs.set("topic", params.topic);
      return request("GET", `/api/notes?${qs}`);
    },

    createNote(note) {
      return request("POST", "/api/notes", note);
    },

    updateNote(id, note) {
      return request("PUT", `/api/notes/${id}`, note);
    },

    deleteNote(id) {
      return request("DELETE", `/api/notes/${id}`);
    },

    // ── Topics ─────────────────────────────────────────────────
    getTopics() {
      return request("GET", "/api/topics");
    },

    createTopic(name, color) {
      return request("POST", "/api/topics", { name, color });
    },

    deleteTopic(id) {
      return request("DELETE", `/api/topics/${id}`);
    },

    // ── Import / Export ────────────────────────────────────────
    exportData() {
      return request("GET", "/api/export");
    },

    importData(payload) {
      return request("POST", "/api/import", payload);
    },
  };
})();
