/**
 * ui.js — Render helpers, modal, toast
 */

const UI = (() => {

  const TOPIC_COLORS = [
    "#4fffb0","#00c8ff","#ff6b6b","#ffd166",
    "#a78bfa","#fb923c","#f472b6","#34d399",
    "#60a5fa","#e879f9","#94a3b8","#ff9f43",
  ];

  let colorIndex = 0;
  function nextColor() {
    return TOPIC_COLORS[colorIndex++ % TOPIC_COLORS.length];
  }

  // ── Escaping ──────────────────────────────────────
  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function highlight(text, q) {
    if (!q || !q.trim()) return esc(text);
    return esc(text).replace(
      new RegExp(`(${escRe(q)})`, "gi"),
      "<mark>$1</mark>"
    );
  }

  // ── Date ─────────────────────────────────────────
  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;
  }

  // ── Modal ─────────────────────────────────────────
  function openModal(id)  { document.getElementById(id).classList.add("show"); }
  function closeModal(id) { document.getElementById(id).classList.remove("show"); }

  // Close buttons (data-close attribute)
  document.addEventListener("click", e => {
    const target = e.target.closest("[data-close]");
    if (target) closeModal(target.dataset.close);
  });

  // Click outside overlay
  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", e => {
      if (e.target === overlay) overlay.classList.remove("show");
    });
  });

  // ── Toast ─────────────────────────────────────────
  function toast(msg, ms = 2800) {
    const container = document.getElementById("toastContainer");
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  // ── Note card ─────────────────────────────────────
  function noteCard(note, topics, query = "") {
    const topic = topics.find(t => t.id === note.topic);
    const color = topic ? topic.color : "#94a3b8";
    const preview = note.content.replace(/\n/g, " ").slice(0, 190);

    const topicTag = topic
      ? `<span class="tag" style="color:${color};border-color:${color}22;background:${color}11">${esc(topic.name)}</span>`
      : "";

    const tags = (note.tags || [])
      .slice(0, 4)
      .map(t => `<span class="tag">${esc(t)}</span>`)
      .join("");

    return `
      <div class="note-card" style="--card-accent:${color}"
           data-id="${note.id}">
        <div class="note-actions">
          <button class="btn btn-ghost btn-sm btn-icon note-edit-btn" data-id="${note.id}" title="Sửa">✏️</button>
          <button class="btn btn-danger btn-sm btn-icon note-delete-btn" data-id="${note.id}" title="Xóa">🗑</button>
        </div>
        <div class="note-card-header">
          <div class="note-q">${highlight(note.question, query)}</div>
        </div>
        <div class="note-preview">${highlight(preview, query)}</div>
        <div class="note-footer">
          <div class="note-tags">${topicTag}${tags}</div>
          <div class="note-meta">${fmtDate(note.updatedAt)}</div>
        </div>
      </div>`;
  }

  // ── Topic item ────────────────────────────────────
  function topicItem(topic, count, isActive) {
    return `
      <div class="topic-item ${isActive ? "active" : ""}" data-topic-id="${topic.id}">
        <div class="topic-left">
          <div class="topic-dot" style="background:${topic.color}"></div>
          <div class="topic-name">${esc(topic.name)}</div>
        </div>
        <span class="topic-count">${count}</span>
        <button class="topic-delete" data-topic-del="${topic.id}" title="Xóa chủ đề">✕</button>
      </div>`;
  }

  return {
    TOPIC_COLORS,
    nextColor,
    esc,
    highlight,
    fmtDate,
    openModal,
    closeModal,
    toast,
    noteCard,
    topicItem,
  };
})();

// ── Markdown Toolbar ──────────────────────────────
const MD = (() => {
  function insertAt(ta, before, after, defaultText) {
    const start = ta.selectionStart;
    const end   = ta.selectionEnd;
    const sel   = ta.value.slice(start, end) || defaultText;
    const replacement = before + sel + after;
    ta.setRangeText(replacement, start, end, "select");
    ta.focus();
  }

  function insertLinePrefix(ta, prefix) {
    const start = ta.selectionStart;
    const end   = ta.selectionEnd;
    const lines = ta.value.split("\n");

    let charCount = 0;
    let startLine = 0, endLine = 0;
    for (let i = 0; i < lines.length; i++) {
      if (charCount + lines[i].length >= start && startLine === 0) startLine = i;
      if (charCount + lines[i].length >= end) { endLine = i; break; }
      charCount += lines[i].length + 1;
    }

    for (let i = startLine; i <= endLine; i++) {
      lines[i] = prefix + lines[i];
    }
    ta.value = lines.join("\n");
    ta.focus();
  }

  const actions = {
    bold:       ta => insertAt(ta, "**", "**", "bold text"),
    italic:     ta => insertAt(ta, "_", "_", "italic text"),
    code:       ta => insertAt(ta, "`", "`", "code"),
    codeblock:  ta => insertAt(ta, "```\n", "\n```", "code here"),
    h2:         ta => insertLinePrefix(ta, "## "),
    h3:         ta => insertLinePrefix(ta, "### "),
    ul:         ta => insertLinePrefix(ta, "- "),
    ol:         ta => insertLinePrefix(ta, "1. "),
    blockquote: ta => insertLinePrefix(ta, "> "),
  };

  function initToolbar() {
    const toolbar = document.querySelector(".md-toolbar");
    const ta      = document.getElementById("fContent");
    const preview = document.getElementById("mdPreview");
    const prevBtn = document.getElementById("btnMdPreview");
    if (!toolbar || !ta) return;

    // ── Paste handler: tự convert URL ảnh → ![](url) khi paste ──
    ta.addEventListener("paste", e => {
      const pasted = (e.clipboardData || window.clipboardData).getData("text");
      if (!pasted) return;

      const imageUrlRe = /^https?:\/\/[^\s<>"]+?\.(?:png|jpg|jpeg|gif|webp|svg)\s*$/i;
      if (imageUrlRe.test(pasted.trim())) {
        e.preventDefault(); // chặn paste thô
        const converted = `![](${pasted.trim()})`;
        const start = ta.selectionStart;
        const end   = ta.selectionEnd;
        ta.setRangeText(converted, start, end, "end");
        ta.dispatchEvent(new Event("input")); // trigger preview nếu đang mở
      }
    });

    let showingPreview = false;

    toolbar.addEventListener("click", e => {
      const btn = e.target.closest(".md-btn[data-md]");
      if (!btn) return;
      const action = btn.dataset.md;
      if (actions[action]) actions[action](ta);
    });

    prevBtn.addEventListener("click", () => {
      showingPreview = !showingPreview;
      if (showingPreview) {
        preview.innerHTML = marked.parse(ta.value || "_Chưa có nội dung_");
        preview.classList.add("md-rendered");
        preview.style.display = "block";
        ta.style.display = "none";
        prevBtn.classList.add("active");
        prevBtn.textContent = "✏️ Edit";
      } else {
        preview.style.display = "none";
        ta.style.display = "block";
        prevBtn.classList.remove("active");
        prevBtn.textContent = "👁 Preview";
      }
    });
  }

  return { initToolbar };
})();
