(function () {
  "use strict";
  const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
  const A = DATA.analytics;
  const NAVY = "#0f1e33", BLUE = "#0891b2", RED = "#dc2626", GREY = "#64748b", GOLD = "#d97706";
  const CHART_MUTED = "#64748b", CHART_GRID = "rgba(15,30,51,0.08)", CHART_LINE = "rgba(15,30,51,0.2)";

  // Shared theme base merged into every Plotly layout: transparent canvas
  // (so the panel background shows through) plus muted axis/legend text so
  // charts match the surrounding mission-control theme instead of Plotly's
  // own default styling.
  function darkLayout(extra) {
    return Object.assign({
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: CHART_MUTED, size: 11 },
      dragmode: false, // no drag-to-zoom rectangle -- these charts are for reading, not exploring
    }, extra);
  }
  function darkAxis(extra) {
    return Object.assign({ gridcolor: CHART_GRID, zerolinecolor: CHART_LINE, linecolor: CHART_LINE, color: CHART_MUTED, fixedrange: true }, extra);
  }

  function fmtMoney(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    const abs = Math.abs(v);
    let s;
    if (abs >= 1e9) s = (v / 1e9).toFixed(2) + "B";
    else if (abs >= 1e6) s = (v / 1e6).toFixed(2) + "M";
    else if (abs >= 1e3) s = (v / 1e3).toFixed(1) + "K";
    else s = v.toFixed(0);
    return (v < 0 ? "-$" : "$") + s.replace("-", "");
  }
  function fmtPct(v) { return v === null || v === undefined || isNaN(v) ? "—" : (v * 100).toFixed(1) + "%"; }
  function fmtNum(v) { return v === null || v === undefined ? "—" : Number(v).toLocaleString(); }

  const EXPLORER_COLS = [
    ["fiscal_year", "FY"], ["action_date", "Action Date"], ["recipient_name_raw", "Raw Recipient"],
    ["normalized_supplier", "Normalized Supplier"], ["transaction_obligation_signed", "Signed Amount"],
    ["obligation_direction", "Direction"], ["award_id_piid", "Award ID"], ["modification_number", "Mod"],
    ["action_type_description", "Action Type"], ["transaction_description", "Description"],
    ["psc_code", "PSC"], ["naics_code", "NAICS"], ["ai_spend_category", "Category"], ["ai_spend_subcategory", "Subcategory"],
    ["classification_confidence", "Class. Confidence"], ["review_status", "Review"], ["flags", "Flags"],
  ];

  function rowsToCsv(rows) {
    const header = EXPLORER_COLS.map(c => c[1]).join(",");
    const csvRows = rows.map(r => {
      const flags = [...(r.opportunity_flags || []), ...(r.data_quality_flags || [])].join("; ");
      const vals = [
        r.fiscal_year, r.action_date, r.recipient_name_raw, r.normalized_supplier,
        r.transaction_obligation_signed, r.obligation_direction, r.award_id_piid, r.modification_number || "",
        r.action_type_description || "", r.transaction_description || "", r.psc_code || "", r.naics_code || "",
        r.ai_spend_category, r.ai_spend_subcategory, r.classification_confidence, r.review_status, flags,
      ];
      return vals.map(v => `"${String(v === undefined || v === null ? "" : v).replace(/"/g, '""')}"`).join(",");
    });
    return [header, ...csvRows].join("\n");
  }

  function downloadCsv(filename, csv) {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  }

  // ---------------- Local-only "mark for review" flags ----------------
  // Persisted to this browser's localStorage only -- does not send, notify,
  // or file anything anywhere. Purely a personal annotation for this device.
  const REVIEW_FLAG_KEY = "nasa_dashboard_review_flags_v1";
  function getReviewFlags() {
    try { return JSON.parse(localStorage.getItem(REVIEW_FLAG_KEY) || "{}"); }
    catch (e) { return {}; }
  }
  function toggleReviewFlag(supplier) {
    const flags = getReviewFlags();
    flags[supplier] = !flags[supplier];
    localStorage.setItem(REVIEW_FLAG_KEY, JSON.stringify(flags));
    return flags[supplier];
  }
  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(c => e.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return e;
  }

  // ---------------- Header ----------------
  function renderHeader() {
    document.getElementById("dash-title").textContent = DATA.meta.title;
    document.getElementById("dash-disclosure").textContent = DATA.meta.disclosure;
    const bar = document.getElementById("meta-bar");
    const items = [
      ["Data period", `${DATA.meta.data_period_start || "—"} to ${DATA.meta.data_period_end || "—"}`],
      ["Last refresh", DATA.meta.last_refresh_utc],
      ["Transactions", fmtNum(DATA.meta.transaction_count)],
      ["Processing mode", DATA.meta.processing_mode],
      ["Source", DATA.meta.source],
    ];
    items.forEach(([label, val]) => {
      bar.appendChild(el("span", { class: "badge" }, [`${label}: `, el("b", {}, [String(val)])]));
    });
  }

  // ---------------- Toast notifications ----------------
  // "Visibility of system status" -- actions like marking for review or
  // exporting a CSV used to happen silently (only a button label change).
  function showToast(message) {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = el("div", { id: "toast-container" });
      document.body.appendChild(container);
    }
    const toast = el("div", { class: "toast" }, [message]);
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 2600);
  }

  // ---------------- Theme toggle ----------------
  function setupThemeToggle() {
    const btn = document.getElementById("theme-toggle-btn");
    if (!btn) return;
    function label(theme) { return theme === "dark" ? "☀ Light theme" : "🌙 Dark theme"; }
    btn.textContent = label(document.documentElement.getAttribute("data-theme") || "light");
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      try { localStorage.setItem("nasa_dashboard_theme", next); } catch (e) {}
      showToast(`Switching to ${next} theme…`);
      // A full reload (not a live swap) is deliberate: chart colors and the
      // category icon SVGs are generated once from theme-specific color
      // constants at load time (see THEME below), same as every other
      // render in this file -- re-running that from a clean load is far
      // less error-prone than re-coloring ~15 already-drawn Plotly charts
      // and re-rendering every already-inserted icon in place. The saved
      // preference (read in the inline <head> script) means the reload
      // renders the new theme immediately, with no flash of the old one.
      setTimeout(() => location.reload(), 200);
    });
  }

  // ---------------- Command palette (Ctrl/Cmd+K) ----------------
  function buildCommandIndex() {
    const items = [];
    document.querySelectorAll("nav.tabs button").forEach(btn => {
      items.push({ type: "Tab", label: btn.textContent.trim(), action: () => switchTab(btn.dataset.tab) });
    });
    Object.keys(DATA.suppliers_detail || {}).forEach(name => {
      items.push({ type: "Supplier", label: name, action: () => jumpToSupplier(name) });
    });
    (DATA.awards_summary || []).forEach(a => {
      items.push({ type: "Award", label: `${a.award_id} — ${a.supplier}`, action: () => jumpToAward(a.award_id) });
    });
    Object.keys(DATA.categories_detail || {}).forEach(name => {
      items.push({ type: "Category", label: name, action: () => jumpToCategory(name) });
    });
    return items;
  }

  function setupCommandPalette() {
    const overlay = document.getElementById("cmdk-overlay");
    const input = document.getElementById("cmdk-input");
    const results = document.getElementById("cmdk-results");
    const trigger = document.getElementById("cmdk-trigger");
    if (!overlay || !input || !results) return;

    const index = buildCommandIndex();
    let activeIndex = 0;
    let currentMatches = [];

    function draw(query) {
      const q = query.trim().toLowerCase();
      currentMatches = (q ? index.filter(it => it.label.toLowerCase().includes(q)) : index.slice(0, 30)).slice(0, 30);
      activeIndex = 0;
      results.innerHTML = "";
      if (!currentMatches.length) {
        results.appendChild(el("div", { class: "cmdk-empty" }, ["No matches. Try a supplier name, award ID, or category."]));
        return;
      }
      currentMatches.forEach((it, i) => {
        const row = el("div", { class: "cmdk-item" + (i === 0 ? " active" : "") }, [
          el("span", { class: "cmdk-type" }, [it.type]),
          el("span", {}, [it.label]),
        ]);
        row.addEventListener("mouseenter", () => setActive(i));
        row.addEventListener("click", () => select(i));
        results.appendChild(row);
      });
    }

    function setActive(i) {
      const rows = results.querySelectorAll(".cmdk-item");
      rows.forEach(r => r.classList.remove("active"));
      activeIndex = (i + rows.length) % rows.length;
      if (rows[activeIndex]) {
        rows[activeIndex].classList.add("active");
        rows[activeIndex].scrollIntoView({ block: "nearest" });
      }
    }

    function select(i) {
      const item = currentMatches[i];
      if (!item) return;
      close();
      item.action();
    }

    function open() {
      overlay.classList.add("open");
      input.value = "";
      draw("");
      setTimeout(() => input.focus(), 20);
    }
    function close() { overlay.classList.remove("open"); }

    input.addEventListener("input", () => draw(input.value));
    input.addEventListener("keydown", ev => {
      if (ev.key === "ArrowDown") { ev.preventDefault(); setActive(activeIndex + 1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive(activeIndex - 1); }
      else if (ev.key === "Enter") { ev.preventDefault(); select(activeIndex); }
      else if (ev.key === "Escape") { ev.preventDefault(); close(); }
    });
    overlay.addEventListener("click", ev => { if (ev.target === overlay) close(); });
    if (trigger) trigger.addEventListener("click", open);
    document.addEventListener("keydown", ev => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault();
        overlay.classList.contains("open") ? close() : open();
      }
    });
  }

  // ---------------- Tabs ----------------
  function setupTabs() {
    const buttons = document.querySelectorAll("nav.tabs button");
    buttons.forEach((btn, i) => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        window.dispatchEvent(new Event("resize"));
      });
      // Left/Right arrow-key navigation between tabs, standard for a tab
      // list (WAI-ARIA tabs pattern) -- keyboard users shouldn't be limited
      // to Tab-and-Enter through every button in the bar.
      btn.addEventListener("keydown", ev => {
        if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
        ev.preventDefault();
        const next = buttons[(i + (ev.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length];
        next.focus();
        next.click();
      });
    });
  }

  // ---------------- Animated KPI count-up (Executive Overview only) ----------------
  function animateNumber(valueEl, from, to, formatFn, duration) {
    const start = performance.now();
    function frame(now) {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      valueEl.textContent = formatFn(Math.round(from + (to - from) * eased));
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function animatedKpiTile(label, targetNum, formatFn, negClass, drilldown) {
    const valueEl = el("div", { class: "value" + (negClass ? " neg" : "") }, [formatFn(0)]);
    const tile = el("div", { class: "kpi" + (drilldown ? " clickable" : "") }, [el("div", { class: "label" }, [label]), valueEl]);
    animateNumber(valueEl, 0, targetNum || 0, formatFn, 700);
    if (drilldown) {
      tile.tabIndex = 0;
      tile.setAttribute("role", "button");
      tile.title = "Click to see how this number is calculated";
      tile.addEventListener("click", () => openKpiModal(drilldown()));
      tile.addEventListener("keydown", ev => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openKpiModal(drilldown()); }
      });
    }
    return tile;
  }

  // ---------------- KPI drill-down modal ("how does this number build up?") ----------------
  function setupKpiModal() {
    const overlay = document.getElementById("kpi-modal-overlay");
    const closeModal = () => overlay.classList.remove("open");
    document.getElementById("kpi-modal-close").addEventListener("click", closeModal);
    overlay.addEventListener("click", ev => { if (ev.target === overlay) closeModal(); });
    document.addEventListener("keydown", ev => {
      if (ev.key === "Escape" && overlay.classList.contains("open")) closeModal();
    });
  }

  function openKpiModal(spec) {
    document.getElementById("kpi-modal-title").textContent = spec.title;
    document.getElementById("kpi-modal-formula").textContent = spec.formula;
    const noteEl = document.getElementById("kpi-modal-note");
    noteEl.textContent = spec.note || "";
    noteEl.style.display = spec.note ? "" : "none";

    const wrap = document.getElementById("kpi-modal-table-wrap");
    wrap.innerHTML = "";
    if (spec.rows && spec.rows.length) {
      const tbl = el("table", { class: "data-table" });
      tbl.appendChild(el("thead", {}, [el("tr", {}, spec.columns.map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      spec.rows.forEach(r => tbody.appendChild(el("tr", {}, r.map(c => el("td", {}, [c])))));
      tbl.appendChild(tbody);
      wrap.appendChild(tbl);
    } else if (!spec.rows) {
      // no drill-down list available for this KPI -- formula-only explanation.
    } else {
      wrap.appendChild(el("div", { class: "small-note" }, ["No contributing rows to show for this dataset."]));
    }
    document.getElementById("kpi-modal-overlay").classList.add("open");
  }

  // ---------------- Cross-tab "jump-in" navigation ----------------
  function switchTab(tabName) {
    const btn = document.querySelector(`nav.tabs button[data-tab="${tabName}"]`);
    if (btn) btn.click();
  }

  function jumpToSupplier(name) {
    switchTab("supplier");
    const sel = document.getElementById("supplier-select");
    if (!sel) return;
    sel.value = name;
    sel.dispatchEvent(new Event("change"));
    document.getElementById("tab-supplier").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function jumpToCategory(name) {
    switchTab("categories");
    const sel = document.getElementById("category-select");
    if (!sel) return;
    sel.value = name;
    sel.dispatchEvent(new Event("change"));
    document.getElementById("tab-categories").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function jumpToAward(awardId) {
    const isStandout = (DATA.standout_awards || []).some(a => a.award_id === awardId);
    if (isStandout) {
      switchTab("highlights");
      setTimeout(() => {
        const card = document.querySelector(`.award-card[data-award-id="${CSS.escape(awardId)}"]`);
        if (!card) return;
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.remove("flash-highlight");
        void card.offsetWidth; // restart animation if clicked twice
        card.classList.add("flash-highlight");
      }, 60);
      return;
    }
    // Not one of the 5 signal-flagged standout cards -- fall back to the
    // Transaction Explorer, filtered to this award, which works for any
    // award (subject to the Explorer's own embedded-row cap, disclosed there).
    switchTab("explorer");
    const resetBtn = document.getElementById("ex-reset");
    if (resetBtn) resetBtn.click();
    const search = document.getElementById("ex-search");
    if (search) {
      search.value = awardId;
      search.dispatchEvent(new Event("input"));
    }
    document.getElementById("tab-explorer").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Global Timeframe control (header) -- a fiscal-year FROM/TO range that
  // scopes the whole dashboard. null/null means the full embedded range
  // ("All Years"); otherwise both bounds are always concrete fiscal years
  // (the header's two <select> elements never show a blank state). Every
  // tab that can meaningfully react registers a listener here;
  // setGlobalTimeframe() (wired to the header selects) fires them all with
  // (fromFY, toFY). Runs entirely against the embedded dataset -- no
  // network call, so it always works regardless of the viewer's own
  // connectivity.
  let globalFromFY = null;
  let globalToFY = null;
  const globalTimeframeListeners = [];
  function onGlobalTimeframeChange(fn) { globalTimeframeListeners.push(fn); }
  function setGlobalTimeframe(fromFY, toFY) {
    globalFromFY = fromFY;
    globalToFY = toFY;
    globalTimeframeListeners.forEach(fn => fn(fromFY, toFY));
  }

  // `drilldown` is a zero-arg function returning { title, formula, note,
  // columns, rows } -- called lazily on click/Enter so building the
  // explanation never costs anything unless someone actually opens it.
  function kpiTile(label, value, negClass, drilldown) {
    const tile = el("div", { class: "kpi" + (drilldown ? " clickable" : "") }, [
      el("div", { class: "label" }, [label]),
      el("div", { class: "value" + (negClass ? " neg" : "") }, [value]),
    ]);
    if (drilldown) {
      tile.tabIndex = 0;
      tile.setAttribute("role", "button");
      tile.title = "Click to see how this number is calculated";
      tile.addEventListener("click", () => openKpiModal(drilldown()));
      tile.addEventListener("keydown", ev => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openKpiModal(drilldown()); }
      });
    }
    return tile;
  }

  // ---------------- Tab 1: Executive Overview ----------------
  function renderOverview() {
    if (DATA.meta.current_fiscal_year_is_partial) {
      document.getElementById("overview-warning").appendChild(el("div", { class: "warning-banner" }, [
        `⚠ FY${DATA.meta.current_fiscal_year} is still in progress (partial year). Totals for the current fiscal year are not directly comparable to completed fiscal years.`
      ]));
    }

    // Timeframe scoping lives in the header's global Timeframe control now
    // (see setGlobalTimeframe()/onGlobalTimeframeChange() near the top of
    // this file) -- drawEmbeddedOverview() below is registered as a listener
    // so changing it redraws this tab's KPIs/charts from the embedded
    // payload. No network call, no separate "live" year option.
    const standoutSupplierCount = (DATA.standout_suppliers || []).length;
    const standoutAwardCount = (DATA.standout_awards || []).length;
    const cta = document.getElementById("overview-jump-cta");
    if (cta && (standoutSupplierCount || standoutAwardCount)) {
      const ctaBtn = el("button", {}, ["View Standouts →"]);
      ctaBtn.addEventListener("click", () => switchTab("highlights"));
      cta.appendChild(el("div", {}, [
        `🌟 ${standoutSupplierCount} standout supplier(s) and ${standoutAwardCount} notable contract(s) flagged for this dataset.`
      ]));
      cta.appendChild(ctaBtn);
    }

    // KPIs and both charts redraw for whichever timespan is selected above
    // (an embedded fiscal year, or "All Years"); Top Suppliers/Contracts and
    // Findings stay all-time regardless (noted in their own headers below --
    // there's no per-year breakdown of those two computed server-side yet).
    function drawEmbeddedOverview(fromFY, toFY) {
      const inRange = fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY);
      const isFullRange = fromFY == null && toFY == null;
      const yearsInRange = A.annual.filter(r => inRange(r.fiscal_year));
      const isSingleYear = !isFullRange && yearsInRange.length === 1;
      const scopeFY = isSingleYear ? yearsInRange[0].fiscal_year : null;
      const rangeLabel = yearsInRange.length
        ? (yearsInRange.length === 1 ? `FY${yearsInRange[0].fiscal_year}` : `FY${yearsInRange[0].fiscal_year}–FY${yearsInRange[yearsInRange.length - 1].fiscal_year}`)
        : "";

      let t;
      if (isFullRange) {
        t = A.totals;
      } else if (isSingleYear) {
        const yearRow = yearsInRange[0];
        t = {
          net_obligations: yearRow.net_obligations, gross_positive_obligations: yearRow.gross_positive_obligations,
          deobligations: yearRow.deobligations, deobligation_rate: yearRow.deobligation_rate,
          transaction_count: yearRow.transaction_count, unique_awards: yearRow.unique_awards, unique_suppliers: yearRow.unique_suppliers,
        };
      } else {
        // Multi-year partial range: net/gross/deob/transaction_count sum
        // exactly. Unique Awards/Normalized Suppliers don't -- an award or
        // supplier active in more than one of the selected years gets
        // counted once per year, so these two are an upper bound, not an
        // exact distinct count (flagged in the scope note below).
        const sum = key => yearsInRange.reduce((s, r) => s + r[key], 0);
        const gross = sum("gross_positive_obligations"), deob = sum("deobligations");
        t = {
          net_obligations: sum("net_obligations"), gross_positive_obligations: gross, deobligations: deob,
          deobligation_rate: gross > 0 ? deob / gross : 0,
          transaction_count: sum("transaction_count"), unique_awards: sum("unique_awards"), unique_suppliers: sum("unique_suppliers"),
        };
      }
      const KD = DATA.kpi_drilldowns || { top_gross_transactions: [], top_deobligation_transactions: [] };
      const txnRow = r => [r.action_date, r.supplier, r.award_id, fmtMoney(r.amount)];

      const kpis = document.getElementById("overview-kpis");
      kpis.innerHTML = "";
      const scopeNote = document.getElementById("overview-kpi-scope-note");
      if (scopeNote) {
        scopeNote.style.display = isFullRange ? "none" : "";
        scopeNote.textContent = isFullRange ? "" : isSingleYear
          ? `Showing ${rangeLabel} only. Click-to-explain "HOW?" breakdowns are computed dataset-wide, so they're only offered in the "All Years" view.`
          : `Showing ${rangeLabel} (${yearsInRange.length} fiscal years). Net Obligations, Gross Positive, Deobligations, and Transactions are exact sums across those years. Unique Awards and Normalized Suppliers are also summed per year, so they may overcount anything active in more than one of the selected years. Click-to-explain "HOW?" breakdowns are computed dataset-wide, so they're only offered in the "All Years" view.`;
      }

      kpis.appendChild(animatedKpiTile("Net Obligations", t.net_obligations, fmtMoney, t.net_obligations < 0, !isFullRange ? undefined : () => ({
        title: "Net Obligations",
        formula: `Sum of every transaction's signed obligation amount across all ${fmtNum(t.transaction_count)} transactions: `
          + `${fmtMoney(t.gross_positive_obligations)} gross positive − ${fmtMoney(t.deobligations)} deobligated = ${fmtMoney(t.net_obligations)} net.`,
        note: `Showing the ${KD.top_gross_transactions.length} largest positive and ${KD.top_deobligation_transactions.length} largest deobligating transactions, ranked by dollar amount -- not an exhaustive list of all ${fmtNum(t.transaction_count)} transactions.`,
        columns: ["Date", "Supplier", "Award", "Signed Amount"],
        rows: [...KD.top_gross_transactions, ...KD.top_deobligation_transactions]
          .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
          .map(txnRow),
      })));
      kpis.appendChild(animatedKpiTile("Gross Positive Obligations", t.gross_positive_obligations, fmtMoney, false, !isFullRange ? undefined : () => ({
        title: "Gross Positive Obligations",
        formula: `Sum of the signed obligation amount for every transaction with a positive value (new obligations and upward modifications), across ${fmtNum(t.transaction_count)} transactions.`,
        note: `Showing the ${KD.top_gross_transactions.length} largest positive transactions, ranked by dollar amount.`,
        columns: ["Date", "Supplier", "Award", "Amount"],
        rows: KD.top_gross_transactions.map(txnRow),
      })));
      kpis.appendChild(animatedKpiTile("Deobligations", t.deobligations, fmtMoney, false, !isFullRange ? undefined : () => ({
        title: "Deobligations",
        formula: `Sum of the absolute value of every transaction with a negative signed amount (downward contract modifications) -- equal to ${fmtPct(t.deobligation_rate)} of gross positive obligations.`,
        note: `Showing the ${KD.top_deobligation_transactions.length} largest deobligating transactions, ranked by dollar amount.`,
        columns: ["Date", "Supplier", "Award", "Amount"],
        rows: KD.top_deobligation_transactions.map(txnRow),
      })));
      kpis.appendChild(animatedKpiTile("Transactions", t.transaction_count, fmtNum, false, !isFullRange ? undefined : () => {
        const posCount = t.transaction_count - t.negative_transaction_count - t.zero_dollar_action_count;
        return {
          title: "Transactions",
          formula: "Count of every transaction row in this dataset, regardless of direction or size.",
          columns: ["Type", "Count"],
          rows: [
            ["Positive obligations (new / increased)", fmtNum(posCount)],
            ["Deobligations (decreased)", fmtNum(t.negative_transaction_count)],
            ["Zero-dollar actions", fmtNum(t.zero_dollar_action_count)],
          ],
        };
      }));
      kpis.appendChild(animatedKpiTile("Unique Awards", t.unique_awards, fmtNum, false, !isFullRange ? undefined : () => {
        const top = (DATA.awards_summary || []).slice().sort((a, b) => b.net_obligations - a.net_obligations).slice(0, 10);
        return {
          title: "Unique Awards",
          formula: "Count of distinct Award ID (PIID) values across all transactions -- each award can span many transactions (new obligations, modifications, deobligations) over time.",
          note: `Showing the top ${top.length} of ${fmtNum(t.unique_awards)} awards by net obligations.`,
          columns: ["Award", "Supplier", "Net Obligations", "Transactions"],
          rows: top.map(a => [a.award_id, a.supplier, fmtMoney(a.net_obligations), fmtNum(a.transaction_count)]),
        };
      }));
      kpis.appendChild(animatedKpiTile("Normalized Suppliers", t.unique_suppliers, fmtNum, false, !isFullRange ? undefined : () => {
        const top = Object.entries(DATA.suppliers_detail || {})
          .sort((a, b) => b[1].total_net_obligations - a[1].total_net_obligations)
          .slice(0, 10);
        return {
          title: "Normalized Suppliers",
          formula: "Count of distinct suppliers after name-variant resolution -- raw recipient name strings (punctuation, DBA names, store-number suffixes, etc.) that resolve to the same vendor are merged into one normalized_supplier before counting.",
          note: `Showing the top ${top.length} of ${fmtNum(t.unique_suppliers)} normalized suppliers by net obligations.`,
          columns: ["Supplier", "Net Obligations", "Transactions"],
          rows: top.map(([name, d]) => [name, fmtMoney(d.total_net_obligations), fmtNum(d.transaction_count)]),
        };
      }));

      // A single- (or two-) fiscal-year dataset gives the annual trend chart
      // too few points to show a trend at all, so fall back to monthly
      // granularity -- same three series, finer time axis. Otherwise the
      // chart always shows every embedded year (its whole point is
      // comparing years), with the selected range's bars highlighted rather
      // than the chart being collapsed down to just those bars.
      const trendTitle = document.getElementById("trend-chart-title");
      const trendNote = document.getElementById("trend-chart-note");
      const useMonthly = A.annual.length < 2 && (A.monthly || []).length > 1;
      const trendSeries = useMonthly ? A.monthly : A.annual;
      const trendX = useMonthly ? trendSeries.map(r => r.period) : trendSeries.map(r => "FY" + r.fiscal_year);
      if (useMonthly) {
        trendTitle.textContent = "Monthly Obligation Trend";
        trendNote.textContent = "This dataset spans a single fiscal year, so monthly granularity is shown instead of a flat one-bar annual chart.";
        trendNote.style.display = "";
      } else {
        trendTitle.textContent = isFullRange ? "Annual Obligation Trend" : `Annual Obligation Trend (${rangeLabel} highlighted)`;
        trendNote.style.display = "none";
      }
      const highlightMask = (!isFullRange && !useMonthly) ? trendSeries.map(r => inRange(r.fiscal_year)) : null;
      const barColor = base => !highlightMask ? base : trendSeries.map((r, i) => highlightMask[i] ? base : "rgba(148,163,184,0.35)");
      Plotly.newPlot("chart-annual-trend", [
        { x: trendX, y: trendSeries.map(r => r.gross_positive_obligations), type: "bar", name: "Gross Obligations", marker: { color: barColor(BLUE) } },
        { x: trendX, y: trendSeries.map(r => -r.deobligations), type: "bar", name: "Deobligations", marker: { color: barColor(RED) } },
        { x: trendX, y: trendSeries.map(r => r.net_obligations), type: "scatter", mode: "lines+markers", name: "Net Obligations", line: { color: NAVY, width: 3 } },
      ], darkLayout({
        barmode: "relative", margin: { t: 10, r: 10, l: 60, b: 40 },
        xaxis: darkAxis({}), yaxis: darkAxis({ title: "USD", tickformat: "~s" }), legend: { orientation: "h", y: -0.2 },
      }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      // "Other or Unclassified" is the classifier's catch-all -- it isn't a
      // peer spend category, and when it's the largest slice it flattens
      // every real category into an unreadable sliver. Pull it out of the
      // ranked chart and surface it as a separate review-queue callout.
      const OTHER_CATEGORY = "Other or Unclassified";
      const cats = {};
      if (isFullRange) {
        A.category_breakdown.forEach(r => { cats[r.category] = (cats[r.category] || 0) + r.net_obligations; });
      } else {
        Object.keys(DATA.categories_detail).forEach(cat => {
          cats[cat] = DATA.categories_detail[cat].annual.filter(r => inRange(r.fiscal_year)).reduce((s, r) => s + r.net_obligations, 0);
        });
      }
      const otherTotal = cats[OTHER_CATEGORY] || 0;
      const totalAll = Object.values(cats).reduce((a, b) => a + b, 0);
      delete cats[OTHER_CATEGORY];
      const catNames = Object.keys(cats).sort((a, b) => cats[b] - cats[a]);
      const categoryChart = document.getElementById("chart-category-comp");
      Plotly.newPlot(categoryChart, [{
        x: catNames.map(c => cats[c]), y: catNames, type: "bar", orientation: "h",
        marker: { color: BLUE },
      }], darkLayout({
        margin: { t: 10, r: 10, l: 230, b: 40 }, xaxis: darkAxis({ title: "Net Obligations (USD)", tickformat: "~s" }), yaxis: darkAxis({}),
      }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });
      categoryChart.on("plotly_click", ev => {
        const name = ev.points && ev.points[0] && ev.points[0].y;
        if (name) jumpToCategory(name);
      });
      categoryChart.style.cursor = "pointer";

      const otherCallout = document.getElementById("category-other-callout");
      otherCallout.innerHTML = "";
      if (otherTotal > 0 && totalAll > 0) {
        const pct = (otherTotal / totalAll * 100).toFixed(1);
        const box = el("div", { class: "other-callout" }, [
          "📋 ", el("strong", {}, [fmtMoney(otherTotal)]), ` (${pct}% of net obligations${isFullRange ? "" : ` in ${rangeLabel}`}) fell into "${OTHER_CATEGORY}" -- `,
          "not shown above since it's a classification review queue, not a real spend category. Click to jump to it.",
        ]);
        box.addEventListener("click", () => jumpToCategory(OTHER_CATEGORY));
        otherCallout.appendChild(box);
      }
    }

    drawEmbeddedOverview(globalFromFY, globalToFY);
    onGlobalTimeframeChange(drawEmbeddedOverview);

    drawTopSuppliers();
    drawTopContracts();
    document.getElementById("top-suppliers-sort").addEventListener("change", () => { topSuppliersSortDir = "desc"; drawTopSuppliers(); });
    document.getElementById("top-contracts-sort").addEventListener("change", () => { topContractsSortDir = "desc"; drawTopContracts(); });

    renderFindings(document.getElementById("overview-findings"), DATA.insights);
  }

  // "TOP" is a choice, not a fact -- these two tables let the viewer pick
  // which metric defines it instead of hard-coding "top = highest dollar
  // value" as the only lens. Sort direction is separate per-table state so a
  // header click can flip asc/desc without disturbing the "top by" dropdown.
  let topSuppliersSortDir = "desc";
  let topContractsSortDir = "desc";

  // A clickable <th>: click once to sort by this column (descending), click
  // again to flip to ascending. Columns with no numeric key (e.g. "Supplier"
  // name) render as a plain header.
  function sortableHeaderCell(label, key, sortSelect, currentDir, onResort) {
    if (!key) return el("th", {}, [label]);
    const th = el("th", { class: "col-sortable" }, [label]);
    if (sortSelect.value === key) th.classList.add(currentDir === "asc" ? "sort-asc" : "sort-desc");
    th.title = "Sort by " + label.toLowerCase();
    th.addEventListener("click", () => {
      if (sortSelect.value === key) {
        onResort(currentDir === "asc" ? "desc" : "asc");
      } else {
        sortSelect.value = key;
        onResort("desc");
      }
    });
    return th;
  }

  function drawTopSuppliers() {
    const sortSelect = document.getElementById("top-suppliers-sort");
    const sortKey = sortSelect.value;
    const rows = Object.entries(DATA.suppliers_detail || {}).map(([name, d]) => ({
      supplier: name,
      net_obligations: d.total_net_obligations,
      transaction_count: d.transaction_count,
      unique_awards: d.unique_awards,
      deobligations: d.deobligations,
    }));
    rows.sort((a, b) => topSuppliersSortDir === "asc" ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);

    const tbl = document.getElementById("table-top-suppliers");
    tbl.innerHTML = "";
    const supplierCols = [["Supplier", null], ["Net Obligations", "net_obligations"], ["Transactions", "transaction_count"], ["Awards", "unique_awards"], ["Deobligations", "deobligations"]];
    tbl.appendChild(el("thead", {}, [el("tr", {}, supplierCols.map(([label, key]) =>
      sortableHeaderCell(label, key, sortSelect, topSuppliersSortDir, dir => { topSuppliersSortDir = dir; drawTopSuppliers(); })))]));
    const tbody = el("tbody");
    rows.slice(0, 12).forEach(r => {
      const row = el("tr", { class: "jump-row" }, [
        el("td", {}, [r.supplier]),
        el("td", {}, [fmtMoney(r.net_obligations)]),
        el("td", {}, [fmtNum(r.transaction_count)]),
        el("td", {}, [fmtNum(r.unique_awards)]),
        el("td", {}, [fmtMoney(r.deobligations)]),
      ]);
      row.title = "Jump to full supplier analysis";
      row.addEventListener("click", () => jumpToSupplier(r.supplier));
      tbody.appendChild(row);
    });
    tbl.appendChild(tbody);
  }

  function drawTopContracts() {
    const sortSelect = document.getElementById("top-contracts-sort");
    const sortKey = sortSelect.value;
    const rows = (DATA.awards_summary || []).slice()
      .sort((a, b) => topContractsSortDir === "asc" ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);

    const contractsTbl = document.getElementById("table-top-contracts");
    if (!contractsTbl) return;
    contractsTbl.innerHTML = "";
    const contractCols = [["Supplier", null], ["Net Obligations", "net_obligations"], ["Transactions", "transaction_count"], ["Modifications", "modification_count"], ["Deobligations", "deobligations"], ["Award", null]];
    contractsTbl.appendChild(el("thead", {}, [el("tr", {}, contractCols.map(([label, key]) =>
      sortableHeaderCell(label, key, sortSelect, topContractsSortDir, dir => { topContractsSortDir = dir; drawTopContracts(); })))]));
    const ctbody = el("tbody");
    if (!rows.length) {
      ctbody.appendChild(el("tr", {}, [el("td", { colspan: 6, class: "small-note" }, ["No contract award data for this dataset."])]));
    }
    rows.slice(0, 12).forEach(a => {
      const row = el("tr", { class: "jump-row" }, [
        el("td", {}, [a.supplier]),
        el("td", {}, [fmtMoney(a.net_obligations)]),
        el("td", {}, [fmtNum(a.transaction_count)]),
        el("td", {}, [fmtNum(a.modification_count)]),
        el("td", {}, [fmtMoney(a.deobligations)]),
        el("td", { class: "code-text" }, [a.award_id]),
      ]);
      row.title = "Jump to this award";
      row.addEventListener("click", () => jumpToAward(a.award_id));
      ctbody.appendChild(row);
    });
    contractsTbl.appendChild(ctbody);
  }

  // A finding "jumps" to the category/supplier it's actually about when one
  // of its affected_entities resolves to a real entry in this dataset.
  function findingJumpTarget(f) {
    for (const name of (f.affected_entities || [])) {
      if (DATA.categories_detail && DATA.categories_detail[name]) return { type: "category", name };
      if (DATA.suppliers_detail && DATA.suppliers_detail[name]) return { type: "supplier", name };
    }
    return null;
  }

  // Clicking a finding pops up its full detail (title/description/every
  // supporting metric, not just what's already visible on the card) plus,
  // when the finding is actually about a known category or supplier, a
  // one-click jump straight to that entity's own tab.
  function openFindingModal(f) {
    const target = findingJumpTarget(f);
    document.getElementById("kpi-modal-title").textContent = f.title;
    document.getElementById("kpi-modal-formula").textContent = f.description;
    const noteEl = document.getElementById("kpi-modal-note");
    noteEl.textContent = target ? `This finding is about ${target.name} -- jump to its full analysis below.` : "";
    noteEl.style.display = target ? "" : "none";

    const wrap = document.getElementById("kpi-modal-table-wrap");
    wrap.innerHTML = "";
    const metrics = f.supporting_metrics || [];
    if (metrics.length) {
      const tbl = el("table", { class: "data-table" });
      tbl.appendChild(el("thead", {}, [el("tr", {}, ["Supporting metric", "Value"].map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      metrics.forEach(m => {
        const eq = m.indexOf("=");
        const [k, v] = eq === -1 ? [m, ""] : [m.slice(0, eq), m.slice(eq + 1)];
        tbody.appendChild(el("tr", {}, [el("td", {}, [k]), el("td", {}, [v])]));
      });
      tbl.appendChild(tbody);
      wrap.appendChild(tbl);
    }
    if (target) {
      const jumpRow = el("div", { class: "controls", style: "margin-top:12px;" });
      const jumpBtn = el("button", {}, [`Jump to ${target.name} →`]);
      jumpBtn.addEventListener("click", () => {
        document.getElementById("kpi-modal-overlay").classList.remove("open");
        if (target.type === "category") jumpToCategory(target.name);
        else jumpToSupplier(target.name);
      });
      jumpRow.appendChild(jumpBtn);
      wrap.appendChild(jumpRow);
    }
    document.getElementById("kpi-modal-overlay").classList.add("open");
  }

  function renderFindings(container, findings) {
    if (!findings || !findings.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No grounded findings met the reporting threshold for this dataset."]));
      return;
    }
    findings.forEach(f => {
      const target = findingJumpTarget(f);
      const card = el("div", { class: "finding-card clickable-card" }, [
        el("h4", {}, [f.title]),
        el("div", {}, [f.description]),
        el("div", { class: "metrics" }, ["Supporting metrics: " + (f.supporting_metrics || []).join(", ")]),
      ]);
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.title = target ? `Click to see details and jump to ${target.name}` : "Click to see details";
      card.addEventListener("click", () => openFindingModal(f));
      card.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openFindingModal(f); } });
      container.appendChild(card);
    });
  }

  // ---------------- Standout Suppliers (Executive Overview) ----------------
  function usaspendingSearchUrl(supplier) {
    return "https://www.usaspending.gov/search/?keyword=" + encodeURIComponent(supplier);
  }

  // A collapsed-by-default wrapper for the longer evidence text, so cards
  // read as a scannable stat + tags by default and the full sentence is one
  // click away rather than always taking up space.
  function detailsToggle(detailNodes) {
    const wrap = el("div", { class: "sc-details" }, detailNodes);
    const btn = el("button", { class: "sc-details-toggle" }, ["Details ▾"]);
    btn.addEventListener("click", () => {
      const nowExpanded = wrap.classList.toggle("expanded");
      btn.textContent = nowExpanded ? "Details ▴" : "Details ▾";
    });
    return { btn, wrap };
  }

  // "New since last run" -- see pipeline._mark_new_since_last_run. Absent/
  // false on a first-ever run (nothing to compare against) or in direct
  // build_payload() calls that don't go through the snapshot step.
  function newBadge(isNew) {
    return isNew ? el("span", { class: "new-badge" }, ["New"]) : null;
  }

  function renderSnapshotStatus() {
    const el_ = document.getElementById("snapshot-status");
    if (!el_) return;
    if (!DATA.meta.has_previous_snapshot) {
      el_.textContent = "First run on record for this dataset -- nothing is marked \"New\" yet; the next run will compare against this one.";
    } else {
      el_.textContent = "Comparing against the previous run -- items marked \"New\" below did not appear last time.";
    }
  }

  // Every fiscal-year-range combination among the embedded years is
  // precomputed server-side (see _standout_by_range() in data_prep.py), so
  // switching the header's Timeframe range just looks this up -- no
  // client-side recomputation, no lag.
  function standoutRangeKey(fromFY, toFY) {
    const embeddedFYs = A.annual.map(r => r.fiscal_year);
    const lo = fromFY == null ? embeddedFYs[0] : fromFY;
    const hi = toFY == null ? embeddedFYs[embeddedFYs.length - 1] : toFY;
    return `${lo}-${hi}`;
  }
  function updateStandoutsScopeNote(fromFY, toFY) {
    const note = document.getElementById("standouts-scope-note");
    if (!note) return;
    const isFullRange = fromFY == null && toFY == null;
    note.textContent = isFullRange
      ? "Showing standouts across the full dataset (all embedded years)."
      : `Showing standouts for FY${fromFY == null ? A.annual[0].fiscal_year : fromFY}–FY${toFY == null ? A.annual[A.annual.length - 1].fiscal_year : toFY} only -- spend-concentration % is relative to that range's own total, not the dataset-wide total.`;
  }

  function renderStandoutSuppliers(fromFY, toFY) {
    updateStandoutsScopeNote(fromFY, toFY);
    const container = document.getElementById("standout-suppliers");
    container.innerHTML = "";
    const key = standoutRangeKey(fromFY, toFY);
    const rangeData = (DATA.standout_by_range || {})[key];
    const list = (rangeData ? rangeData.standout_suppliers : DATA.standout_suppliers) || [];
    if (!list.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No supplier met the standout criteria for this dataset."]));
      return;
    }
    const flags = getReviewFlags();

    list.forEach(s => {
      const tagRow = el("div", {}, s.reasons.map(r => el("span", { class: "reason-tag " + r.type }, [r.label])));
      const { btn: detailsBtn, wrap: detailsWrap } = detailsToggle(
        s.reasons.map(r => el("div", { class: "sc-reason-detail" }, [r.detail]))
      );

      const flagBtn = el("button", { class: "flag-btn" + (flags[s.supplier] ? " marked" : "") },
        [flags[s.supplier] ? "★ Marked for review" : "Mark for review"]);
      flagBtn.title = "Saved locally in this browser only -- does not notify or send anything to anyone.";
      flagBtn.addEventListener("click", () => {
        const nowMarked = toggleReviewFlag(s.supplier);
        flagBtn.textContent = nowMarked ? "★ Marked for review" : "Mark for review";
        flagBtn.classList.toggle("marked", nowMarked);
        showToast(nowMarked ? `Marked ${s.supplier} for review` : `Removed ${s.supplier} from review`);
      });

      const viewBtn = el("button", { class: "primary" }, ["View on USAspending.gov ↗"]);
      viewBtn.title = "Opens the official public search on usaspending.gov in a new tab.";
      viewBtn.addEventListener("click", () => window.open(usaspendingSearchUrl(s.supplier), "_blank", "noopener"));

      const exportBtn = el("button", {}, ["Export supplier CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.normalized_supplier === s.supplier);
        const safeName = s.supplier.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_supplier_${safeName}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for ${s.supplier}`);
      });

      const card = el("div", { class: "standout-card" }, [
        el("div", { class: "sc-head" }, [
          el("div", { class: "sc-name" }, [s.supplier, newBadge(s.is_new)].filter(Boolean)),
          el("div", { class: "sc-amount" }, [fmtMoney(s.net_obligations)]),
        ]),
        el("div", { class: "sc-sub" }, [`${fmtNum(s.transaction_count)} transactions · ${fmtNum(s.unique_awards)} awards · ${s.concentration_pct.toFixed(1)}% of total`]),
        tagRow,
        detailsBtn,
        detailsWrap,
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn]),
      ]);
      container.appendChild(card);
    });
  }

  // ---------------- Category icons (generated locally, not fetched) ----------------
  const CATEGORY_ICONS = {
    "Aerospace, Spacecraft, and Mission Systems":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2c2 3 3 8 3 12 0 2-1 4-3 6-2-2-3-4-3-6 0-4 1-9 3-12Z" fill="#0891b2"/><path d="M9 14l-3 3 1 3 3-1" stroke="#3d5a75" stroke-width="1.2" fill="none"/><path d="M15 14l3 3-1 3-3-1" stroke="#3d5a75" stroke-width="1.2" fill="none"/><circle cx="12" cy="9" r="1.4" fill="#fff"/></svg>',
    "Research, Engineering, and Technical Services":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9 3h6v4l4 9c.6 1.4-.4 3-2 3H7c-1.6 0-2.6-1.6-2-3l4-9V3Z" stroke="#0891b2" stroke-width="1.3" fill="none"/><path d="M9 3h6" stroke="#0891b2" stroke-width="1.3"/><path d="M8 14h8" stroke="#0891b2" stroke-width="1.1"/></svg>',
    "Information Technology and Cybersecurity":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="12" rx="1.5" stroke="#0891b2" stroke-width="1.3"/><path d="M8 20h8M12 17v3" stroke="#0891b2" stroke-width="1.3"/><path d="M7 10l2 2-2 2M13 14h4" stroke="#3d5a75" stroke-width="1.1"/></svg>',
    "Facilities, Construction, and Maintenance":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 21V10l8-6 8 6v11" stroke="#0891b2" stroke-width="1.3" fill="none"/><path d="M9 21v-6h6v6" stroke="#3d5a75" stroke-width="1.2"/></svg>',
    "Scientific Instruments and Laboratory Supplies":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M10 2v6l-5 10a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-10V2" stroke="#0891b2" stroke-width="1.3" fill="none"/><path d="M8 2h8M7 15h10" stroke="#0891b2" stroke-width="1.2"/></svg>',
    "Professional and Administrative Services":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="7" width="18" height="13" rx="1.5" stroke="#0891b2" stroke-width="1.3"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="#0891b2" stroke-width="1.3"/></svg>',
    "Logistics, Transportation, and Operations":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="2" y="8" width="12" height="8" rx="1" stroke="#0891b2" stroke-width="1.3"/><path d="M14 11h4l3 3v2h-7" stroke="#0891b2" stroke-width="1.3"/><circle cx="6.5" cy="18" r="1.6" fill="#3d5a75"/><circle cx="17.5" cy="18" r="1.6" fill="#3d5a75"/></svg>',
    "Communications and Electronics":
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 12a8 8 0 0 1 16 0" stroke="#0891b2" stroke-width="1.3" fill="none"/><path d="M7.5 12a4.5 4.5 0 0 1 9 0" stroke="#0891b2" stroke-width="1.1" fill="none"/><circle cx="12" cy="12" r="1.6" fill="#3d5a75"/><path d="M12 13.5V21" stroke="#0891b2" stroke-width="1.3"/></svg>',
  };
  const DEFAULT_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="#64748b" stroke-width="1.3"/><path d="M12 16v.01M12 8a2.5 2.5 0 0 1 2.5 2.5c0 1.5-2.5 1.5-2.5 3.5" stroke="#64748b" stroke-width="1.3"/></svg>';
  function categoryIcon(category) { return CATEGORY_ICONS[category] || DEFAULT_ICON; }

  function renderStandoutAwards(fromFY, toFY) {
    const container = document.getElementById("standout-awards");
    container.innerHTML = "";
    const key = standoutRangeKey(fromFY, toFY);
    const rangeData = (DATA.standout_by_range || {})[key];
    const list = (rangeData ? rangeData.standout_awards : DATA.standout_awards) || [];
    if (!list.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No contract award met the standout criteria for this dataset."]));
      return;
    }
    const flags = getReviewFlags();

    const DESC_SHORT_LEN = 110;

    list.forEach(a => {
      const key = "award:" + a.award_id;
      const tagRow = el("div", {}, a.reasons.map(r => el("span", { class: "reason-tag " + r.type }, [r.label])));

      const desc = a.description || "";
      const descIsLong = desc.length > DESC_SHORT_LEN;
      const descShort = descIsLong ? desc.slice(0, DESC_SHORT_LEN) + "…" : desc;
      const detailNodes = [
        ...(descIsLong ? [el("div", { class: "award-desc" }, [desc])] : []),
        ...a.reasons.map(r => el("div", { class: "sc-reason-detail" }, [r.detail])),
      ];
      const { btn: detailsBtn, wrap: detailsWrap } = detailsToggle(detailNodes);

      const flagBtn = el("button", { class: "flag-btn" + (flags[key] ? " marked" : "") },
        [flags[key] ? "★ Marked for review" : "Mark for review"]);
      flagBtn.title = "Saved locally in this browser only -- does not notify or send anything to anyone.";
      flagBtn.addEventListener("click", () => {
        const nowMarked = toggleReviewFlag(key);
        flagBtn.textContent = nowMarked ? "★ Marked for review" : "Mark for review";
        flagBtn.classList.toggle("marked", nowMarked);
        showToast(nowMarked ? `Marked award ${a.award_id} for review` : `Removed award ${a.award_id} from review`);
      });

      const viewBtn = el("button", { class: "primary" }, ["View award on USAspending.gov ↗"]);
      viewBtn.title = "Opens the official public search on usaspending.gov in a new tab.";
      viewBtn.addEventListener("click", () => window.open(usaspendingSearchUrl(a.award_id), "_blank", "noopener"));

      const exportBtn = el("button", {}, ["Export contract CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.award_id_piid === a.award_id);
        const safeId = a.award_id.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_award_${safeId}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for award ${a.award_id}`);
      });

      const card = el("div", { class: "standout-card award-card", "data-award-id": a.award_id }, [
        el("div", { class: "award-head-row" }, [
          el("div", { class: "award-icon", html: categoryIcon(a.category) }),
          el("div", { class: "award-head-text" }, [
            el("div", { class: "sc-name" }, [a.supplier, newBadge(a.is_new)].filter(Boolean)),
            el("div", { class: "award-category" }, [a.category]),
            el("div", { class: "award-id code-text" }, [a.award_id]),
          ]),
          el("div", { class: "sc-amount" }, [fmtMoney(a.net_obligations)]),
        ]),
        el("div", { class: "sc-sub" }, [`${fmtNum(a.transaction_count)} transaction(s) · ${fmtNum(a.modification_count)} modification(s)`]),
        desc ? el("div", { class: "award-desc-short" }, [descShort]) : el("div", { class: "small-note" }, ["No transaction description on record."]),
        tagRow,
        detailsBtn,
        detailsWrap,
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn]),
      ]);
      container.appendChild(card);
    });
  }

  function setupStandoutAwardPhotoToggle() {
    const photoToggle = document.getElementById("award-photo-note-toggle");
    const photoNote = document.getElementById("award-photo-note");
    if (photoToggle && photoNote) {
      photoToggle.addEventListener("click", () => {
        const nowExpanded = photoNote.classList.toggle("expanded");
        photoToggle.textContent = nowExpanded ? "Why no real photos? (hide)" : "Why no real photos?";
      });
    }
  }

  function renderConsolidationOpportunities() {
    const container = document.getElementById("consolidation-opportunities");
    const list = DATA.consolidation_opportunities || [];
    if (!container) return;
    if (!list.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No category met the fragmentation criteria for this dataset."]));
      return;
    }
    const flags = getReviewFlags();

    list.forEach(c => {
      const key = "consolidation:" + c.category;
      const { btn: detailsBtn, wrap: detailsWrap } = detailsToggle([
        el("div", { class: "sc-reason-detail" }, [c.detail]),
        el("div", { class: "small-note" }, ["Leading suppliers in this category: " +
          c.leading_suppliers.map(s => `${s.supplier} (${fmtMoney(s.net_obligations)})`).join(", ")]),
      ]);

      const flagBtn = el("button", { class: "flag-btn" + (flags[key] ? " marked" : "") },
        [flags[key] ? "★ Marked for review" : "Mark for review"]);
      flagBtn.title = "Saved locally in this browser only -- does not notify or send anything to anyone.";
      flagBtn.addEventListener("click", () => {
        const nowMarked = toggleReviewFlag(key);
        flagBtn.textContent = nowMarked ? "★ Marked for review" : "Mark for review";
        flagBtn.classList.toggle("marked", nowMarked);
        showToast(nowMarked ? `Marked ${c.category} for review` : `Removed ${c.category} from review`);
      });

      const viewBtn = el("button", { class: "primary" }, ["View category ↗"]);
      viewBtn.title = "Jump to this category in Categories & Opportunities.";
      viewBtn.addEventListener("click", () => jumpToCategory(c.category));

      const exportBtn = el("button", {}, ["Export category CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.ai_spend_category === c.category);
        const safeName = c.category.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_category_${safeName}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for ${c.category}`);
      });

      const card = el("div", { class: "standout-card" }, [
        el("div", { class: "sc-head" }, [
          el("div", { class: "sc-name" }, [c.category, newBadge(c.is_new)].filter(Boolean)),
          el("div", { class: "sc-amount" }, [fmtMoney(c.total_net_obligations)]),
        ]),
        el("div", { class: "sc-sub" }, [
          `${fmtNum(c.unique_suppliers)} suppliers · HHI ${c.concentration_hhi.toFixed(0)} · top supplier ${c.top_supplier_share_pct.toFixed(0)}% share`,
        ]),
        el("div", {}, [el("span", { class: "reason-tag deobligation_flag" }, ["Fragmented spend"])]),
        detailsBtn,
        detailsWrap,
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn]),
      ]);
      container.appendChild(card);
    });
  }

  function renderDuplicateCandidates() {
    const container = document.getElementById("duplicate-candidates");
    const list = DATA.duplicate_purchase_candidates || [];
    if (!container) return;
    if (!list.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No pair of awards met the possible-duplicate criteria for this dataset."]));
      return;
    }
    const flags = getReviewFlags();

    list.forEach(d => {
      const key = "duplicate:" + d.pair_id;
      const { btn: detailsBtn, wrap: detailsWrap } = detailsToggle([
        el("div", { class: "sc-reason-detail" }, [d.detail]),
      ]);

      const rowA = el("div", { class: "duplicate-pair-row" }, [
        el("span", { class: "code-text" }, [d.award_id_a]),
        el("span", {}, [fmtMoney(d.amount_a) + " on " + d.date_a]),
      ]);
      const rowB = el("div", { class: "duplicate-pair-row" }, [
        el("span", { class: "code-text" }, [d.award_id_b]),
        el("span", {}, [fmtMoney(d.amount_b) + " on " + d.date_b]),
      ]);
      rowA.style.cursor = rowB.style.cursor = "pointer";
      rowA.title = rowB.title = "Jump to this award";
      rowA.addEventListener("click", () => jumpToAward(d.award_id_a));
      rowB.addEventListener("click", () => jumpToAward(d.award_id_b));

      const flagBtn = el("button", { class: "flag-btn" + (flags[key] ? " marked" : "") },
        [flags[key] ? "★ Marked for review" : "Mark for review"]);
      flagBtn.title = "Saved locally in this browser only -- does not notify or send anything to anyone.";
      flagBtn.addEventListener("click", () => {
        const nowMarked = toggleReviewFlag(key);
        flagBtn.textContent = nowMarked ? "★ Marked for review" : "Mark for review";
        flagBtn.classList.toggle("marked", nowMarked);
        showToast(nowMarked ? `Marked this pair for review` : `Removed this pair from review`);
      });

      const exportBtn = el("button", { class: "primary" }, ["Export both awards' CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.award_id_piid === d.award_id_a || r.award_id_piid === d.award_id_b);
        const safeId = d.pair_id.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_duplicate_pair_${safeId}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for this pair`);
      });

      const card = el("div", { class: "standout-card" }, [
        el("div", { class: "sc-head" }, [
          el("div", { class: "sc-name" }, [d.supplier, newBadge(d.is_new)].filter(Boolean)),
          el("div", { class: "sc-amount" }, [fmtMoney(d.combined_value)]),
        ]),
        el("div", { class: "sc-sub" }, [`${d.category} · ${fmtNum(d.days_apart)} day(s) apart`]),
        rowA, rowB,
        el("div", {}, [el("span", { class: "reason-tag cost_growth" }, ["Possible duplicate"])]),
        detailsBtn,
        detailsWrap,
        el("div", { class: "sc-actions" }, [exportBtn, flagBtn]),
      ]);
      container.appendChild(card);
    });
  }

  // ---------------- Tab 2: YoY ----------------
  function renderYoY() {
    const allAnnual = A.annual;
    if (DATA.meta.current_fiscal_year_is_partial) {
      document.getElementById("yoy-warning").appendChild(el("div", { class: "warning-banner" }, [
        `⚠ FY${DATA.meta.current_fiscal_year} is partial (in progress). Use the "Comparable year-to-date" view to compare fairly against prior years.`
      ]));
    }
    // Compare range comes from the header's global Timeframe control (see
    // setGlobalTimeframe()/onGlobalTimeframeChange() near the top of this
    // file) -- no local Fiscal Year selects on this tab anymore.
    function draw(fromFY, toFY) {
      const lo = fromFY == null ? allAnnual[0].fiscal_year : fromFY;
      const hi = toFY == null ? allAnnual[allAnnual.length - 1].fiscal_year : toFY;
      const inRange = fy => fy >= lo && fy <= hi;
      const annual = allAnnual.filter(r => inRange(r.fiscal_year));
      const conc = A.concentration_by_year.filter(r => inRange(r.fiscal_year));

      const years = annual.map(r => "FY" + r.fiscal_year + (r.is_partial_year ? " (partial)" : ""));
      Plotly.newPlot("chart-yoy-obligations", [
        { x: years, y: annual.map(r => r.net_obligations), type: "bar", name: "Net", marker: { color: NAVY } },
        { x: years, y: annual.map(r => r.gross_positive_obligations), type: "bar", name: "Gross Positive", marker: { color: BLUE } },
      ], darkLayout({ barmode: "group", margin: { t: 10, r: 10, l: 60, b: 60 }, yaxis: darkAxis({ tickformat: "~s" }), xaxis: darkAxis({}), legend: { orientation: "h", y: -0.3 } }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      Plotly.newPlot("chart-yoy-deob", [
        { x: years, y: annual.map(r => r.deobligations), type: "bar", marker: { color: RED }, name: "Deobligations" },
        { x: years, y: annual.map(r => r.deobligation_rate * 100), type: "scatter", mode: "lines+markers", name: "Rate %", yaxis: "y2", line: { color: GOLD } },
      ], darkLayout({
        margin: { t: 10, r: 40, l: 60, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ title: "USD", tickformat: "~s" }),
        yaxis2: darkAxis({ title: "Rate %", overlaying: "y", side: "right" }), legend: { orientation: "h", y: -0.3 },
      }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      Plotly.newPlot("chart-yoy-counts", [
        { x: years, y: annual.map(r => r.unique_suppliers), type: "bar", name: "Unique Suppliers", marker: { color: BLUE } },
        { x: years, y: annual.map(r => r.unique_awards), type: "bar", name: "Unique Awards", marker: { color: NAVY } },
      ], darkLayout({ barmode: "group", margin: { t: 10, r: 10, l: 50, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({}), legend: { orientation: "h", y: -0.3 } }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      Plotly.newPlot("chart-yoy-concentration", [
        { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.hhi), type: "scatter", mode: "lines+markers", name: "HHI", line: { color: RED } },
        { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.top5_share * 100), type: "scatter", mode: "lines+markers", name: "Top-5 Share %", yaxis: "y2", line: { color: BLUE } },
      ], darkLayout({
        margin: { t: 10, r: 40, l: 50, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ title: "HHI" }),
        yaxis2: darkAxis({ title: "Top-5 Share %", overlaying: "y", side: "right" }), legend: { orientation: "h", y: -0.3 },
      }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      // category_breakdown has no per-year breakdown; categories_detail does.
      const catNames = Object.keys(DATA.categories_detail);
      const traces = catNames.slice(0, 8).map((cat, i) => {
        const rows = DATA.categories_detail[cat].annual.filter(r => inRange(r.fiscal_year));
        return {
          x: rows.map(r => "FY" + r.fiscal_year), y: rows.map(r => r.net_obligations),
          type: "scatter", mode: "lines+markers", name: cat.length > 28 ? cat.slice(0, 26) + "…" : cat,
        };
      });
      Plotly.newPlot("chart-yoy-category", traces, darkLayout({ margin: { t: 10, r: 10, l: 60, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }), legend: { orientation: "h", y: -0.25 } }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      const tbl = document.getElementById("table-yoy");
      tbl.innerHTML = "";
      tbl.appendChild(el("thead", {}, [el("tr", {}, ["Fiscal Year", "Net Obligations", "Gross Positive", "Deobligations", "Deob. Rate", "Suppliers", "Awards", "Transactions"].map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      annual.forEach(r => {
        tbody.appendChild(el("tr", {}, [
          el("td", {}, ["FY" + r.fiscal_year + (r.is_partial_year ? " ⚠ partial" : "")]),
          el("td", {}, [fmtMoney(r.net_obligations)]),
          el("td", {}, [fmtMoney(r.gross_positive_obligations)]),
          el("td", {}, [fmtMoney(r.deobligations)]),
          el("td", {}, [fmtPct(r.deobligation_rate)]),
          el("td", {}, [fmtNum(r.unique_suppliers)]),
          el("td", {}, [fmtNum(r.unique_awards)]),
          el("td", {}, [fmtNum(r.transaction_count)]),
        ]));
      });
      tbl.appendChild(tbody);
    }

    draw(globalFromFY, globalToFY);
    onGlobalTimeframeChange(draw);
  }

  // ---------------- Tab 3: Transaction Explorer ----------------
  let explorerSort = { col: "action_date", dir: -1 };
  function renderExplorer() {
    document.getElementById("explorer-disclosure").textContent =
      `Showing ${fmtNum(DATA.meta.explorer_embedded_count)} of ${fmtNum(DATA.meta.transaction_count)} total transactions ` +
      `(most recent, capped at ${fmtNum(DATA.meta.explorer_row_limit)} rows embedded in this file). ` +
      `The complete processed dataset is retained outside the HTML in data/processed/.`;

    const rows = DATA.explorer_rows;
    const supSel = document.getElementById("ex-supplier"), catSel = document.getElementById("ex-category");
    // Fiscal-year filtering comes from the header's global Timeframe range
    // (see setGlobalTimeframe()/onGlobalTimeframeChange() near the top of
    // this file), not a local select here.
    const explorerWindowFYs = [...new Set(rows.map(r => r.fiscal_year))].sort();
    const suppliers = [...new Set(rows.map(r => r.normalized_supplier))].sort();
    suppliers.forEach(s => supSel.appendChild(el("option", { value: s }, [s])));
    const cats = [...new Set(rows.map(r => r.ai_spend_category))].sort();
    cats.forEach(c => catSel.appendChild(el("option", { value: c }, [c])));

    // Whether the header's global Timeframe range overlaps this tab's
    // embedded window -- set by the onGlobalTimeframeChange listener below.
    // When it doesn't overlap, the FY range is not applied (all embedded
    // rows pass) and an explanatory note is shown instead.
    let fyRangeApplies = true;

    function currentFiltered() {
      const q = document.getElementById("ex-search").value.trim().toLowerCase();
      const sup = supSel.value, cat = catSel.value, dir = document.getElementById("ex-direction").value;
      const minConf = parseFloat(document.getElementById("ex-confidence").value || "0");
      const minAmt = parseFloat(document.getElementById("ex-amount").value || "0");
      return rows.filter(r => {
        if (fyRangeApplies && globalFromFY != null && r.fiscal_year < globalFromFY) return false;
        if (fyRangeApplies && globalToFY != null && r.fiscal_year > globalToFY) return false;
        if (sup && r.normalized_supplier !== sup) return false;
        if (cat && r.ai_spend_category !== cat) return false;
        if (dir && r.obligation_direction !== dir) return false;
        if ((r.classification_confidence || 0) < minConf) return false;
        if (Math.abs(r.transaction_obligation_signed) < minAmt) return false;
        if (q) {
          const hay = [r.normalized_supplier, r.recipient_name_raw, r.award_id_piid, r.transaction_description].join(" ").toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
    }

    const COLS = [
      ["fiscal_year", "FY"], ["action_date", "Action Date"], ["recipient_name_raw", "Raw Recipient"],
      ["normalized_supplier", "Normalized Supplier"], ["transaction_obligation_signed", "Signed Amount"],
      ["obligation_direction", "Direction"], ["award_id_piid", "Award ID"], ["modification_number", "Mod"],
      ["action_type_description", "Action Type"], ["transaction_description", "Description"],
      ["psc_code", "PSC"], ["naics_code", "NAICS"], ["ai_spend_category", "Category"], ["ai_spend_subcategory", "Subcategory"],
      ["classification_confidence", "Class. Confidence"], ["review_status", "Review"], ["flags", "Flags"],
    ];

    function draw() {
      let filtered = currentFiltered();
      filtered.sort((a, b) => {
        const c = explorerSort.col;
        let va = a[c], vb = b[c];
        if (va === undefined) va = "";
        if (vb === undefined) vb = "";
        if (typeof va === "number" && typeof vb === "number") return (va - vb) * explorerSort.dir;
        return String(va).localeCompare(String(vb)) * explorerSort.dir;
      });
      document.getElementById("explorer-count").textContent = `${fmtNum(filtered.length)} rows match current filters (of ${fmtNum(rows.length)} embedded).`;

      const tbl = document.getElementById("table-explorer");
      tbl.innerHTML = "";
      const thead = el("tr", {});
      COLS.forEach(([key, label]) => {
        const th = el("th", { class: "sortable" }, [label + (explorerSort.col === key ? (explorerSort.dir === 1 ? " ▲" : " ▼") : "")]);
        th.addEventListener("click", () => {
          explorerSort.dir = explorerSort.col === key ? -explorerSort.dir : -1;
          explorerSort.col = key;
          draw();
        });
        thead.appendChild(th);
      });
      tbl.appendChild(el("thead", {}, [thead]));
      const tbody = el("tbody");
      filtered.slice(0, 500).forEach(r => {
        const amt = r.transaction_obligation_signed;
        const flags = [...(r.opportunity_flags || []), ...(r.data_quality_flags || [])];
        tbody.appendChild(el("tr", {}, [
          el("td", {}, [String(r.fiscal_year)]),
          el("td", {}, [r.action_date]),
          el("td", {}, [r.recipient_name_raw]),
          el("td", {}, [r.normalized_supplier]),
          el("td", { class: amt < 0 ? "neg" : "pos" }, [fmtMoney(amt)]),
          el("td", {}, [r.obligation_direction]),
          el("td", { class: "code-text" }, [r.award_id_piid]),
          el("td", { class: "code-text" }, [r.modification_number || ""]),
          el("td", {}, [r.action_type_description || ""]),
          el("td", {}, [(r.transaction_description || "").slice(0, 80)]),
          el("td", { class: "code-text" }, [r.psc_code || ""]),
          el("td", { class: "code-text" }, [r.naics_code || ""]),
          el("td", {}, [r.ai_spend_category]),
          el("td", {}, [r.ai_spend_subcategory]),
          el("td", {}, [fmtPct(r.classification_confidence)]),
          el("td", {}, [r.review_status]),
          el("td", {}, flags.map(f => el("span", { class: "flag-pill" + (r.review_status === "NEEDS_REVIEW" ? " review" : "") }, [f]))),
        ]));
      });
      tbl.appendChild(tbody);
      if (filtered.length > 500) {
        tbl.appendChild(el("tfoot", {}, [el("tr", {}, [el("td", { colspan: COLS.length, class: "small-note" }, [`Showing first 500 of ${filtered.length} filtered rows in the table view; CSV export includes all filtered rows.`])])]));
      }
      return filtered;
    }

    ["ex-search", "ex-supplier", "ex-category", "ex-direction", "ex-confidence", "ex-amount"].forEach(id => {
      document.getElementById(id).addEventListener("input", draw);
      document.getElementById(id).addEventListener("change", draw);
    });
    document.getElementById("ex-reset").addEventListener("click", () => {
      document.getElementById("ex-search").value = "";
      supSel.value = ""; catSel.value = "";
      document.getElementById("ex-direction").value = "";
      document.getElementById("ex-confidence").value = "0";
      document.getElementById("ex-amount").value = "0";
      draw();
    });
    document.getElementById("ex-export").addEventListener("click", () => {
      downloadCsv("nasa_procurement_filtered_export.csv", rowsToCsv(currentFiltered()));
    });

    // Global Timeframe control: applies directly as a fiscal-year range
    // filter above (see currentFiltered()). The Explorer table only embeds
    // the most recent explorer_row_limit transactions (not the whole
    // dataset), so a global range that doesn't overlap that window at all
    // would otherwise silently show zero rows -- fall back to "no FY
    // filter" and say so instead.
    onGlobalTimeframeChange((fromFY, toFY) => {
      const note = document.getElementById("explorer-timeframe-note");
      const overlaps = explorerWindowFYs.some(fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY));
      fyRangeApplies = overlaps;
      if (note) {
        note.textContent = overlaps ? "" :
          `The selected timeframe isn't in the Transaction Explorer's embedded window (only the most recent ${fmtNum(rows.length)} transactions are embedded here, covering ${explorerWindowFYs.map(y => "FY" + y).join(", ")}) -- showing all embedded transactions instead.`;
      }
      draw();
    });
    draw();
  }

  // ---------------- Tab 4: Supplier Analysis ----------------
  function renderSupplierTab() {
    const sel = document.getElementById("supplier-select");
    const names = Object.keys(DATA.suppliers_detail).sort((a, b) => DATA.suppliers_detail[b].total_net_obligations - DATA.suppliers_detail[a].total_net_obligations);
    names.forEach(n => sel.appendChild(el("option", { value: n }, [n])));

    function draw(fromFY, toFY) {
      const name = sel.value;
      const d = DATA.suppliers_detail[name];
      ["supplier-kpis", "chart-supplier-annual", "chart-supplier-category", "supplier-variants", "supplier-evidence", "supplier-offices", "supplier-flags", "supplier-headline"]
        .forEach(id => { const e = document.getElementById(id); e.innerHTML = ""; });
      if (!d) return;

      const headline = document.getElementById("supplier-headline");
      headline.appendChild(el("h3", { style: "margin:0; font-size:17px; color:var(--navy); text-transform:none; letter-spacing:0;" }, [name]));

      const kpis = document.getElementById("supplier-kpis");
      kpis.appendChild(kpiTile("Total Net Obligations", fmtMoney(d.total_net_obligations), d.total_net_obligations < 0));
      kpis.appendChild(kpiTile("Gross Positive", fmtMoney(d.gross_positive_obligations)));
      kpis.appendChild(kpiTile("Deobligations", fmtMoney(d.deobligations)));
      kpis.appendChild(kpiTile("Transactions", fmtNum(d.transaction_count)));
      kpis.appendChild(kpiTile("Unique Awards", fmtNum(d.unique_awards)));
      kpis.appendChild(kpiTile("Share of Total Obligations", fmtPct(d.share_of_agency_obligations)));

      // KPI tiles above are always all-time for this supplier (only
      // net_obligations is broken out per fiscal year server-side); the
      // header's Timeframe range instead highlights the matching bars below.
      const inRange = fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY);
      const isFullRange = fromFY == null && toFY == null;
      const annualColor = isFullRange ? BLUE : d.annual.map(r => inRange(r.fiscal_year) ? BLUE : "rgba(148,163,184,0.35)");
      Plotly.newPlot("chart-supplier-annual", [{
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: annualColor },
      }], darkLayout({ margin: { t: 10, r: 10, l: 55, b: 40 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }) }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      Plotly.newPlot("chart-supplier-category", [{
        labels: d.category_mix.map(r => r.category), values: d.category_mix.map(r => Math.max(r.net_obligations, 0)), type: "pie", hole: 0.45,
        marker: { line: { color: "#ffffff", width: 2 } }, textfont: { color: "#0f1e33" },
      }], darkLayout({ margin: { t: 10, r: 10, l: 10, b: 10 }, showlegend: true, legend: { font: { color: CHART_MUTED } } }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      const variants = document.getElementById("supplier-variants");
      d.raw_name_variants.forEach(v => variants.appendChild(el("span", { class: "chip" }, [v])));
      document.getElementById("supplier-evidence").textContent =
        `Resolution confidence: ${fmtPct(d.resolution_confidence)}. Evidence: ${d.resolution_evidence.join(" | ")}`;

      const offices = document.getElementById("supplier-offices");
      (d.awarding_offices.length ? d.awarding_offices : ["—"]).forEach(o => offices.appendChild(el("span", { class: "chip" }, [o])));

      const flagsDiv = document.getElementById("supplier-flags");
      if (d.flags.length) d.flags.forEach(f => flagsDiv.appendChild(el("span", { class: "flag-pill review" }, [f])));
      else flagsDiv.appendChild(el("span", { class: "small-note" }, ["No data-quality flags."]));
    }
    sel.addEventListener("change", () => draw(globalFromFY, globalToFY));
    onGlobalTimeframeChange(draw);
    if (names.length) { sel.value = names[0]; draw(globalFromFY, globalToFY); }
  }

  // ---------------- Tab 5: Categories & Opportunities ----------------
  function renderCategoriesTab() {
    const sel = document.getElementById("category-select");
    const names = Object.keys(DATA.categories_detail).sort((a, b) => {
      const sa = DATA.categories_detail[a].annual.reduce((s, r) => s + r.net_obligations, 0);
      const sb = DATA.categories_detail[b].annual.reduce((s, r) => s + r.net_obligations, 0);
      return sb - sa;
    });
    names.forEach(n => sel.appendChild(el("option", { value: n }, [n])));

    function draw(fromFY, toFY) {
      const name = sel.value;
      const d = DATA.categories_detail[name];
      ["category-kpis", "chart-category-annual", "category-findings", "category-quality-kpis"].forEach(id => document.getElementById(id).innerHTML = "");
      document.getElementById("table-category-suppliers").innerHTML = "";
      document.getElementById("table-review-queue").innerHTML = "";
      if (!d) return;

      const kpis = document.getElementById("category-kpis");
      const totalNet = d.annual.reduce((s, r) => s + r.net_obligations, 0);
      const leadingRows = () => d.leading_suppliers.map(r => [r.supplier, fmtMoney(r.net_obligations)]);
      const leadingNote = `Showing the top ${d.leading_suppliers.length} of ${fmtNum(d.unique_suppliers)} suppliers active in this category, by net obligations.`;

      kpis.appendChild(kpiTile("Net Obligations", fmtMoney(totalNet), totalNet < 0, () => ({
        title: `Net Obligations -- ${name}`,
        formula: `Sum of signed obligation amounts for every transaction classified into "${name}", across all fiscal years in this dataset.`,
        note: leadingNote,
        columns: ["Supplier", "Net Obligations"],
        rows: leadingRows(),
      })));
      kpis.appendChild(kpiTile("Unique Suppliers", fmtNum(d.unique_suppliers), false, () => ({
        title: `Unique Suppliers -- ${name}`,
        formula: `Count of distinct normalized suppliers with at least one transaction classified into "${name}".`,
        note: leadingNote,
        columns: ["Supplier", "Net Obligations"],
        rows: leadingRows(),
      })));
      kpis.appendChild(kpiTile("Concentration (HHI)", d.concentration_hhi.toFixed(0), false, () => {
        const posTotal = d.leading_suppliers.reduce((s, r) => s + Math.max(r.net_obligations, 0), 0);
        return {
          title: `Concentration (HHI) -- ${name}`,
          formula: "Herfindahl-Hirschman Index: each supplier's % share of this category's positive spend, squared, then summed (0-10,000 scale). DOJ/FTC convention: <1,500 unconcentrated, 1,500-2,500 moderate, >2,500 concentrated. Computed server-side over every supplier in the category, not just the ones shown below.",
          note: posTotal > 0
            ? `Share breakdown for the top ${d.leading_suppliers.length} suppliers shown below (long-tail suppliers outside this list also contribute to the actual HHI).`
            : undefined,
          columns: ["Supplier", "Share of Category Spend"],
          rows: posTotal > 0 ? d.leading_suppliers.map(r => [r.supplier, fmtPct(Math.max(r.net_obligations, 0) / posTotal)]) : [],
        };
      }));
      kpis.appendChild(kpiTile("Tail Spend Share", fmtPct(d.tail_spend_share), false, () => ({
        title: `Tail Spend Share -- ${name}`,
        formula: "Share of this category's positive net obligations attributable to suppliers outside the top 10% (by spend) within the category -- a measure of how much spend sits with the long tail of smaller vendors rather than the handful of largest ones.",
        note: "No per-supplier drill-down list is stored for the tail itself (only the top 10 \"head\" suppliers are embedded, shown on the Leading Suppliers table on this tab) -- the percentage above is computed server-side over every supplier in the category.",
        columns: null,
        rows: null,
      })));

      // KPI tiles above are always all-time for this category (the
      // per-category annual breakdown only has net_obligations); the
      // header's Timeframe range instead highlights the matching bars here.
      const inRange = fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY);
      const isFullRange = fromFY == null && toFY == null;
      const annualColor = isFullRange ? BLUE : d.annual.map(r => inRange(r.fiscal_year) ? BLUE : "rgba(148,163,184,0.35)");
      Plotly.newPlot("chart-category-annual", [{
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: annualColor },
      }], darkLayout({ margin: { t: 10, r: 10, l: 55, b: 40 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }) }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      const tbl = document.getElementById("table-category-suppliers");
      tbl.appendChild(el("thead", {}, [el("tr", {}, ["Supplier", "Net Obligations"].map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      d.leading_suppliers.forEach(r => tbody.appendChild(el("tr", {}, [el("td", {}, [r.supplier]), el("td", {}, [fmtMoney(r.net_obligations)])])));
      tbl.appendChild(tbody);

      const catFindings = (DATA.insights || []).filter(f => (f.affected_entities || []).some(e => e === name) || (f.title || "").includes(name));
      const findingsContainer = document.getElementById("category-findings");
      if (catFindings.length) {
        renderFindings(findingsContainer, catFindings);
      } else {
        findingsContainer.appendChild(el("div", { class: "small-note" }, ["No findings specifically cite this category. See Executive Overview for dataset-wide findings."]));
      }

      const explorerIsPartial = DATA.meta.transaction_count > DATA.meta.explorer_embedded_count;
      const explorerCaveat = explorerIsPartial
        ? ` The Transaction Explorer only embeds the ${fmtNum(DATA.meta.explorer_embedded_count)} most recent of ${fmtNum(DATA.meta.transaction_count)} transactions dataset-wide, so this sample may not include every matching row.`
        : "";
      const qk = document.getElementById("category-quality-kpis");
      qk.appendChild(kpiTile("Needs Review (this category)", fmtNum(d.needs_review_count), false, () => {
        const rows = DATA.explorer_rows.filter(r => r.ai_spend_category === name && r.review_status === "NEEDS_REVIEW").slice(0, 10);
        return {
          title: `Needs Review -- ${name}`,
          formula: `Count of transactions in "${name}" where review_status is NEEDS_REVIEW -- classification or supplier resolution fell below the confidence threshold and was not confirmed by an agent call.`,
          note: `Showing up to ${rows.length} matching rows.${explorerCaveat}`,
          columns: ["Date", "Supplier", "Award", "Amount"],
          rows: rows.map(r => [r.action_date, r.normalized_supplier, r.award_id_piid, fmtMoney(r.transaction_obligation_signed)]),
        };
      }));
      qk.appendChild(kpiTile("Low Classification Confidence (<0.6)", fmtNum(d.low_confidence_count), false, () => {
        const rows = DATA.explorer_rows.filter(r => r.ai_spend_category === name && r.classification_confidence < 0.6).slice(0, 10);
        return {
          title: `Low Classification Confidence -- ${name}`,
          formula: `Count of transactions in "${name}" with classification_confidence below 0.6.`,
          note: `Showing up to ${rows.length} matching rows.${explorerCaveat}`,
          columns: ["Date", "Supplier", "Award", "Confidence"],
          rows: rows.map(r => [r.action_date, r.normalized_supplier, r.award_id_piid, fmtPct(r.classification_confidence)]),
        };
      }));

      const rq = document.getElementById("table-review-queue");
      rq.appendChild(el("thead", {}, [el("tr", {}, ["Action Date", "Supplier", "Award ID", "Amount", "Confidence", "Flags"].map(h => el("th", {}, [h])))]));
      const rqBody = el("tbody");
      DATA.explorer_rows.filter(r => r.ai_spend_category === name && r.review_status === "NEEDS_REVIEW").slice(0, 100).forEach(r => {
        const flags = [...(r.opportunity_flags || []), ...(r.data_quality_flags || [])];
        rqBody.appendChild(el("tr", {}, [
          el("td", {}, [r.action_date]), el("td", {}, [r.normalized_supplier]), el("td", { class: "code-text" }, [r.award_id_piid]),
          el("td", {}, [fmtMoney(r.transaction_obligation_signed)]), el("td", {}, [fmtPct(r.classification_confidence)]),
          el("td", {}, flags.map(f => el("span", { class: "flag-pill review" }, [f]))),
        ]));
      });
      rq.appendChild(rqBody);
    }
    sel.addEventListener("change", () => draw(globalFromFY, globalToFY));
    onGlobalTimeframeChange(draw);
    if (names.length) { sel.value = names[0]; draw(globalFromFY, globalToFY); }
  }

  renderHeader();
  setupTabs();
  setupThemeToggle();
  setupCommandPalette();
  setupKpiModal();
  renderOverview();
  renderSnapshotStatus();
  setupStandoutAwardPhotoToggle();
  renderStandoutSuppliers(globalFromFY, globalToFY);
  renderStandoutAwards(globalFromFY, globalToFY);
  onGlobalTimeframeChange((fromFY, toFY) => {
    renderStandoutSuppliers(fromFY, toFY);
    renderStandoutAwards(fromFY, toFY);
  });
  renderConsolidationOpportunities();
  renderDuplicateCandidates();
  renderYoY();
  renderExplorer();
  renderSupplierTab();
  renderCategoriesTab();

  // Global Timeframe control (header FY-from/FY-to range) -- wired up last,
  // after every tab above has registered its onGlobalTimeframeChange()
  // listener, so the first change event already reaches all of them. Both
  // selects default to the full embedded range (equivalent to "All Years");
  // that default is never sent through setGlobalTimeframe() explicitly --
  // every listener above already treats its own (null, null) starting
  // state as "full range", so there's nothing to fire on load.
  const timeframeFromSel = document.getElementById("global-timeframe-from");
  const timeframeToSel = document.getElementById("global-timeframe-to");
  if (timeframeFromSel && timeframeToSel) {
    const embeddedFYs = A.annual.map(r => r.fiscal_year);
    const minFY = embeddedFYs[0], maxFY = embeddedFYs[embeddedFYs.length - 1];
    embeddedFYs.forEach(fy => {
      timeframeFromSel.appendChild(el("option", { value: fy }, ["FY" + fy]));
      timeframeToSel.appendChild(el("option", { value: fy }, ["FY" + fy]));
    });
    timeframeFromSel.value = minFY;
    timeframeToSel.value = maxFY;
    const onRangeChange = () => {
      let f = parseInt(timeframeFromSel.value, 10), t = parseInt(timeframeToSel.value, 10);
      if (f > t) { [f, t] = [t, f]; timeframeFromSel.value = f; timeframeToSel.value = t; }
      const isFull = f === minFY && t === maxFY;
      setGlobalTimeframe(isFull ? null : f, isFull ? null : t);
    };
    timeframeFromSel.addEventListener("change", onRangeChange);
    timeframeToSel.addEventListener("change", onRangeChange);
  }
})();
