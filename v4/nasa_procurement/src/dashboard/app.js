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

  // ---------------- Action Center: mitigation-workflow playbooks ----------------
  // Reference workflow templates this dashboard suggests for each disclosed
  // signal type. Every step here is generic, common-sense contract/spend
  // management practice -- not a real NASA procedure, not legal or
  // contracting guidance, and not connected to any real system. Workflow
  // *state* (which step you're on, notes, status) is a separate concern,
  // stored purely in this browser's localStorage -- see WORKFLOW_KEY below.
  const PLAYBOOKS = {
    deobligation_mitigation: {
      name: "Deobligation Mitigation",
      trigger: "Notable deobligations",
      summary: "Confirm the cause of a deobligation and line up an alternative funding path so program work doesn't stall.",
      steps: [
        "Flag for contracting officer review",
        "Confirm cause: data correction, descope, or funding cut",
        "Assess downstream budget & schedule impact",
        "Evaluate alternative funding (budget reallocation, private investment / Other Transaction Authority partnership, phased scope)",
        "Document mitigation decision and close out",
      ],
    },
    rapid_decline_continuity: {
      name: "Rapid Decline — Supplier Continuity Review",
      trigger: "Rapid year-over-year decline",
      summary: "Check whether a steep year-over-year drop threatens program continuity, and line up a backup path if it does.",
      steps: [
        "Confirm the decline against the award record (completion, non-renewal, performance issue)",
        "Assess schedule risk to dependent program milestones",
        "Identify qualified backup suppliers in this category",
        "Decide: renew/extend, re-solicit, or accept planned wind-down",
        "Document decision and notify affected program leads",
      ],
    },
    rapid_growth_review: {
      name: "Rapid Growth — Scope & Ceiling Review",
      trigger: "Rapid year-over-year growth",
      summary: "Confirm a steep spend increase reflects justified, in-scope work rather than uncontrolled scope creep.",
      steps: [
        "Compare current obligations against the award ceiling",
        "Confirm modifications are within original scope",
        "Check competition requirements weren't bypassed via improper sole-source growth",
        "Flag for program-office sign-off if ceiling is at risk",
        "Document review outcome",
      ],
    },
    cost_growth_review: {
      name: "Cost Growth via Modifications — Value Review",
      trigger: "Grew via modifications",
      summary: "A contract that grew substantially through modifications gets a second look at whether the added scope still represents good value.",
      steps: [
        "Pull modification history and stated justification for each",
        "Confirm pricing basis (fixed-price change vs. cost-reimbursement growth)",
        "Compare against market rates for comparable scope",
        "Escalate to price/cost analysis if growth exceeds threshold",
        "Document conclusion",
      ],
    },
    concentration_diversification: {
      name: "Spend Concentration — Market Diversification",
      trigger: "High spend concentration",
      summary: "Reduce single-supplier dependency risk by identifying alternate qualified sources before the next re-compete.",
      steps: [
        "Confirm this is a genuine single-point-of-failure risk (vs. a legitimately sole-source capability)",
        "Identify alternate qualified suppliers in the market",
        "Evaluate a set-aside or multi-award strategy for the next re-compete",
        "Brief program leadership on diversification options",
        "Track progress toward the next re-compete milestone",
      ],
    },
    high_value_oversight: {
      name: "High-Value Award — Enhanced Oversight",
      trigger: "High contract value",
      summary: "Route the largest contracts onto a higher oversight cadence, independent of any specific issue.",
      steps: [
        "Confirm current oversight tier matches contract value",
        "Schedule a recurring program-review cadence",
        "Verify earned-value / milestone reporting is current",
        "Log the oversight assignment",
      ],
    },
    consolidation_sourcing: {
      name: "Category Consolidation — Strategic Sourcing Initiative",
      trigger: "Fragmented spend",
      summary: "Explore whether consolidating routine, fragmented category spend onto fewer suppliers could create pricing leverage.",
      steps: [
        "Confirm fragmentation isn't driven by legitimate specialization needs",
        "Shortlist candidate suppliers for a consolidated vehicle",
        "Model a volume-based pricing scenario (directional, not a savings commitment)",
        "Brief the category manager / strategic sourcing lead",
        "Decide: pursue a consolidated vehicle or maintain current mix",
      ],
    },
    duplicate_dedup_audit: {
      name: "Possible Duplicate Purchase — Procurement Dedup Audit",
      trigger: "Possible duplicate",
      summary: "Check whether two similar, closely-timed awards to the same supplier reflect one need bought twice.",
      steps: [
        "Compare both awards' stated requirements side by side",
        "Confirm with the requesting office whether this was one need or two",
        "If duplicate: document lessons learned for future consolidated buys",
        "If not duplicate: document the distinguishing need",
      ],
    },
    general_review: {
      name: "General Review",
      trigger: "Marked for review",
      summary: "A generic starting workflow for anything flagged without a more specific signal.",
      steps: [
        "Confirm what prompted the flag",
        "Gather supporting documentation",
        "Decide on a course of action",
        "Document the outcome",
      ],
    },
  };
  // Priority order when an item carries more than one reason -- the most
  // consequential/negative signal picks the suggested playbook.
  const REASON_PLAYBOOK_PRIORITY = [
    ["deobligation_flag", "deobligation_mitigation"],
    ["rapid_decline", "rapid_decline_continuity"],
    ["cost_growth", "cost_growth_review"],
    ["rapid_growth", "rapid_growth_review"],
    ["high_concentration", "concentration_diversification"],
    ["high_value", "high_value_oversight"],
  ];
  const NEGATIVE_PLAYBOOK_IDS = new Set(["deobligation_mitigation", "rapid_decline_continuity", "cost_growth_review"]);
  function pickPlaybookForReasons(reasons) {
    const types = new Set((reasons || []).map(r => r.type));
    for (const [type, playbookId] of REASON_PLAYBOOK_PRIORITY) {
      if (types.has(type)) return playbookId;
    }
    return null;
  }

  // ---------------- Action Center: local-only workflow state ----------------
  // Same storage pattern as the review flags above -- a plain object in
  // localStorage, never sent anywhere. Keyed the same way review-flag keys
  // are (supplier name, "award:<id>", "consolidation:<category>",
  // "duplicate:<pair_id>") so both features identify the same entity
  // consistently without colliding (separate storage keys).
  const WORKFLOW_KEY = "nasa_dashboard_workflows_v1";
  function getWorkflows() {
    try { return JSON.parse(localStorage.getItem(WORKFLOW_KEY) || "{}"); }
    catch (e) { return {}; }
  }
  function saveWorkflows(all) { localStorage.setItem(WORKFLOW_KEY, JSON.stringify(all)); }
  function getWorkflow(entityKey) { return getWorkflows()[entityKey] || null; }
  function startWorkflow(entityKey, meta) {
    const all = getWorkflows();
    const now = new Date().toISOString();
    all[entityKey] = Object.assign({ stepIndex: 0, status: "in_progress", notes: "", startedAt: now, updatedAt: now }, meta);
    saveWorkflows(all);
    return all[entityKey];
  }
  function advanceWorkflowStep(entityKey, delta) {
    const all = getWorkflows();
    const wf = all[entityKey];
    if (!wf) return null;
    const steps = PLAYBOOKS[wf.playbookId].steps;
    wf.stepIndex = Math.max(0, Math.min(steps.length - 1, wf.stepIndex + delta));
    if (wf.status !== "complete") wf.status = "in_progress";
    wf.updatedAt = new Date().toISOString();
    saveWorkflows(all);
    return wf;
  }
  function completeWorkflow(entityKey) {
    const all = getWorkflows();
    const wf = all[entityKey];
    if (!wf) return null;
    wf.status = "complete";
    wf.stepIndex = PLAYBOOKS[wf.playbookId].steps.length - 1;
    wf.updatedAt = new Date().toISOString();
    saveWorkflows(all);
    return wf;
  }
  function resetWorkflow(entityKey) {
    const all = getWorkflows();
    delete all[entityKey];
    saveWorkflows(all);
  }
  function setWorkflowNotes(entityKey, notes) {
    const all = getWorkflows();
    if (!all[entityKey]) return;
    all[entityKey].notes = notes;
    all[entityKey].updatedAt = new Date().toISOString();
    saveWorkflows(all);
  }

  // Full labeled stepper (used in the workflow modal and the Playbook
  // Library reference cards).
  function buildStepper(steps, currentIndex, status) {
    const wrap = el("div", { class: "wf-stepper" });
    steps.forEach((label, i) => {
      const state = status === "complete" || i < currentIndex ? "done" : i === currentIndex ? "active" : "pending";
      wrap.appendChild(el("div", { class: "wf-step " + state }, [
        el("div", { class: "wf-step-dot" }, [state === "done" ? "✓" : String(i + 1)]),
        el("div", { class: "wf-step-label" }, [label]),
      ]));
      if (i < steps.length - 1) {
        wrap.appendChild(el("div", { class: "wf-step-connector" + ((i < currentIndex || status === "complete") ? " done" : "") }));
      }
    });
    return wrap;
  }
  // Compact dots-only stepper for cards/lists.
  function buildMiniStepper(stepCount, currentIndex, status) {
    const wrap = el("div", { class: "wf-mini-stepper" });
    for (let i = 0; i < stepCount; i++) {
      const state = status === "complete" || i < currentIndex ? "done" : i === currentIndex ? "active" : "";
      wrap.appendChild(el("div", { class: "wf-mini-dot" + (state ? " " + state : "") }));
    }
    return wrap;
  }
  function workflowStatusBadge(status) {
    const label = status === "complete" ? "Complete" : status === "in_progress" ? "In progress" : "Not started";
    return el("span", { class: "wf-status-badge " + status }, [label]);
  }

  let workflowModalEntityKey = null;
  function openWorkflowModal(entityKey, meta) {
    workflowModalEntityKey = entityKey;
    let wf = getWorkflow(entityKey);
    if (!wf) wf = startWorkflow(entityKey, meta);
    renderWorkflowModal();
    document.getElementById("wf-modal-overlay").classList.add("open");
  }
  function renderWorkflowModal() {
    const wf = getWorkflow(workflowModalEntityKey);
    if (!wf) { document.getElementById("wf-modal-overlay").classList.remove("open"); return; }
    const playbook = PLAYBOOKS[wf.playbookId];
    document.getElementById("wf-modal-title").textContent = playbook.name;
    const meta = document.getElementById("wf-modal-meta");
    meta.innerHTML = "";
    meta.appendChild(el("span", {}, [wf.label + " · "]));
    meta.appendChild(workflowStatusBadge(wf.status));

    const stepperWrap = document.getElementById("wf-modal-stepper");
    stepperWrap.innerHTML = "";
    stepperWrap.appendChild(buildStepper(playbook.steps, wf.stepIndex, wf.status));

    document.getElementById("wf-modal-current-step").textContent =
      `Step ${wf.stepIndex + 1} of ${playbook.steps.length}: ${playbook.steps[wf.stepIndex]}`;

    const notesArea = document.getElementById("wf-modal-notes");
    notesArea.value = wf.notes || "";

    const actions = document.getElementById("wf-modal-actions");
    actions.innerHTML = "";
    const prevBtn = el("button", { class: "secondary" }, ["◀ Previous step"]);
    prevBtn.disabled = wf.stepIndex === 0;
    prevBtn.addEventListener("click", () => { advanceWorkflowStep(workflowModalEntityKey, -1); renderWorkflowModal(); refreshActionCenterIfOpen(); });
    const nextBtn = el("button", {}, ["Next step ▶"]);
    nextBtn.disabled = wf.stepIndex >= playbook.steps.length - 1;
    nextBtn.addEventListener("click", () => { advanceWorkflowStep(workflowModalEntityKey, 1); renderWorkflowModal(); refreshActionCenterIfOpen(); });
    const completeBtn = el("button", { class: "primary" }, ["✓ Mark complete"]);
    completeBtn.disabled = wf.status === "complete";
    completeBtn.addEventListener("click", () => {
      completeWorkflow(workflowModalEntityKey);
      showToast("Workflow marked complete (saved locally)");
      renderWorkflowModal();
      refreshActionCenterIfOpen();
    });
    const resetBtn = el("button", { class: "secondary" }, ["↺ Reset workflow"]);
    resetBtn.addEventListener("click", () => {
      resetWorkflow(workflowModalEntityKey);
      showToast("Workflow reset (removed from Active Workflows)");
      document.getElementById("wf-modal-overlay").classList.remove("open");
      refreshActionCenterIfOpen();
    });
    actions.appendChild(prevBtn);
    actions.appendChild(nextBtn);
    actions.appendChild(completeBtn);
    actions.appendChild(resetBtn);
  }
  function setupWorkflowModal() {
    const overlay = document.getElementById("wf-modal-overlay");
    if (!overlay) return;
    const closeModal = () => overlay.classList.remove("open");
    document.getElementById("wf-modal-close").addEventListener("click", closeModal);
    overlay.addEventListener("click", ev => { if (ev.target === overlay) closeModal(); });
    document.addEventListener("keydown", ev => {
      if (ev.key === "Escape" && overlay.classList.contains("open")) closeModal();
    });
    let notesDebounce = null;
    document.getElementById("wf-modal-notes").addEventListener("input", ev => {
      clearTimeout(notesDebounce);
      const val = ev.target.value;
      notesDebounce = setTimeout(() => {
        if (workflowModalEntityKey) { setWorkflowNotes(workflowModalEntityKey, val); refreshActionCenterIfOpen(); }
      }, 400);
    });
  }
  // Set by renderActionCenter() once the tab exists, so modal actions taken
  // from a *different* tab's card (e.g. clicking "Take Action" on a
  // Standout Supplier card) still refresh the Action Center in the
  // background if it's already been drawn once.
  let refreshActionCenterIfOpen = () => {};

  // Builds a "Take Action" button for a card, wired to open the workflow
  // modal for the given entity/playbook. Returns null if no reasons map to
  // a known playbook (nothing forced -- most cards simply won't offer one).
  function takeActionButton(entityKey, playbookId, label) {
    if (!playbookId || !PLAYBOOKS[playbookId]) return null;
    const wf = getWorkflow(entityKey);
    const btn = el("button", { class: "wf-take-action" + (wf ? " secondary" : " primary") },
      [wf ? `▶ Continue workflow (${wf.status === "complete" ? "complete" : `step ${wf.stepIndex + 1}/${PLAYBOOKS[wf.playbookId].steps.length}`})` : `▶ Take action: ${PLAYBOOKS[playbookId].name}`]);
    btn.addEventListener("click", () => openWorkflowModal(entityKey, { playbookId, label }));
    return btn;
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
  // Plotly sizes a chart when it is created. Charts on inactive tabs are
  // created inside a display:none panel, where the container measures zero,
  // so Plotly falls back to its built-in 700px default and keeps it -- which
  // silently overflows any column narrower than that (a tablet-width
  // two-column grid gives each panel ~440px). Re-measuring on tab show is
  // the actual fix; `window.resize` alone was not enough, because it fires
  // before the panel has been laid out.
  function resizePlotsIn(root) {
    if (!root || typeof Plotly === "undefined" || !Plotly.Plots) return;
    requestAnimationFrame(() => {
      root.querySelectorAll(".js-plotly-plot").forEach(gd => {
        try { Plotly.Plots.resize(gd); } catch (e) { /* chart not initialised yet */ }
      });
    });
  }

  function setupTabs() {
    const buttons = document.querySelectorAll("nav.tabs button");
    buttons.forEach((btn, i) => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const panel = document.getElementById("tab-" + btn.dataset.tab);
        panel.classList.add("active");
        resizePlotsIn(panel);
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

  // Which drill-down columns name something a workflow can attach to.
  // Shared by the table (which rows are selectable) and the workflow starter
  // (what the "Apply to" list contains) so the two can never disagree.
  function kpiTargetIndices(spec) {
    const cols = (spec.columns || []).map(c => String(c).toLowerCase());
    return {
      supIdx: cols.findIndex(c => c.includes("supplier")),
      awdIdx: cols.findIndex(c => c.includes("award")),
    };
  }

  // Installed by renderKpiModalWorkflowStarter, called by the table's row
  // clicks. The table is built first, but only ever clicked afterwards, so
  // the ordering is safe.
  let kpiModalApplyTarget = null;

  function highlightKpiModalRows(key) {
    const wrap = document.getElementById("kpi-modal-table-wrap");
    if (!wrap) return null;
    let first = null;
    wrap.querySelectorAll("tbody tr").forEach(tr => {
      const hit = !!key && (tr.dataset.supKey === key || tr.dataset.awdKey === key);
      tr.classList.toggle("kpi-row-selected", hit);
      if (hit && !first) first = tr;
    });
    return first;
  }

  function openKpiModal(spec) {
    kpiModalApplyTarget = null;
    document.getElementById("kpi-modal-title").textContent = spec.title;
    document.getElementById("kpi-modal-formula").textContent = spec.formula;
    const noteEl = document.getElementById("kpi-modal-note");
    noteEl.textContent = spec.note || "";
    noteEl.style.display = spec.note ? "" : "none";

    const wrap = document.getElementById("kpi-modal-table-wrap");
    wrap.innerHTML = "";
    if (spec.rows && spec.rows.length) {
      const { supIdx, awdIdx } = kpiTargetIndices(spec);
      const tbl = el("table", { class: "data-table" });
      tbl.appendChild(el("thead", {}, [el("tr", {}, spec.columns.map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      let anyPickable = false;
      spec.rows.forEach(r => {
        const tr = el("tr", {}, r.map(c => el("td", {}, [c])));
        const sup = supIdx >= 0 && r[supIdx] ? String(r[supIdx]) : null;
        const awd = awdIdx >= 0 && r[awdIdx] ? String(r[awdIdx]) : null;
        if (sup || awd) {
          anyPickable = true;
          tr.classList.add("kpi-row-pick");
          if (sup) { tr.dataset.supKey = sup; tr.children[supIdx].classList.add("kpi-pick-cell"); }
          if (awd) { tr.dataset.awdKey = "award:" + awd; tr.children[awdIdx].classList.add("kpi-pick-cell"); }
          tr.addEventListener("click", ev => {
            // A row usually names both a supplier and an award. Clicking
            // either of those two cells picks that one specifically;
            // clicking anywhere else falls back to the supplier, which is
            // what most playbooks act on.
            const td = ev.target && ev.target.closest ? ev.target.closest("td") : null;
            const idx = td ? Array.prototype.indexOf.call(tr.children, td) : -1;
            let pick;
            if (idx === awdIdx && awd) pick = { key: "award:" + awd, label: awd, kind: "Award" };
            else if (idx === supIdx && sup) pick = { key: sup, label: sup, kind: "Supplier" };
            else if (sup) pick = { key: sup, label: sup, kind: "Supplier" };
            else pick = { key: "award:" + awd, label: awd, kind: "Award" };
            highlightKpiModalRows(pick.key);
            if (kpiModalApplyTarget) kpiModalApplyTarget(pick);
          });
        }
        tbody.appendChild(tr);
      });
      if (anyPickable) {
        wrap.appendChild(el("div", { class: "kpi-modal-pick-hint" }, [
          "Click a row to apply a workflow to it -- click the supplier or the award cell to pick that one specifically.",
        ]));
      }
      tbl.appendChild(tbody);
      wrap.appendChild(tbl);
    } else if (!spec.rows) {
      // no drill-down list available for this KPI -- formula-only explanation.
    } else {
      wrap.appendChild(el("div", { class: "small-note" }, ["No contributing rows to show for this dataset."]));
    }
    renderKpiModalWorkflowStarter(spec);
    document.getElementById("kpi-modal-overlay").classList.add("open");
  }

  // Any drill-down can become the starting point for a workflow: pick the
  // playbook, and pick what it attaches to -- the metric itself, or one of
  // the specific suppliers/awards listed in this popup's table. Without the
  // target picker you could only ever track "the KPI", which is rarely the
  // thing someone actually follows up on.
  function renderKpiModalWorkflowStarter(spec) {
    const host = document.getElementById("kpi-modal-workflow");
    if (!host) return;
    host.innerHTML = "";

    // Candidate targets pulled out of the drill-down table. Supplier and
    // award columns are the only ones a workflow can meaningfully attach to.
    const targets = [{ key: "kpi:" + spec.title, label: spec.title, kind: "This metric" }];
    const { supIdx, awdIdx } = kpiTargetIndices(spec);
    const seen = new Set();
    (spec.rows || []).forEach(r => {
      if (supIdx >= 0 && r[supIdx]) {
        const v = String(r[supIdx]);
        if (!seen.has("s" + v)) { seen.add("s" + v); targets.push({ key: v, label: v, kind: "Supplier" }); }
      }
      if (awdIdx >= 0 && r[awdIdx]) {
        const v = String(r[awdIdx]);
        if (!seen.has("a" + v)) { seen.add("a" + v); targets.push({ key: "award:" + v, label: v, kind: "Award" }); }
      }
    });

    const details = el("div", { class: "sc-details" });
    const toggle = el("button", { class: "sc-details-toggle" }, ["▶ Start a workflow from this"]);
    toggle.addEventListener("click", () => {
      const open = details.classList.toggle("expanded");
      toggle.textContent = open ? "▾ Start a workflow from this" : "▶ Start a workflow from this";
    });

    const pbSel = el("select", { id: "kpi-modal-playbook" },
      Object.entries(PLAYBOOKS).map(([id, pb]) => el("option", { value: id }, [pb.name])));
    const tgSel = el("select", { id: "kpi-modal-target" },
      targets.slice(0, 60).map(t => el("option", { value: t.key }, [`${t.kind}: ${t.label}`])));

    // Selecting a row in the table above drives this dropdown. The list is
    // capped at 60 options, so a click further down the table may name
    // something that isn't in it yet -- add it rather than silently
    // selecting nothing.
    kpiModalApplyTarget = pick => {
      let opt = Array.prototype.find.call(tgSel.options, o => o.value === pick.key);
      if (!opt) {
        opt = el("option", { value: pick.key }, [`${pick.kind}: ${pick.label}`]);
        tgSel.appendChild(opt);
        targets.push(pick);
      }
      tgSel.value = pick.key;
      if (!details.classList.contains("expanded")) {
        details.classList.add("expanded");
        toggle.textContent = "▾ Start a workflow from this";
      }
    };
    // ...and the reverse, so the two views never disagree about what is
    // selected: choosing from the dropdown highlights the matching rows.
    tgSel.addEventListener("change", () => {
      const first = highlightKpiModalRows(tgSel.value);
      if (first) first.scrollIntoView({ block: "nearest" });
    });

    const startBtn = el("button", { class: "primary" }, ["Start workflow"]);
    startBtn.addEventListener("click", () => {
      const key = tgSel.value;
      const chosen = targets.find(t => t.key === key) || targets[0];
      document.getElementById("kpi-modal-overlay").classList.remove("open");
      openWorkflowModal(key, { playbookId: pbSel.value, label: chosen.label });
      refreshActionCenterIfOpen();
    });

    details.appendChild(el("div", { class: "controls", style: "margin-bottom:6px;" }, [
      el("div", { style: "min-width:240px;" }, [el("label", {}, ["Playbook"]), pbSel]),
      el("div", { style: "min-width:240px;" }, [el("label", {}, ["Apply to"]), tgSel]),
      el("div", { style: "align-self:flex-end;" }, [startBtn]),
    ]));
    details.appendChild(el("div", { class: "small-note" }, [
      "Workflow state is saved in this browser only -- see the Action Center's banner.",
    ]));
    host.appendChild(toggle);
    host.appendChild(details);
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
    kpiModalApplyTarget = null;
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
    // This modal is shared with the KPI drill-downs, so its workflow starter
    // has to be re-rendered for the finding -- otherwise the previous
    // drill-down's target would still be sitting there. A finding that
    // resolves to a supplier offers that supplier as a target; one that
    // doesn't can still be tracked as the finding itself.
    renderKpiModalWorkflowStarter({
      title: f.title,
      columns: target && target.type === "supplier" ? ["Supplier"] : [],
      rows: target && target.type === "supplier" ? [[target.name]] : [],
    });
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
  // The plain keyword-search link this used to build isn't a real deep link
  // -- usaspending.gov's search page doesn't read `?keyword=` from the URL,
  // so it opened a blank generic search screen. Its own award-detail API
  // returns two ids built exactly for direct linking: generated_unique_award_id
  // for /award/<id> and recipient.recipient_hash for /recipient/<hash>/latest
  // (see _standout_by_range / _supplier_detail / _award_rows in
  // data_prep.py, and tools/backfill_recipient_hash.py for how the latter
  // was backfilled). Both ids are only available where award-detail
  // enrichment ran, so a plain keyword search stays as the fallback for a
  // dataset ingested without it (e.g. a raw repo CSV).
  function usaspendingSearchUrl(supplier) {
    return "https://www.usaspending.gov/search/?keyword=" + encodeURIComponent(supplier);
  }
  function usaspendingAwardUrl(generatedAwardId, fallbackAwardId) {
    return generatedAwardId
      ? "https://www.usaspending.gov/award/" + encodeURIComponent(generatedAwardId)
      : usaspendingSearchUrl(fallbackAwardId);
  }
  function usaspendingRecipientUrl(recipientHash, fallbackSupplierName) {
    return recipientHash
      ? "https://www.usaspending.gov/recipient/" + encodeURIComponent(recipientHash) + "/latest"
      : usaspendingSearchUrl(fallbackSupplierName);
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

      // A real <a href target="_blank"> rather than a button that calls
      // window.open() -- Edge (and other browsers) can silently swallow a
      // script-triggered popup even from a genuine click handler, especially
      // when the page itself was opened from a local file. A direct link
      // click is ordinary navigation, not a popup, so it isn't blockable.
      const viewBtn = el("a", {
        class: "primary", href: usaspendingRecipientUrl(s.recipient_hash, s.supplier),
        target: "_blank", rel: "noopener noreferrer",
        title: s.recipient_hash
          ? "Opens this supplier's official recipient profile on usaspending.gov in a new tab."
          : "Opens the official public search on usaspending.gov in a new tab (no direct recipient link available for this dataset).",
      }, ["View on USAspending.gov ↗"]);

      const exportBtn = el("button", {}, ["Export supplier CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.normalized_supplier === s.supplier);
        const safeName = s.supplier.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_supplier_${safeName}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for ${s.supplier}`);
      });

      const actionBtn = takeActionButton(s.supplier, pickPlaybookForReasons(s.reasons), s.supplier);
      const card = el("div", { class: "standout-card" }, [
        el("div", { class: "sc-head" }, [
          el("div", { class: "sc-name" }, [s.supplier, newBadge(s.is_new)].filter(Boolean)),
          el("div", { class: "sc-amount" }, [fmtMoney(s.net_obligations)]),
        ]),
        el("div", { class: "sc-sub" }, [`${fmtNum(s.transaction_count)} transactions · ${fmtNum(s.unique_awards)} awards · ${s.concentration_pct.toFixed(1)}% of total`]),
        tagRow,
        detailsBtn,
        detailsWrap,
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn].concat(actionBtn ? [actionBtn] : [])),
      ]);
      container.appendChild(card);
    });
  }


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

      // Real <a> for the same Edge popup-blocking reason as the supplier
      // card's view button above.
      const viewBtn = el("a", {
        class: "primary", href: usaspendingAwardUrl(a.generated_award_id, a.award_id),
        target: "_blank", rel: "noopener noreferrer",
        title: a.generated_award_id
          ? "Opens this award's official profile page on usaspending.gov in a new tab."
          : "Opens the official public search on usaspending.gov in a new tab (no direct award link available for this dataset).",
      }, ["View award on USAspending.gov ↗"]);

      const exportBtn = el("button", {}, ["Export contract CSV"]);
      exportBtn.addEventListener("click", () => {
        const rows = DATA.explorer_rows.filter(r => r.award_id_piid === a.award_id);
        const safeId = a.award_id.replace(/[^a-z0-9]+/gi, "_").toLowerCase().slice(0, 60);
        downloadCsv(`nasa_award_${safeId}.csv`, rowsToCsv(rows));
        showToast(`Exported ${fmtNum(rows.length)} row(s) for award ${a.award_id}`);
      });
      const awardActionBtn = takeActionButton(key, pickPlaybookForReasons(a.reasons), `${a.supplier} — ${a.award_id}`);

      const card = el("div", { class: "standout-card award-card", "data-award-id": a.award_id }, [
        el("div", { class: "award-head-row" }, [
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
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn].concat(awardActionBtn ? [awardActionBtn] : [])),
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
      const actionBtn = takeActionButton(key, "consolidation_sourcing", c.category);

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
        el("div", { class: "sc-actions" }, [viewBtn, exportBtn, flagBtn, actionBtn]),
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
      const actionBtn = takeActionButton(key, "duplicate_dedup_audit", `${d.supplier} (${d.award_id_a} / ${d.award_id_b})`);

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
        el("div", { class: "sc-actions" }, [exportBtn, flagBtn, actionBtn]),
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
      ["supplier-kpis", "chart-supplier-annual", "chart-supplier-category", "supplier-variants", "supplier-evidence", "supplier-offices", "supplier-flags", "supplier-headline", "supplier-action-area"]
        .forEach(id => { const e = document.getElementById(id); e.innerHTML = ""; });
      if (!d) return;

      renderSupplierActionArea(name, fromFY, toFY);

      const headline = document.getElementById("supplier-headline");
      headline.appendChild(el("h3", { style: "margin:0; font-size:17px; color:var(--navy); text-transform:none; letter-spacing:0;" }, [name]));

      const inRange = fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY);
      const isFullRange = fromFY == null && toFY == null;

      // KPI tiles follow the header's Timeframe range. Net, gross,
      // deobligations and transaction count are exact sums over the
      // selected years. Unique Awards is not: an award running across
      // three selected years is counted once per year, so a multi-year
      // range shows it as an upper bound rather than a distinct count.
      const yearsInRange = d.annual.filter(r => inRange(r.fiscal_year));
      const sum = key => yearsInRange.reduce((s, r) => s + (r[key] || 0), 0);
      const scoped = isFullRange ? {
        net: d.total_net_obligations, gross: d.gross_positive_obligations,
        deob: d.deobligations, txns: d.transaction_count,
        awards: d.unique_awards, awardsExact: true,
      } : {
        net: sum("net_obligations"), gross: sum("gross_positive_obligations"),
        deob: sum("deobligations"), txns: sum("transaction_count"),
        awards: sum("unique_awards"), awardsExact: yearsInRange.length <= 1,
      };
      // Share is recomputed against the same range's agency-wide total, so
      // it stays a true share rather than a range numerator over an
      // all-time denominator.
      const agencyNet = isFullRange
        ? A.totals.net_obligations
        : A.annual.filter(r => inRange(r.fiscal_year)).reduce((s, r) => s + r.net_obligations, 0);

      const rangeLabel = isFullRange ? "" : yearsInRange.length === 1
        ? `FY${yearsInRange[0].fiscal_year}`
        : yearsInRange.length ? `FY${yearsInRange[0].fiscal_year}–FY${yearsInRange[yearsInRange.length - 1].fiscal_year}` : "";
      const scopeNote = document.getElementById("supplier-scope-note");
      if (scopeNote) {
        scopeNote.style.display = isFullRange ? "none" : "";
        scopeNote.textContent = isFullRange ? "" :
          `Showing ${rangeLabel}. Net, gross, deobligations, transactions and share are exact for that range.`
          + (scoped.awardsExact ? "" : " Unique Awards is summed per year, so an award spanning several of the selected years is counted once per year -- treat it as an upper bound.");
      }

      const kpis = document.getElementById("supplier-kpis");
      kpis.appendChild(kpiTile("Total Net Obligations", fmtMoney(scoped.net), scoped.net < 0));
      kpis.appendChild(kpiTile("Gross Positive", fmtMoney(scoped.gross)));
      kpis.appendChild(kpiTile("Deobligations", fmtMoney(scoped.deob)));
      kpis.appendChild(kpiTile("Transactions", fmtNum(scoped.txns)));
      kpis.appendChild(kpiTile((scoped.awardsExact ? "" : "≤ ") + "Unique Awards", fmtNum(scoped.awards)));
      kpis.appendChild(kpiTile("Share of Total Obligations", fmtPct(agencyNet ? scoped.net / agencyNet : 0)));
      const annualColor = isFullRange ? BLUE : d.annual.map(r => inRange(r.fiscal_year) ? BLUE : "rgba(148,163,184,0.35)");
      Plotly.newPlot("chart-supplier-annual", [{
        x: d.annual.map(r => "FY" + r.fiscal_year), y: d.annual.map(r => r.net_obligations), type: "bar", marker: { color: annualColor },
      }], darkLayout({ margin: { t: 10, r: 10, l: 55, b: 40 }, xaxis: darkAxis({}), yaxis: darkAxis({ tickformat: "~s" }) }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });

      // Many suppliers are effectively single-category, which rendered as
      // "100%" plus an unreadable hairline (Caltech: 0.000277%). Roll
      // everything under 1% into one "Other categories" slice and say how
      // many were folded in, so the chart stays legible without hiding that
      // the long tail exists.
      const MIX_MIN_SHARE = 0.01;
      const mix = d.category_mix.map(r => ({ category: r.category, value: Math.max(r.net_obligations, 0) }));
      const mixTotal = mix.reduce((s, r) => s + r.value, 0);
      const major = mix.filter(r => mixTotal > 0 && r.value / mixTotal >= MIX_MIN_SHARE);
      const minor = mix.filter(r => !(mixTotal > 0 && r.value / mixTotal >= MIX_MIN_SHARE) && r.value > 0);
      const mixSlices = major.slice();
      if (minor.length) {
        mixSlices.push({
          category: `Other categories (${fmtNum(minor.length)})`,
          value: minor.reduce((s, r) => s + r.value, 0),
        });
      }
      Plotly.newPlot("chart-supplier-category", [{
        labels: mixSlices.map(r => r.category), values: mixSlices.map(r => r.value), type: "pie", hole: 0.45,
        marker: { line: { color: "#ffffff", width: 2 } }, textfont: { color: "#0f1e33" },
        texttemplate: "%{percent:.1%}", hovertemplate: "%{label}<br>%{value:$,.0f} (%{percent:.2%})<extra></extra>",
      }], darkLayout({ margin: { t: 10, r: 10, l: 10, b: 10 }, showlegend: true, legend: { font: { color: CHART_MUTED } } }), { displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false });
      const mixNote = document.getElementById("supplier-mix-note");
      if (mixNote) {
        mixNote.textContent = minor.length
          ? `${fmtNum(minor.length)} categor${minor.length === 1 ? "y" : "ies"} under 1% grouped into "Other categories". Hover a slice for its exact share.`
          : "";
        mixNote.style.display = minor.length ? "" : "none";
      }

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
      const inRangeCat = fy => (fromFY == null || fy >= fromFY) && (toFY == null || fy <= toFY);
      const isFullRangeCat = fromFY == null && toFY == null;
      const catYears = d.annual.filter(r => inRangeCat(r.fiscal_year));
      const catSum = key => catYears.reduce((s, r) => s + (r[key] || 0), 0);
      const totalNet = isFullRangeCat
        ? d.annual.reduce((s, r) => s + r.net_obligations, 0)
        : catSum("net_obligations");
      // Unique suppliers, like unique awards on the Supplier tab, is a
      // distinct count that does not sum across years -- exact for a single
      // year, an upper bound for a range.
      const suppliersExact = isFullRangeCat || catYears.length <= 1;
      const uniqueSuppliers = isFullRangeCat ? d.unique_suppliers : catSum("unique_suppliers");
      const catRangeLabel = isFullRangeCat ? "" : catYears.length === 1
        ? `FY${catYears[0].fiscal_year}`
        : catYears.length ? `FY${catYears[0].fiscal_year}–FY${catYears[catYears.length - 1].fiscal_year}` : "";
      const catScopeNote = document.getElementById("category-scope-note");
      if (catScopeNote) {
        catScopeNote.style.display = isFullRangeCat ? "none" : "";
        catScopeNote.textContent = isFullRangeCat ? "" :
          `Showing ${catRangeLabel}. Net Obligations is exact for that range.`
          + (suppliersExact ? "" : " Unique Suppliers is summed per year, so a supplier active in several of the selected years is counted once per year -- treat it as an upper bound.")
          + " Concentration (HHI) and Tail Spend Share stay all-time: both are ratios over the whole supplier distribution, and a range's real figure can't be derived by summing yearly values.";
      }
      const leadingRows = () => d.leading_suppliers.map(r => [r.supplier, fmtMoney(r.net_obligations)]);
      const leadingNote = `Showing the top ${d.leading_suppliers.length} of ${fmtNum(d.unique_suppliers)} suppliers active in this category (all-time), by net obligations.`;

      kpis.appendChild(kpiTile("Net Obligations", fmtMoney(totalNet), totalNet < 0, () => ({
        title: `Net Obligations -- ${name}`,
        formula: `Sum of signed obligation amounts for every transaction classified into "${name}"`
          + (isFullRangeCat ? ", across all fiscal years in this dataset." : `, across ${catRangeLabel}.`),
        note: leadingNote,
        columns: ["Supplier", "Net Obligations"],
        rows: leadingRows(),
      })));
      kpis.appendChild(kpiTile((suppliersExact ? "" : "≤ ") + "Unique Suppliers", fmtNum(uniqueSuppliers), false, () => ({
        title: `Unique Suppliers -- ${name}`,
        formula: `Count of distinct normalized suppliers with at least one transaction classified into "${name}"`
          + (suppliersExact ? "." : `, summed across ${catRangeLabel} -- a supplier active in more than one of those years is counted once per year, so this is an upper bound on the distinct count.`),
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

  // ---------------- Tab: Misuse Protection ----------------
  // Server-side signal from _bid_competition_review() in data_prep.py:
  // suppliers whose awards below a threshold (default $350,000, editable
  // here -- this stays purely a client-side re-filter of DATA.awards_summary
  // when the backend precomputed threshold doesn't match, see below) skew
  // toward single-offer or non-competed procurements. Needs award-detail
  // fields (number_of_offers_received, extent_competed_description) that
  // only exist when that per-award API call actually ran -- large
  // multi-year pulls in this project skip it for speed, so this tab is
  // often unavailable there and says so rather than showing an empty or
  // misleadingly-confident table.
  function renderMisuseProtectionTab() {
    const review = DATA.bid_competition_review || { available: false, suppliers: [] };
    const unavailableNote = document.getElementById("misuse-unavailable-note");
    const content = document.getElementById("misuse-content");
    if (!review.available) {
      content.style.display = "none";
      unavailableNote.style.display = "";
      unavailableNote.innerHTML = "";
      unavailableNote.appendChild(el("div", { class: "small-note" }, [
        `Award-detail data (number of offers received, extent competed) isn't available for this build`
        + (review.awards_total ? ` -- ${fmtNum(review.awards_total)} awards were found, but none had that data fetched.` : ".")
        + " That per-award lookup is skipped on large multi-year pulls for speed. It's included on the small-sample build (see the CLI's \"sample\" command) and on any refresh run without --skip-award-details.",
      ]));
      return;
    }
    content.style.display = "";
    unavailableNote.style.display = "none";

    const thresholdInput = document.getElementById("misuse-threshold");
    if (!thresholdInput.dataset.wired) {
      thresholdInput.dataset.wired = "1";
      thresholdInput.value = review.threshold;
      thresholdInput.max = review.threshold;
      let debounce = null;
      thresholdInput.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(drawMisuseTable, 300);
      });
    }

    const kpis = document.getElementById("misuse-kpis");
    kpis.innerHTML = "";
    kpis.appendChild(kpiTile("Awards With Bid Data", fmtNum(review.awards_with_detail)));
    kpis.appendChild(kpiTile("...of Total Awards Found", fmtNum(review.awards_total)));
    kpis.appendChild(kpiTile("Suppliers Worth a Look", fmtNum(review.suppliers.length)));

    renderSetAsidePanel();
    drawMisuseTable();

    // Awards whose PSC identifies a proprietary software license are kept
    // out of the ranking (a single offer for a product only one vendor
    // sells is the expected outcome, not a signal) -- but shown here, so
    // the screen never silently hides a supplier from a reviewer.
    function renderSetAsidePanel() {
      const wrap = document.getElementById("misuse-set-aside");
      if (!wrap) return;
      wrap.innerHTML = "";
      const sa = review.set_aside || { supplier_count: 0, award_count: 0, suppliers: [] };
      const ex = review.excluded_psc || { label: "", reasons: [] };
      if (!sa.award_count) {
        wrap.appendChild(el("div", { class: "small-note" }, ["No awards were set aside for this dataset."]));
        return;
      }
      const summary = el("div", { class: "small-note", style: "margin-bottom:8px;" }, [
        `${fmtNum(sa.award_count)} single-bid/non-competed award(s) across ${fmtNum(sa.supplier_count)} supplier(s), worth ${fmtMoney(sa.value || 0)}, are excluded from the ranking above as `,
        el("strong", {}, [ex.label || "excluded PSCs"]),
        ". A single offer for a named proprietary product is the expected outcome, not a competition-avoidance signal. They are listed here so nothing is hidden.",
      ]);
      wrap.appendChild(summary);
      if ((ex.reasons || []).length) {
        wrap.appendChild(el("div", { class: "small-note", style: "margin-bottom:8px;" }, [
          "Set-aside PSC codes: " + ex.reasons.map(r => `${r.code} (${r.why})`).join(" · "),
        ]));
      }
      const tbl = el("table", { class: "data-table" }, [
        el("thead", {}, [el("tr", {}, ["Supplier", "Set-Aside Awards", "Value"].map(h => el("th", {}, [h])))]),
        el("tbody", {}, sa.suppliers.map(s => el("tr", {}, [
          el("td", {}, [s.supplier]),
          el("td", {}, [fmtNum(s.award_count)]),
          el("td", {}, [fmtMoney(s.value)]),
        ]))),
      ]);
      wrap.appendChild(el("div", { class: "table-wrap", style: "max-height:260px;" }, [tbl]));
    }

    function drawMisuseTable() {
      // Every sub-threshold award (competed and not) is embedded per
      // supplier, so lowering the threshold recomputes both the numerator
      // and the denominator exactly -- no server round-trip, no guessing
      // from a partial sample. Raising it above the payload's own threshold
      // isn't possible (the input is capped), since awards above it were
      // never fetched.
      const threshold = Math.min(parseFloat(thresholdInput.value) || review.threshold, review.threshold);
      const tbl = document.getElementById("table-misuse-suppliers");
      tbl.innerHTML = "";
      const atDefault = threshold >= review.threshold;
      const filtered = review.suppliers
        .map(s => {
          if (atDefault) {
            return Object.assign({}, s, {
              matchingAwards: s.awards.filter(a => a.low_competition),
              shownSubThreshold: s.sub_threshold_award_count,
              shownLowComp: s.low_competition_award_count,
              shownShare: s.low_competition_share,
              shownValue: s.total_sub_threshold_value,
              approximate: false,
            });
          }
          const inRange = s.awards.filter(a => a.value < threshold);
          const lowComp = inRange.filter(a => a.low_competition);
          if (!lowComp.length) return null;
          return Object.assign({}, s, {
            matchingAwards: lowComp,
            shownSubThreshold: inRange.length,
            shownLowComp: lowComp.length,
            shownShare: lowComp.length / inRange.length,
            shownValue: inRange.reduce((sum, a) => sum + a.value, 0),
            // Only the largest N awards per supplier are embedded; if that
            // cap was hit, a lowered threshold may exclude awards we never
            // shipped, so the recomputed counts are a floor, not exact.
            approximate: s.awards_truncated,
          });
        })
        .filter(Boolean);
      if (!filtered.length) {
        tbl.appendChild(el("tbody", {}, [el("tr", {}, [el("td", { class: "small-note" }, [
          "No supplier's below-threshold awards are concentrated in single-offer/non-competed procurements at this threshold.",
        ])])]));
        return;
      }
      filtered.sort((a, b) => (b.shownShare - a.shownShare) || (b.shownSubThreshold - a.shownSubThreshold));
      tbl.appendChild(el("thead", {}, [el("tr", {}, [
        "Supplier", "Below-Threshold Awards", "Low-Competition Awards", "Concentration", "Below-Threshold Value", "Total Contracts (all values)",
      ].map(h => el("th", {}, [h])))]));
      const tbody = el("tbody");
      filtered.forEach(s => {
        const approxMark = s.approximate ? "≥" : "";
        const row = el("tr", { class: "jump-row" }, [
          el("td", {}, [s.supplier]),
          el("td", {}, [approxMark + fmtNum(s.shownSubThreshold)]),
          el("td", {}, [approxMark + fmtNum(s.shownLowComp)]),
          el("td", {}, [fmtPct(s.shownShare)]),
          el("td", {}, [fmtMoney(s.shownValue)]),
          el("td", {}, [fmtNum(s.total_award_count)]),
        ]);
        row.title = s.approximate
          ? "Click to see the flagged awards. Counts are a floor -- only this supplier's largest awards are embedded."
          : "Click to see the flagged awards";
        row.addEventListener("click", () => {
          const existing = row.nextElementSibling;
          if (existing && existing.classList.contains("misuse-detail-row")) { existing.remove(); return; }
          const shown = s.matchingAwards.slice(0, 25);
          const detail = el("tr", { class: "misuse-detail-row" }, [
            el("td", { colspan: "6" }, [
              el("div", { class: "table-wrap" }, [
                el("table", { class: "data-table" }, [
                  el("thead", {}, [el("tr", {}, ["Award", "Value", "Offers Received", "Extent Competed", "Set-Aside"].map(h => el("th", {}, [h])))]),
                  el("tbody", {}, shown.map(a => el("tr", {}, [
                    el("td", { class: "code-text" }, [a.award_id]),
                    el("td", {}, [fmtMoney(a.value)]),
                    el("td", {}, [a.num_offers == null ? "—" : fmtNum(a.num_offers)]),
                    el("td", {}, [a.extent_competed || "—"]),
                    el("td", {}, [a.set_aside || "—"]),
                  ]))),
                ]),
              ]),
              s.matchingAwards.length > shown.length
                ? el("div", { class: "small-note" }, [`Showing the ${shown.length} largest of ${fmtNum(s.matchingAwards.length)} flagged awards.`])
                : null,
            ].filter(Boolean)),
          ]);
          row.after(detail);
        });
        tbody.appendChild(row);
      });
      tbl.appendChild(tbody);
    }
  }

  // ---------------- Tab 6: Action Center ----------------
  // Reference library (static -- rendered once) plus two live sections:
  // Suggested Actions (flagged items with no workflow started yet, drawn
  // from the currently-selected Timeframe range) and Active Workflows
  // (everything with workflow state in localStorage, any range).
  function renderPlaybookLibrary() {
    const container = document.getElementById("playbook-library");
    if (!container || container.dataset.rendered) return;
    container.dataset.rendered = "1";
    Object.values(PLAYBOOKS).forEach(pb => {
      const card = el("div", { class: "panel" }, [
        el("h3", { style: "margin:0 0 4px 0; font-size:13.5px; color:var(--navy); text-transform:none; letter-spacing:0;" }, [pb.name]),
        el("div", { class: "small-note", style: "margin-bottom:4px;" }, [`Triggered by: ${pb.trigger}`]),
        el("div", { class: "small-note", style: "margin-bottom:6px;" }, [pb.summary]),
        buildStepper(pb.steps, -1, "not_started"),
      ]);
      container.appendChild(card);
    });
  }

  // Action state for one supplier, shown on the Supplier Analysis tab so the
  // question "is anyone already dealing with this vendor?" is answerable
  // without going to the Action Center. Three states: a workflow is running
  // (continue it), one is suggested by a standout signal (start it), or
  // nothing is flagged (say so, with the reasoning one click away).
  function renderSupplierActionArea(supplier, fromFY, toFY) {
    const wrap = document.getElementById("supplier-action-area");
    if (!wrap) return;
    wrap.innerHTML = "";

    const wf = getWorkflow(supplier);
    if (wf) {
      const pb = PLAYBOOKS[wf.playbookId];
      const card = el("div", { class: "wf-action-card" + (NEGATIVE_PLAYBOOK_IDS.has(wf.playbookId) ? " wf-priority-negative" : "") }, [
        el("div", { class: "wf-head" }, [
          el("div", {}, [
            el("div", { class: "wf-name" }, ["Workflow in progress for this supplier"]),
            el("div", { class: "wf-playbook-name" }, [pb.name]),
          ]),
          workflowStatusBadge(wf.status),
        ]),
        buildMiniStepper(pb.steps.length, wf.stepIndex, wf.status),
        el("div", { class: "small-note" }, [`Step ${wf.stepIndex + 1} of ${pb.steps.length}: ${pb.steps[wf.stepIndex]}`]),
      ]);
      if (wf.notes) card.appendChild(el("div", { class: "small-note", style: "margin-top:4px;" }, ["Notes: " + wf.notes.slice(0, 160) + (wf.notes.length > 160 ? "…" : "")]));
      const cont = el("button", { class: "primary", style: "margin-top:8px;" }, ["▶ Continue workflow"]);
      cont.addEventListener("click", () => openWorkflowModal(supplier, { playbookId: wf.playbookId, label: supplier }));
      card.appendChild(cont);
      wrap.appendChild(card);
      return;
    }

    const suggested = collectSuggestedActions(fromFY, toFY).find(it => it.entityKey === supplier);
    if (suggested) {
      const pb = PLAYBOOKS[suggested.playbookId];
      const card = el("div", { class: "wf-action-card" + (NEGATIVE_PLAYBOOK_IDS.has(suggested.playbookId) ? " wf-priority-negative" : "") }, [
        el("div", { class: "wf-head" }, [
          el("div", {}, [
            el("div", { class: "wf-name" }, ["Suggested action for this supplier"]),
            el("div", { class: "wf-playbook-name" }, [pb.name]),
          ]),
          el("span", { class: "reason-tag " + (NEGATIVE_PLAYBOOK_IDS.has(suggested.playbookId) ? "deobligation_flag" : "high_concentration") }, [pb.trigger]),
        ]),
        el("div", { class: "small-note" }, [pb.summary]),
      ]);
      const start = el("button", { class: "primary", style: "margin-top:8px;" }, [`▶ Start: ${pb.name}`]);
      start.addEventListener("click", () => {
        openWorkflowModal(supplier, { playbookId: suggested.playbookId, label: supplier });
        renderSupplierActionArea(supplier, fromFY, toFY);
      });
      card.appendChild(start);
      wrap.appendChild(card);
      return;
    }

    // Nothing flagged. Say so plainly, and put the "why not" behind a click
    // rather than asserting the supplier is fine.
    const row = el("div", { class: "small-note" }, ["No workflow running and no action suggested for this supplier. "]);
    const info = el("button", { class: "sc-details-toggle" }, ["Why? ⓘ"]);
    info.addEventListener("click", () => openKpiModal({
      title: `No suggested action -- ${supplier}`,
      formula: "A supplier only gets a suggested action when one of this dashboard's disclosed signals fires for it: "
        + "high spend concentration, notable deobligations, or a rapid year-over-year swing. "
        + `${supplier} did not trigger any of those in the selected timeframe.`,
      note: "This is the absence of a signal, not a clean bill of health -- the screens here cover a narrow set of "
        + "patterns computed from obligation amounts, and plenty of things they do not look at could still warrant review. "
        + "You can still start any playbook manually from the Action Center.",
      columns: null, rows: null,
    }));
    row.appendChild(info);
    const openAC = el("button", { class: "sc-details-toggle", style: "margin-left:8px;" }, ["Open Action Center →"]);
    openAC.addEventListener("click", () => switchTab("actions"));
    row.appendChild(openAC);
    wrap.appendChild(row);
  }

  function collectSuggestedActions(fromFY, toFY) {
    const key = standoutRangeKey(fromFY, toFY);
    const rangeData = (DATA.standout_by_range || {})[key];
    const suppliers = (rangeData ? rangeData.standout_suppliers : DATA.standout_suppliers) || [];
    const awards = (rangeData ? rangeData.standout_awards : DATA.standout_awards) || [];
    const consolidations = DATA.consolidation_opportunities || [];
    const duplicates = DATA.duplicate_purchase_candidates || [];

    const items = [];
    suppliers.forEach(s => {
      const playbookId = pickPlaybookForReasons(s.reasons);
      if (playbookId) items.push({ entityKey: s.supplier, label: s.supplier, sub: `Supplier · ${fmtMoney(s.net_obligations)}`, playbookId });
    });
    awards.forEach(a => {
      const playbookId = pickPlaybookForReasons(a.reasons);
      if (playbookId) items.push({ entityKey: "award:" + a.award_id, label: `${a.supplier} — ${a.award_id}`, sub: `Contract award · ${fmtMoney(a.net_obligations)}`, playbookId });
    });
    consolidations.forEach(c => {
      items.push({ entityKey: "consolidation:" + c.category, label: c.category, sub: `Category · ${fmtMoney(c.total_net_obligations)}`, playbookId: "consolidation_sourcing" });
    });
    duplicates.forEach(d => {
      items.push({ entityKey: "duplicate:" + d.pair_id, label: `${d.supplier} (possible duplicate)`, sub: `${d.category} · ${fmtMoney(d.combined_value)}`, playbookId: "duplicate_dedup_audit" });
    });

    // Only items with no workflow started yet -- "suggested", not "already
    // being worked" (those show up in Active Workflows below instead).
    const workflows = getWorkflows();
    const pending = items.filter(it => !workflows[it.entityKey]);
    // Negatively-outstanding signals (deobligations, rapid decline, cost
    // growth) surface first, per the "especially the negatively outstanding
    // ones" ask.
    pending.sort((a, b) => (NEGATIVE_PLAYBOOK_IDS.has(a.playbookId) ? 0 : 1) - (NEGATIVE_PLAYBOOK_IDS.has(b.playbookId) ? 0 : 1));
    return pending;
  }

  function renderSuggestedActions(fromFY, toFY) {
    const container = document.getElementById("suggested-actions");
    const note = document.getElementById("suggested-actions-note");
    if (!container) return;
    container.innerHTML = "";
    const isFullRange = fromFY == null && toFY == null;
    note.textContent = isFullRange
      ? "Drawn from Standout Suppliers & Contracts (all years), Consolidation Opportunities, and Possible Duplicate Purchases. Negatively-flagged items (deobligations, rapid decline, cost growth) are listed first."
      : `Drawn from Standout Suppliers & Contracts for the header's selected FY${fromFY}–FY${toFY} range; Consolidation Opportunities and Possible Duplicate Purchases stay all-time. Negatively-flagged items are listed first.`;

    const items = collectSuggestedActions(fromFY, toFY);
    if (!items.length) {
      container.appendChild(el("div", { class: "small-note" }, ["Nothing currently outstanding -- every flagged item already has a workflow started, or none met the signal criteria for this timeframe."]));
      return;
    }
    items.forEach(it => {
      const playbook = PLAYBOOKS[it.playbookId];
      const negative = NEGATIVE_PLAYBOOK_IDS.has(it.playbookId);
      const card = el("div", { class: "wf-action-card" + (negative ? " wf-priority-negative" : "") }, [
        el("div", { class: "wf-head" }, [
          el("div", {}, [
            el("div", { class: "wf-name" }, [it.label]),
            el("div", { class: "small-note" }, [it.sub]),
            el("div", { class: "wf-playbook-name" }, [playbook.name]),
          ]),
          el("span", { class: "reason-tag " + (negative ? "deobligation_flag" : "high_concentration") }, [playbook.trigger]),
        ]),
      ]);
      const startBtn = el("button", { class: "primary" }, [`▶ Start: ${playbook.name}`]);
      startBtn.addEventListener("click", () => {
        openWorkflowModal(it.entityKey, { playbookId: it.playbookId, label: it.label });
        renderActionCenter(globalFromFY, globalToFY);
      });
      card.appendChild(startBtn);
      container.appendChild(card);
    });
  }

  function renderActiveWorkflows() {
    const container = document.getElementById("active-workflows");
    if (!container) return;
    container.innerHTML = "";
    const filterSel = document.getElementById("wf-status-filter");
    const filterVal = filterSel ? filterSel.value : "";
    const all = getWorkflows();
    const entries = Object.entries(all).filter(([, wf]) => !filterVal || wf.status === filterVal);
    if (!entries.length) {
      container.appendChild(el("div", { class: "small-note" }, ["No active workflows yet -- start one from Suggested Actions above, or from a \"Take action\" button on a flagged item elsewhere in the dashboard."]));
      return;
    }
    entries.sort((a, b) => new Date(b[1].updatedAt) - new Date(a[1].updatedAt));
    entries.forEach(([entityKey, wf]) => {
      const playbook = PLAYBOOKS[wf.playbookId];
      const done = wf.status === "complete" ? playbook.steps.length : wf.stepIndex;
      const card = el("div", { class: "wf-action-card" + (NEGATIVE_PLAYBOOK_IDS.has(wf.playbookId) ? " wf-priority-negative" : "") }, [
        el("div", { class: "wf-head" }, [
          el("div", {}, [
            el("div", { class: "wf-name" }, [wf.label]),
            el("div", { class: "wf-playbook-name" }, [playbook.name]),
          ]),
          workflowStatusBadge(wf.status),
        ]),
        buildMiniStepper(playbook.steps.length, wf.stepIndex, wf.status),
        el("div", { class: "small-note" }, [
          wf.status === "complete"
            ? `All ${playbook.steps.length} steps complete.`
            : `Step ${wf.stepIndex + 1} of ${playbook.steps.length}: ${playbook.steps[wf.stepIndex]}  ·  ${done} done`,
        ]),
      ]);

      // Which steps are actually finished, and any notes written -- the two
      // things you need to pick a workflow back up without opening it first.
      const stepList = el("ul", { class: "wf-step-list" });
      playbook.steps.forEach((label, i) => {
        const state = (wf.status === "complete" || i < wf.stepIndex) ? "done" : (i === wf.stepIndex ? "current" : "todo");
        stepList.appendChild(el("li", { class: "wf-step-item " + state }, [
          el("span", { class: "wf-step-mark" }, [state === "done" ? "✓" : state === "current" ? "▸" : "○"]),
          el("span", {}, [label]),
        ]));
      });
      card.appendChild(stepList);

      if (wf.notes && wf.notes.trim()) {
        card.appendChild(el("div", { class: "wf-notes-preview" }, [
          el("strong", {}, ["Notes: "]),
          wf.notes.trim().slice(0, 220) + (wf.notes.trim().length > 220 ? "…" : ""),
        ]));
      } else {
        card.appendChild(el("div", { class: "small-note" }, ["No notes yet."]));
      }

      const cont = el("button", { class: "primary", style: "margin-top:8px;" },
        [wf.status === "complete" ? "Review workflow" : "▶ Continue workflow"]);
      cont.addEventListener("click", ev => {
        ev.stopPropagation();
        openWorkflowModal(entityKey, { playbookId: wf.playbookId, label: wf.label });
      });
      card.appendChild(cont);

      card.style.cursor = "pointer";
      card.addEventListener("click", () => openWorkflowModal(entityKey, { playbookId: wf.playbookId, label: wf.label }));
      container.appendChild(card);
    });
  }

  // Compact status summary of workflows actually acted on (started, in
  // progress, or complete) -- the primary thing this tab leads with. The
  // full step-by-step Playbook Library reference is collapsed below it
  // (see setupPlaybookLibraryToggle()), not shown by default.
  function renderWorkflowStatusSummary() {
    const container = document.getElementById("workflow-status-summary");
    if (!container) return;
    container.innerHTML = "";
    const all = Object.values(getWorkflows());
    const inProgress = all.filter(wf => wf.status === "in_progress").length;
    const complete = all.filter(wf => wf.status === "complete").length;
    const filterSel = document.getElementById("wf-status-filter");
    const current = filterSel ? filterSel.value : "";

    // Each counter is a filter for the Active Workflows list below, so the
    // summary is a way into the detail rather than a dead readout.
    const tile = (label, value, filterValue) => {
      const t = kpiTile(label, fmtNum(value));
      t.classList.add("clickable");
      if (current === filterValue) t.classList.add("kpi-filter-active");
      t.title = "Show these in Active Workflows below";
      t.tabIndex = 0;
      t.setAttribute("role", "button");
      const apply = () => {
        if (filterSel) { filterSel.value = filterValue; }
        renderActiveWorkflows();
        renderWorkflowStatusSummary();
        const target = document.getElementById("active-workflows");
        if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
      };
      t.addEventListener("click", apply);
      t.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); apply(); } });
      return t;
    };
    container.appendChild(tile("Workflows Started", all.length, ""));
    container.appendChild(tile("In Progress", inProgress, "in_progress"));
    container.appendChild(tile("Complete", complete, "complete"));
    if (!all.length) {
      container.appendChild(el("div", { class: "small-note" }, ["Nothing started yet -- pick something from Suggested Actions below."]));
    }
  }

  function setupPlaybookLibraryToggle() {
    const toggle = document.getElementById("playbook-library-toggle");
    const wrap = document.getElementById("playbook-library");
    if (!toggle || !wrap) return;
    toggle.addEventListener("click", () => {
      const nowExpanded = wrap.classList.toggle("expanded");
      toggle.textContent = nowExpanded ? "Show reference ▴" : "Show reference ▾";
    });
  }

  function renderActionCenter(fromFY, toFY) {
    renderPlaybookLibrary();
    renderWorkflowStatusSummary();
    renderSuggestedActions(fromFY, toFY);
    renderActiveWorkflows();
  }

  renderHeader();
  setupTabs();
  setupThemeToggle();
  setupCommandPalette();
  setupKpiModal();
  setupWorkflowModal();
  renderOverview();
  renderSnapshotStatus();
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
  renderMisuseProtectionTab();
  setupPlaybookLibraryToggle();
  renderActionCenter(globalFromFY, globalToFY);
  onGlobalTimeframeChange(renderActionCenter);
  refreshActionCenterIfOpen = () => renderActionCenter(globalFromFY, globalToFY);
  const wfStatusFilter = document.getElementById("wf-status-filter");
  // Keep the counter tiles' active-filter highlight in sync when the filter
  // is changed from the dropdown rather than by clicking a tile.
  if (wfStatusFilter) wfStatusFilter.addEventListener("change", () => {
    renderActiveWorkflows();
    renderWorkflowStatusSummary();
  });

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
