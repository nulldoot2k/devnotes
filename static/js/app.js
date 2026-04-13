/**
 * app.js — Controller chính: state, events, render
 */

const App = (() => {

  // ── State ───────────────────────────────────────────
  let state = {
    notes:       [],
    topics:      [],
    filterTopic: null,   // topic id hoặc null
    searchQuery: "",
    viewingId:   null,
  };

  // ── Getters ─────────────────────────────────────────
  const topicById = id => state.topics.find(t => String(t.id) === String(id));

  function filteredNotes() {
    return state.notes.filter(n => {
      const matchTopic = state.filterTopic === null || String(n.topic) === String(state.filterTopic);
      const q = state.searchQuery.toLowerCase();
      const matchQ = !q
        || n.question.toLowerCase().includes(q)
        || n.content.toLowerCase().includes(q)
        || (n.tags || []).some(t => t.toLowerCase().includes(q))
        || (topicById(n.topic)?.name || "").toLowerCase().includes(q);
      return matchTopic && matchQ;
    });
  }

  // ── Load data ────────────────────────────────────────
  async function loadData() {
    const params = {};
    if (state.filterTopic) params.topic = state.filterTopic;
    if (state.searchQuery) params.q = state.searchQuery;

    const data = await API.getNotes(params);
    state.notes  = data.notes;
    state.topics = data.topics;
  }

  // ── Render ───────────────────────────────────────────
  function renderAll() {
    renderStats();
    renderTopics();
    renderNotes();
  }

  function renderStats() {
    document.getElementById("statTotal").textContent  = state.notes.length;
    document.getElementById("statTopics").textContent = state.topics.length;
  }

  function renderTopics() {
    const list = document.getElementById("topicList");

    // Count per topic
    const countMap = {};
    state.notes.forEach(n => {
      if (n.topic) countMap[String(n.topic)] = (countMap[String(n.topic)] || 0) + 1;
    });

    const allItem = `
      <div class="topic-item ${state.filterTopic === null ? "active" : ""}"
           data-topic-id="__all__">
        <div class="topic-left">
          <div class="topic-dot" style="background:#94a3b8"></div>
          <div class="topic-name">Tất cả</div>
        </div>
        <span class="topic-count">${state.notes.length}</span>
      </div>`;

    const items = state.topics.map(t =>
      UI.topicItem(t, countMap[String(t.id)] || 0, String(state.filterTopic) === String(t.id))
    ).join("");

    list.innerHTML = allItem + items;
  }

  function renderNotes() {
    const grid  = document.getElementById("notesGrid");
    const notes = filteredNotes();
    const q     = state.searchQuery;

    // Toolbar
    const topic = state.filterTopic ? topicById(state.filterTopic) : null;
    document.getElementById("viewTitle").textContent =
      topic ? topic.name : (q ? `"${q}"` : "Tất cả Notes");
    document.getElementById("viewSubtitle").textContent =
      topic ? `${notes.length} note` : "";
    document.getElementById("resultBadge").textContent = `${notes.length} kết quả`;

    if (notes.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">${q ? "🔍" : "📝"}</div>
          <div class="empty-title">${q ? "Không tìm thấy kết quả" : "Chưa có note nào"}</div>
          <div class="empty-desc">${q ? "Thử từ khóa khác" : 'Nhấn "+ Thêm Note" để bắt đầu'}</div>
        </div>`;
      return;
    }

    grid.innerHTML = notes
      .map(n => UI.noteCard(n, state.topics, q))
      .join("");
  }

  // ── Populate topic <select> ───────────────────────────
  function populateTopicSelect(selectedId = null) {
    const sel = document.getElementById("fTopic");
    sel.innerHTML = '<option value="">— Chưa phân loại —</option>';
    state.topics.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      if (String(t.id) === String(selectedId)) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  // ═══════════════════════════════════════════
  //  NOTE FORM
  // ═══════════════════════════════════════════
  let editingId = null;

  function openAddModal() {
    editingId = null;
    document.getElementById("modalNoteTitle").textContent = "✏️ Thêm Note Mới";
    document.getElementById("fNoteId").value  = "";
    document.getElementById("fQuestion").value = "";
    document.getElementById("fContent").value  = "";
    document.getElementById("fTags").value     = "";
    populateTopicSelect(state.filterTopic);
    UI.openModal("modalNote");
    MD.initToolbar();
    setTimeout(() => document.getElementById("fQuestion").focus(), 80);
  }

  function openEditModal(id) {
    const n = state.notes.find(x => String(x.id) === String(id));
    if (!n) return;
    editingId = id;
    document.getElementById("modalNoteTitle").textContent = "✏️ Chỉnh sửa Note";
    document.getElementById("fNoteId").value   = id;
    document.getElementById("fQuestion").value = n.question;
    document.getElementById("fContent").value  = n.content;
    document.getElementById("fTags").value     = (n.tags || []).join(", ");
    populateTopicSelect(n.topic);
    UI.closeModal("modalDetail");
    UI.openModal("modalNote");
    MD.initToolbar();
    // reset preview
    const prev = document.getElementById('mdPreview');
    const ta   = document.getElementById('fContent');
    const pb   = document.getElementById('btnMdPreview');
    if (prev) { prev.style.display='none'; ta.style.display='block'; pb.textContent='👁 Preview'; pb.classList.remove('active'); }
  }

  async function saveNote() {
    const question = document.getElementById("fQuestion").value.trim();
    const content  = document.getElementById("fContent").value.trim();
    const topicRaw = document.getElementById("fTopic").value;
    const tagsRaw  = document.getElementById("fTags").value;

    if (!question) { alert("Vui lòng nhập câu hỏi!"); return; }
    if (!content)  { alert("Vui lòng nhập nội dung!"); return; }

    const payload = {
      question,
      content,
      topic: topicRaw || null,
      tags: tagsRaw ? tagsRaw.split(",").map(s => s.trim()).filter(Boolean) : [],
    };

    try {
      if (editingId !== null) {
        await API.updateNote(editingId, payload);
        UI.toast("✅ Đã cập nhật note!");
      } else {
        await API.createNote(payload);
        UI.toast("✅ Đã thêm note mới!");
      }
      UI.closeModal("modalNote");
      await refresh();
    } catch (err) {
      UI.toast("❌ Lỗi: " + err.message);
    }
  }

  // ═══════════════════════════════════════════
  //  DETAIL
  // ═══════════════════════════════════════════
  function openDetail(id) {
    const n = state.notes.find(x => String(x.id) === String(id));
    if (!n) return;
    state.viewingId = id;

    const topic = topicById(n.topic);
    const tags  = (n.tags || []).map(t => `<span class="tag">${UI.esc(t)}</span>`).join("");

    const topicBadge = topic
      ? `<span class="detail-topic-badge"
              style="background:${topic.color}18;color:${topic.color};border:1px solid ${topic.color}33">
           ${UI.esc(topic.name)}
         </span>`
      : "";

    document.getElementById("detailMeta").innerHTML =
      `${topicBadge}${tags}
       <span style="margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--text3)">
         ${UI.fmtDate(n.updatedAt)}
       </span>`;

    document.getElementById("detailQuestion").textContent = n.question;
    const answerEl = document.getElementById("detailAnswer");
    answerEl.innerHTML = (typeof marked !== 'undefined') ? marked.parse(n.content) : n.content.replace(/\n/g,'<br>');
    answerEl.classList.add('md-rendered');

    document.getElementById("detailEditBtn").onclick   = () => openEditModal(id);
    document.getElementById("detailDeleteBtn").onclick = async () => {
      if (!confirm("Xóa note này?")) return;
      try {
        await API.deleteNote(id);
        UI.closeModal("modalDetail");
        UI.toast("🗑 Đã xóa note");
        await refresh();
      } catch (err) { UI.toast("❌ " + err.message); }
    };

    UI.openModal("modalDetail");
  }

  // ═══════════════════════════════════════════
  //  TOPICS
  // ═══════════════════════════════════════════
  async function addTopic() {
    const input = document.getElementById("newTopicInput");
    const name  = input.value.trim();
    if (!name) return;
    try {
      await API.createTopic(name, UI.nextColor());
      input.value = "";
      UI.toast("✅ Đã thêm chủ đề: " + name);
      await refresh();
    } catch (err) { UI.toast("❌ " + err.message); }
  }

  async function deleteTopic(id) {
    if (!confirm("Xóa chủ đề này? Notes thuộc chủ đề sẽ thành 'Chưa phân loại'.")) return;
    try {
      await API.deleteTopic(id);
      if (String(state.filterTopic) === String(id)) state.filterTopic = null;
      UI.toast("🗑 Đã xóa chủ đề");
      await refresh();
    } catch (err) { UI.toast("❌ " + err.message); }
  }

  // ═══════════════════════════════════════════
  //  IMPORT / EXPORT
  // ═══════════════════════════════════════════
  async function exportData() {
    try {
      const data = await API.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `devnotes-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      UI.toast("⬇️ Đã export!");
    } catch (err) { UI.toast("❌ " + err.message); }
  }

  async function doImport() {
    const raw = document.getElementById("pasteJson").value.trim();
    if (!raw) { alert("Vui lòng paste hoặc chọn file JSON!"); return; }

    let parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) { alert("JSON không hợp lệ: " + e.message); return; }

    try {
      const res = await API.importData(parsed);
      UI.closeModal("modalImport");
      document.getElementById("pasteJson").value = "";
      UI.toast(`✅ Đã import ${res.added} notes!`);
      await refresh();
    } catch (err) { UI.toast("❌ " + err.message); }
  }

  // ═══════════════════════════════════════════
  //  REFRESH
  // ═══════════════════════════════════════════
  async function refresh() {
    const [data, topics] = await Promise.all([
      API.getNotes({ q: state.searchQuery }),
      API.getTopics(),
    ]);
    state.notes  = data.notes;
    state.topics = topics;
    renderAll();
  }

  // ═══════════════════════════════════════════
  //  FULLSCREEN EDITOR
  // ═══════════════════════════════════════════
  const FS = (() => {
    const overlay  = () => document.getElementById("fsEditor");
    const fsTa     = () => document.getElementById("fsContent");
    const mainTa   = () => document.getElementById("fContent");
    const preview  = () => document.getElementById("fsPreview");
    const titleEl  = () => document.getElementById("fsTitleLabel");
    let previewTimer = null;

    function updatePreview() {
      clearTimeout(previewTimer);
      previewTimer = setTimeout(() => {
        const html = (typeof marked !== "undefined")
          ? marked.parse(fsTa().value || "")
          : fsTa().value.replace(/\n/g, "<br>");
        preview().innerHTML = html;
      }, 120);
    }

    function open() {
      // Sync nội dung từ textarea chính vào FS
      fsTa().value = mainTa().value;
      // Hiển thị tiêu đề note
      const q = document.getElementById("fQuestion").value.trim();
      titleEl().textContent = q ? "✏️ " + q : "✏️ Editor";
      overlay().classList.add("show");
      updatePreview();
      setTimeout(() => {
        const ta = fsTa();
        ta.focus();
        ta.setSelectionRange(ta.value.length, ta.value.length);
      }, 60);
    }

    function close() {
      // Sync nội dung ngược lại vào textarea chính
      mainTa().value = fsTa().value;
      overlay().classList.remove("show");
    }

    function init() {
      // Nút expand trong toolbar
      document.getElementById("btnMdExpand").addEventListener("click", open);

      // Nút thu nhỏ trong FS header
      document.getElementById("fsBtnClose").addEventListener("click", close);

      // Nút lưu trong FS header — gọi saveNote() của App
      document.getElementById("fsBtnSave").addEventListener("click", async () => {
        close();
        // Đợi sync xong rồi save
        setTimeout(() => document.getElementById("btnSaveNote").click(), 50);
      });

      // Live preview khi gõ
      fsTa().addEventListener("input", updatePreview);

      // Phím tắt trong FS: Escape = thu nhỏ, Tab = indent
      fsTa().addEventListener("keydown", e => {
        if (e.key === "Escape") { e.preventDefault(); close(); }
        if (e.key === "Tab") {
          e.preventDefault();
          const ta = fsTa();
          const s = ta.selectionStart, end = ta.selectionEnd;
          ta.setRangeText("  ", s, end, "end");
          updatePreview();
        }
      });
    }

    return { init, open, close };
  })();

  // ═══════════════════════════════════════════
  //  EVENT WIRING
  // ═══════════════════════════════════════════
  function wireEvents() {
    // Header buttons
    document.getElementById("btnAdd").addEventListener("click", openAddModal);

    // Logout
    const logoutBtn = document.getElementById("btnLogout");
    if (logoutBtn) logoutBtn.addEventListener("click", () => {
      if (confirm("Đăng xuất?")) API.logout();
    });

    // Show username
    const userEl = document.getElementById("headerUser");
    if (userEl) userEl.textContent = "👤 " + (localStorage.getItem("dn_user") || "");
    document.getElementById("btnExport").addEventListener("click", exportData);
    document.getElementById("btnImport").addEventListener("click", () => {
      document.getElementById("pasteJson").value = "";
      UI.openModal("modalImport");
    });

    // Save note
    document.getElementById("btnSaveNote").addEventListener("click", saveNote);

    // Search
    let searchTimer;
    document.getElementById("searchInput").addEventListener("input", e => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(async () => {
        state.searchQuery = e.target.value;
        state.filterTopic = null;
        await refresh();
      }, 220);
    });

    // Clear filter
    document.getElementById("btnClearFilter").addEventListener("click", async () => {
      state.filterTopic = null;
      state.searchQuery = "";
      document.getElementById("searchInput").value = "";
      await refresh();
    });

    // Add topic
    document.getElementById("btnAddTopic").addEventListener("click", addTopic);
    document.getElementById("newTopicInput").addEventListener("keydown", e => {
      if (e.key === "Enter") addTopic();
    });

    // Import actions
    document.getElementById("btnDoImport").addEventListener("click", doImport);

    // File input → paste textarea
    document.getElementById("fileInput").addEventListener("change", e => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = ev => { document.getElementById("pasteJson").value = ev.target.result; };
      reader.readAsText(file);
      e.target.value = "";
    });

    // Drag & drop on import zone
    const zone = document.getElementById("importDropZone");
    zone.addEventListener("dragover",  e => { e.preventDefault(); zone.classList.add("drag-over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", e => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = ev => { document.getElementById("pasteJson").value = ev.target.result; };
      reader.readAsText(file);
    });

    // Note grid: delegate clicks
    document.getElementById("notesGrid").addEventListener("click", e => {
      const editBtn   = e.target.closest(".note-edit-btn");
      const deleteBtn = e.target.closest(".note-delete-btn");
      const card      = e.target.closest(".note-card");

      if (editBtn) {
        e.stopPropagation();
        openEditModal(editBtn.dataset.id);
        return;
      }
      if (deleteBtn) {
        e.stopPropagation();
        const id = deleteBtn.dataset.id;
        if (confirm("Xóa note này?")) {
          API.deleteNote(id)
            .then(() => { UI.toast("🗑 Đã xóa note"); return refresh(); })
            .catch(err => UI.toast("❌ " + err.message));
        }
        return;
      }
      if (card) openDetail(card.dataset.id);
    });

    // Topic list: delegate clicks
    document.getElementById("topicList").addEventListener("click", async e => {
      const delBtn = e.target.closest("[data-topic-del]");
      const item   = e.target.closest("[data-topic-id]");

      if (delBtn) {
        e.stopPropagation();
        await deleteTopic(delBtn.dataset.topicDel);
        return;
      }
      if (item) {
        const rawId = item.dataset.topicId;
        state.filterTopic = rawId === "__all__" ? null : rawId;
        state.searchQuery = "";
        document.getElementById("searchInput").value = "";
        await refresh();
      }
    });

    // Keyboard shortcuts
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") {
        // Nếu FS đang mở → thu nhỏ, không đóng modal bên dưới
        if (document.getElementById("fsEditor").classList.contains("show")) {
          FS.close(); return;
        }
        document.querySelectorAll(".modal-overlay.show")
          .forEach(m => m.classList.remove("show"));
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        const inp = document.getElementById("searchInput");
        inp.focus(); inp.select();
      }
      if (e.altKey && e.key === "n") {
        e.preventDefault();
        openAddModal();
      }
      // F11 → toggle fullscreen editor (khi modal note đang mở)
      if (e.key === "F11") {
        const modalOpen = document.getElementById("modalNote").classList.contains("show");
        const fsOpen    = document.getElementById("fsEditor").classList.contains("show");
        if (modalOpen || fsOpen) {
          e.preventDefault();
          fsOpen ? FS.close() : FS.open();
        }
      }
    });

    // Init fullscreen editor
    FS.init();
  }

  // ═══════════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════════
  async function init() {
    wireEvents();
    await refresh();
  }

  document.addEventListener("DOMContentLoaded", init);

})();
