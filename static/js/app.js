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
  //  PDF EXPORT
  // ═══════════════════════════════════════════

  /**
   * Render markdown to clean text with structure for PDF
   * jsPDF doesn't support HTML directly, so we convert MD → structured lines
   */
  function mdToLines(md, doc, maxWidth) {
    const lines = [];
    const rawLines = md.split('\n');
    let inCodeBlock = false;
    for (const line of rawLines) {
      if (line.startsWith('```')) {
        inCodeBlock = !inCodeBlock;
        if (inCodeBlock) lines.push({ text: '', style: 'spacer' });
        continue;
      }
      if (inCodeBlock) {
        lines.push({ text: '    ' + line, style: 'code' });
        continue;
      }
      if (line.startsWith('### ')) {
        lines.push({ text: line.slice(4), style: 'h3' });
      } else if (line.startsWith('## ')) {
        lines.push({ text: line.slice(3), style: 'h2' });
      } else if (line.startsWith('# ')) {
        lines.push({ text: line.slice(2), style: 'h1' });
      } else if (line.startsWith('> ')) {
        lines.push({ text: '  ' + line.slice(2), style: 'quote' });
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        lines.push({ text: '  • ' + line.slice(2), style: 'body' });
      } else if (/^\d+\. /.test(line)) {
        lines.push({ text: '  ' + line, style: 'body' });
      } else if (line.trim() === '') {
        lines.push({ text: '', style: 'spacer' });
      } else {
        const clean = line
          .replace(/\*\*(.*?)\*\*/g, '$1')
          .replace(/\*(.*?)\*/g, '$1')
          .replace(/`(.*?)`/g, '$1')
          .replace(/\[(.*?)\]\(.*?\)/g, '$1');
        lines.push({ text: clean, style: 'body' });
      }
    }
    return lines;
  }

  function renderNoteToPdf(doc, note, topics, startY, pageW, pageH, margin) {
    const usableW = pageW - margin * 2;
    let y = startY;

    const checkPage = (needed = 10) => {
      if (y + needed > pageH - margin) {
        doc.addPage();
        y = margin;
      }
    };

    // Topic badge
    const topic = topics.find(t => String(t.id) === String(note.topic));
    if (topic) {
      doc.setFontSize(9);
      doc.setTextColor(120, 120, 140);
      doc.text('[' + topic.name + ']', margin, y);
      y += 6;
    }

    // Question (title)
    checkPage(14);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(20, 20, 30);
    const qLines = doc.splitTextToSize(note.question, usableW);
    qLines.forEach(l => {
      checkPage(8);
      doc.text(l, margin, y);
      y += 7;
    });
    y += 3;

    // Divider
    doc.setDrawColor(220, 220, 230);
    doc.line(margin, y, pageW - margin, y);
    y += 6;

    // Content lines
    const contentLines = mdToLines(note.content, doc, usableW);
    for (const line of contentLines) {
      if (line.style === 'spacer') {
        y += 3;
        continue;
      }

      checkPage(8);

      if (line.style === 'h1') {
        doc.setFontSize(13);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 30, 50);
      } else if (line.style === 'h2') {
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(50, 120, 100);
      } else if (line.style === 'h3') {
        doc.setFontSize(11);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 100, 160);
      } else if (line.style === 'quote') {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(100, 100, 120);
        doc.setDrawColor(180, 200, 220);
        doc.line(margin + 2, y - 4, margin + 2, y + 2);
      } else if (line.style === 'code') {
        doc.setFontSize(9);
        doc.setFont('courier', 'normal');
        doc.setTextColor(80, 180, 120);
      } else {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(50, 50, 70);
      }

      const wrapped = doc.splitTextToSize(line.text || ' ', usableW - (line.style === 'quote' ? 8 : 0));
      const xOffset = line.style === 'quote' ? margin + 6 : margin;
      for (const wl of wrapped) {
        checkPage(6);
        doc.text(wl, xOffset, y);
        y += 5.5;
      }
    }

    // Tags
    if (note.tags && note.tags.length) {
      y += 4;
      checkPage(8);
      doc.setFontSize(8.5);
      doc.setFont('helvetica', 'italic');
      doc.setTextColor(140, 140, 160);
      doc.text('Tags: ' + note.tags.join(', '), margin, y);
      y += 5;
    }

    return y;
  }

  function buildPdf(notes, topics, filename) {
    if (!notes.length) { UI.toast("⚠️ Không có note nào để export"); return; }

    const { jsPDF } = window.jspdf;
    const doc    = new jsPDF({ unit: 'mm', format: 'a4' });
    doc.setFont('Roboto-Regular', 'normal');
    const pageW  = doc.internal.pageSize.getWidth();
    const pageH  = doc.internal.pageSize.getHeight();
    const margin = 18;

    // Cover / header
    doc.setFillColor(13, 15, 20);
    doc.rect(0, 0, pageW, 22, 'F');
    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(79, 255, 176);
    doc.text('dev/notes', margin, 14);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(140, 150, 170);
    doc.text(`${notes.length} notes · ${new Date().toLocaleDateString('vi-VN')}`, pageW - margin, 14, { align: 'right' });

    let y = 34;

    notes.forEach((note, idx) => {
      if (idx > 0) {
        // Separator between notes
        // Separator between notes
        if (y + 18 > pageH - margin) {
          doc.addPage();
          y = margin;
        } else {
          y += 6;
          doc.setDrawColor(200, 210, 225);
          doc.setLineDash([2, 2]);
          doc.line(margin, y, pageW - margin, y);
          doc.setLineDash([]);
          y += 8;
        }
      }
      y = renderNoteToPdf(doc, note, topics, y, pageW, pageH, margin);
      y += 4;
    });

    // Page numbers
    const total = doc.internal.getNumberOfPages();
    for (let i = 1; i <= total; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(160, 160, 180);
      doc.text(`${i} / ${total}`, pageW / 2, pageH - 8, { align: 'center' });
    }

    doc.save(filename);
    UI.toast(`✅ Đã export ${notes.length} notes ra PDF!`);
  }

  function exportSingleNotePdf(note) {
    buildPdf([note], state.topics, `devnotes-${note.id}.pdf`);
  }

  function openExportPdfModal() {
    // Populate topic select
    const sel = document.getElementById("exportTopicSelect");
    sel.innerHTML = '<option value="">— Chọn chủ đề —</option>';
    state.topics.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      sel.appendChild(opt);
    });

    // Reset to "all"
    document.querySelector('[name="exportScope"][value="all"]').checked = true;
    document.getElementById("exportTopicGroup").style.display = "none";
    document.getElementById("exportNoteCount").textContent = state.notes.length;

    UI.openModal("modalExportPdf");
  }

  function wireExportPdfModal() {
    document.getElementById("btnExportPdf").addEventListener("click", openExportPdfModal);

    // Scope radio change
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

    // Topic select change
    document.getElementById("exportTopicSelect").addEventListener("change", () => {
      const topicId = document.getElementById("exportTopicSelect").value;
      const count = topicId
        ? state.notes.filter(n => String(n.topic) === topicId).length
        : 0;
      document.getElementById("exportNoteCount").textContent = count;
    });

    // Do export
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

    // Change password → navigate to forgot page (tab "change")
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
      // Đóng khi click ra ngoài
      document.addEventListener("click", () => userDropdown.classList.remove("show"));
      // Giữ mở khi click bên trong dropdown
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
