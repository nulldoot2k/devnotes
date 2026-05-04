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
  //  UNSAVED CHANGES GUARD
  // ═══════════════════════════════════════════

  let _savedQuestion   = "";
  let _savedContent    = "";
  let _originalContent = "";
 
  function markSaved() {
    _savedQuestion = document.getElementById("fQuestion").value;
    _savedContent  = document.getElementById("fContent").value;
  }
 
  function hasUnsavedChanges() {
    const q = document.getElementById("fQuestion").value;
    const c = document.getElementById("fContent").value;
    return q !== _savedQuestion || c !== _savedContent;
  }
 
  // ← THÊM: discard ảnh temp khi thoát không save
  function _discardCurrentTemp() {
    const ta = document.getElementById("fContent");
    if (!ta) return;
    const content = ta.value || "";
    if (content.includes("/temp/")) {
      API.discardImages(content).catch(() => {});
    }
  }
 
  function confirmClose() {
    if (!hasUnsavedChanges()) {
      _discardCurrentTemp();   // ← THÊM
      return true;
    }
    if (confirm("Bạn có nội dung chưa lưu. Thoát không?")) {
      _discardCurrentTemp();   // ← THÊM
      return true;
    }
    return false;
  }

  /**
   * Gọi /api/images/discard cho tất cả URL temp trong textarea hiện tại.
   * Dùng khi user đóng modal mà không bấm Save.
   */
  function _discardCurrentTemp() {
    const ta = document.getElementById("fContent");
    if (!ta) return;
    const content = ta.value || "";
    // Chỉ gọi nếu có URL temp (tránh request thừa)
    if (content.includes("/temp/")) {
      API.discardImages(content).catch(() => {});
    }
  }

  // ═══════════════════════════════════════════
  //  IMAGE PASTE HANDLER
  //  Dùng chung cho cả #fContent và #fsContent
  // ═══════════════════════════════════════════

  /**
   * Chèn text vào textarea tại vị trí con trỏ.
   * @param {HTMLTextAreaElement} ta
   * @param {string} text
   */
  function insertAtCursor(ta, text) {
    const start = ta.selectionStart;
    const end   = ta.selectionEnd;
    ta.setRangeText(text, start, end, "end");
    // Trigger input event để live-preview cập nhật
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /**
   * Xử lý paste ảnh từ clipboard vào một textarea.
   * - Thêm placeholder `<!-- Uploading "filename"... -->`
   * - Upload lên server
   * - Thay placeholder bằng `<img ... src="url" />`
   *
   * @param {ClipboardEvent} e
   * @param {HTMLTextAreaElement} ta  — textarea nhận paste
   */
  async function handleImagePaste(e, ta) {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItem = items.find(it => it.type.startsWith("image/"));
    if (!imageItem) return;   // không có ảnh → để trình duyệt xử lý bình thường

    e.preventDefault();

    const file      = imageItem.getAsFile();
    const ext       = file.type.split("/")[1]?.replace("jpeg", "jpg") || "png";
    const filename  = `image.${ext}`;
    const placeholder = `<!-- Uploading "${filename}"... -->`;

    // 1. Chèn placeholder ngay lập tức
    insertAtCursor(ta, placeholder);

    // Lưu vị trí placeholder để replace sau
    // (placeholder bắt đầu tại selectionStart - placeholder.length sau khi chèn)
    const placeholderStart = ta.selectionStart - placeholder.length;

    try {
      // 2. Upload lên server
      const { url } = await API.uploadImage(file);

      // Kích thước thực tế của ảnh (để điền width/height)
      let width = 0, height = 0;
      try {
        const bmp = await createImageBitmap(file);
        width  = bmp.width;
        height = bmp.height;
        bmp.close();
      } catch (_) { /* bỏ qua nếu trình duyệt không hỗ trợ */ }

      // 3. Build chuỗi thay thế giống GitHub
      //    <img width="W" height="H" alt="Image" src="URL" />
      //    Nếu không lấy được kích thước thì bỏ width/height
      let imgTag;
      if (width && height) {
        imgTag = `<img width="${width}" height="${height}" alt="Image" src="${url}" />`;
      } else {
        imgTag = `<img alt="Image" src="${url}" />`;
      }

      // 4. Replace placeholder bằng img tag
      //    Tìm lại placeholder trong value (đề phòng user đã gõ thêm)
      const currentVal = ta.value;
      const idx = currentVal.indexOf(placeholder, Math.max(0, placeholderStart - 5));
      if (idx !== -1) {
        ta.value =
          currentVal.slice(0, idx) +
          imgTag +
          currentVal.slice(idx + placeholder.length);
        // Đặt con trỏ sau img tag
        const newPos = idx + imgTag.length;
        ta.setSelectionRange(newPos, newPos);
      } else {
        // Fallback: placeholder bị mất (user xoá) → chèn vào vị trí con trỏ hiện tại
        insertAtCursor(ta, imgTag);
      }

      ta.dispatchEvent(new Event("input", { bubbles: true }));
      UI.toast("🖼 Đã upload ảnh!");

    } catch (err) {
      // Upload thất bại → xoá placeholder, hiển thị lỗi
      const currentVal = ta.value;
      const idx = currentVal.indexOf(placeholder, Math.max(0, placeholderStart - 5));
      if (idx !== -1) {
        ta.value =
          currentVal.slice(0, idx) +
          currentVal.slice(idx + placeholder.length);
        const newPos = idx;
        ta.setSelectionRange(newPos, newPos);
        ta.dispatchEvent(new Event("input", { bubbles: true }));
      }
      UI.toast(`❌ Upload ảnh thất bại: ${err.message}`);
    }
  }

  // ═══════════════════════════════════════════
  //  NOTE FORM
  // ═══════════════════════════════════════════
  let editingId = null;

  function openAddModal() {
    editingId = null;
    _originalContent = "";
    document.getElementById("modalNoteTitle").textContent = "✏️ Thêm Note Mới";
    document.getElementById("fNoteId").value   = "";
    document.getElementById("fQuestion").value = "";
    document.getElementById("fContent").value  = "";
    document.getElementById("fTags").value     = "";
    populateTopicSelect(state.filterTopic);
    UI.openModal("modalNote");
    MD.initToolbar();
    setTimeout(() => {
      markSaved();
      document.getElementById("fQuestion").focus();
    }, 80);
  }

  function openEditModal(id) {
    const n = state.notes.find(x => String(x.id) === String(id));
    if (!n) return;
    editingId = id;
    _originalContent = n.content;
    document.getElementById("modalNoteTitle").textContent = "✏️ Chỉnh sửa Note";
    document.getElementById("fNoteId").value   = id;
    document.getElementById("fQuestion").value = n.question;
    document.getElementById("fContent").value  = n.content;
    document.getElementById("fTags").value     = (n.tags || []).join(", ");
    populateTopicSelect(n.topic);
    UI.closeModal("modalDetail");
    UI.openModal("modalNote");
    MD.initToolbar();
    const prev = document.getElementById('mdPreview');
    const ta   = document.getElementById('fContent');
    const pb   = document.getElementById('btnMdPreview');
    if (prev) { prev.style.display='none'; ta.style.display='block'; pb.textContent='👁 Preview'; pb.classList.remove('active'); }
    markSaved();
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
      markSaved();
      UI.closeModal("modalNote");
      await refresh();
    } catch (err) {
      UI.toast("❌ Lỗi: " + err.message);
    }
  }

  // ═══════════════════════════════════════════
  //  DETAIL MODAL
  // ═══════════════════════════════════════════
  function openDetail(id) {
    const n = state.notes.find(x => String(x.id) === String(id));
    if (!n) return;

    state.viewingId = id;

    document.getElementById("detailQuestion").textContent = n.question;

    const topic = topicById(n.topic);
    let metaHTML = '';

    if (topic) {
      metaHTML += `
        <span class="detail-topic-badge" 
              style="--tc:${topic.color}">
          ${UI.esc(topic.name)}
        </span>`;
    }

    if (n.tags && n.tags.length > 0) {
      metaHTML += (n.tags || []).map(t => 
        `<span class="tag">${UI.esc(t)}</span>`
      ).join('');
    }

    metaHTML += `
      <span style="margin-left:auto;font-family:var(--mono);font-size:12.5px;color:var(--text3)">
        ${UI.fmtDate(n.updatedAt)}
      </span>`;

    document.getElementById("detailMeta").innerHTML = metaHTML;

    const answerEl = document.getElementById("detailAnswer");
    answerEl.innerHTML = (typeof marked !== 'undefined') 
      ? marked.parse(n.content) 
      : n.content.replace(/\n/g, '<br>');
    answerEl.classList.add('md-rendered');

    document.getElementById("detailEditBtn").onclick   = () => openEditModal(id);
    document.getElementById("detailDeleteBtn").onclick = async () => {
      if (!confirm("Xóa note này?")) return;
      try {
        await API.deleteNote(id);
        UI.closeModal("modalDetail");
        UI.toast("🗑 Đã xóa note");
        await refresh();
      } catch (err) { 
        UI.toast("❌ " + err.message); 
      }
    };

    document.getElementById("detailCopyBtn").onclick = () => {
      navigator.clipboard.writeText(n.content).then(() => {
        UI.toast("📋 Đã sao chép nội dung Markdown!");
      }).catch(() => UI.toast("📋 Đã sao chép!"));
    };

    document.getElementById("detailExportPdfBtn").onclick = () => {
      exportSingleNotePdf(n);
    };

    const fsBtn = document.getElementById("btnDetailFullscreen");
    if (fsBtn) fsBtn.innerHTML = "⛶";

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
      fsTa().value = mainTa().value;
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
      mainTa().value = fsTa().value;
      overlay().classList.remove("show");
    }

    function init() {
      document.getElementById("btnMdExpand").addEventListener("click", open);
      document.getElementById("fsBtnClose").addEventListener("click", close);
      document.getElementById("fsBtnSave").addEventListener("click", async () => {
        close();
        setTimeout(() => document.getElementById("btnSaveNote").click(), 50);
      });

      // Scroll sync: textarea → preview
      fsTa().addEventListener("scroll", () => {
        const ta = fsTa();
        const pv = preview();
        if (!pv) return;
        const ratio = ta.scrollTop / (ta.scrollHeight - ta.clientHeight || 1);
        pv.scrollTop = ratio * (pv.scrollHeight - pv.clientHeight);
      });

      // ── Paste handler cho fsContent ──────────────────────
      // Ưu tiên: ảnh → upload | URL ảnh → convert | text thường → default
      fsTa().addEventListener("paste", async e => {
        // 1. Thử xử lý ảnh từ clipboard
        const items = Array.from(e.clipboardData?.items || []);
        const imageItem = items.find(it => it.type.startsWith("image/"));
        if (imageItem) {
          await handleImagePaste(e, fsTa());
          updatePreview();
          return;
        }

        // 2. URL ảnh thuần (hành vi cũ)
        const pasted = (e.clipboardData || window.clipboardData).getData("text");
        if (!pasted) return;
        const imageUrlRe = /^https?:\/\/[^\s<>"]+?\.(?:png|jpg|jpeg|gif|webp|svg)(\?[^\s]*)?$/i;
        if (imageUrlRe.test(pasted.trim())) {
          e.preventDefault();
          const ta = fsTa();
          const converted = `![](${pasted.trim()})`;
          const start = ta.selectionStart;
          const end   = ta.selectionEnd;
          ta.setRangeText(converted, start, end, "end");
          updatePreview();
        }
      });

      // Live preview khi gõ
      fsTa().addEventListener("input", updatePreview);

      // Phím tắt trong FS
      fsTa().addEventListener("keydown", e => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          close();
          return;
        }
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
  //  FULLSCREEN DETAIL VIEW
  // ═══════════════════════════════════════════
  const FSD = (() => {
    const overlay   = () => document.getElementById("fsDetail");
    const titleEl   = () => document.getElementById("fsDetailTitle");
    const metaEl    = () => document.getElementById("fsDetailMeta");
    const contentEl = () => document.getElementById("fsDetailContent");
    
    let currentNoteId = null;

    function open(note) {
      if (!note) return;
      currentNoteId = note.id;

      titleEl().textContent = note.question || "Chi tiết Note";

      const topic = topicById ? topicById(note.topic) : null;
      let metaHTML = '';

      if (topic) {
        metaHTML += `
          <span class="detail-topic-badge" 
                style="--tc:${topic.color}">
            ${UI.esc(topic.name)}
          </span>`;
      }

      if (note.tags && note.tags.length > 0) {
        metaHTML += (note.tags || []).map(t => 
          `<span class="tag">${UI.esc(t)}</span>`
        ).join('');
      }

      metaHTML += `
        <span style="margin-left:auto;font-family:var(--mono);font-size:13px;color:#64748b;">
          ${UI.fmtDate(note.updatedAt)}
        </span>`;

      metaEl().innerHTML = metaHTML;

      const htmlContent = (typeof marked !== 'undefined') 
        ? marked.parse(note.content || "") 
        : (note.content || "").replace(/\n/g, '<br>');

      contentEl().innerHTML = htmlContent;
      contentEl().classList.add('md-rendered');

      overlay().classList.add("show");

      const fsBtn = document.getElementById("btnDetailFullscreen");
      if (fsBtn) fsBtn.innerHTML = "❐";
    }

    function close() {
      overlay().classList.remove("show");
      
      const fsBtn = document.getElementById("btnDetailFullscreen");
      if (fsBtn) fsBtn.innerHTML = "⛶";

      currentNoteId = null;
    }

    function toggle() {
      if (overlay().classList.contains("show")) {
        close();
      } else if (state.viewingId) {
        const note = state.notes.find(n => String(n.id) === String(state.viewingId));
        if (note) open(note);
      }
    }

    function init() {
      const fsButton = document.getElementById("btnDetailFullscreen");
      if (fsButton) fsButton.addEventListener("click", toggle);

      const closeFsBtn = document.getElementById("fsDetailClose");
      if (closeFsBtn) closeFsBtn.addEventListener("click", close);

      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && overlay().classList.contains("show")) {
          e.preventDefault();
          e.stopImmediatePropagation();
          close();
        }
      }, true);

      document.addEventListener("keydown", (e) => {
        if (e.key === "F11") {
          const modalOpen = document.getElementById("modalDetail").classList.contains("show");
          const fsOpen    = overlay().classList.contains("show");
          if (modalOpen || fsOpen) {
            e.preventDefault();
            toggle();
          }
        }
      });
    }

    return { init, open, close, toggle };
  })();

  // ═══════════════════════════════════════════
  //  PDF EXPORT
  // ═══════════════════════════════════════════

  function buildPdfHtml(notes, topics) {
    const topicById = id => topics.find(t => String(t.id) === String(id));
    return notes.map((note, idx) => {
      const topic = topicById(note.topic);
      const tags  = (note.tags || []).map(t => `<span class="pdf-tag">${t}</span>`).join('');
      const topicBadge = topic
        ? `<div class="pdf-topic" style="color:${topic.color}">[${topic.name}]</div>` : '';
      const bodyHtml = (typeof marked !== 'undefined')
        ? marked.parse(note.content)
        : note.content.replace(/\n/g, '<br>');
      const separator = idx > 0 ? '<div class="pdf-sep"></div>' : '';
      return `
        ${separator}
        <div class="pdf-note">
          ${topicBadge}
          <div class="pdf-question">${note.question}</div>
          <div class="pdf-divider"></div>
          <div class="pdf-body md-rendered">${bodyHtml}</div>
          ${tags ? `<div class="pdf-tags">${tags}</div>` : ''}
        </div>`;
    }).join('');
  }

  async function imgToBase64ViaProxy(url) {
    try {
      const res = await fetch(`/api/image-proxy?url=${encodeURIComponent(url)}`);
      if (!res.ok) { console.warn('[PDF] proxy lỗi', res.status, url); return null; }
      const blob = await res.blob();
      return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload  = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (err) {
      console.warn('[PDF] imgToBase64 thất bại:', url, err);
      return null;
    }
  }

  async function resolveImagesForPdf(container) {
    const imgs = Array.from(container.querySelectorAll('img'));
    await Promise.all(imgs.map(async img => {
      const src = img.getAttribute('src') || '';
      if (!src || src.startsWith('data:')) return;
      const b64 = await imgToBase64ViaProxy(src);
      if (b64) {
        img.src = b64;
        img.style.maxWidth = '100%';
        img.style.height   = 'auto';
      } else {
        const label = document.createElement('div');
        label.style.cssText = 'border:1px dashed #94a3b8;padding:6px 10px;border-radius:4px;color:#64748b;font-size:11px;margin:4px 0;word-break:break-all;';
        label.textContent = '[Ảnh không tải được: ' + src.slice(0, 80) + ']';
        img.replaceWith(label);
      }
    }));
  }

  async function buildPdf(notes, topics, filename) {
    if (!notes.length) { UI.toast('⚠️ Không có note nào để export'); return; }
    UI.toast('⏳ Đang tạo PDF… vui lòng chờ');

    const { jsPDF } = window.jspdf;

    const MARGIN_X = 40;
    const MARGIN_Y = 36;

    const pdf  = new jsPDF({ unit: 'pt', format: 'a4' });
    const pdfW = pdf.internal.pageSize.getWidth();
    const pdfH = pdf.internal.pageSize.getHeight();
    const contentW = pdfW - MARGIN_X * 2;

    const CSS = `
      * { box-sizing: border-box; }
      body { margin: 0; padding: 0; background: #fff; }
      .note-wrap {
        width: 714px; padding: 0;
        font-family: 'Sora', ui-sans-serif, sans-serif;
        font-size: 13px; line-height: 1.75; color: #1e293b;
      }
      .pdf-sep { border-top: 1.5px dashed #cbd5e1; margin: 0 0 24px 0; }
      .pdf-topic { font-size: 10px; margin-bottom: 4px; font-weight: 600; }
      .pdf-question { font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
      .pdf-divider { border-top: 1px solid #e2e8f0; margin-bottom: 12px; }
      .pdf-body { font-size: 12.5px; color: #334155; }
      .pdf-body h1 { font-size: 15px; font-weight: 700; margin: 14px 0 6px; color: #0f172a; }
      .pdf-body h2 { font-size: 13px; font-weight: 700; margin: 12px 0 5px; color: #1d4ed8; }
      .pdf-body h3 { font-size: 12px; font-weight: 700; margin: 10px 0 4px; color: #1d4ed8; }
      .pdf-body p  { margin: 0 0 8px; }
      .pdf-body ul, .pdf-body ol { padding-left: 20px; margin: 4px 0 10px; }
      .pdf-body li { margin: 3px 0; }
      .pdf-body img { max-width: 100%; height: auto; display: block; margin: 8px 0; border-radius: 6px; }
      .pdf-body code { background: #f1f5f9; color: #0f766e; padding: 1px 5px; border-radius: 3px; font-size: 11px; font-family: monospace; }
      .pdf-body pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin: 8px 0; }
      .pdf-body pre code { background: none; color: #334155; font-size: 11px; }
      .pdf-body blockquote { border-left: 3px solid #3b82f6; margin: 8px 0; padding: 4px 12px; background: #eff6ff; color: #475569; }
      .pdf-body strong { color: #0f172a; font-weight: 700; }
      .pdf-tags { margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
      .pdf-tag { background: #f1f5f9; color: #64748b; font-size: 10px; padding: 2px 8px; border-radius: 10px; }
    `;

    const topicById = id => topics.find(t => String(t.id) === String(id));

    async function renderNoteCanvas(note, idx) {
      const topic = topicById(note.topic);
      const tags  = (note.tags || []).map(t => `<span class="pdf-tag">${t}</span>`).join('');
      const topicBadge = topic
        ? `<div class="pdf-topic" style="color:${topic.color}">[${topic.name}]</div>` : '';
      const bodyHtml = (typeof marked !== 'undefined')
        ? marked.parse(note.content)
        : note.content.replace(/\n/g, '<br>');
      const sep = idx > 0 ? '<div class="pdf-sep"></div>' : '';

      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:fixed;left:-9999px;top:0;background:#fff;';
      wrap.innerHTML = `
        <style>${CSS}</style>
        <div class="note-wrap">
          ${sep}
          <div class="pdf-note">
            ${topicBadge}
            <div class="pdf-question">${note.question}</div>
            <div class="pdf-divider"></div>
            <div class="pdf-body md-rendered">${bodyHtml}</div>
            ${tags ? `<div class="pdf-tags">${tags}</div>` : ''}
          </div>
        </div>`;
      document.body.appendChild(wrap);

      await resolveImagesForPdf(wrap);
      await new Promise(r => setTimeout(r, 100));

      const canvas = await html2canvas(wrap, {
        scale: 2,
        useCORS: false,
        allowTaint: true,
        backgroundColor: '#ffffff',
        width: 714,
        windowWidth: 714,
        logging: false,
      });

      document.body.removeChild(wrap);
      return canvas;
    }

    try {
      let curY    = MARGIN_Y;
      let isFirst = true;

      for (let i = 0; i < notes.length; i++) {
        UI.toast(`⏳ Đang xử lý note ${i + 1}/${notes.length}…`);

        const canvas   = await renderNoteCanvas(notes[i], i);
        const pxToPt   = contentW / canvas.width;
        const noteH_pt = canvas.height * pxToPt;

        const remaining = pdfH - curY - MARGIN_Y;
        if (!isFirst && noteH_pt > remaining) {
          pdf.addPage();
          curY = MARGIN_Y;
        }

        if (noteH_pt > pdfH - MARGIN_Y * 2) {
          const slicePx = Math.round((pdfH - MARGIN_Y * 2) / pxToPt);
          let srcY = 0;

          while (srcY < canvas.height) {
            if (srcY > 0) {
              pdf.addPage();
              curY = MARGIN_Y;
            }

            const cropH  = Math.min(slicePx, canvas.height - srcY);
            const slice  = document.createElement('canvas');
            slice.width  = canvas.width;
            slice.height = cropH;
            slice.getContext('2d').drawImage(
              canvas, 0, srcY, canvas.width, cropH,
                      0, 0,   canvas.width, cropH
            );

            const cropH_pt = cropH * pxToPt;
            pdf.addImage(slice.toDataURL('image/jpeg', 0.92), 'JPEG',
              MARGIN_X, curY, contentW, cropH_pt);

            curY += cropH_pt;
            srcY += slicePx;
          }
        } else {
          pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG',
            MARGIN_X, curY, contentW, noteH_pt);
          curY += noteH_pt;
        }

        isFirst = false;
      }

      pdf.save(filename);
      UI.toast(`✅ Đã export ${notes.length} notes ra PDF!`);
    } catch (err) {
      console.error('[PDF] Lỗi:', err);
      UI.toast('❌ Export PDF thất bại: ' + err.message);
    }
  }

  function exportSingleNotePdf(note) {
    buildPdf([note], state.topics, `devnotes-${note.id}.pdf`);
  }

  function openExportPdfModal() {
    const sel = document.getElementById("exportTopicSelect");
    sel.innerHTML = '<option value="">— Chọn chủ đề —</option>';
    state.topics.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      sel.appendChild(opt);
    });

    document.querySelector('[name="exportScope"][value="all"]').checked = true;
    document.getElementById("exportTopicGroup").style.display = "none";
    document.getElementById("exportNoteCount").textContent = state.notes.length;

    UI.openModal("modalExportPdf");
  }

  function wireExportPdfModal() {
    document.getElementById("btnExportPdf").addEventListener("click", openExportPdfModal);

    document.querySelectorAll('[name="exportScope"]').forEach(radio => {
      radio.addEventListener("change", () => {
        const isAll = radio.value === "all";
        document.getElementById("exportTopicGroup").style.display = isAll ? "none" : "block";
        const count = isAll
          ? state.notes.length
          : state.notes.filter(n => String(n.topic) === document.getElementById("exportTopicSelect").value).length;
        document.getElementById("exportNoteCount").textContent = count;
      });
    });

    document.getElementById("exportTopicSelect").addEventListener("change", () => {
      const topicId = document.getElementById("exportTopicSelect").value;
      const count = topicId
        ? state.notes.filter(n => String(n.topic) === topicId).length
        : 0;
      document.getElementById("exportNoteCount").textContent = count;
    });

    document.getElementById("btnDoExportPdf").addEventListener("click", () => {
      const scope = document.querySelector('[name="exportScope"]:checked').value;
      let notes, filename;

      if (scope === "all") {
        notes    = state.notes;
        filename = `devnotes-all-${new Date().toISOString().slice(0,10)}.pdf`;
      } else {
        const topicId = document.getElementById("exportTopicSelect").value;
        if (!topicId) { UI.toast("⚠️ Chọn chủ đề để export"); return; }
        const topic = state.topics.find(t => String(t.id) === topicId);
        notes    = state.notes.filter(n => String(n.topic) === topicId);
        filename = `devnotes-${(topic?.name || topicId).replace(/\s+/g,'-')}-${new Date().toISOString().slice(0,10)}.pdf`;
      }

      UI.closeModal("modalExportPdf");
      setTimeout(() => buildPdf(notes, state.topics, filename), 100);
    });
  }

  // ═══════════════════════════════════════════
  //  EVENT WIRING
  // ═══════════════════════════════════════════
  function wireEvents() {
    // Header buttons
    document.getElementById("btnAdd").addEventListener("click", openAddModal);

    const changePwBtn = document.getElementById("btnChangePassword");
    if (changePwBtn) changePwBtn.addEventListener("click", () => {
      window.location.href = "/forgot-password";
    });

    const logoutBtn = document.getElementById("btnLogout");
    if (logoutBtn) logoutBtn.addEventListener("click", () => {
      if (confirm("Đăng xuất?")) API.logout();
    });

    // User dropdown toggle
    const btnUserMenu  = document.getElementById("btnUserMenu");
    const userDropdown = document.getElementById("userDropdown");
    if (btnUserMenu && userDropdown) {
      btnUserMenu.addEventListener("click", e => {
        e.stopPropagation();
        userDropdown.classList.toggle("show");
      });
      document.addEventListener("click", () => userDropdown.classList.remove("show"));
      userDropdown.addEventListener("click", e => e.stopPropagation());
    }

    const userEl = document.getElementById("headerUser");
    if (userEl) userEl.textContent = "👤 " + (localStorage.getItem("dn_user") || "");
    document.getElementById("btnExport").addEventListener("click", exportData);
    document.getElementById("btnImport").addEventListener("click", () => {
      document.getElementById("pasteJson").value = "";
      UI.openModal("modalImport");
    });

    wireExportPdfModal();

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

    document.getElementById("btnClearFilter").addEventListener("click", async () => {
      state.filterTopic = null;
      state.searchQuery = "";
      document.getElementById("searchInput").value = "";
      await refresh();
    });

    document.getElementById("btnAddTopic").addEventListener("click", addTopic);
    document.getElementById("newTopicInput").addEventListener("keydown", e => {
      if (e.key === "Enter") addTopic();
    });

    document.getElementById("btnDoImport").addEventListener("click", doImport);

    document.getElementById("fileInput").addEventListener("change", e => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = ev => { document.getElementById("pasteJson").value = ev.target.result; };
      reader.readAsText(file);
      e.target.value = "";
    });

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

    // ── Paste ảnh vào #fContent (modal editor) ────────────
    document.getElementById("fContent").addEventListener("paste", async e => {
      const items = Array.from(e.clipboardData?.items || []);
      const imageItem = items.find(it => it.type.startsWith("image/"));
      if (!imageItem) return;  // không có ảnh → browser xử lý bình thường

      await handleImagePaste(e, document.getElementById("fContent"));
    });

    // Nút X và Hủy trên modal Note
    document.querySelectorAll('[data-close="modalNote"]').forEach(btn => {
      btn.addEventListener("click", e => {
        if (!confirmClose()) {
          e.stopImmediatePropagation();
          e.preventDefault();
        } else {
          markSaved();
        }
      }, true);
    });

    // Keyboard shortcuts
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") {
        if (document.getElementById("fsEditor").classList.contains("show")) {
          FS.close(); return;
        }

        const modalNote = document.getElementById("modalNote");
        if (modalNote.classList.contains("show")) {
          if (!confirmClose()) return;
          markSaved();
          modalNote.classList.remove("show");
          return;
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
      if (e.key === "F11") {
        const modalOpen = document.getElementById("modalNote").classList.contains("show");
        const fsOpen    = document.getElementById("fsEditor").classList.contains("show");
        if (modalOpen || fsOpen) {
          e.preventDefault();
          fsOpen ? FS.close() : FS.open();
        }
      }
    });

    FS.init();
  }

  // ═══════════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════════
  async function init() {
    wireEvents();
    FSD.init();
    await refresh();
  }

  document.addEventListener("DOMContentLoaded", init);

})();

// ── Theme Toggle ─────────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem("devnotes-theme") || "dark";
  applyTheme(saved);

  document.addEventListener("DOMContentLoaded", () => {
    const btnDark  = document.getElementById("themeDark");
    const btnLight = document.getElementById("themeLight");
    if (btnDark)  btnDark.addEventListener("click",  () => applyTheme("dark"));
    if (btnLight) btnLight.addEventListener("click", () => applyTheme("light"));
    updateToggleUI(saved);
  });

  function applyTheme(theme) {
    const isDark = theme === "dark";
    document.body.classList.toggle("light-mode", !isDark);
    localStorage.setItem("devnotes-theme", theme);
    updateToggleUI(theme);
  }

  function updateToggleUI(theme) {
    const btnDark  = document.getElementById("themeDark");
    const btnLight = document.getElementById("themeLight");
    if (!btnDark || !btnLight) return;
    btnDark.classList.toggle("active",  theme === "dark");
    btnLight.classList.toggle("active", theme === "light");
  }

  // Áp dụng ngay trước khi DOM load xong để tránh flash trắng
  const earlyTheme = localStorage.getItem("devnotes-theme") || "dark";
  if (earlyTheme === "light") document.documentElement.classList.add("light-mode-early");
})();
