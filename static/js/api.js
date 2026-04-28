/**
 * api.js — Tất cả lời gọi tới Flask backend
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

    // Token hết hạn / chưa login → redirect
    if (res.status === 401) {
      localStorage.removeItem("dn_token");
      localStorage.removeItem("dn_user");
      window.location.href = "/login";
      return;
    }

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
    // ── Auth ─────────────────────────────────────────────────
    logout() {
      return fetch("/api/auth/logout", {
        method: "POST",
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

    changePassword(oldPassword, newPassword) {
      return request("POST", "/api/auth/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
    },

    // ── Notes ────────────────────────────────────────────────
    getNotes(params = {}) {
      const qs = new URLSearchParams();
      if (params.q)     qs.set("q",     params.q);
      if (params.topic) qs.set("topic", params.topic);
      return request("GET", `/api/notes?${qs}`);
    },

    createNote(note) {
      return request("POST", "/api/notes", note);
    },

    updateNote(id, note) {
      if (!id) throw new Error("updateNote: id is required");
      return request("PUT", `/api/notes/${id}`, note);
    },

    deleteNote(id) {
      if (!id) throw new Error("deleteNote: id is required");
      return request("DELETE", `/api/notes/${id}`);
    },

    // ── Topics ───────────────────────────────────────────────
    getTopics() {
      return request("GET", "/api/topics");
    },

    createTopic(name, color) {
      return request("POST", "/api/topics", { name, color });
    },

    deleteTopic(id) {
      if (!id) throw new Error("deleteTopic: id is required");
      return request("DELETE", `/api/topics/${id}`);
    },

    // ── Import / Export ───────────────────────────────────────
    exportData() {
      return request("GET", "/api/export");
    },

    importData(payload) {
      return request("POST", "/api/import", payload);
    },

    // ── Image Upload ─────────────────────────────────────────
    /**
     * Upload ảnh lên static/temp/ (cache tạm).
     * Ảnh chỉ được persist khi note được Save.
     * Trả về { url, filename, temp: true }
     */
    async uploadImage(file) {
      const token = getToken();
      const form  = new FormData();
      form.append("file", file);

      const res = await fetch("/api/images/upload", {
        method:  "POST",
        headers: token ? { "Authorization": `Bearer ${token}` } : {},
        body:    form,
      });

      if (res.status === 401) {
        localStorage.removeItem("dn_token");
        localStorage.removeItem("dn_user");
        window.location.href = "/login";
        return;
      }

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    },

    /**
     * Báo server xóa ảnh temp trong content (khi Cancel / đóng modal).
     * @param {string} content — nội dung markdown hiện tại trong textarea
     */
    discardImages(content) {
      if (!content || !content.includes("/static/temp/")) return Promise.resolve();
      return request("POST", "/api/images/discard", { content });
    },
  };
})();
