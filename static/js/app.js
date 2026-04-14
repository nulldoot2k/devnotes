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
  //  UNSAVED CHANGES GUARD
  // ═══════════════════════════════════════════

  // Lưu nội dung gốc khi mở modal để so sánh khi đóng
  let _savedQuestion = "";
  let _savedContent  = "";

  function markSaved() {
    _savedQuestion = document.getElementById("fQuestion").value;
    _savedContent  = document.getElementById("fContent").value;
  }

  function hasUnsavedChanges() {
    const q = document.getElementById("fQuestion").value;
    const c = document.getElementById("fContent").value;
    // Có thay đổi so với lúc mở, HOẶC có nội dung mới (modal thêm mới)
    return q !== _savedQuestion || c !== _savedContent;
  }

  function confirmClose() {
    if (!hasUnsavedChanges()) return true;
    return confirm("Bạn có nội dung chưa lưu. Thoát không?");
  }

  // ═══════════════════════════════════════════
  //  NOTE FORM
  // ═══════════════════════════════════════════
  let editingId = null;

  function openAddModal() {
    editingId = null;
    document.getElementById("modalNoteTitle").textContent = "✏️ Thêm Note Mới";
    document.getElementById("fNoteId").value   = "";
    document.getElementById("fQuestion").value = "";
    document.getElementById("fContent").value  = "";
    document.getElementById("fTags").value     = "";
    populateTopicSelect(state.filterTopic);
    UI.openModal("modalNote");
    MD.initToolbar();
    setTimeout(() => {
      markSaved(); // snapshot trạng thái rỗng
      document.getElementById("fQuestion").focus();
    }, 80);
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
    markSaved(); // snapshot nội dung gốc
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
      markSaved(); // reset guard sau khi lưu thành công
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

    // Copy markdown content
    document.getElementById("detailCopyBtn").onclick = () => {
      navigator.clipboard.writeText(n.content).then(() => {
        UI.toast("📋 Đã sao chép nội dung Markdown!");
      }).catch(() => {
        // Fallback
        const ta = document.createElement("textarea");
        ta.value = n.content;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        UI.toast("📋 Đã sao chép!");
      });
    };

    // Export single note as PDF
    document.getElementById("detailExportPdfBtn").onclick = () => {
      exportSingleNotePdf(n);
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

      // Nút thu nhỏ trong FS header — chỉ thu nhỏ, không hỏi gì
      document.getElementById("fsBtnClose").addEventListener("click", close);

      // Nút lưu trong FS header — gọi saveNote() của App
      document.getElementById("fsBtnSave").addEventListener("click", async () => {
        close();
        setTimeout(() => document.getElementById("btnSaveNote").click(), 50);
      });

      // Live preview khi gõ
      fsTa().addEventListener("input", updatePreview);

      // Phím tắt trong FS: Escape = thu nhỏ (KHÔNG thoát), Tab = indent
      fsTa().addEventListener("keydown", e => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation(); // chặn bubble lên global handler
          close();             // chỉ thu nhỏ về modal, không đóng modal
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

  // Fetch ảnh qua Flask proxy → trả về base64 data URL
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

  // Thay tất cả <img src="http..."> trong container thành base64
  async function resolveImagesForPdf(container) {
    const imgs = Array.from(container.querySelectorAll('img'));
    console.log(`[PDF] Tìm thấy ${imgs.length} ảnh cần xử lý`);
    await Promise.all(imgs.map(async img => {
      const src = img.getAttribute('src') || '';
      if (!src || src.startsWith('data:')) return;
      console.log('[PDF] Đang fetch ảnh:', src);
      const b64 = await imgToBase64ViaProxy(src);
      if (b64) {
        img.src = b64;
        // Đảm bảo ảnh không vượt quá width container
        img.style.maxWidth = '100%';
        img.style.height   = 'auto';
        console.log('[PDF] ✅ Đã convert:', src.slice(0, 60));
      } else {
        // Thay bằng label nếu không fetch được
        const label = document.createElement('div');
        label.style.cssText = 'border:1px dashed #94a3b8;padding:6px 10px;border-radius:4px;color:#64748b;font-size:11px;margin:4px 0;word-break:break-all;';
        label.textContent = '[Ảnh không tải được: ' + src.slice(0, 80) + ']';
        img.replaceWith(label);
        console.warn('[PDF] ❌ Không fetch được:', src);
      }
    }));
  }

  async function buildPdf(notes, topics, filename) {
    if (!notes.length) { UI.toast('⚠️ Không có note nào để export'); return; }
    UI.toast('⏳ Đang tạo PDF… (đang tải ảnh, vui lòng chờ)');

    const container = document.createElement('div');
    container.id = 'pdfContainer';
    container.innerHTML = `
      <div class="pdf-header">
        <span class="pdf-logo">dev/notes</span>
        <span class="pdf-meta">${notes.length} notes · ${new Date().toLocaleDateString('vi-VN')}</span>
      </div>
      <div class="pdf-content">${buildPdfHtml(notes, topics)}</div>`;

    const style = document.createElement('style');
    style.textContent = `
      #pdfContainer {
        position: fixed; left: -9999px; top: 0;
        width: 794px; background: #fff;
        font-family: 'Sora', sans-serif;
        color: #1a1a2e; font-size: 13px; line-height: 1.7;
      }
      .pdf-header {
        background: #0d0f14; padding: 14px 28px;
        display: flex; justify-content: space-between; align-items: center;
      }
      .pdf-logo { color: #4fffb0; font-weight: 700; font-size: 15px; }
      .pdf-meta { color: #8892a4; font-size: 11px; }
      .pdf-content { padding: 28px 36px; }
      .pdf-note { margin-bottom: 8px; }
      .pdf-sep { border-top: 1.5px dashed #cbd5e1; margin: 24px 0; }
      .pdf-topic { font-size: 10px; color: #64748b; margin-bottom: 4px; font-weight: 600; }
      .pdf-question { font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
      .pdf-divider { border-top: 1px solid #e2e8f0; margin-bottom: 12px; }
      .pdf-body { font-size: 12.5px; color: #334155; }
      .pdf-body h1 { font-size: 15px; font-weight: 700; margin: 14px 0 6px; color: #0f172a; }
      .pdf-body h2 { font-size: 13px; font-weight: 700; margin: 12px 0 5px; color: #0369a1; }
      .pdf-body h3 { font-size: 12px; font-weight: 700; margin: 10px 0 4px; color: #0284c7; }
      .pdf-body p  { margin: 0 0 8px; }
      .pdf-body ul, .pdf-body ol { padding-left: 20px; margin: 4px 0 10px; }
      .pdf-body li { margin: 3px 0; }
      .pdf-body img { max-width: 680px; height: auto; display: block; margin: 8px 0; border-radius: 6px; }
      .pdf-body code { background: #f1f5f9; color: #0f766e; padding: 1px 5px; border-radius: 3px; font-size: 11px; font-family: monospace; }
      .pdf-body pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; overflow: hidden; margin: 8px 0; }
      .pdf-body pre code { background: none; color: #334155; font-size: 11px; }
      .pdf-body blockquote { border-left: 3px solid #0ea5e9; margin: 8px 0; padding: 4px 12px; background: #f0f9ff; color: #475569; }
      .pdf-body strong { color: #0f172a; font-weight: 700; }
      .pdf-tags { margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
      .pdf-tag { background: #f1f5f9; color: #64748b; font-size: 10px; padding: 2px 8px; border-radius: 10px; }
    `;

    document.head.appendChild(style);
    document.body.appendChild(container);

    try {
      // Bước 1: Chờ ảnh load xong trong DOM (nếu có src thông thường)
      await new Promise(r => setTimeout(r, 100));

      // Bước 2: Convert tất cả ảnh → base64 qua proxy
      await resolveImagesForPdf(container);

      // Bước 3: Chờ thêm để browser render ảnh base64 xong
      await new Promise(r => setTimeout(r, 300));

      const { jsPDF } = window.jspdf;
      const pdf  = new jsPDF({ unit: 'pt', format: 'a4' });
      const pdfW = pdf.internal.pageSize.getWidth();
      const pdfH = pdf.internal.pageSize.getHeight();

      const canvas = await html2canvas(container, {
        scale: 2,
        useCORS: false,       // tắt vì ảnh đã là base64, không cần CORS
        allowTaint: true,
        backgroundColor: '#ffffff',
        width: 794,
        windowWidth: 794,
        logging: false,
      });

      const imgData = canvas.toDataURL('image/jpeg', 0.92);
      const imgW    = pdfW;
      const imgH    = (canvas.height * pdfW) / canvas.width;
      let   posY    = 0;

      while (posY < imgH) {
        if (posY > 0) pdf.addPage();
        pdf.addImage(imgData, 'JPEG', 0, -posY, imgW, imgH);
        posY += pdfH;
      }

      pdf.save(filename);
      UI.toast(`✅ Đã export ${notes.length} notes ra PDF!`);
    } catch (err) {
      console.error('[PDF] Lỗi:', err);
      UI.toast('❌ Export PDF thất bại: ' + err.message);
    } finally {
      document.body.removeChild(container);
      document.head.removeChild(style);
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

    // Change password
    const changePwBtn = document.getElementById("btnChangePassword");
    if (changePwBtn) changePwBtn.addEventListener("click", () => {
      window.location.href = "/forgot-password";
    });

    // Logout
    const logoutBtn = document.getElementById("btnLogout");
    if (logoutBtn) logoutBtn.addEventListener("click", () => {
      if (confirm("Đăng xuất?")) API.logout();
    });

    // ── User dropdown toggle ──────────────────────────────
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

    // Show username
    const userEl = document.getElementById("headerUser");
    if (userEl) userEl.textContent = "👤 " + (localStorage.getItem("dn_user") || "");
    document.getElementById("btnExport").addEventListener("click", exportData);
    document.getElementById("btnImport").addEventListener("click", () => {
      document.getElementById("pasteJson").value = "";
      UI.openModal("modalImport");
    });

    // Export PDF modal
    wireExportPdfModal();

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

    // ── Nút X và Hủy trên modal Note → hỏi xác nhận nếu có thay đổi ──
    document.querySelectorAll('[data-close="modalNote"]').forEach(btn => {
      btn.addEventListener("click", e => {
        if (!confirmClose()) {
          e.stopImmediatePropagation();
          e.preventDefault();
        }
        // Nếu cho phép đóng, reset guard
        else {
          markSaved();
        }
      }, true); // capture để chạy trước handler gốc của UI
    });

    // Keyboard shortcuts
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") {
        // FS đang mở → chỉ thu nhỏ, Esc đã được xử lý trong fsTa keydown
        // (stopPropagation ở đó), nhưng giữ thêm guard ở đây cho chắc
        if (document.getElementById("fsEditor").classList.contains("show")) {
          FS.close(); return;
        }

        // Modal Note đang mở → hỏi xác nhận nếu có nội dung chưa lưu
        const modalNote = document.getElementById("modalNote");
        if (modalNote.classList.contains("show")) {
          if (!confirmClose()) return; // chặn đóng
          markSaved();
          modalNote.classList.remove("show");
          return;
        }

        // Các modal khác → đóng bình thường
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
