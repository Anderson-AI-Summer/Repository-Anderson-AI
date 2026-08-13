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
    }, extra);
  }
  function darkAxis(extra) {
    return Object.assign({ gridcolor: CHART_GRID, zerolinecolor: CHART_LINE, linecolor: CHART_LINE, color: CHART_MUTED }, extra);
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

  // ---------------- Tabs ----------------
  function setupTabs() {
    const buttons = document.querySelectorAll("nav.tabs button");
    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        window.dispatchEvent(new Event("resize"));
      });
    });
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

  function kpiTile(label, value, negClass) {
    return el("div", { class: "kpi" }, [
      el("div", { class: "label" }, [label]),
      el("div", { class: "value" + (negClass ? " neg" : "") }, [value]),
    ]);
  }

  // ---------------- Tab 1: Executive Overview ----------------
  function renderOverview() {
    if (DATA.meta.current_fiscal_year_is_partial) {
      document.getElementById("overview-warning").appendChild(el("div", { class: "warning-banner" }, [
        `⚠ FY${DATA.meta.current_fiscal_year} is still in progress (partial year). Totals for the current fiscal year are not directly comparable to completed fiscal years.`
      ]));
    }
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

    const t = A.totals;
    const kpis = document.getElementById("overview-kpis");
    kpis.appendChild(kpiTile("Net Obligations", fmtMoney(t.net_obligations), t.net_obligations < 0));
    kpis.appendChild(kpiTile("Gross Positive Obligations", fmtMoney(t.gross_positive_obligations)));
    kpis.appendChild(kpiTile("Deobligations", fmtMoney(t.deobligations)));
    kpis.appendChild(kpiTile("Transactions", fmtNum(t.transaction_count)));
    kpis.appendChild(kpiTile("Unique Awards", fmtNum(t.unique_awards)));
    kpis.appendChild(kpiTile("Normalized Suppliers", fmtNum(t.unique_suppliers)));

    const years = A.annual.map(r => "FY" + r.fiscal_year);
    Plotly.newPlot("chart-annual-trend", [
      { x: years, y: A.annual.map(r => r.gross_positive_obligations), type: "bar", name: "Gross Obligations", marker: { color: BLUE } },
      { x: years, y: A.annual.map(r => -r.deobligations), type: "bar", name: "Deobligations", marker: { color: RED } },
      { x: years, y: A.annual.map(r => r.net_obligations), type: "scatter", mode: "lines+markers", name: "Net Obligations", line: { color: NAVY, width: 3 } },
    ], darkLayout({
      barmode: "relative", margin: { t: 10, r: 10, l: 60, b: 40 },
      yaxis: darkAxis({ title: "USD", tickformat: "~s" }), legend: { orientation: "h", y: -0.2 },
    }), { displayModeBar: false, responsive: true });

    const cats = A.category_breakdown.slice().reduce((acc, r) => {
      acc[r.category] = (acc[r.category] || 0) + r.net_obligations; return acc;
    }, {});
    const catNames = Object.keys(cats).sort((a, b) => cats[b] - cats[a]);
    const categoryChart = document.getElementById("chart-category-comp");
    Plotly.newPlot(categoryChart, [{
      x: catNames.map(c => cats[c]), y: catNames, type: "bar", orientation: "h",
      marker: { color: BLUE },
    }], darkLayout({
      margin: { t: 10, r: 10, l: 230, b: 40 }, xaxis: darkAxis({ title: "Net Obligations (USD)", tickformat: "~s" }), yaxis: darkAxis({}),
    }), { displayModeBar: false, responsive: true });
    categoryChart.on("plotly_click", ev => {
      const name = ev.points && ev.points[0] && ev.points[0].y;
      if (name) jumpToCategory(name);
    });
    categoryChart.style.cursor = "pointer";

    drawTopSuppliers();
    drawTopContracts();
    document.getElementById("top-suppliers-sort").addEventListener("change", drawTopSuppliers);
    document.getElementById("top-contracts-sort").addEventListener("change", drawTopContracts);

    renderFindings(document.getElementById("overview-findings"), DATA.insights);
  }

  // "TOP" is a choice, not a fact -- these two tables let the viewer pick
  // which metric defines it instead of hard-coding "top = highest dollar
  // value" as the only lens.
  function drawTopSuppliers() {
    const sortKey = document.getElementById("top-suppliers-sort").value;
    const rows = Object.entries(DATA.suppliers_detail || {}).map(([name, d]) => ({
      supplier: name,
      net_obligations: d.total_net_obligations,
      transaction_count: d.transaction_count,
      unique_awards: d.unique_awards,
      deobligations: d.deobligations,
    }));
    rows.sort((a, b) => b[sortKey] - a[sortKey]);

    const tbl = document.getElementById("table-top-suppliers");
    tbl.innerHTML = "";
    tbl.appendChild(el("thead", {}, [el("tr", {}, ["Supplier", "Net Obligations", "Transactions", "Awards", "Deobligations"].map(h => el("th", {}, [h])))]));
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
    const sortKey = document.getElementById("top-contracts-sort").value;
    const rows = (DATA.awards_summary || []).slice().sort((a, b) => b[sortKey] - a[sortKey]);

    const contractsTbl = document.getElementById("table-top-contracts");
    if (!contractsTbl) return;
    contractsTbl.innerHTML = "";
    contractsTbl.appendChild(el("thead", {}, [el("tr", {}, ["Supplier", "Net Obligations", "Transactions", "Modifications", "Deobligations", "Award"].map(h => el("th", {}, [h])))]));
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

  function renderFindings(container, findings) {
    if (!findings || !findings.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No grounded findings met the reporting threshold for this dataset."]));
      return;
    }
    findings.forEach(f => {
      const card = el("div", { class: "finding-card" }, [
        el("h4", {}, [f.title]),
        el("div", {}, [f.description]),
        el("div", { class: "metrics" }, ["Supporting metrics: " + (f.supporting_metrics || []).join(", ")]),
      ]);
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

  function renderStandoutSuppliers() {
    const container = document.getElementById("standout-suppliers");
    const list = DATA.standout_suppliers || [];
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
      });

      const viewBtn = el("button", { class: "primary" }, ["View on USAspending.gov ↗"]);
      viewBtn.title = "Opens the official public search on usaspending.gov in a new tab.";
      viewBtn.addEventListener("click", () => window.open(usaspendingSearchUrl(s.supplier), "_blank", "noopener"));

      const exportBtn = el("button", {}, ["Export supplier CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.normalized_supplier === s.supplier);
        const safeName = s.supplier.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_supplier_${safeName}.csv`, rowsToCsv(rows));
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

  function renderStandoutAwards() {
    const photoToggle = document.getElementById("award-photo-note-toggle");
    const photoNote = document.getElementById("award-photo-note");
    if (photoToggle && photoNote) {
      photoToggle.addEventListener("click", () => {
        const nowExpanded = photoNote.classList.toggle("expanded");
        photoToggle.textContent = nowExpanded ? "Why no real photos? (hide)" : "Why no real photos?";
      });
    }

    const container = document.getElementById("standout-awards");
    const list = DATA.standout_awards || [];
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
      });

      const viewBtn = el("button", { class: "primary" }, ["View award on USAspending.gov ↗"]);
      viewBtn.title = "Opens the official public search on usaspending.gov in a new tab.";
      viewBtn.addEventListener("click", () => window.open(usaspendingSearchUrl(a.award_id), "_blank", "noopener"));

      const exportBtn = el("button", {}, ["Export contract CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.award_id_piid === a.award_id);
        const safeId = a.award_id.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_award_${safeId}.csv`, rowsToCsv(rows));
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
      });

      const viewBtn = el("button", { class: "primary" }, ["View category ↗"]);
      viewBtn.title = "Jump to this category in Categories & Opportunities.";
      viewBtn.addEventListener("click", () => jumpToCategory(c.category));

      const exportBtn = el("button", {}, ["Export category CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.ai_spend_category === c.category);
        const safeName = c.category.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_category_${safeName}.csv`, rowsToCsv(rows));
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
      });

      const exportBtn = el("button", { class: "primary" }, ["Export both awards' CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.award_id_piid === d.award_id_a || r.award_id_piid === d.award_id_b);
        const safeId = d.pair_id.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_duplicate_pair_${safeId}.csv`, rowsToCsv(rows));
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
    const annual = A.annual;
    if (DATA.meta.current_fiscal_year_is_partial) {
      document.getElementById("yoy-warning").appendChild(el("div", { class: "warning-banner" }, [
        `⚠ FY${DATA.meta.current_fiscal_year} is partial (in progress). Use the "Comparable year-to-date" view to compare fairly against prior years.`
      ]));
    }
    const fyFrom = document.getElementById("yoy-fy-from"), fyTo = document.getElementById("yoy-fy-to");
    annual.forEach(r => {
      fyFrom.appendChild(el("option", { value: r.fiscal_year }, ["FY" + r.fiscal_year]));
      fyTo.appendChild(el("option", { value: r.fiscal_year }, ["FY" + r.fiscal_year]));
    });
    if (annual.length > 1) { fyFrom.value = annual[0].fiscal_year; fyTo.value = annual[annual.length - 1].fiscal_year; }

    const years = annual.map(r => "FY" + r.fiscal_year + (r.is_partial_year ? " (partial)" : ""));
    Plotly.newPlot("chart-yoy-obligations", [
      { x: years, y: annual.map(r => r.net_obligations), type: "bar", name: "Net", marker: { color: NAVY } },
      { x: years, y: annual.map(r => r.gross_positive_obligations), type: "bar", name: "Gross Positive", marker: { color: BLUE } },
    ], darkLayout({ barmode: "group", margin: { t: 10, r: 10, l: 60, b: 60 }, yaxis: darkAxis({ tickformat: "~s" }), xaxis: darkAxis({}), legend: { orientation: "h", y: -0.3 } }), { displayModeBar: false, responsive: true });

    Plotly.newPlot("chart-yoy-deob", [
      { x: years, y: annual.map(r => r.deobligations), type: "bar", marker: { color: RED }, name: "Deobligations" },
      { x: years, y: annual.map(r => r.deobligation_rate * 100), type: "scatter", mode: "lines+markers", name: "Rate %", yaxis: "y2", line: { color: GOLD } },
    ], darkLayout({
      margin: { t: 10, r: 40, l: 60, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ title: "USD", tickformat: "~s" }),
      yaxis2: darkAxis({ title: "Rate %", overlaying: "y", side: "right" }), legend: { orientation: "h", y: -0.3 },
    }), { displayModeBar: false, responsive: true });

    Plotly.newPlot("chart-yoy-counts", [
      { x: years, y: annual.map(r => r.unique_suppliers), type: "bar", name: "Unique Suppliers", marker: { color: BLUE } },
      { x: years, y: annual.map(r => r.unique_awards), type: "bar", name: "Unique Awards", marker: { color: NAVY } },
    ], darkLayout({ barmode: "group", margin: { t: 10, r: 10, l: 50, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({}), legend: { orientation: "h", y: -0.3 } }), { displayModeBar: false, responsive: true });

    const conc = A.concentration_by_year;
    Plotly.newPlot("chart-yoy-concentration", [
      { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.hhi), type: "scatter", mode: "lines+markers", name: "HHI", line: { color: RED } },
      { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.top5_share * 100), type: "scatter", mode: "lines+markers", name: "Top-5 Share %", yaxis: "y2", line: { color: BLUE } },
    ], darkLayout({
      margin: { t: 10, r: 40, l: 50, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ title: "HHI" }),
      yaxis2: darkAxis({ title: "Top-5 Share %", overlaying: "y", side: "right" }), legend: { orientation: "h", y: -0.3 },
    }), { displayModeBar: false, responsive: true });

    // category_breakdown has no per-year breakdown; categories_detail does.
    const catNames = Object.keys(DATA.categories_detail);
    const traces = catNames.slice(0, 8).map((cat, i) => {
      const rows = DATA.categories_detail[cat].annual;
      return {
        x: rows.map(r => "FY" + r.fiscal_year), y: rows.map(r => r.net_obligations),
        type: "scatter", mode: "lines+markers", name: cat.length > 28 ? cat.slice(0, 26) + "…" : cat,
      };
    });
    Plotly.newPlot("chart-yoy-category", traces, darkLayout({ margin: { t: 10, r: 10, l: 60, b: 60 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }), legend: { orientation: "h", y: -0.25 } }), { displayModeBar: false, responsive: true });

    const tbl = document.getElementById("table-yoy");
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

  // ---------------- Tab 3: Transaction Explorer ----------------
  let explorerSort = { col: "action_date", dir: -1 };
  function renderExplorer() {
    document.getElementById("explorer-disclosure").textContent =
      `Showing ${fmtNum(DATA.meta.explorer_embedded_count)} of ${fmtNum(DATA.meta.transaction_count)} total transactions ` +
      `(most recent, capped at ${fmtNum(DATA.meta.explorer_row_limit)} rows embedded in this file). ` +
      `The complete processed dataset is retained outside the HTML in data/processed/.`;

    const rows = DATA.explorer_rows;
    const fySel = document.getElementById("ex-fy"), supSel = document.getElementById("ex-supplier"), catSel = document.getElementById("ex-category");
    const fys = [...new Set(rows.map(r => r.fiscal_year))].sort();
    fys.forEach(fy => fySel.appendChild(el("option", { value: fy }, ["FY" + fy])));
    const suppliers = [...new Set(rows.map(r => r.normalized_supplier))].sort();
    suppliers.forEach(s => supSel.appendChild(el("option", { value: s }, [s])));
    const cats = [...new Set(rows.map(r => r.ai_spend_category))].sort();
    cats.forEach(c => catSel.appendChild(el("option", { value: c }, [c])));

    function currentFiltered() {
      const q = document.getElementById("ex-search").value.trim().toLowerCase();
      const fy = fySel.value, sup = supSel.value, cat = catSel.value, dir = document.getElementById("ex-direction").value;
      const minConf = parseFloat(document.getElementById("ex-confidence").value || "0");
      const minAmt = parseFloat(document.getElementById("ex-amount").value || "0");
      return rows.filter(r => {
        if (fy && String(r.fiscal_year) !== String(fy)) return false;
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

    ["ex-search", "ex-fy", "ex-supplier", "ex-category", "ex-direction", "ex-confidence", "ex-amount"].forEach(id => {
      document.getElementById(id).addEventListener("input", draw);
      document.getElementById(id).addEventListener("change", draw);
    });
    document.getElementById("ex-reset").addEventListener("click", () => {
      document.getElementById("ex-search").value = "";
      fySel.value = ""; supSel.value = ""; catSel.value = "";
      document.getElementById("ex-direction").value = "";
      document.getElementById("ex-confidence").value = "0";
      document.getElementById("ex-amount").value = "0";
      draw();
    });
    document.getElementById("ex-export").addEventListener("click", () => {
      downloadCsv("nasa_procurement_filtered_export.csv", rowsToCsv(currentFiltered()));
    });

    draw();
  }

  // ---------------- Tab 4: Supplier Analysis ----------------
  function renderSupplierTab() {
    const sel = document.getElementById("supplier-select");
    const names = Object.keys(DATA.suppliers_detail).sort((a, b) => DATA.suppliers_detail[b].total_net_obligations - DATA.suppliers_detail[a].total_net_obligations);
    names.forEach(n => sel.appendChild(el("option", { value: n }, [n])));

    function draw() {
      const name = sel.value;
      const d = DATA.suppliers_detail[name];
      ["supplier-kpis", "chart-supplier-annual", "chart-supplier-category", "supplier-variants", "supplier-evidence", "supplier-offices", "supplier-flags"]
        .forEach(id => { const e = document.getElementById(id); e.innerHTML = ""; });
      if (!d) return;

      const kpis = document.getElementById("supplier-kpis");
      kpis.appendChild(kpiTile("Total Net Obligations", fmtMoney(d.total_net_obligations), d.total_net_obligations < 0));
      kpis.appendChild(kpiTile("Gross Positive", fmtMoney(d.gross_positive_obligations)));
      kpis.appendChild(kpiTile("Deobligations", fmtMoney(d.deobligations)));
      kpis.appendChild(kpiTile("Transactions", fmtNum(d.transaction_count)));
      kpis.appendChild(kpiTile("Unique Awards", fmtNum(d.unique_awards)));
      kpis.appendChild(kpiTile("Share of Total Obligations", fmtPct(d.share_of_agency_obligations)));

      Plotly.newPlot("chart-supplier-annual", [{
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: BLUE },
      }], darkLayout({ margin: { t: 10, r: 10, l: 55, b: 40 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }) }), { displayModeBar: false, responsive: true });

      Plotly.newPlot("chart-supplier-category", [{
        labels: d.category_mix.map(r => r.category), values: d.category_mix.map(r => Math.max(r.net_obligations, 0)), type: "pie", hole: 0.45,
        marker: { line: { color: "#ffffff", width: 2 } }, textfont: { color: "#0f1e33" },
      }], darkLayout({ margin: { t: 10, r: 10, l: 10, b: 10 }, showlegend: true, legend: { font: { color: CHART_MUTED } } }), { displayModeBar: false, responsive: true });

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
    sel.addEventListener("change", draw);
    if (names.length) { sel.value = names[0]; draw(); }
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

    function draw() {
      const name = sel.value;
      const d = DATA.categories_detail[name];
      ["category-kpis", "chart-category-annual", "category-findings", "category-quality-kpis"].forEach(id => document.getElementById(id).innerHTML = "");
      document.getElementById("table-category-suppliers").innerHTML = "";
      document.getElementById("table-review-queue").innerHTML = "";
      if (!d) return;

      const kpis = document.getElementById("category-kpis");
      const totalNet = d.annual.reduce((s, r) => s + r.net_obligations, 0);
      kpis.appendChild(kpiTile("Net Obligations", fmtMoney(totalNet), totalNet < 0));
      kpis.appendChild(kpiTile("Unique Suppliers", fmtNum(d.unique_suppliers)));
      kpis.appendChild(kpiTile("Concentration (HHI)", d.concentration_hhi.toFixed(0)));
      kpis.appendChild(kpiTile("Tail Spend Share", fmtPct(d.tail_spend_share)));

      Plotly.newPlot("chart-category-annual", [{
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: BLUE },
      }], darkLayout({ margin: { t: 10, r: 10, l: 55, b: 40 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }) }), { displayModeBar: false, responsive: true });

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

      const qk = document.getElementById("category-quality-kpis");
      qk.appendChild(kpiTile("Needs Review (this category)", fmtNum(d.needs_review_count)));
      qk.appendChild(kpiTile("Low Classification Confidence (<0.6)", fmtNum(d.low_confidence_count)));

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
    sel.addEventListener("change", draw);
    if (names.length) { sel.value = names[0]; draw(); }
  }

  renderHeader();
  setupTabs();
  renderOverview();
  renderSnapshotStatus();
  renderStandoutSuppliers();
  renderStandoutAwards();
  renderConsolidationOpportunities();
  renderDuplicateCandidates();
  renderYoY();
  renderExplorer();
  renderSupplierTab();
  renderCategoriesTab();
})();
