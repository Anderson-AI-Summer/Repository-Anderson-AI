(function () {
  "use strict";
  const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
  const A = DATA.analytics;
  const NAVY = "#0b1f3a", BLUE = "#2a6df4", RED = "#d0392b", GREY = "#8a93a6", GOLD = "#c98a1a";

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
    ], {
      barmode: "relative", margin: { t: 10, r: 10, l: 60, b: 40 },
      yaxis: { title: "USD", tickformat: "~s" }, legend: { orientation: "h", y: -0.2 },
    }, { displayModeBar: false, responsive: true });

    const cats = A.category_breakdown.slice().reduce((acc, r) => {
      acc[r.category] = (acc[r.category] || 0) + r.net_obligations; return acc;
    }, {});
    const catNames = Object.keys(cats).sort((a, b) => cats[b] - cats[a]);
    Plotly.newPlot("chart-category-comp", [{
      x: catNames.map(c => cats[c]), y: catNames, type: "bar", orientation: "h",
      marker: { color: BLUE },
    }], {
      margin: { t: 10, r: 10, l: 230, b: 40 }, xaxis: { title: "Net Obligations (USD)", tickformat: "~s" },
    }, { displayModeBar: false, responsive: true });

    const tbl = document.getElementById("table-top-suppliers");
    tbl.appendChild(el("thead", {}, [el("tr", {}, ["Supplier", "Net Obligations", "Transactions", "Awards"].map(h => el("th", {}, [h])))]));
    const tbody = el("tbody");
    A.top_suppliers.slice(0, 12).forEach(r => {
      tbody.appendChild(el("tr", {}, [
        el("td", {}, [r.normalized_supplier]),
        el("td", {}, [fmtMoney(r.net_obligations)]),
        el("td", {}, [fmtNum(r.transaction_count)]),
        el("td", {}, [fmtNum(r.unique_awards)]),
      ]));
    });
    tbl.appendChild(tbody);

    renderFindings(document.getElementById("overview-findings"), DATA.insights);
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
    ], { barmode: "group", margin: { t: 10, r: 10, l: 60, b: 60 }, yaxis: { tickformat: "~s" }, legend: { orientation: "h", y: -0.3 } }, { displayModeBar: false, responsive: true });

    Plotly.newPlot("chart-yoy-deob", [
      { x: years, y: annual.map(r => r.deobligations), type: "bar", marker: { color: RED }, name: "Deobligations" },
      { x: years, y: annual.map(r => r.deobligation_rate * 100), type: "scatter", mode: "lines+markers", name: "Rate %", yaxis: "y2", line: { color: GOLD } },
    ], {
      margin: { t: 10, r: 40, l: 60, b: 60 }, yaxis: { title: "USD", tickformat: "~s" },
      yaxis2: { title: "Rate %", overlaying: "y", side: "right" }, legend: { orientation: "h", y: -0.3 },
    }, { displayModeBar: false, responsive: true });

    Plotly.newPlot("chart-yoy-counts", [
      { x: years, y: annual.map(r => r.unique_suppliers), type: "bar", name: "Unique Suppliers", marker: { color: BLUE } },
      { x: years, y: annual.map(r => r.unique_awards), type: "bar", name: "Unique Awards", marker: { color: NAVY } },
    ], { barmode: "group", margin: { t: 10, r: 10, l: 50, b: 60 }, legend: { orientation: "h", y: -0.3 } }, { displayModeBar: false, responsive: true });

    const conc = A.concentration_by_year;
    Plotly.newPlot("chart-yoy-concentration", [
      { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.hhi), type: "scatter", mode: "lines+markers", name: "HHI", line: { color: RED } },
      { x: conc.map(r => "FY" + r.fiscal_year), y: conc.map(r => r.top5_share * 100), type: "scatter", mode: "lines+markers", name: "Top-5 Share %", yaxis: "y2", line: { color: BLUE } },
    ], {
      margin: { t: 10, r: 40, l: 50, b: 60 }, yaxis: { title: "HHI" },
      yaxis2: { title: "Top-5 Share %", overlaying: "y", side: "right" }, legend: { orientation: "h", y: -0.3 },
    }, { displayModeBar: false, responsive: true });

    const topCats = Object.keys(A.category_breakdown.reduce((a, r) => { a[r.category] = (a[r.category] || 0) + r.net_obligations; return a; }, {}))
      .sort((x, y) => 0);
    const catByYear = {};
    A.category_breakdown.forEach(() => {});
    // Build category-by-year net obligations from explorer-independent source: category_breakdown lacks per-year; use categories_detail annual arrays.
    const catNames = Object.keys(DATA.categories_detail);
    const traces = catNames.slice(0, 8).map((cat, i) => {
      const rows = DATA.categories_detail[cat].annual;
      return {
        x: rows.map(r => "FY" + r.fiscal_year), y: rows.map(r => r.net_obligations),
        type: "scatter", mode: "lines+markers", name: cat.length > 28 ? cat.slice(0, 26) + "…" : cat,
      };
    });
    Plotly.newPlot("chart-yoy-category", traces, { margin: { t: 10, r: 10, l: 60, b: 60 }, yaxis: { tickformat: "~s" }, legend: { orientation: "h", y: -0.25 } }, { displayModeBar: false, responsive: true });

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
          el("td", {}, [r.award_id_piid]),
          el("td", {}, [r.modification_number || ""]),
          el("td", {}, [r.action_type_description || ""]),
          el("td", {}, [(r.transaction_description || "").slice(0, 80)]),
          el("td", {}, [r.psc_code || ""]),
          el("td", {}, [r.naics_code || ""]),
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
      const filtered = currentFiltered();
      const header = COLS.map(c => c[1]).join(",");
      const csvRows = filtered.map(r => {
        const flags = [...(r.opportunity_flags || []), ...(r.data_quality_flags || [])].join("; ");
        const vals = [
          r.fiscal_year, r.action_date, r.recipient_name_raw, r.normalized_supplier,
          r.transaction_obligation_signed, r.obligation_direction, r.award_id_piid, r.modification_number || "",
          r.action_type_description || "", r.transaction_description || "", r.psc_code || "", r.naics_code || "",
          r.ai_spend_category, r.ai_spend_subcategory, r.classification_confidence, r.review_status, flags,
        ];
        return vals.map(v => `"${String(v === undefined || v === null ? "" : v).replace(/"/g, '""')}"`).join(",");
      });
      const csv = [header, ...csvRows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "nasa_procurement_filtered_export.csv";
      link.click();
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
      }], { margin: { t: 10, r: 10, l: 55, b: 40 }, yaxis: { tickformat: "~s" } }, { displayModeBar: false, responsive: true });

      Plotly.newPlot("chart-supplier-category", [{
        labels: d.category_mix.map(r => r.category), values: d.category_mix.map(r => Math.max(r.net_obligations, 0)), type: "pie", hole: 0.45,
      }], { margin: { t: 10, r: 10, l: 10, b: 10 }, showlegend: true }, { displayModeBar: false, responsive: true });

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
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: NAVY },
      }], { margin: { t: 10, r: 10, l: 55, b: 40 }, yaxis: { tickformat: "~s" } }, { displayModeBar: false, responsive: true });

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
          el("td", {}, [r.action_date]), el("td", {}, [r.normalized_supplier]), el("td", {}, [r.award_id_piid]),
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
  renderYoY();
  renderExplorer();
  renderSupplierTab();
  renderCategoriesTab();
})();
