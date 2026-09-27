/*
 * Dashboard logic (D-04, D-05): plain JavaScript + Chart.js, data from the FastAPI endpoints (D-44).
 *
 * How it works:
 *   1. init() loads /api/filters, fills the dropdowns, and loads /api/health.
 *   2. Any filter change -> the visible tab reloads (every chart and table uses the same filters).
 *   3. Each tab has one loader: loadExplore, loadUnderstand, loadChallenge, loadTrust.
 *   4. Errors from the API are shown as a message (role="alert"); empty results as an "empty" message.
 *
 * Safety: text from the API is always inserted with textContent, never innerHTML.
 * Statistical wording follows D-63 (associative, not causal; "did not show a clear association").
 */
"use strict";

// ---------------------------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------------------------

const TABS = ["explore", "understand", "challenge", "trust"];
const TURNOVER = "REGRETTED_TURNOVER_12M";
const COUNTRIES = ["GR", "RO", "PL", "IT", "IE", "BG"];

const state = {
  tab: "explore",
  filters: null, // the /api/filters response
  objective: "NEW_HIRE_6M",
  country: "ALL",
  segment: "",
  yearFrom: null,
  yearTo: null,
  variant: "primary",
};
const charts = {}; // canvas id -> Chart instance
let loadCounter = 0; // ignore answers from older requests when filters change quickly

// ---------------------------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------------------------

function byId(id) {
  return document.getElementById(id);
}

/** Create an element with safe text. */
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) {
    node.textContent = String(text);
  }
  if (className) {
    node.className = className;
  }
  return node;
}

function clear(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

/** 0.8752 -> "87.5%" (digits = decimals). Missing -> "–". */
function pct(value, digits) {
  if (value === null || value === undefined) {
    return "–";
  }
  return (value * 100).toFixed(digits) + "%";
}

function num(value, digits) {
  if (value === null || value === undefined) {
    return "–";
  }
  return Number(value).toFixed(digits);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function rateDigits() {
  return state.objective === TURNOVER ? 2 : 1;
}

function objectiveMeta(objectiveId) {
  for (const objective of state.filters.objectives) {
    if (objective.objective_id === objectiveId) {
      return objective;
    }
  }
  return null;
}

function countryName(code) {
  for (const country of state.filters.countries) {
    if (country.code === code) {
      return country.name;
    }
  }
  return code;
}

/** A status pill: icon + word, never colour alone (D-75). */
function statusBadge(status) {
  const labels = { met: "Met", not_met: "Not met", inconclusive: "Inconclusive" };
  const text = labels[status] || "No verdict (trend only)";
  const badge = el("span", text, "status " + (status || "none"));
  badge.setAttribute("data-status", status || "none");
  return badge;
}

function targetText(meta) {
  const sign = meta.direction === "at_least" ? "≥" : "≤";
  const digits = meta.objective_id === TURNOVER ? 1 : 0;
  return "Target " + sign + " " + pct(meta.target, digits);
}

/**
 * Build a table. columns = [{key, label, numeric, format(row) -> string | Node}]
 * rowClass(row) may return a CSS class for the row.
 */
function buildTable(container, columns, rows, rowClass) {
  clear(container);
  const table = el("table");
  const head = el("thead");
  const headRow = el("tr");
  for (const column of columns) {
    const th = el("th", column.label, column.numeric ? "num" : "");
    th.setAttribute("scope", "col");
    headRow.appendChild(th);
  }
  head.appendChild(headRow);
  table.appendChild(head);

  const body = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    if (rowClass) {
      const cls = rowClass(row);
      if (cls) {
        tr.className = cls;
      }
    }
    for (const column of columns) {
      const td = el("td", null, column.numeric ? "num" : "");
      const value = column.format ? column.format(row) : row[column.key];
      if (value instanceof Node) {
        td.appendChild(value);
      } else {
        td.textContent = value === null || value === undefined ? "–" : String(value);
      }
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  table.appendChild(body);
  container.appendChild(table);
}

// ---------------------------------------------------------------------------------------------
// API access and messages
// ---------------------------------------------------------------------------------------------

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/** GET an API path with query parameters (empty values are left out). */
async function fetchJson(path, params) {
  const query = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined && value !== "") {
        query.append(key, value);
      }
    }
  }
  const url = query.toString() ? path + "?" + query.toString() : path;
  let response;
  try {
    response = await fetch(url);
  } catch (networkError) {
    throw new ApiError("The API is not reachable. Is `retention serve` running?", 0);
  }
  let body = null;
  try {
    body = await response.json();
  } catch (parseError) {
    body = null;
  }
  if (!response.ok) {
    const message = body && body.error ? body.error.message : "HTTP " + response.status;
    throw new ApiError(message, response.status);
  }
  return body;
}

function showMessage(tab, kind, text) {
  const box = byId(tab + "-message");
  box.hidden = false;
  box.className = "message " + kind;
  box.setAttribute("role", kind === "error" ? "alert" : "status");
  box.setAttribute("data-kind", kind);
  box.textContent = text;
}

function hideMessage(tab) {
  const box = byId(tab + "-message");
  box.hidden = true;
  box.textContent = "";
}

function errorText(error) {
  if (error.status === 503) {
    return "No data yet: " + error.message;
  }
  if (error.status === 400 || error.status === 404) {
    return "This filter cannot be used: " + error.message;
  }
  return "Could not load data: " + error.message;
}

// ---------------------------------------------------------------------------------------------
// Charts (Chart.js). One y-axis per chart, never two (dataviz rule).
// ---------------------------------------------------------------------------------------------

/** Position of a period on a decimal-year axis: "2023-Q2" -> 2023.375, "2024-03-31" -> 2024.21. */
function xFromPeriod(period) {
  if (period.indexOf("-Q") > 0) {
    const year = Number(period.slice(0, 4));
    const quarter = Number(period.slice(6));
    return year + (quarter - 1) / 4 + 0.125;
  }
  if (period.length === 10) {
    const year = Number(period.slice(0, 4));
    const month = Number(period.slice(5, 7));
    return year + (month - 0.5) / 12;
  }
  if (period.length === 7) {
    const year = Number(period.slice(0, 4));
    const month = Number(period.slice(5, 7));
    return year + (month - 0.5) / 12;
  }
  return Number(period) + 0.5;
}

function yearRange() {
  const years = state.filters.years;
  const from = state.yearFrom || Number(years[0]);
  const to = state.yearTo || Number(years[years.length - 1]);
  return { min: from, max: to + 1 };
}

function drawChart(canvasId, config) {
  if (charts[canvasId]) {
    charts[canvasId].destroy();
  }
  charts[canvasId] = new Chart(byId(canvasId).getContext("2d"), config);
}

function baseOptions(yTitle, yFormat, xRange) {
  const ink = cssVar("--text-2");
  const grid = cssVar("--grid");
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    plugins: {
      legend: {
        labels: {
          color: ink,
          boxHeight: 2,
          filter: function (item) {
            return !item.text.startsWith("_");
          },
        },
      },
      tooltip: {
        filter: function (item) {
          return !item.dataset.label.startsWith("_");
        },
      },
    },
    scales: {
      x: {
        type: "linear",
        min: xRange.min,
        max: xRange.max,
        ticks: {
          color: ink,
          stepSize: 1,
          callback: function (value) {
            return Number.isInteger(value) ? String(value) : "";
          },
        },
        grid: { color: grid },
      },
      y: {
        title: { display: true, text: yTitle, color: ink },
        ticks: { color: ink, callback: yFormat },
        grid: { color: grid },
      },
    },
  };
}

/** Rate line + 95% CI band + target line. points = [{period, rate, ci_low, ci_high, n}] */
function drawTrend(canvasId, points, meta, yTitle) {
  const accent = cssVar("--accent");
  const band = cssVar("--band");
  const muted = cssVar("--text-2");
  const digits = rateDigits();
  const range = yearRange();

  const rateData = [];
  const lowData = [];
  const highData = [];
  for (const point of points) {
    if (point.rate === null) {
      continue; // e.g. a quarter with only immature hires
    }
    const x = xFromPeriod(point.period);
    rateData.push({ x: x, y: point.rate, n: point.n, period: point.period });
    lowData.push({ x: x, y: point.ci_low });
    highData.push({ x: x, y: point.ci_high });
  }

  const options = baseOptions(yTitle, function (value) {
    return pct(value, digits === 2 ? 1 : 0);
  }, range);
  options.plugins.tooltip.callbacks = {
    title: function (items) {
      const raw = items[0].raw;
      return raw.period || "";
    },
    label: function (item) {
      if (item.dataset.label === "Target") {
        return "Target " + pct(item.raw.y, digits);
      }
      const raw = item.raw;
      const index = item.dataIndex;
      return pct(raw.y, digits) + "  (95% CI " + pct(lowData[index].y, digits) + "–" +
        pct(highData[index].y, digits) + ", n=" + num(raw.n, 0) + ")";
    },
  };

  drawChart(canvasId, {
    type: "line",
    data: {
      datasets: [
        { label: "_ci_high", data: highData, borderWidth: 0, pointRadius: 0, fill: false },
        { label: "95% interval", data: lowData, borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: band },
        { label: meta.objective_id, data: rateData, borderColor: accent, backgroundColor: accent, borderWidth: 2, pointRadius: 3 },
        {
          label: "Target",
          data: [{ x: range.min, y: meta.target }, { x: range.max, y: meta.target }],
          borderColor: muted,
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
        },
      ],
    },
    options: options,
  });
}

// ---------------------------------------------------------------------------------------------
// Filters and tabs
// ---------------------------------------------------------------------------------------------

function fillSelect(select, options, selectedValue) {
  clear(select);
  for (const option of options) {
    const node = el("option", option.label);
    node.value = option.value;
    if (option.value === selectedValue) {
      node.selected = true;
    }
    select.appendChild(node);
  }
}

function fillFilters(filters) {
  state.filters = filters;

  const objectives = [];
  for (const objective of filters.objectives) {
    objectives.push({ value: objective.objective_id, label: objective.name });
  }
  fillSelect(byId("f-objective"), objectives, state.objective);

  const countries = [];
  for (const country of filters.countries) {
    countries.push({ value: country.code, label: country.name });
  }
  fillSelect(byId("f-country"), countries, state.country);

  // Segment: one list, grouped by dimension; value "dimension:value" (D-77).
  const segment = byId("f-segment");
  clear(segment);
  const all = el("option", "All employees");
  all.value = "";
  segment.appendChild(all);
  const dimensionLabels = {
    employment_type: "Employment type",
    career_level: "Career level",
    business_unit: "Business unit",
    job_family: "Job family",
  };
  for (const [dimension, values] of Object.entries(filters.segments)) {
    const group = document.createElement("optgroup");
    group.label = dimensionLabels[dimension] || dimension;
    for (const value of values) {
      const option = el("option", value);
      option.value = dimension + ":" + value;
      group.appendChild(option);
    }
    segment.appendChild(group);
  }

  const years = [];
  for (const year of filters.years) {
    years.push({ value: year, label: year });
  }
  fillSelect(byId("f-from"), years, filters.years[0]);
  fillSelect(byId("f-to"), years, filters.years[filters.years.length - 1]);

  const indicators = [];
  for (const indicator of filters.indicators) {
    indicators.push({ value: indicator.indicator, label: indicatorLabel(indicator.indicator) });
  }
  fillSelect(byId("u-indicator"), indicators, "unemployment");
  fillSelect(byId("c-indicator"), indicators, "unemployment");

  fillVariants();
}

function indicatorLabel(name) {
  const labels = {
    unemployment: "Unemployment rate (Eurostat, monthly)",
    inflation: "HICP inflation (Eurostat, monthly)",
    job_vacancy: "Job vacancy rate (Eurostat, quarterly)",
    gdp_growth: "GDP growth (World Bank, annual)",
  };
  return labels[name] || name;
}

function fillVariants() {
  const labels = {
    primary: "Primary (unverified exits quarantined)",
    with_unverified_exits: "Sensitivity: unverified exits counted",
    unknown_as_regretted: "Sensitivity: unknown regretted counted as regretted",
  };
  const key = state.objective === TURNOVER ? "turnover" : "hire_objectives";
  const options = [];
  for (const variant of state.filters.variants[key]) {
    options.push({ value: variant, label: labels[variant] });
  }
  if (options.map((o) => o.value).indexOf(state.variant) < 0) {
    state.variant = "primary";
  }
  fillSelect(byId("f-variant"), options, state.variant);

  // Segments exist for hire cohorts only (D-77); turnover is for all employees.
  const segment = byId("f-segment");
  segment.disabled = state.objective === TURNOVER;
  if (segment.disabled) {
    segment.value = "";
    state.segment = "";
  }
}

function readFilters() {
  const previousObjective = state.objective;
  state.objective = byId("f-objective").value;
  state.country = byId("f-country").value;
  state.segment = byId("f-segment").value;
  state.yearFrom = Number(byId("f-from").value);
  state.yearTo = Number(byId("f-to").value);
  state.variant = byId("f-variant").value;
  if (state.objective !== previousObjective) {
    fillVariants();
    state.variant = byId("f-variant").value;
  }
}

function commonParams() {
  return {
    objective: state.objective,
    country: state.country,
    variant: state.variant,
    segment: state.segment,
    year_from: state.yearFrom,
    year_to: state.yearTo,
  };
}

function selectTab(tab, moveFocus) {
  state.tab = tab;
  for (const name of TABS) {
    const button = byId("tab-" + name);
    const selected = name === tab;
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.tabIndex = selected ? 0 : -1;
    byId("panel-" + name).hidden = !selected;
    if (selected && moveFocus) {
      button.focus();
    }
  }
  loadCurrentTab();
}

function setupTabs() {
  for (const name of TABS) {
    const button = byId("tab-" + name);
    button.addEventListener("click", function () {
      selectTab(name, false);
    });
    button.addEventListener("keydown", function (event) {
      // Arrow keys move between tabs (WAI-ARIA tabs pattern).
      const index = TABS.indexOf(name);
      if (event.key === "ArrowRight") {
        selectTab(TABS[(index + 1) % TABS.length], true);
        event.preventDefault();
      } else if (event.key === "ArrowLeft") {
        selectTab(TABS[(index + TABS.length - 1) % TABS.length], true);
        event.preventDefault();
      }
    });
  }
}

async function loadCurrentTab() {
  const loaders = { explore: loadExplore, understand: loadUnderstand, challenge: loadChallenge, trust: loadTrust };
  const panel = byId("panel-" + state.tab);
  const myLoad = ++loadCounter;
  panel.classList.add("loading");
  panel.setAttribute("aria-busy", "true");
  hideMessage(state.tab);
  try {
    await loaders[state.tab](myLoad);
  } catch (error) {
    if (myLoad === loadCounter) {
      showMessage(state.tab, "error", errorText(error));
      if (state.tab === "explore") {
        byId("explore-content").hidden = true;
      }
    }
  } finally {
    panel.classList.remove("loading");
    panel.setAttribute("aria-busy", "false");
  }
}

// ---------------------------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------------------------

async function loadHealth() {
  const box = byId("health");
  try {
    const health = await fetchJson("/api/health");
    byId("as-of").textContent = health.as_of_date;
    clear(box);
    const labels = { ok: "met", degraded: "inconclusive", no_data: "not_met" };
    const badge = el("span", health.status === "ok" ? "Data OK" : health.status === "degraded" ? "Degraded" : "No data",
      "status " + labels[health.status]);
    box.appendChild(badge);
    box.appendChild(el("span", " " + health.message));
    if (health.data_built_by_run) {
      box.appendChild(el("div", "Built by " + health.data_built_by_run + " at " + health.data_built_at, "muted"));
    }
    box.setAttribute("data-health", health.status);
  } catch (error) {
    box.textContent = "API not reachable: " + error.message;
    box.setAttribute("data-health", "error");
  }
}

// ---------------------------------------------------------------------------------------------
// EXPLORE
// ---------------------------------------------------------------------------------------------

async function loadExplore(myLoad) {
  const meta = objectiveMeta(state.objective);
  byId("explore-title").textContent = meta.name + " · " + countryName(state.country);
  const label = byId("explore-label");
  label.textContent = targetText(meta) + " · " + meta.label + (state.segment ? " · segment " + state.segment.replace(":", " = ") : "");

  if (state.objective === TURNOVER) {
    await exploreTurnover(meta, myLoad);
  } else {
    await exploreCohorts(meta, myLoad);
  }
}

async function exploreCohorts(meta, myLoad) {
  const params = commonParams();
  const answers = await Promise.all([
    fetchJson("/api/retention/cohorts", Object.assign({}, params, { grain: "period" })),
    fetchJson("/api/retention/cohorts", Object.assign({}, params, { grain: "year" })),
    fetchJson("/api/retention/cohorts", Object.assign({}, params, { grain: "quarter" })),
  ]);
  if (myLoad !== loadCounter) {
    return; // a newer filter change is already loading
  }
  const period = answers[0].rows;
  const years = answers[1].rows;
  const quarters = answers[2].rows;
  const content = byId("explore-content");

  // Empty state: nothing measurable in this slice.
  if (period.length === 0 || period[0].n === 0) {
    content.hidden = true;
    showMessage("explore", "empty",
      "No mature hires match these filters (for example a small segment in one country). Try a wider filter.");
    return;
  }
  content.hidden = false;
  byId("exit-card").hidden = false;

  // 1. Tiles: whole period + the latest selected year.
  const tiles = byId("explore-tiles");
  clear(tiles);
  const whole = period[0];
  tiles.appendChild(rateTile("2021–2025 (whole period)", whole, meta));
  const measuredYears = years.filter((row) => row.n > 0);
  if (measuredYears.length > 0) {
    const last = measuredYears[measuredYears.length - 1];
    tiles.appendChild(rateTile("Hire year " + last.period, last, meta));
  }
  const immature = el("div", null, "tile");
  immature.appendChild(el("div", "Not yet measurable", "tile-label"));
  immature.appendChild(el("div", String(whole.immature_hires), "tile-value"));
  immature.appendChild(el("div", "hires whose " + (meta.objective_id === "NEW_HIRE_6M" ? "6" : "12") +
    "-month window ends after the as-of date (D-18)", "tile-detail"));
  tiles.appendChild(immature);

  // 2. Year table (verdict rows).
  buildTable(byId("explore-years"), cohortColumns(), years);

  // 3. Quarterly trend (no verdicts on quarters, D-76).
  byId("trend-caption").textContent = "Quarterly cohorts: rate with 95% interval (trend only, no verdict)";
  drawTrend("trend-chart", quarters, meta, "Retained");
  buildTable(byId("trend-table"), cohortColumns(), quarters);

  // 4. Exit type breakdown over the selected years (D-17).
  const totals = { Voluntary: 0, Involuntary: 0, "End of contract": 0, "Unknown type": 0 };
  for (const row of years) {
    totals.Voluntary += row.exits_voluntary;
    totals.Involuntary += row.exits_involuntary;
    totals["End of contract"] += row.exits_end_of_contract;
    totals["Unknown type"] += row.exits_unknown_type;
  }
  const labels = Object.keys(totals);
  const values = labels.map((key) => totals[key]);
  drawChart("exit-chart", {
    type: "bar",
    data: { labels: labels, datasets: [{ label: "Exits within the window", data: values, backgroundColor: cssVar("--accent"), borderRadius: 4, barThickness: 18 }] },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: cssVar("--text-2"), precision: 0 }, grid: { color: cssVar("--grid") } },
        y: { ticks: { color: cssVar("--text-2") }, grid: { display: false } },
      },
    },
  });
  const exitRows = labels.map((key) => ({ type: key, exits: totals[key] }));
  buildTable(byId("exit-table"), [
    { key: "type", label: "Exit type" },
    { key: "exits", label: "Exits", numeric: true },
  ], exitRows);

  fillNotes(answers[0].notes.concat(["Values: " + answers[0].computed + "."]));
}

function rateTile(title, row, meta) {
  const digits = rateDigits();
  const tile = el("div", null, "tile");
  tile.setAttribute("data-testid", "rate-tile");
  tile.appendChild(el("div", title, "tile-label"));
  tile.appendChild(el("div", pct(row.rate, digits), "tile-value"));
  tile.appendChild(statusBadge(row.status));
  const n = row.n !== undefined ? row.n : row.avg_headcount;
  let detail = "95% CI " + pct(row.ci_low, digits) + "–" + pct(row.ci_high, digits) + " · n = " + num(n, 0) + " · " + targetText(meta);
  tile.appendChild(el("div", detail, "tile-detail"));
  if (row.small_sample) {
    tile.appendChild(el("div", "⚠ Small sample (fewer than 10): read with care", "small-sample"));
  }
  return tile;
}

function cohortColumns() {
  return [
    { key: "period", label: "Period" },
    { key: "n", label: "Mature hires (n)", numeric: true },
    { key: "retained", label: "Retained", numeric: true },
    { label: "Rate", numeric: true, format: (row) => pct(row.rate, 1) },
    { label: "95% interval", numeric: true, format: (row) => (row.rate === null ? "–" : pct(row.ci_low, 1) + "–" + pct(row.ci_high, 1)) },
    { label: "Status", format: (row) => statusBadge(row.status) },
    { label: "Sample", format: (row) => (row.small_sample ? "⚠ small (n<10)" : "") },
    { key: "immature_hires", label: "Not yet measurable", numeric: true },
  ];
}

function turnoverColumns() {
  return [
    { key: "month_end", label: "Month end" },
    { key: "regretted_exits", label: "Regretted exits (12m)", numeric: true },
    { key: "unknown_regretted_exits", label: "Unknown regretted", numeric: true },
    { label: "Avg headcount", numeric: true, format: (row) => num(row.avg_headcount, 0) },
    { label: "Rate", numeric: true, format: (row) => pct(row.rate, 2) },
    { label: "95% interval", numeric: true, format: (row) => pct(row.ci_low, 2) + "–" + pct(row.ci_high, 2) },
    { label: "Status", format: (row) => statusBadge(row.status) },
  ];
}

async function exploreTurnover(meta, myLoad) {
  const answer = await fetchJson("/api/retention/turnover", {
    country: state.country,
    variant: state.variant,
    year_from: state.yearFrom,
    year_to: state.yearTo,
  });
  if (myLoad !== loadCounter) {
    return;
  }
  const rows = answer.rows;
  const content = byId("explore-content");
  if (rows.length === 0) {
    content.hidden = true;
    showMessage("explore", "empty", "No turnover values for these filters.");
    return;
  }
  content.hidden = false;
  byId("exit-card").hidden = true;

  const decembers = rows.filter((row) => row.is_year_end);
  const tiles = byId("explore-tiles");
  clear(tiles);
  if (decembers.length > 0) {
    const last = decembers[decembers.length - 1];
    tiles.appendChild(rateTile("12 months to " + last.month_end, last, meta));
    let met = 0;
    for (const row of decembers) {
      if (row.status === "met") {
        met += 1;
      }
    }
    const summary = el("div", null, "tile");
    summary.appendChild(el("div", "Years meeting the target", "tile-label"));
    summary.appendChild(el("div", met + " of " + decembers.length, "tile-value"));
    summary.appendChild(el("div", "December values only: consecutive months overlap (D-37)", "tile-detail"));
    tiles.appendChild(summary);
  }

  buildTable(byId("explore-years"), turnoverColumns(), decembers);

  const points = rows.map((row) => Object.assign({ period: row.month_end, n: row.avg_headcount }, row));
  byId("trend-caption").textContent = "Trailing-12-month regretted turnover by month-end, with 95% interval (verdicts on December values only)";
  drawTrend("trend-chart", points, meta, "Regretted turnover");
  buildTable(byId("trend-table"), turnoverColumns(), rows);
  fillNotes(answer.notes);
}

function fillNotes(notes) {
  const list = byId("explore-notes");
  clear(list);
  for (const note of notes) {
    list.appendChild(el("li", note));
  }
}

// ---------------------------------------------------------------------------------------------
// UNDERSTAND
// ---------------------------------------------------------------------------------------------

async function loadUnderstand(myLoad) {
  const country = state.country;
  byId("understand-country").textContent = countryName(country);
  const indicator = byId("u-indicator").value;
  const segment = state.segment;

  // 1. Status of all three objectives for the selected country (whole period / latest December).
  const hireParams = { country: country, variant: state.variant === "unknown_as_regretted" ? "primary" : state.variant, segment: segment, grain: "period" };
  const answers = await Promise.all([
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "NEW_HIRE_6M" }, hireParams)),
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "SENIOR_HIRE_12M" }, hireParams)),
    fetchJson("/api/retention/turnover", { country: country, year_end_only: true }),
    fetchJson("/api/indicators", { indicator: indicator, country: country === "ALL" ? null : country, year_from: state.yearFrom, year_to: state.yearTo }),
  ]);
  if (myLoad !== loadCounter) {
    return;
  }

  const tiles = byId("understand-tiles");
  clear(tiles);
  const newHire = answers[0].rows[0];
  const senior = answers[1].rows[0];
  if (newHire && newHire.n > 0) {
    tiles.appendChild(rateTile("New-hire 6-month retention, 2021–2025", newHire, objectiveMeta("NEW_HIRE_6M")));
  }
  if (senior && senior.n > 0) {
    tiles.appendChild(rateTile("Senior-hire 12-month retention, 2021–2025", senior, objectiveMeta("SENIOR_HIRE_12M")));
  }
  const decembers = answers[2].rows;
  if (decembers.length > 0) {
    const savedObjective = state.objective;
    state.objective = TURNOVER; // two decimals for turnover
    tiles.appendChild(rateTile("Regretted turnover, 12 months to " + decembers[decembers.length - 1].month_end, decembers[decembers.length - 1], objectiveMeta(TURNOVER)));
    state.objective = savedObjective;
  }
  if (segment) {
    tiles.appendChild(el("p", "Segment " + segment.replace(":", " = ") + " applies to the hire objectives only (turnover covers all employees).", "muted"));
  }

  // 2. The selected objective's trend.
  const meta = objectiveMeta(state.objective);
  if (state.objective === TURNOVER) {
    const turnover = await fetchJson("/api/retention/turnover", { country: country, variant: state.variant, year_from: state.yearFrom, year_to: state.yearTo });
    const points = turnover.rows.map((row) => Object.assign({ period: row.month_end, n: row.avg_headcount }, row));
    byId("u-rate-caption").textContent = meta.name + " · " + countryName(country) + " (monthly, trailing 12 months)";
    drawTrend("u-rate-chart", points, meta, "Regretted turnover");
    buildTable(byId("u-rate-table"), turnoverColumns(), turnover.rows);
  } else {
    const cohorts = await fetchJson("/api/retention/cohorts", Object.assign({}, commonParams(), { grain: "quarter" }));
    byId("u-rate-caption").textContent = meta.name + " · " + countryName(country) + " (quarterly cohorts)";
    drawTrend("u-rate-chart", cohorts.rows, meta, "Retained");
    buildTable(byId("u-rate-table"), cohortColumns(), cohorts.rows);
  }
  if (myLoad !== loadCounter) {
    return;
  }

  // 3. The external signal, drawn at its own frequency; one line per country with a fixed colour.
  drawIndicator(answers[3].rows, indicator, country);
}

function drawIndicator(rows, indicator, country) {
  const caption = byId("u-indicator-caption");
  caption.textContent = indicatorLabel(indicator) + (country === "ALL" ? " · all six countries" : " · " + countryName(country));
  if (rows.length === 0) {
    showMessage("understand", "empty", "No values for this signal in the selected years.");
    return;
  }
  const byCountry = {};
  for (const row of rows) {
    if (!byCountry[row.country_code]) {
      byCountry[row.country_code] = [];
    }
    byCountry[row.country_code].push(row);
  }

  const datasets = [];
  for (const code of COUNTRIES) {
    const series = byCountry[code];
    if (!series) {
      continue;
    }
    const color = cssVar("--c-" + code); // colour follows the country, never its rank
    const data = [];
    let annual = false;
    for (const row of series) {
      if (row.frequency === "annual") {
        annual = true;
        data.push({ x: Number(row.period), y: row.value, row: row });
      } else {
        data.push({ x: xFromPeriod(row.period), y: row.value, row: row });
      }
    }
    if (annual && data.length > 0) {
      const last = data[data.length - 1];
      data.push({ x: last.x + 1, y: last.y, row: last.row }); // close the last step at year end
    }
    datasets.push({
      label: countryName(code),
      data: data,
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: annual ? 3 : 0,
      stepped: annual ? "before" : false,
    });
  }

  const unit = rows[0].unit;
  const options = baseOptions(unit, function (value) {
    return num(value, 1);
  }, yearRange());
  options.plugins.tooltip.callbacks = {
    title: function (items) {
      return items.length ? items[0].raw.row.period : "";
    },
    label: function (item) {
      const row = item.raw.row;
      const flag = row.obs_status ? " (" + (row.obs_status_label || row.obs_status) + ")" : "";
      return num(row.value, 1) + "  " + item.dataset.label + flag;
    },
  };
  options.interaction = { mode: "nearest", intersect: false };
  drawChart("u-indicator-chart", { type: "line", data: { datasets: datasets }, options: options });

  buildTable(byId("u-indicator-table"), [
    { key: "country_code", label: "Country" },
    { key: "period", label: "Period" },
    { key: "frequency", label: "Frequency" },
    { label: "Value", numeric: true, format: (row) => num(row.value, 1) },
    { key: "unit", label: "Unit" },
    { label: "Status", format: (row) => row.obs_status_label || row.obs_status || "" },
  ], rows);
}

// ---------------------------------------------------------------------------------------------
// CHALLENGE
// ---------------------------------------------------------------------------------------------

function viewLabel(view) {
  const labels = {
    within_country: "Within-country (formal)",
    pooled: "Pooled (descriptive)",
    time_adjusted: "Time-adjusted (descriptive)",
  };
  return labels[view] || view;
}

async function loadChallenge(myLoad) {
  const objective = state.objective;
  const indicator = byId("c-indicator").value;
  const view = byId("c-view").value;
  const setField = byId("c-set-field");
  setField.hidden = objective !== "SENIOR_HIRE_12M";
  const analysisSet = objective === "SENIOR_HIRE_12M" ? byId("c-set").value : "formal";

  const answers = await Promise.all([
    fetchJson("/api/association", { objective: objective }),
    fetchJson("/api/association/points", { objective: objective, indicator: indicator, view: view, analysis_set: analysisSet }),
  ]);
  if (myLoad !== loadCounter) {
    return;
  }
  const results = answers[0].rows;
  const points = answers[1].points;
  byId("challenge-label").textContent = results.length ? results[0].label : "";

  // 1. All results: formal rows first and bold.
  buildTable(byId("challenge-results"), [
    { label: "Signal", format: (row) => indicatorLabel(row.indicator) },
    { label: "View", format: (row) => viewLabel(row.view) },
    { label: "rho", numeric: true, format: (row) => num(row.rho, 2) },
    { label: "Bootstrap 95% (exploratory)", numeric: true, format: (row) => num(row.ci_low, 2) + " to " + num(row.ci_high, 2) },
    { key: "n_rows", label: "n (rows)", numeric: true },
    { label: "p", numeric: true, format: (row) => num(row.p_value, 2) },
    { label: "Holm p", numeric: true, format: (row) => (row.p_holm === null ? "not a formal test" : num(row.p_holm, 2)) },
    { key: "result", label: "Result" },
  ], results, (row) => (row.is_formal ? "formal" : ""));

  // 2. Scatter: emphasis on the selected country, others grey (no 6-colour scatter).
  const accent = cssVar("--accent");
  const grey = cssVar("--axis");
  const selected = [];
  const others = [];
  for (const point of points) {
    if (point.view_x === null || point.view_y === null) {
      continue; // e.g. Ireland in GDP tests (D-59)
    }
    const item = { x: point.view_x, y: point.view_y, point: point };
    if (state.country === "ALL" || point.country_code === state.country) {
      selected.push(item);
    } else {
      others.push(item);
    }
  }
  const selectedLabel = state.country === "ALL" ? "Country-period rows" : countryName(state.country);
  const isPooled = view === "pooled";
  const xTitle = isPooled ? indicatorLabel(indicator) : indicatorLabel(indicator) + " (minus country average)";
  const yTitle = isPooled ? "Outcome rate" : "Outcome rate (minus country average)";
  const setText = analysisSet === "descriptive" ? " · quarterly rows, descriptive only (not tested)" : "";
  const viewText = analysisSet === "descriptive" ? viewLabel(view).replace(" (formal)", "") : viewLabel(view);
  byId("scatter-caption").textContent = viewText + ": " + indicatorLabel(indicator) + " vs " + objective +
    " · " + selected.concat(others).length + " rows" + setText;

  const ink = cssVar("--text-2");
  const grid = cssVar("--grid");
  drawChart("scatter-chart", {
    type: "scatter",
    data: {
      datasets: [
        { label: "Other countries", data: others, backgroundColor: grey, pointRadius: 4, pointHoverRadius: 6 },
        { label: selectedLabel, data: selected, backgroundColor: accent, borderColor: cssVar("--surface"), borderWidth: 2, pointRadius: 5, pointHoverRadius: 7 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: {
          labels: {
            color: ink,
            filter: function (item, data) {
              return data.datasets[item.datasetIndex].data.length > 0; // no legend entry for an empty series
            },
          },
        },
        tooltip: {
          callbacks: {
            label: function (item) {
              const p = item.raw.point;
              return p.country_code + " " + p.period + ": rate " + pct(p.outcome_rate, 1) + " (n=" + num(p.cohort_n, 0) + "), " +
                indicator + " " + num(p.value, 1) + " from " + p.source_period + " (" + p.source_frequency + ", " + num(p.age_months, 0) + " months old)";
            },
          },
        },
      },
      scales: {
        x: { title: { display: true, text: xTitle, color: ink }, ticks: { color: ink }, grid: { color: grid } },
        y: {
          title: { display: true, text: yTitle, color: ink },
          ticks: { color: ink, callback: (value) => (isPooled ? pct(value, 0) : num(value * 100, 0) + " pp") },
          grid: { color: grid },
        },
      },
    },
  });

  buildTable(byId("scatter-table"), [
    { key: "country_code", label: "Country" },
    { key: "period", label: "Period" },
    { label: "Rate", numeric: true, format: (row) => pct(row.outcome_rate, 1) },
    { label: "n", numeric: true, format: (row) => num(row.cohort_n, 0) },
    { label: "Signal value", numeric: true, format: (row) => num(row.value, 2) },
    { key: "source_period", label: "Value's own period" },
    { label: "Age (months)", numeric: true, format: (row) => num(row.age_months, 0) },
    { label: "Used in test", format: (row) => (row.excluded_from_tests ? "No: " + (row.exclusion_reason || "") : "Yes") },
  ], points);

  // 3. The selected result, in words.
  const box = byId("challenge-result");
  clear(box);
  let chosen = null;
  for (const row of results) {
    if (row.indicator === indicator && row.view === view) {
      chosen = row;
    }
  }
  if (analysisSet === "descriptive") {
    // The test results above belong to the country x year rows; these quarterly rows are never tested.
    box.appendChild(el("p", "Descriptive only: no test is run on these quarterly rows.", "analysis-label"));
    box.appendChild(el("p", "Quarterly senior rows hold 1–8 people each, so rates jump between 0% and 100%. " +
      "They are shown to make that noise visible; the formal test uses country × year rows (D-36).", "muted"));
    chosen = null;
  }
  if (chosen) {
    box.appendChild(el("p", chosen.result, "analysis-label"));
    const detail = "rho " + num(chosen.rho, 2) + " (bootstrap 95% " + num(chosen.ci_low, 2) + " to " + num(chosen.ci_high, 2) +
      "), n = " + chosen.n_rows + " rows in " + chosen.n_countries + " countries" +
      (chosen.p_holm === null ? "" : ", Holm-adjusted p = " + num(chosen.p_holm, 2) + " (family of " + chosen.holm_family_size + ")");
    box.appendChild(el("p", detail));
    box.appendChild(el("p", chosen.caveat, "muted"));
  }
}

// ---------------------------------------------------------------------------------------------
// TRUST
// ---------------------------------------------------------------------------------------------

async function loadTrust(myLoad) {
  const answers = await Promise.all([
    fetchJson("/api/sources"),
    fetchJson("/api/quality"),
    fetchJson("/api/retention/sensitivity", { objective: state.objective }),
  ]);
  if (myLoad !== loadCounter) {
    return;
  }
  const sources = answers[0].sources;
  const quality = answers[1];
  const sensitivity = answers[2];

  // 1. Sources: status, freshness, licence, attribution.
  buildTable(byId("trust-sources"), [
    { key: "indicator", label: "Source" },
    { label: "Provider / dataset", format: (row) => row.provider + " · " + row.dataset },
    { label: "Status", format: (row) => statusText(row.status) },
    { label: "Fetched", format: (row) => row.fetched_at || "delivered pack" },
    { key: "latest_period", label: "Latest period" },
    { label: "Coverage", format: (row) => (row.coverage_first_period ? row.coverage_first_period + " to " + row.coverage_last_period : "–") },
    { label: "Frequency / lag", format: (row) => row.frequency + (row.publication_lag_months ? " / +" + row.publication_lag_months + " months" : "") },
    { label: "Licence", format: (row) => licenceCell(row) },
    { key: "note", label: "Note" },
  ], sources);

  // 2. Quality: reconciliation, statuses, flags.
  const hr = quality.report.hr;
  const rec = hr.reconciliation;
  byId("trust-reconciliation").textContent = rec.rows_in_file + " rows in the HR file − " + rec.duplicate_rows_removed +
    " repeated rows removed = " + rec.employees_out + " employees (" + (rec.balanced ? "reconciled" : "NOT reconciled") + ").";
  const statusTiles = byId("trust-status");
  clear(statusTiles);
  const statusMeaning = {
    INCLUDED: "used in the primary metrics",
    QUARANTINED: "unverified exits, added back only in the sensitivity run",
    EXCLUDED: "no usable hire date or impossible dates",
  };
  for (const [status, count] of Object.entries(hr.metric_status)) {
    const tile = el("div", null, "tile");
    tile.appendChild(el("div", status, "tile-label"));
    tile.appendChild(el("div", String(count), "tile-value"));
    tile.appendChild(el("div", statusMeaning[status] || "", "tile-detail"));
    statusTiles.appendChild(tile);
  }
  buildTable(byId("trust-flags"), [
    { key: "flag", label: "Flag" },
    { key: "rows", label: "Rows", numeric: true },
    { key: "effect", label: "Effect" },
    { key: "decision", label: "Decision" },
    { key: "meaning", label: "Meaning" },
  ], hr.flags);
  byId("trust-principle").textContent = quality.principle;

  // 3. Sensitivity for the selected objective.
  byId("trust-sensitivity-summary").textContent = objectiveMeta(state.objective).name + ": " + sensitivity.summary;
  const digits = state.objective === TURNOVER ? 2 : 1;
  buildTable(byId("trust-sensitivity"), [
    { key: "period", label: "Period" },
    { label: "Treatment", format: (row) => row.variant + ": " + (sensitivity.variants[row.variant] || "") },
    { label: "n", numeric: true, format: (row) => num(row.n, 0) },
    { label: "Rate", numeric: true, format: (row) => pct(row.rate, digits) },
    { label: "95% interval", numeric: true, format: (row) => (row.rate === null ? "–" : pct(row.ci_low, digits) + "–" + pct(row.ci_high, digits)) },
    { label: "Status", format: (row) => statusBadge(row.status) },
  ], sensitivity.rows);

  // 4. Coverage.
  buildTable(byId("trust-coverage"), [
    { key: "indicator", label: "Signal" },
    { key: "country_code", label: "Country" },
    { key: "frequency", label: "Frequency" },
    { key: "first_period", label: "First" },
    { key: "last_period", label: "Last" },
    { key: "observations", label: "Values", numeric: true },
    { key: "missing_periods", label: "Gaps", numeric: true },
    { key: "provisional_values", label: "Provisional", numeric: true },
  ], quality.report.indicators.coverage);
}

function statusText(status) {
  const words = {
    fresh: "fresh (fetched this run)",
    replayed: "replayed (saved snapshot)",
    stale: "STALE (fetch failed, last good snapshot)",
    unavailable: "UNAVAILABLE",
  };
  return words[status] || status || "–";
}

function licenceCell(row) {
  const wrapper = el("span");
  wrapper.appendChild(el("span", row.licence));
  if (row.terms_url) {
    wrapper.appendChild(document.createTextNode(" "));
    const link = el("a", "terms");
    link.href = row.terms_url;
    link.rel = "noopener";
    wrapper.appendChild(link);
  }
  return wrapper;
}

// ---------------------------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------------------------

async function init() {
  setupTabs();
  try {
    fillFilters(await fetchJson("/api/filters"));
  } catch (error) {
    showMessage("explore", "error", errorText(error));
    byId("explore-content").hidden = true;
    loadHealth();
    return;
  }
  loadHealth();

  const filterIds = ["f-objective", "f-country", "f-segment", "f-from", "f-to", "f-variant"];
  for (const id of filterIds) {
    byId(id).addEventListener("change", function () {
      readFilters();
      loadCurrentTab();
    });
  }
  for (const id of ["u-indicator", "c-indicator", "c-view", "c-set"]) {
    byId(id).addEventListener("change", loadCurrentTab);
  }
  readFilters();
  loadCurrentTab();
}

document.addEventListener("DOMContentLoaded", init);
