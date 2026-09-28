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

const VIEWS = ["overview", "explore", "evidence"]; // main navigation (D-87)
const TABS = ["explore", "understand", "challenge"]; // the Explore switch: detail, signals, relationships
const TAB_ADDRESS = { explore: "detail", understand: "signals", challenge: "relationships" };
const TURNOVER = "REGRETTED_TURNOVER_12M";
const FILTER_SCOPE = {
  challenge: {
    filters: ["f-segment", "f-from", "f-to", "f-variant"],
    hint: "Relationships: the formal tests always use all years, all employees and the primary data treatment (D-35, D-55). Country only highlights that country's points.",
  },
  trust: {
    filters: ["f-country", "f-segment", "f-from", "f-to", "f-variant"],
    hint: "Evidence covers the whole data set, so the filters do not apply here.",
    hideRow: true, // D-93: no filter applies, so the row is hidden and only the note stays
  },
};
const SEGMENT_DISABLED_HINT = "Segments apply to hire cohorts only. Regretted turnover is measured for all employees.";
const COUNTRIES = ["GR", "RO", "PL", "IT", "IE", "BG"];

const state = {
  view: "overview", // D-87
  tab: "explore", // Explore sub-view
  filters: null, // the /api/filters response
  objective: "NEW_HIRE_6M",
  country: "ALL",
  segments: {}, // D-86: {dimension: value}, combined with AND
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
  return "Target " + sign + " " + targetPct(meta);
}

/** The target as a percentage: 0.86 -> "86%", 0.075 -> "7.5%". */
function targetPct(meta) {
  const digits = meta.objective_id === TURNOVER ? 1 : 0;
  return pct(meta.target, digits);
}

/** 1804 -> "1,804". */
function count(value) {
  return Number(value).toLocaleString("en-US");
}

/** "New-hire six-month retention" -> "new-hire six-month retention" (for use inside a sentence). */
function lowerFirst(text) {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

// ---------------------------------------------------------------------------------------------
// Findings (D-84, D-85): each tab opens with a plain-language sentence built from the data on screen,
// so a reviewer, an HR reader or the presenter can read the answer before the evidence.
// Wording follows D-63: verdicts come from the 95% interval; associations are never causal.
// ---------------------------------------------------------------------------------------------

/** Write the finding sentence (+ optional status pill) and the "What this means" line of a tab. */
function setFinding(tab, sentence, status, meaning) {
  const finding = byId(tab + "-finding");
  clear(finding);
  finding.appendChild(document.createTextNode(sentence));
  if (status !== undefined) {
    finding.appendChild(statusBadge(status));
  }
  const meaningBox = byId(tab + "-meaning");
  clear(meaningBox);
  if (meaning) {
    meaningBox.appendChild(el("strong", "What this means: "));
    meaningBox.appendChild(document.createTextNode(meaning));
  }
}

function clearFinding(tab) {
  if (!byId(tab + "-finding")) {
    return; // the Overview has a findings list instead
  }
  clear(byId(tab + "-finding"));
  clear(byId(tab + "-meaning"));
  if (byId(tab + "-next")) {
    clear(byId(tab + "-next"));
  }
}

/** "What would settle this" line under a finding (D-92: what further evidence would be needed). */
function setNext(tab, text) {
  const box = byId(tab + "-next");
  clear(box);
  if (text) {
    box.appendChild(el("strong", "What would settle this: "));
    box.appendChild(document.createTextNode(text));
  }
}

/** 95% Wilson interval, as in the pipeline (service/stats.py, D-33). */
function wilsonBounds(rate, n) {
  const z = 1.96;
  const denominator = 1 + (z * z) / n;
  const centre = (rate + (z * z) / (2 * n)) / denominator;
  const half = (z * Math.sqrt((rate * (1 - rate)) / n + (z * z) / (4 * n * n))) / denominator;
  return [centre - half, centre + half];
}

/** Smallest n at which the same rate would give a 95% interval that no longer includes the target; null if unrealistic. */
function hiresNeeded(rate, target) {
  if (Math.abs(rate - target) < 0.002) {
    return null; // the rate sits on the target: no sample size settles it
  }
  const settled = function (n) {
    const bounds = wilsonBounds(rate, n);
    return rate > target ? bounds[0] > target : bounds[1] < target;
  };
  let high = 1;
  while (!settled(high)) {
    high *= 2;
    if (high > 10000000) {
      return null;
    }
  }
  let low = Math.floor(high / 2);
  while (high - low > 1) {
    const middle = Math.floor((low + high) / 2);
    if (settled(middle)) {
      high = middle;
    } else {
      low = middle;
    }
  }
  return high;
}

/**
 * The verdict in words, from the interval and the target (D-75).
 * Example: not_met, at_least 90% -> "The whole 95% range (72.9%–82.7%) is below the 90% target, so the target is not met."
 */
function verdictSentence(row, meta, digits) {
  const range = "(" + pct(row.ci_low, digits) + "–" + pct(row.ci_high, digits) + ")";
  const target = targetPct(meta);
  const goodSide = meta.direction === "at_least" ? "above" : "below";
  const badSide = meta.direction === "at_least" ? "below" : "above";
  if (row.status === "met") {
    return "The whole 95% range " + range + " is " + goodSide + " the " + target + " target, so the target is met.";
  }
  if (row.status === "not_met") {
    return "The whole 95% range " + range + " is " + badSide + " the " + target + " target, so the target is not met.";
  }
  if (row.status === "inconclusive") {
    return "The 95% range " + range + " includes the " + target + " target, so the data cannot yet say whether it is met.";
  }
  return "No verdict is given for this slice.";
}

/**
 * Summarise the status of each year in one phrase.
 * Example: all inconclusive 2021-2025 -> "Inconclusive in every year from 2021 to 2025."
 */
function yearPattern(rows, periodKey) {
  const words = { met: "met", not_met: "not met", inconclusive: "inconclusive" };
  // 1. Keep only the years that have a verdict.
  const judged = [];
  for (const row of rows) {
    if (row.status) {
      judged.push(row);
    }
  }
  if (judged.length === 0) {
    return "";
  }
  const first = String(judged[0][periodKey]).slice(0, 4);
  const last = String(judged[judged.length - 1][periodKey]).slice(0, 4);

  // 2. Group the years by status.
  const groups = {};
  for (const row of judged) {
    if (!groups[row.status]) {
      groups[row.status] = [];
    }
    groups[row.status].push(String(row[periodKey]).slice(0, 4));
  }

  // 3. One status for every year, or a list per status.
  const statuses = Object.keys(groups);
  if (statuses.length === 1) {
    const word = words[statuses[0]];
    if (judged.length === 1) {
      return word.charAt(0).toUpperCase() + word.slice(1) + " in " + first + ".";
    }
    return word.charAt(0).toUpperCase() + word.slice(1) + " in every year from " + first + " to " + last + ".";
  }
  const parts = [];
  for (const status of ["met", "not_met", "inconclusive"]) {
    if (groups[status]) {
      parts.push(words[status] + " in " + groups[status].join(", "));
    }
  }
  return "By year: " + parts.join("; ") + ".";
}

/** " in Romania" / "" for the whole company. */
function placeText(country) {
  return country === "ALL" ? "" : " in " + countryName(country);
}

/** " (Fixed Term employees)" / "". */
function segmentText() {
  const values = segmentValues();
  if (values.length === 0) {
    return "";
  }
  return " (segment: " + values.join(", ") + ")";
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
      if (Array.isArray(value)) {
        for (const item of value) {
          query.append(key, item); // e.g. segment=a&segment=b (D-86)
        }
      } else if (value !== null && value !== undefined && value !== "") {
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

/** The selected hire years as text (D-90): "2021–2025", or "2025" for one year. */
function yearsText() {
  const range = yearRange();
  const last = range.max - 1;
  return range.min === last ? String(last) : range.min + "–" + last;
}

/** True when the years filter covers every available year (the whole period). */
function allYearsSelected() {
  const years = state.filters.years;
  const range = yearRange();
  return range.min === Number(years[0]) && range.max - 1 === Number(years[years.length - 1]);
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
        { label: meta.objective_id === TURNOVER ? "Turnover rate" : "Retention rate", data: rateData, borderColor: accent, backgroundColor: accent, borderWidth: 2, pointRadius: 3 },
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
// Workforce segment (D-86): one button opens a small panel with one list per field.
// The chosen values combine with AND and are sent as repeated `segment=dimension:value` parameters.
// ---------------------------------------------------------------------------------------------

const SEGMENT_FIELDS = ["employment_type", "career_level", "business_unit", "job_family"];

/** state.segments as API values. Example: {employment_type: "Fixed Term"} -> ["employment_type:Fixed Term"] */
function segmentList() {
  const list = [];
  for (const dimension of SEGMENT_FIELDS) {
    if (state.segments[dimension]) {
      list.push(dimension + ":" + state.segments[dimension]);
    }
  }
  return list;
}

/** Just the chosen values. Example: ["Fixed Term", "Manager"] */
function segmentValues() {
  const values = [];
  for (const dimension of SEGMENT_FIELDS) {
    if (state.segments[dimension]) {
      values.push(state.segments[dimension]);
    }
  }
  return values;
}

/** "employment_type = Fixed Term and career_level = Manager" ("" when nothing is chosen). */
function segmentDescription() {
  const parts = [];
  for (const item of segmentList()) {
    parts.push(item.replace(":", " = "));
  }
  return parts.join(" and ");
}

/** Fill one panel list with "Any" + values, keeping the current choice when it is still valid. */
function fillSegmentSelect(dimension, values, selected) {
  const options = [{ value: "", label: "Any" }];
  for (const value of values) {
    options.push({ value: value, label: value });
  }
  const keep = values.indexOf(selected) >= 0 ? selected : "";
  fillSelect(byId("seg-" + dimension), options, keep);
}

/** Job families follow the chosen business unit (each family belongs to one unit). */
function fillJobFamilies(selected) {
  const unit = byId("seg-business_unit").value;
  const families = unit ? state.filters.job_families_by_unit[unit] || [] : state.filters.segments.job_family;
  fillSegmentSelect("job_family", families, selected);
}

function openSegmentPanel() {
  // 1. Show the current choices in the lists.
  for (const dimension of SEGMENT_FIELDS) {
    if (dimension !== "job_family") {
      fillSegmentSelect(dimension, state.filters.segments[dimension], state.segments[dimension] || "");
    }
  }
  fillJobFamilies(state.segments.job_family || "");
  // 2. Open the panel and move focus into it.
  byId("segment-panel").hidden = false;
  byId("f-segment").setAttribute("aria-expanded", "true");
  byId("seg-employment_type").focus();
}

function closeSegmentPanel(returnFocus) {
  byId("segment-panel").hidden = true;
  byId("f-segment").setAttribute("aria-expanded", "false");
  if (returnFocus) {
    byId("f-segment").focus();
  }
}

/** Show the choice on the button and as removable chips under the filter row. */
function updateSegmentUi() {
  const values = segmentValues();
  byId("f-segment").textContent = values.length ? values.join(", ") : "All employees";
  const chips = byId("segment-chips");
  clear(chips);
  for (const dimension of SEGMENT_FIELDS) {
    const value = state.segments[dimension];
    if (!value) {
      continue;
    }
    const chip = el("button");
    chip.type = "button";
    chip.setAttribute("data-dimension", dimension);
    chip.setAttribute("aria-label", "Remove filter " + value);
    chip.appendChild(el("span", value));
    chip.appendChild(el("span", "✕", "chip-x"));
    chip.addEventListener("click", function () {
      delete state.segments[dimension];
      updateSegmentUi();
      loadCurrentTab();
    });
    chips.appendChild(chip);
  }
  const active = values.length > 0;
  byId("segment-bar").hidden = !active;
  chips.hidden = !active;
}

/** Apply the panel's lists to the filters and reload the visible tab. */
function applySegmentPanel() {
  state.segments = {};
  for (const dimension of SEGMENT_FIELDS) {
    const value = byId("seg-" + dimension).value;
    if (value) {
      state.segments[dimension] = value;
    }
  }
  closeSegmentPanel(true);
  updateSegmentUi();
  loadCurrentTab();
}

function setupSegmentPanel() {
  const button = byId("f-segment");
  const panel = byId("segment-panel");
  button.addEventListener("click", function () {
    if (panel.hidden) {
      openSegmentPanel();
    } else {
      closeSegmentPanel(false);
    }
  });
  byId("seg-business_unit").addEventListener("change", function () {
    fillJobFamilies(byId("seg-job_family").value);
  });
  byId("seg-apply").addEventListener("click", applySegmentPanel);
  byId("seg-clear").addEventListener("click", function () {
    for (const dimension of SEGMENT_FIELDS) {
      byId("seg-" + dimension).value = "";
    }
    applySegmentPanel();
  });
  byId("segment-clear-all").addEventListener("click", function () {
    state.segments = {};
    updateSegmentUi();
    loadCurrentTab();
  });
  // Escape closes without applying; a click outside closes too.
  panel.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeSegmentPanel(true);
      event.preventDefault();
    }
  });
  document.addEventListener("click", function (event) {
    if (!panel.hidden && !panel.contains(event.target) && event.target !== button) {
      closeSegmentPanel(false);
    }
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
  fillSelect(byId("e-objective"), objectives, state.objective); // Evidence's own choice (D-91)

  const countries = [];
  for (const country of filters.countries) {
    countries.push({ value: country.code, label: country.name });
  }
  fillSelect(byId("f-country"), countries, state.country);

  // Segment: the panel's lists are filled when it opens (D-86).
  updateSegmentUi();

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
  if (state.objective === TURNOVER) {
    state.segments = {};
    closeSegmentPanel(false);
    updateSegmentUi();
  }
  applyFilterScope();
}

/**
 * Disable the filters the current view does not use, with the reason as a tooltip and one visible line (D-91).
 * Relationships: the formal tests are fixed (all years, all employees, primary data). Evidence: the whole data set.
 * Disabling never clears a choice, so a segment is still there when you come back.
 */
function applyFilterScope() {
  const panel = currentPanel();
  const locked = FILTER_SCOPE[panel] || { filters: [], hint: "" };
  const note = byId("filter-scope-note");
  note.textContent = locked.hint;
  note.hidden = locked.filters.length === 0;
  byId("filters").hidden = Boolean(locked.hideRow);
  byId("segment-bar").hidden = Boolean(locked.hideRow) || segmentList().length === 0;
  for (const id of ["f-country", "f-segment", "f-from", "f-to", "f-variant"]) {
    let hint = locked.filters.indexOf(id) >= 0 ? locked.hint : "";
    if (!hint && id === "f-segment" && state.objective === TURNOVER) {
      hint = SEGMENT_DISABLED_HINT; // D-88
    }
    const control = byId(id);
    control.disabled = hint !== "";
    if (id === "f-segment" && control.disabled) {
      closeSegmentPanel(false);
    }
    // Disabled controls get no hover events in some browsers, so the hint also sits on the wrapper.
    for (const node of [control, control.parentElement]) {
      if (hint) {
        node.title = hint;
      } else {
        node.removeAttribute("title");
      }
    }
  }
}

function readFilters() {
  const previousObjective = state.objective;
  state.objective = byId("f-objective").value;
  state.country = byId("f-country").value;
  state.yearFrom = Number(byId("f-from").value);
  state.yearTo = Number(byId("f-to").value);
  state.variant = byId("f-variant").value;
  if (state.objective !== previousObjective) {
    byId("e-objective").value = state.objective; // Evidence follows Explore until changed there
    fillVariants();
    state.variant = byId("f-variant").value;
  }
}

function commonParams() {
  return {
    objective: state.objective,
    country: state.country,
    variant: state.variant,
    segment: segmentList(),
    year_from: state.yearFrom,
    year_to: state.yearTo,
  };
}

/** Mark one button of a tab list as selected and show only its panel. */
function showSelected(names, prefix, panelPrefix, selectedName, moveFocus) {
  for (const name of names) {
    const button = byId(prefix + name);
    const selected = name === selectedName;
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.tabIndex = selected ? 0 : -1;
    byId(panelPrefix + name).hidden = !selected;
    if (selected && moveFocus) {
      button.focus();
    }
  }
}

/** The address of the current view, e.g. "#explore/relationships" (bookmarkable, survives a reload). */
function writeAddress() {
  let address = "#" + state.view;
  if (state.view === "explore") {
    address += "/" + TAB_ADDRESS[state.tab];
  }
  if (window.location.hash !== address) {
    history.replaceState(null, "", address);
  }
}

/** Read the address into state.view / state.tab. Unknown addresses fall back to the Overview. */
function readAddress() {
  const parts = window.location.hash.replace("#", "").split("/");
  state.view = VIEWS.indexOf(parts[0]) >= 0 ? parts[0] : "overview";
  if (state.view === "explore") {
    state.tab = "explore";
    for (const tab of TABS) {
      if (TAB_ADDRESS[tab] === parts[1]) {
        state.tab = tab;
      }
    }
  }
}

/** Show the current view and Explore sub-view, update the address, load the data. */
function showCurrent(moveFocusTo) {
  showSelected(VIEWS, "nav-", "view-", state.view, moveFocusTo === "view");
  showSelected(TABS, "tab-", "panel-", state.tab, moveFocusTo === "tab");
  applyFilterScope();
  writeAddress();
  loadCurrentTab();
}

function selectView(view, moveFocus) {
  state.view = view;
  showCurrent(moveFocus ? "view" : null);
}

function selectTab(tab, moveFocus) {
  state.view = "explore";
  state.tab = tab;
  showCurrent(moveFocus ? "tab" : null);
}

/** Click and arrow-key handling for one tab list (WAI-ARIA tabs pattern). */
function setupTabList(names, prefix, select) {
  for (const name of names) {
    const button = byId(prefix + name);
    button.addEventListener("click", function () {
      select(name, false);
    });
    button.addEventListener("keydown", function (event) {
      const index = names.indexOf(name);
      if (event.key === "ArrowRight") {
        select(names[(index + 1) % names.length], true);
        event.preventDefault();
      } else if (event.key === "ArrowLeft") {
        select(names[(index + names.length - 1) % names.length], true);
        event.preventDefault();
      }
    });
  }
}

function setupTabs() {
  setupTabList(VIEWS, "nav-", selectView);
  setupTabList(TABS, "tab-", selectTab);
  window.addEventListener("hashchange", function () {
    readAddress();
    showCurrent(null);
  });
}

/** The panel whose data is on screen: "overview", "trust" (Evidence) or an Explore sub-view. */
function currentPanel() {
  if (state.view === "overview") {
    return "overview";
  }
  if (state.view === "evidence") {
    return "trust";
  }
  return state.tab;
}

async function loadCurrentTab() {
  const loaders = {
    overview: loadOverview,
    explore: loadExplore,
    understand: loadUnderstand,
    challenge: loadChallenge,
    trust: loadTrust,
  };
  const name = currentPanel();
  const panel = byId("panel-" + name);
  const myLoad = ++loadCounter;
  panel.classList.add("loading");
  panel.setAttribute("aria-busy", "true");
  hideMessage(name);
  try {
    await loaders[name](myLoad);
  } catch (error) {
    if (myLoad === loadCounter) {
      clearFinding(name);
      showMessage(name, "error", errorText(error));
      if (name === "explore") {
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
// OVERVIEW (D-87): three objective cards, one trend, market context, key findings.
// Everything is built from the same API answers the other views use.
// ---------------------------------------------------------------------------------------------

const OVERVIEW_SIGNALS = ["unemployment", "inflation", "job_vacancy"];

async function loadOverview(myLoad) {
  const country = state.country;
  const segment = segmentList();
  const hireVariant = state.variant === "unknown_as_regretted" ? "primary" : state.variant;
  const hireParams = { country: country, variant: hireVariant, segment: segment };
  const years = { year_from: state.yearFrom, year_to: state.yearTo };

  // 1. One request per piece of data, all at once.
  const requests = [
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "NEW_HIRE_6M", grain: "period" }, hireParams, years)),
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "SENIOR_HIRE_12M", grain: "period" }, hireParams, years)),
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "NEW_HIRE_6M", grain: "year" }, hireParams, years)),
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "SENIOR_HIRE_12M", grain: "year" }, hireParams, years)),
    fetchJson("/api/retention/turnover", Object.assign({ country: country, variant: state.variant, year_end_only: true }, years)),
    fetchJson("/api/association"),
    fetchJson("/api/quality"),
    fetchJson("/api/retention/segments", Object.assign({ objective: "SENIOR_HIRE_12M" }, hireParams, years)),
    fetchJson("/api/retention/segments", Object.assign({ objective: "NEW_HIRE_6M" }, hireParams, years)),
    fetchJson("/api/retention/sensitivity", { objective: "NEW_HIRE_6M" }),
    fetchJson("/api/retention/sensitivity", { objective: "SENIOR_HIRE_12M" }),
    fetchJson("/api/retention/sensitivity", { objective: TURNOVER }),
  ];
  const signalsFrom = requests.length; // the indicator answers follow
  for (const indicator of OVERVIEW_SIGNALS) {
    requests.push(fetchJson("/api/indicators", Object.assign({ indicator: indicator, country: country === "ALL" ? null : country }, years)));
  }
  const answers = await Promise.all(requests);
  if (myLoad !== loadCounter) {
    return;
  }
  const newHire = answers[0].rows[0];
  const senior = answers[1].rows[0];
  const newHireYears = answers[2].rows;
  const seniorYears = answers[3].rows;
  const decembers = answers[4].rows;
  const lastDecember = decembers.length > 0 ? decembers[decembers.length - 1] : null;

  // 2. Cards: the selected hire years; turnover = the 12 months to the last selected December (D-90).
  byId("overview-help").textContent = "Each card is the " + yearsText() + " result for the filters above " +
    "(turnover: the 12 months to the last selected December). Select a card to explore it.";
  const cards = byId("overview-cards");
  clear(cards);
  cards.appendChild(overviewCard("NEW_HIRE_6M", "New-hire retention, 6 months, " + yearsText(), newHire, 1));
  cards.appendChild(overviewCard("SENIOR_HIRE_12M", "Senior-hire retention, 12 months, " + yearsText(), senior, 1));
  const turnoverTitle = "Regretted turnover, " + (lastDecember ? "12 months to " + lastDecember.month_end : "last 12 months");
  const turnoverCard = overviewCard(TURNOVER, turnoverTitle, lastDecember, 2);
  if (segment.length > 0) {
    // Segments exist for hire cohorts only (D-77, D-88).
    turnoverCard.insertBefore(el("span", "All employees: the segment filter applies to the hire objectives only.", "card-detail"),
      turnoverCard.lastChild);
  }
  cards.appendChild(turnoverCard);

  // 3. Trend by hire year for the two hire objectives (both are rates, so one axis).
  drawOverviewTrend(newHireYears, seniorYears);

  // 4. Market context: one sentence per signal.
  const market = byId("overview-market");
  clear(market);
  for (let index = 0; index < OVERVIEW_SIGNALS.length; index++) {
    const indicator = OVERVIEW_SIGNALS[index];
    const item = el("li");
    item.appendChild(el("strong", indicatorLabel(indicator)));
    const sentence = signalMovement(answers[signalsFrom + index].rows, indicator, country, false);
    item.appendChild(el("span", sentence || "No values in the selected years.", "market-text"));
    market.appendChild(item);
  }

  // 5. Key findings.
  const findings = byId("overview-findings");
  clear(findings);
  const lines = [
    hireFinding("SENIOR_HIRE_12M", senior, seniorYears),
    hireFinding("NEW_HIRE_6M", newHire, newHireYears),
    turnoverFinding(decembers),
    stabilityFinding([["SENIOR_HIRE_12M", answers[7]], ["NEW_HIRE_6M", answers[8]]]),
    associationFinding(answers[5]),
    qualityFinding(answers[6].report.hr, [answers[9], answers[10], answers[11]]),
  ];
  for (const line of lines) {
    if (line) {
      findings.appendChild(el("li", line));
    }
  }
}

/** A card that opens its objective in Explore. row = the whole-period (or latest December) row. */
function overviewCard(objectiveId, title, row, digits) {
  const meta = objectiveMeta(objectiveId);
  const card = el("button", null, "overview-card");
  card.type = "button";
  card.setAttribute("data-testid", "overview-card");
  card.setAttribute("data-objective", objectiveId);
  card.appendChild(el("span", title, "card-title"));
  if (!row || row.n === 0) {
    card.appendChild(el("span", "–", "card-value"));
    card.appendChild(statusBadge(null));
    card.appendChild(el("span", "No mature hires match these filters.", "card-detail"));
  } else {
    card.appendChild(el("span", pct(row.rate, digits), "card-value"));
    card.appendChild(statusBadge(row.status));
    const n = row.n !== undefined ? row.n : row.avg_headcount;
    card.appendChild(el("span", "95% CI " + pct(row.ci_low, digits) + "–" + pct(row.ci_high, digits) +
      ", n = " + count(Math.round(n)) + ". " + targetText(meta) + ".", "card-detail"));
  }
  card.appendChild(el("span", "Explore this objective", "card-link"));
  card.addEventListener("click", function () {
    openObjective(objectiveId);
  });
  return card;
}

/** Switch the Explore objective filter and open Objective detail. */
function openObjective(objectiveId) {
  byId("f-objective").value = objectiveId;
  readFilters();
  state.view = "explore";
  state.tab = "explore";
  showCurrent(null);
}

function drawOverviewTrend(newHireYears, seniorYears) {
  const series = [
    { id: "NEW_HIRE_6M", label: "New-hire 6 months", rows: newHireYears, color: cssVar("--accent") },
    { id: "SENIOR_HIRE_12M", label: "Senior-hire 12 months", rows: seniorYears, color: cssVar("--c-RO") },
  ];
  const range = yearRange();
  const datasets = [];
  const tableRows = [];
  for (const item of series) {
    const meta = objectiveMeta(item.id);
    const data = [];
    for (const row of item.rows) {
      if (row.rate === null) {
        continue; // hires not yet measurable
      }
      data.push({ x: xFromPeriod(row.period), y: row.rate, row: row });
      tableRows.push(Object.assign({ objective: item.label }, row));
    }
    datasets.push({ label: item.label, data: data, borderColor: item.color, backgroundColor: item.color, borderWidth: 2, pointRadius: 4 });
    datasets.push({
      label: item.label + " target",
      data: [{ x: range.min, y: meta.target }, { x: range.max, y: meta.target }],
      borderColor: item.color,
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
    });
  }
  const options = baseOptions("Retained", function (value) {
    return pct(value, 0);
  }, range);
  options.plugins.tooltip.callbacks = {
    title: function (items) {
      return items.length && items[0].raw.row ? items[0].raw.row.period : "";
    },
    label: function (item) {
      if (!item.raw.row) {
        return item.dataset.label + " " + pct(item.raw.y, 0);
      }
      const row = item.raw.row;
      return item.dataset.label + ": " + pct(row.rate, 1) + " (95% CI " + pct(row.ci_low, 1) + "–" +
        pct(row.ci_high, 1) + ", n=" + row.n + ")";
    },
  };
  drawChart("overview-trend-chart", { type: "line", data: { datasets: datasets }, options: options });
  buildTable(byId("overview-trend-table"), [
    { key: "objective", label: "Objective" },
    { key: "period", label: "Hire year" },
    { key: "n", label: "Mature hires (n)", numeric: true },
    { label: "Rate", numeric: true, format: (row) => pct(row.rate, 1) },
    { label: "95% interval", numeric: true, format: (row) => pct(row.ci_low, 1) + "–" + pct(row.ci_high, 1) },
    { label: "Status", format: (row) => statusBadge(row.status) },
  ], tableRows);
}

/** Example: "Senior-hire twelve-month retention is not met: 78.2% against the 90% target; not met in every year from 2021 to 2024." */
function hireFinding(objectiveId, whole, years) {
  const meta = objectiveMeta(objectiveId);
  if (!whole || whole.n === 0) {
    return meta.name + ": no mature hires match these filters.";
  }
  const words = { met: "met", not_met: "not met", inconclusive: "inconclusive (the 95% range includes the target)" };
  let line = meta.name + " is " + (words[whole.status] || "without a verdict") + ": " + pct(whole.rate, 1) +
    " against the " + targetPct(meta) + " target";
  const pattern = yearPattern(years.filter((row) => row.n > 0), "period");
  if (pattern) {
    line += "; " + lowerFirst(pattern);
  } else {
    line += ".";
  }
  return line;
}

/** Example: "Regretted turnover is met (5.11% against at most 7.5%), but it rose from 3.30% in 2024 to 5.11% in 2025." */
function turnoverFinding(decembers) {
  if (decembers.length === 0) {
    return "";
  }
  const meta = objectiveMeta(TURNOVER);
  const last = decembers[decembers.length - 1];
  const words = { met: "met", not_met: "not met", inconclusive: "inconclusive" };
  let line = "Regretted turnover is " + (words[last.status] || "without a verdict") + " (" + pct(last.rate, 2) +
    " against at most " + targetPct(meta) + ")";
  if (decembers.length >= 2) {
    const before = decembers[decembers.length - 2];
    if (last.rate > before.rate) {
      line += ", but it rose from " + pct(before.rate, 2) + " in " + before.month_end.slice(0, 4) + " to " +
        pct(last.rate, 2) + " in " + last.month_end.slice(0, 4);
    } else if (last.rate < before.rate) {
      line += ", and it fell from " + pct(before.rate, 2) + " in " + before.month_end.slice(0, 4) + " to " +
        pct(last.rate, 2) + " in " + last.month_end.slice(0, 4);
    }
  }
  return line + ".";
}

/** Counts the formal tests of all objectives with a clear association (D-63 wording). */
function associationFinding(answer) {
  const formal = answer.rows.filter((row) => row.is_formal);
  const clearRows = formal.filter((row) => row.p_holm !== null && row.p_holm < answer.alpha);
  if (clearRows.length === 0) {
    return "None of the " + formal.length + " formal within-country tests shows a clear association between " +
      "the external signals and the three objectives. This is associative, not causal, and small samples limit inference.";
  }
  return clearRows.length + " of " + formal.length + " formal within-country tests show an association " +
    "(associative, not causal); see Relationships in Explore.";
}

/** Example: "Across segments, senior-hire ... is not met in all 6 segments; new-hire ... is inconclusive overall but met for ...". */
function stabilityFinding(pairs) {
  const clauses = pairs.map((pair) => stabilityClause(pair[0], pair[1])).filter((clause) => clause);
  if (clauses.length === 0) {
    return "";
  }
  return "Across segments, " + clauses.join("; ") + " (descriptive; see Explore).";
}

/**
 * Data health (D-92), e.g. "2,407 HR rows reconcile to 2,400 employees; 12 uncertain exits are quarantined and 10 records
 * excluded. Treating the uncertain records differently changes no verdict for any objective (details in Evidence)."
 */
function qualityFinding(hr, sensitivities) {
  const rec = hr.reconciliation;
  const statuses = hr.metric_status;
  let line = count(rec.rows_in_file) + " HR rows " + (rec.balanced ? "reconcile" : "do NOT reconcile") + " to " +
    count(rec.employees_out) + " employees; " + count(statuses.QUARANTINED || 0) + " uncertain exits are quarantined and " +
    count(statuses.EXCLUDED || 0) + " records excluded.";
  const changed = sensitivities.filter((answer) => answer.verdict_changes.length > 0);
  if (changed.length === 0) {
    line += " Treating the uncertain records differently changes no verdict for any objective";
  } else {
    line += " Treating the uncertain records differently changes a verdict for " +
      joinWords(changed.map((answer) => lowerFirst(answer.objective.name)));
  }
  return line + " (details in Evidence).";
}

// ---------------------------------------------------------------------------------------------
// EXPLORE
// ---------------------------------------------------------------------------------------------

async function loadExplore(myLoad) {
  const meta = objectiveMeta(state.objective);
  byId("explore-title").textContent = meta.name + ", " + countryName(state.country);
  const label = byId("explore-label");
  label.textContent = targetText(meta) + ". " + meta.label + "." + (segmentList().length ? " Segment " + segmentDescription() + "." : "");

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
    fetchJson("/api/retention/segments", params),
  ]);
  if (myLoad !== loadCounter) {
    return; // a newer filter change is already loading
  }
  const stability = answers[3];
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
  byId("segments-card").hidden = false;
  byId("years-help-hires").hidden = false;

  // 1. Tiles: whole period + the latest selected year.
  const tiles = byId("explore-tiles");
  clear(tiles);
  const whole = period[0];
  // The API computes this row for the selected hire years (D-90).
  const periodText = String(whole.period).replace("-", "–");
  tiles.appendChild(rateTile(periodText + (allYearsSelected() ? " (whole period)" : " (selected years)"), whole, meta));
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

  // 5. The finding in words (D-84).
  const sentence = meta.name + placeText(state.country) + segmentText() + " was " + pct(whole.rate, 1) +
    " for hires in " + periodText + " (" + count(whole.retained) + " of " + count(whole.n) + " hires stayed). " +
    verdictSentence(whole, meta, 1) +
    (whole.small_sample ? " The sample is small (fewer than 10 hires), so read it with care." : "");
  setFinding("explore", sentence, whole.status, cohortMeaning(years, whole, totals, meta));
  setNext("explore", cohortNext(whole, meta));

  // 6. Segment stability (D-92).
  byId("segments-finding").textContent = stabilitySentence(stability);
  buildTable(byId("explore-segments"), [
    { label: "Field", format: (row) => DIMENSION_LABELS[row.dimension] || row.dimension },
    { key: "value", label: "Group" },
    { key: "n", label: "Mature hires (n)", numeric: true },
    { label: "Rate", numeric: true, format: (row) => pct(row.rate, 1) },
    { label: "95% interval", numeric: true, format: (row) => (row.rate === null ? "–" : pct(row.ci_low, 1) + "–" + pct(row.ci_high, 1)) },
    { label: "Status", format: (row) => statusBadge(row.status) },
    { label: "Compared with everyone", format: (row) => AGREEMENT_WORDS[row.agreement] },
  ], stability.rows);

  fillNotes(answers[0].notes.concat(["Values: " + answers[0].computed + "."]));
}

const DIMENSION_LABELS = { employment_type: "Employment type", career_level: "Career level", business_unit: "Business unit" };
const AGREEMENT_WORDS = {
  same: "Same verdict",
  clearer: "Clearer verdict",
  less_certain: "Less certain (smaller group)",
  opposite: "Opposite verdict",
  no_data: "No mature hires",
};
const VERDICT_WORDS = { met: "met", not_met: "not met", inconclusive: "inconclusive" };

/**
 * Segment stability in words (D-92).
 * Example: "The inconclusive verdict holds in 7 of 9 segments. Clearer: Permanent (met, 88.0%), Manager (met, 91.1%)."
 */
function stabilitySentence(answer) {
  const rows = answer.rows.filter((row) => row.agreement !== "no_data");
  if (!answer.overall || rows.length === 0) {
    return "No segment has mature hires for these filters.";
  }
  const verdict = VERDICT_WORDS[answer.overall.status] || "overall";
  const same = rows.filter((row) => row.agreement === "same").length;
  let text = same === rows.length
    ? "The " + verdict + " verdict holds in all " + rows.length + " segments."
    : "The " + verdict + " verdict holds in " + same + " of " + rows.length + " segments.";
  const groups = [["opposite", "Opposite"], ["clearer", "Clearer"], ["less_certain", "Less certain"]];
  for (const [agreement, label] of groups) {
    const names = rows.filter((row) => row.agreement === agreement)
      .map((row) => row.value + " (" + VERDICT_WORDS[row.status] + ", " + pct(row.rate, 1) + ")");
    if (names.length > 0) {
      text += " " + label + ": " + names.join(", ") + ".";
    }
  }
  return text;
}

/** One objective for the Overview, e.g. "new-hire ... is inconclusive overall but met for Permanent and Manager hires". */
function stabilityClause(objectiveId, answer) {
  const name = lowerFirst(objectiveMeta(objectiveId).name);
  const rows = answer.rows.filter((row) => row.agreement !== "no_data");
  if (!answer.overall || rows.length === 0) {
    return "";
  }
  const verdict = VERDICT_WORDS[answer.overall.status];
  if (rows.every((row) => row.agreement === "same")) {
    return name + " is " + verdict + " in all " + rows.length + " segments";
  }
  const byStatus = {};
  for (const row of rows.filter((item) => item.agreement === "clearer" || item.agreement === "opposite")) {
    byStatus[row.status] = (byStatus[row.status] || []).concat([row.value]);
  }
  const parts = Object.keys(byStatus).map((status) => VERDICT_WORDS[status] + " for " + joinWords(byStatus[status]) + " hires");
  if (parts.length === 0) {
    const unsure = rows.filter((row) => row.agreement === "less_certain").length;
    return name + " is " + verdict + " overall; " + unsure + " smaller segments are inconclusive";
  }
  return name + " is " + verdict + " overall but " + parts.join(" and ");
}

/** ["A"] -> "A"; ["A", "B"] -> "A and B"; ["A", "B", "C"] -> "A, B and C". */
function joinWords(words) {
  if (words.length <= 1) {
    return words.join("");
  }
  return words.slice(0, -1).join(", ") + " and " + words[words.length - 1];
}

/** What further evidence would settle a hire objective (D-92). */
function cohortNext(whole, meta) {
  if (whole.status === "inconclusive") {
    const needed = hiresNeeded(whole.rate, meta.target);
    if (needed === null) {
      return "The rate sits almost exactly on the target, so more hires alone would not settle it.";
    }
    return "At the same rate, about " + count(needed) + " mature hires would be needed for the 95% range to exclude the target (now " +
      count(whole.n) + "). More years of hires would give that.";
  }
  return "The verdict is clear with this sample. To act on it, the next evidence is why hires leave: exit reasons " +
    "(interviews, surveys) are not in this data set.";
}

/** "What this means" for a hire objective: the year pattern, the main exit reason, the hires not yet measurable. */
function cohortMeaning(years, whole, totals, meta) {
  const parts = [];
  const pattern = yearPattern(years.filter((row) => row.n > 0), "period");
  if (pattern) {
    parts.push(pattern);
  }
  const leavers = whole.n - whole.retained;
  if (leavers > 0) {
    let topType = null;
    for (const type of Object.keys(totals)) {
      if (topType === null || totals[type] > totals[topType]) {
        topType = type;
      }
    }
    const topCount = totals[topType];
    parts.push("Of the " + count(leavers) + " hires who left within the window, " + count(topCount) +
      (topCount === 1 ? " was a " + lowerFirst(topType) + " exit." : " were " + lowerFirst(topType) + " exits."));
  }
  if (whole.immature_hires > 0) {
    const months = meta.objective_id === "NEW_HIRE_6M" ? "6" : "12";
    parts.push(count(whole.immature_hires) + " more hires joined too recently to complete " + months + " months, so they are not counted yet.");
  }
  return parts.join(" ");
}

function rateTile(title, row, meta) {
  const digits = rateDigits();
  const tile = el("div", null, "tile");
  tile.setAttribute("data-testid", "rate-tile");
  tile.appendChild(el("div", title, "tile-label"));
  tile.appendChild(el("div", pct(row.rate, digits), "tile-value"));
  tile.appendChild(statusBadge(row.status));
  const n = row.n !== undefined ? row.n : row.avg_headcount;
  const detail = "95% CI " + pct(row.ci_low, digits) + "–" + pct(row.ci_high, digits) + ", n = " + count(Math.round(n));
  tile.appendChild(el("div", detail, "tile-detail"));
  tile.appendChild(el("div", targetText(meta), "tile-detail"));
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
  byId("segments-card").hidden = true; // segments exist for hire cohorts only (D-77)
  byId("years-help-hires").hidden = true; // no hire windows in turnover

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

  // The finding in words (D-84), from the latest December value.
  if (decembers.length > 0) {
    const last = decembers[decembers.length - 1];
    const sentence = "Regretted turnover" + placeText(state.country) + " in the 12 months to " + last.month_end + " was " +
      pct(last.rate, 2) + " (" + count(last.regretted_exits) + " regretted exits, average headcount " +
      count(Math.round(last.avg_headcount)) + "). " + verdictSentence(last, meta, 2);
    setFinding("explore", sentence, last.status, turnoverMeaning(decembers, rows, meta));
    setNext("explore", "The data holds only employees hired since 2020 (D-23), so the early headcounts are too low. " +
      "A full-workforce extract, with people hired before 2020, would settle the early years; exits with an unknown " +
      "regretted flag are shown as a worst case in Evidence.");
  } else {
    setNext("explore", "");
    setFinding("explore", "No December value in the selected years, so no verdict is given. The chart shows the monthly trend.");
  }
  fillNotes(answer.notes);
}

/** "What this means" for turnover: years meeting the target, the change in the latest year, the 2021 ramp-up. */
function turnoverMeaning(decembers, rows, meta) {
  let met = 0;
  for (const row of decembers) {
    if (row.status === "met") {
      met += 1;
    }
  }
  const parts = ["The target was met in " + met + " of " + decembers.length + " years (December values)."];
  if (decembers.length >= 2) {
    const last = decembers[decembers.length - 1];
    const before = decembers[decembers.length - 2];
    const direction = last.rate > before.rate ? "rose" : last.rate < before.rate ? "fell" : "stayed";
    parts.push("It " + direction + " from " + pct(before.rate, 2) + " in " + before.month_end.slice(0, 4) +
      " to " + pct(last.rate, 2) + " in " + last.month_end.slice(0, 4) + ".");
  }
  const rampUp = rampUpText(rows, meta);
  if (rampUp) {
    parts.push(rampUp);
  }
  return parts.join(" ");
}

/**
 * The 2021 ramp-up (confirmed finding 6): months above the target while headcount was still small and growing.
 * Example: "In 2021 the monthly rate was above the target for 8 months (peak 10.40% in 2021-02) ..."
 */
function rampUpText(rows, meta) {
  const firstYear = String(state.filters.years[0]);
  const above = rows.filter((row) => row.month_end.slice(0, 4) === firstYear && row.rate !== null &&
    (meta.direction === "at_most" ? row.rate > meta.target : row.rate < meta.target));
  if (above.length === 0) {
    return "";
  }
  let peak = above[0];
  for (const row of above) {
    if (row.rate > peak.rate) {
      peak = row;
    }
  }
  return "In " + firstYear + " the monthly rate was above the target for " + above.length + " month" + (above.length === 1 ? "" : "s") +
    " (peak " + pct(peak.rate, 2) + " in " + peak.month_end.slice(0, 7) + ") while headcount was still small and growing: " +
    "a ramp-up effect of data that holds only employees hired since 2020 (D-23), not a verdict.";
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
  const segment = segmentList();

  // 1. Status of all three objectives for the selected country (whole period / latest December).
  const years = { year_from: state.yearFrom, year_to: state.yearTo };
  const hireParams = { country: country, variant: state.variant === "unknown_as_regretted" ? "primary" : state.variant, segment: segment, grain: "period" };
  const answers = await Promise.all([
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "NEW_HIRE_6M" }, hireParams, years)),
    fetchJson("/api/retention/cohorts", Object.assign({ objective: "SENIOR_HIRE_12M" }, hireParams, years)),
    fetchJson("/api/retention/turnover", Object.assign({ country: country, variant: state.variant, year_end_only: true }, years)),
    fetchJson("/api/indicators", { indicator: indicator, country: country === "ALL" ? null : country, year_from: state.yearFrom, year_to: state.yearTo }),
  ]);
  if (myLoad !== loadCounter) {
    return;
  }

  byId("understand-help").textContent = "The " + yearsText() + " result for each objective " +
    "(turnover: the 12 months to the last selected December), with its verdict.";
  const tiles = byId("understand-tiles");
  clear(tiles);
  const newHire = answers[0].rows[0];
  const senior = answers[1].rows[0];
  if (newHire && newHire.n > 0) {
    tiles.appendChild(rateTile("New-hire 6-month retention, " + yearsText(), newHire, objectiveMeta("NEW_HIRE_6M")));
  }
  if (senior && senior.n > 0) {
    tiles.appendChild(rateTile("Senior-hire 12-month retention, " + yearsText(), senior, objectiveMeta("SENIOR_HIRE_12M")));
  }
  const decembers = answers[2].rows;
  if (decembers.length > 0) {
    const savedObjective = state.objective;
    state.objective = TURNOVER; // two decimals for turnover
    tiles.appendChild(rateTile("Regretted turnover, 12 months to " + decembers[decembers.length - 1].month_end, decembers[decembers.length - 1], objectiveMeta(TURNOVER)));
    state.objective = savedObjective;
  }
  if (segment.length > 0) {
    tiles.appendChild(el("p", "Segment " + segmentDescription() + " applies to the hire objectives only (turnover covers all employees).", "muted"));
  }

  // 2. The selected objective's trend.
  const meta = objectiveMeta(state.objective);
  if (state.objective === TURNOVER) {
    const turnover = await fetchJson("/api/retention/turnover", { country: country, variant: state.variant, year_from: state.yearFrom, year_to: state.yearTo });
    const points = turnover.rows.map((row) => Object.assign({ period: row.month_end, n: row.avg_headcount }, row));
    byId("u-rate-caption").textContent = meta.name + ", " + countryName(country) + " (monthly, trailing 12 months)";
    drawTrend("u-rate-chart", points, meta, "Regretted turnover");
    buildTable(byId("u-rate-table"), turnoverColumns(), turnover.rows);
  } else {
    const cohorts = await fetchJson("/api/retention/cohorts", Object.assign({}, commonParams(), { grain: "quarter" }));
    byId("u-rate-caption").textContent = meta.name + ", " + countryName(country) + " (quarterly cohorts)";
    drawTrend("u-rate-chart", cohorts.rows, meta, "Retained");
    buildTable(byId("u-rate-table"), cohortColumns(), cohorts.rows);
  }
  if (myLoad !== loadCounter) {
    return;
  }

  // 3. The external signal, drawn at its own frequency; one line per country with a fixed colour.
  drawIndicator(answers[3].rows, indicator, country);

  // 4. The finding in words (D-84): the three verdicts, then how the signal moved.
  const lastDecember = decembers.length > 0 ? decembers[decembers.length - 1] : null;
  setFinding("understand", understandSentence(newHire, senior, lastDecember, country), undefined,
    signalMovement(answers[3].rows, indicator, country));
}

/**
 * Example: "Across 2021–2025 (the selected years), new-hire retention is inconclusive, senior-hire retention is not met,
 * and regretted turnover is met (12 months to 2025-12-31)."
 */
function understandSentence(newHire, senior, lastDecember, country) {
  const words = { met: "met", not_met: "not met", inconclusive: "inconclusive" };
  const parts = [];
  if (newHire && newHire.n > 0) {
    parts.push("new-hire retention is " + (words[newHire.status] || "without a verdict"));
  }
  if (senior && senior.n > 0) {
    parts.push("senior-hire retention is " + (words[senior.status] || "without a verdict"));
  }
  if (lastDecember) {
    parts.push("regretted turnover is " + (words[lastDecember.status] || "without a verdict") +
      " in the latest 12 months");
  }
  if (parts.length === 0) {
    return "No objective can be measured for " + countryName(country) + " with these filters.";
  }
  let list = parts[0];
  if (parts.length === 2) {
    list = parts[0] + " and " + parts[1];
  } else if (parts.length === 3) {
    list = parts[0] + ", " + parts[1] + ", and " + parts[2];
  }
  return "Across " + yearsText() + placeText(country) + ", " + list + ".";
}

/**
 * How the selected signal moved between the first and last period shown.
 * Example: "Unemployment rate fell in 5 of 6 countries between 2021-01 and 2025-12; it rose in Romania."
 */
function signalMovement(rows, indicator, country, withClosing = true) {
  const names = {
    unemployment: "Unemployment rate",
    inflation: "Inflation",
    job_vacancy: "The job vacancy rate",
    gdp_growth: "GDP growth",
  };
  const name = names[indicator] || indicatorLabel(indicator);
  const closing = withClosing
    ? " Moving at the same time does not mean one drives the other; Relationships (in Explore) tests this."
    : "";
  if (rows.length === 0) {
    return "";
  }

  // 1. First and last value per country (rows are sorted by country, then period).
  const firstRow = {};
  const lastRow = {};
  for (const row of rows) {
    if (!firstRow[row.country_code]) {
      firstRow[row.country_code] = row;
    }
    lastRow[row.country_code] = row;
  }
  const codes = COUNTRIES.filter((code) => firstRow[code]);
  const fromPeriod = firstRow[codes[0]].period;
  const toPeriod = lastRow[codes[0]].period;

  // 2. One country: say the two values.
  if (codes.length === 1) {
    const code = codes[0];
    return name + " in " + countryName(code) + " went from " + num(firstRow[code].value, 1) + " to " +
      num(lastRow[code].value, 1) + " (" + firstRow[code].unit + ") between " + fromPeriod + " and " + toPeriod + "." + closing;
  }

  // 3. Several countries: count how many fell, and name the others.
  const rose = [];
  const flat = [];
  let fell = 0;
  for (const code of codes) {
    const change = lastRow[code].value - firstRow[code].value;
    if (change < 0) {
      fell += 1;
    } else if (change > 0) {
      rose.push(countryName(code));
    } else {
      flat.push(countryName(code));
    }
  }
  let text = name + " fell in " + fell + " of " + codes.length + " countries between " + fromPeriod + " and " + toPeriod;
  if (rose.length > 0) {
    text += "; it rose in " + rose.join(", ");
  }
  if (flat.length > 0) {
    text += "; it was unchanged in " + flat.join(", ");
  }
  return text + "." + closing;
}

function drawIndicator(rows, indicator, country) {
  const caption = byId("u-indicator-caption");
  caption.textContent = indicatorLabel(indicator) + (country === "ALL" ? ", all six countries" : ", " + countryName(country));
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

/** Signal name with the sample size underneath. */
function signalCell(row) {
  const cell = el("span", indicatorLabel(row.indicator));
  cell.appendChild(el("span", "n = " + row.n_rows + " rows, " + row.n_countries + " countries", "cell-sub"));
  return cell;
}

/** A small interval bar on a −1 … +1 scale: the band is the bootstrap interval, the dot is rho. */
function ciBar(row) {
  const bar = el("span", null, "ci-bar");
  bar.setAttribute("role", "img");
  bar.setAttribute("aria-label", "rho " + num(row.rho, 2) + ", interval " + num(row.ci_low, 2) + " to " + num(row.ci_high, 2));
  bar.title = "rho " + num(row.rho, 2) + " (" + num(row.ci_low, 2) + " to " + num(row.ci_high, 2) + ")";
  bar.appendChild(el("span", null, "zero"));
  const range = el("span", null, "range");
  range.style.left = ((row.ci_low + 1) * 50) + "%";
  range.style.width = ((row.ci_high - row.ci_low) * 50) + "%";
  bar.appendChild(range);
  const point = el("span", null, "point");
  point.style.left = ((row.rho + 1) * 50) + "%";
  bar.appendChild(point);
  const wrapper = el("span");
  wrapper.appendChild(bar);
  wrapper.appendChild(el("span", " " + num(row.ci_low, 2) + " to " + num(row.ci_high, 2), "cell-sub-inline"));
  return wrapper;
}

/** Example: "None of the 4 formal within-country tests shows a clear association between an external signal and new-hire six-month retention." */
function challengeSentence(formal, alpha, objective) {
  const name = lowerFirst(objectiveMeta(objective).name);
  const clearRows = formal.filter((row) => row.p_holm !== null && row.p_holm < alpha);
  if (formal.length === 0) {
    return "No formal test exists for " + name + ".";
  }
  if (clearRows.length === 0) {
    return "None of the " + formal.length + " formal within-country tests shows a clear association between an external signal and " + name + ".";
  }
  const signals = clearRows.map((row) => indicatorLabel(row.indicator));
  return clearRows.length + " of " + formal.length + " formal within-country tests show an association with " + name +
    ": " + signals.join(", ") + ".";
}

/** The strongest formal result and the careful reading (D-63). */
function challengeMeaning(formal) {
  if (formal.length === 0) {
    return "";
  }
  let strongest = formal[0];
  for (const row of formal) {
    if (row.p_value < strongest.p_value) {
      strongest = row;
    }
  }
  return "The strongest was " + indicatorLabel(strongest.indicator) + " (rho " + num(strongest.rho, 2) +
    ", raw p " + num(strongest.p_value, 2) + ", Holm-adjusted p " + num(strongest.p_holm, 2) + "). " +
    "These results are associative, not causal, and a result without a clear association does not show that no relationship exists: " +
    "small samples and repeated observations limit inference. Stronger evidence would need a longer history per country, " +
    "more countries or employee-level exit reasons, and a test that allows for the time trend (D-79).";
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

  // 1. The finding in words (D-84): how many formal tests show a clear association.
  const alpha = answers[0].alpha;
  const formal = results.filter((row) => row.is_formal);
  const descriptive = results.filter((row) => !row.is_formal);
  setFinding("challenge", challengeSentence(formal, alpha, objective), undefined, challengeMeaning(formal));

  // 2. Formal tests on top with an interval bar; the descriptive views folded underneath.
  const container = byId("challenge-results");
  clear(container);
  const formalBox = el("div");
  container.appendChild(formalBox);
  buildTable(formalBox, [
    { label: "Signal", format: (row) => signalCell(row) },
    { label: "rho", numeric: true, format: (row) => num(row.rho, 2) },
    { label: "Bootstrap 95% (exploratory), scale −1 to +1", format: (row) => ciBar(row) },
    { label: "p", numeric: true, format: (row) => num(row.p_value, 2) },
    { label: "Holm p", numeric: true, format: (row) => num(row.p_holm, 2) },
    { label: "Result", format: (row) => (row.p_holm < alpha ? "Association (not causal)" : "No clear association") },
  ], formal, () => "formal");
  const more = el("details");
  more.appendChild(el("summary", "Show the " + descriptive.length + " descriptive views (pooled and time-adjusted, not formal tests)"));
  const descriptiveBox = el("div", null, "table-wrap");
  more.appendChild(descriptiveBox);
  container.appendChild(more);
  buildTable(descriptiveBox, [
    { label: "Signal", format: (row) => signalCell(row) },
    { label: "View", format: (row) => viewLabel(row.view) },
    { label: "rho", numeric: true, format: (row) => num(row.rho, 2) },
    { label: "Bootstrap 95% (exploratory)", format: (row) => ciBar(row) },
    { label: "p", numeric: true, format: (row) => num(row.p_value, 2) },
  ], descriptive);

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
  const setText = analysisSet === "descriptive" ? ", quarterly rows, descriptive only (not tested)" : "";
  const viewText = analysisSet === "descriptive" ? viewLabel(view).replace(" (formal)", "") : viewLabel(view);
  byId("scatter-caption").textContent = viewText + ": " + indicatorLabel(indicator) + " vs " + objective +
    ", " + selected.concat(others).length + " rows" + setText;

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
    fetchJson("/api/retention/sensitivity", { objective: byId("e-objective").value }),
  ]);
  if (myLoad !== loadCounter) {
    return;
  }
  const sources = answers[0].sources;
  const quality = answers[1];
  const sensitivity = answers[2];

  // 1. The finding in words (D-84): reconciliation, what was set aside, sensitivity, sources.
  const hr = quality.report.hr;
  const rec = hr.reconciliation;
  const statuses = hr.metric_status;
  const trustSentence = count(rec.rows_in_file) + " HR rows " + (rec.balanced ? "reconcile" : "do NOT reconcile") + " to " +
    count(rec.employees_out) + " employees: " + count(statuses.INCLUDED || 0) + " are used, " + count(statuses.QUARANTINED || 0) +
    " are quarantined and " + count(statuses.EXCLUDED || 0) + " are excluded.";
  setFinding("trust", trustSentence, undefined, trustMeaning(sources, sensitivity));

  // 2. Sources: status, freshness, licence, attribution. Long notes fold into the row.
  buildTable(byId("trust-sources"), [
    { label: "Source", format: (row) => sourceCell(row) },
    { label: "Status", format: (row) => statusText(row.status) },
    { label: "Latest period", format: (row) => row.latest_period || "–" },
    { label: "Coverage", format: (row) => (row.coverage_first_period ? row.coverage_first_period + " to " + row.coverage_last_period : "–") },
    { label: "Frequency / lag", format: (row) => row.frequency + (row.publication_lag_months ? ", +" + row.publication_lag_months + " months" : "") },
    { label: "Licence", format: (row) => licenceCell(row) },
  ], sources);

  // 3. Quality: reconciliation, statuses, flags.
  byId("trust-reconciliation").textContent = count(rec.rows_in_file) + " rows in the HR file − " + rec.duplicate_rows_removed +
    " repeated rows removed = " + rec.employees_out + " employees (" + (rec.balanced ? "reconciled" : "NOT reconciled") + ").";
  const statusTiles = byId("trust-status");
  clear(statusTiles);
  const statusMeaning = {
    INCLUDED: "used in the primary metrics",
    QUARANTINED: "unverified exits, added back only in the sensitivity run",
    EXCLUDED: "no usable hire date or impossible dates",
  };
  for (const [status, total] of Object.entries(hr.metric_status)) {
    const tile = el("div", null, "tile");
    tile.appendChild(el("div", status.charAt(0) + status.slice(1).toLowerCase(), "tile-label"));
    tile.appendChild(el("div", count(total), "tile-value"));
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
  const evidenceObjective = byId("e-objective").value;
  byId("trust-sensitivity-summary").textContent = objectiveMeta(evidenceObjective).name + ": " + sensitivity.summary;
  const digits = evidenceObjective === TURNOVER ? 2 : 1;
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

/** "Sensitivity + source" reading for the Trust finding. */
function trustMeaning(sources, sensitivity) {
  const name = lowerFirst(objectiveMeta(byId("e-objective").value).name);
  const byStatus = {};
  for (const source of sources) {
    byStatus[source.status] = (byStatus[source.status] || 0) + 1;
  }
  const parts = [sensitivity.summary.replace(/\.$/, "") + " (" + name + ")."];
  const usable = (byStatus.fresh || 0) + (byStatus.replayed || 0);
  let sourceText = usable + " of " + sources.length + " sources are usable";
  const detail = [];
  if (byStatus.fresh) {
    detail.push(byStatus.fresh + " fetched in this run");
  }
  if (byStatus.replayed) {
    detail.push(byStatus.replayed + " replayed from saved snapshots");
  }
  if (byStatus.stale) {
    detail.push(byStatus.stale + " stale");
  }
  if (detail.length > 0) {
    sourceText += " (" + detail.join(", ") + ")";
  }
  parts.push(sourceText + ".");
  parts.push("Uncertain records are flagged and set aside, never deleted or guessed.");
  return parts.join(" ");
}

/** Source name + provider/dataset, with the long note folded into a details element. */
function sourceCell(row) {
  const cell = el("div");
  cell.appendChild(el("span", row.indicator));
  cell.appendChild(el("span", row.provider + ", " + row.dataset, "cell-sub"));
  if (row.note) {
    const note = el("details");
    note.appendChild(el("summary", "Note"));
    note.appendChild(el("p", row.note, "cell-note"));
    cell.appendChild(note);
  }
  return cell;
}

/** Short licence name; the full wording is on the provider's terms page (and in /api/sources). */
function licenceShort(licence) {
  if (licence.indexOf("2011/833/EU") >= 0) {
    return "EU reuse decision 2011/833/EU (CC BY 4.0)";
  }
  if (licence.indexOf("CC BY 4.0") >= 0) {
    return "CC BY 4.0";
  }
  return licence;
}

function licenceCell(row) {
  const wrapper = el("span");
  const name = el("span", licenceShort(row.licence));
  name.title = row.licence;
  wrapper.appendChild(name);
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
  setupSegmentPanel();
  try {
    fillFilters(await fetchJson("/api/filters"));
  } catch (error) {
    showMessage("explore", "error", errorText(error));
    byId("explore-content").hidden = true;
    loadHealth();
    return;
  }
  loadHealth();

  const filterIds = ["f-objective", "f-country", "f-from", "f-to", "f-variant"];
  for (const id of filterIds) {
    byId(id).addEventListener("change", function () {
      readFilters();
      loadCurrentTab();
    });
  }
  for (const id of ["u-indicator", "c-indicator", "c-view", "c-set", "e-objective"]) {
    byId(id).addEventListener("change", loadCurrentTab);
  }
  readFilters();
  readAddress();
  showCurrent(null);
}

document.addEventListener("DOMContentLoaded", init);
