"use strict";

const WORK = "/work";
const INPUT = WORK + "/in";
const MAX_TOTAL_BYTES = 150000000;
const MAX_ROWS_SHOWN = 200;
const WHEEL_NAME = /^[A-Za-z0-9_.+-]+\.whl$/;
const MARKS = {
  hit: "Hit",
  false_alarm: "False alarm",
  miss: "Miss",
  other_label: "On another label",
  not_scored: "Not scored",
  to_check: "To check",
};
const SVG_NS = "http://www.w3.org/2000/svg";

const $ = (id) => document.getElementById(id);
const whole = new Intl.NumberFormat("en-US");
const share4 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const rate3 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const size1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

let pyodide = null;
let demo = null;
let fields = {};
let chosen = [];
let headers = {};
let current = null;
let downloadUrl = null;

function setStatus(text) {
  $("status").textContent = text;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function svg(tag, attrs, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  return node;
}

function pyError(e) {
  const lines = String(e && e.message ? e.message : e).trim().split("\n");
  return lines[lines.length - 1].replace(/^[A-Za-z]*Error: /, "");
}

function number(value, format) {
  return value === null || value === undefined ? "n/a" : format.format(value);
}

function makeTable(title, columns, rows, numeric) {
  const numbers = new Set(numeric || []);
  const wrap = el("div", undefined, "scroll");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", title);
  const table = el("table");
  table.appendChild(el("caption", title));
  const head = el("tr");
  columns.forEach((c, i) => {
    const th = el("th", c.label, numbers.has(i) ? "num" : undefined);
    th.scope = "col";
    head.appendChild(th);
  });
  const thead = el("thead");
  thead.appendChild(head);
  table.appendChild(thead);
  const body = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    row.forEach((cell, i) => {
      const td = el("td", cell.text, numbers.has(i) ? "num" : cell.className);
      tr.appendChild(td);
    });
    body.appendChild(tr);
  }
  table.appendChild(body);
  wrap.appendChild(table);
  return wrap;
}

function cell(text, className) {
  return { text: String(text), className };
}

function renderSummary(data) {
  const list = $("summary");
  list.replaceChildren();
  const rows = Object.values(data.tables).reduce((sum, n) => sum + (n || 0), 0);
  const items = [
    [whole.format(rows), "rows read"],
    [whole.format(data.items.filter((i) => i.mark !== "miss").length), "items to check"],
  ];
  if (data.mode === "synthetic") {
    items.push([whole.format(data.info.labels), "planted labels"]);
    items.push([whole.format(data.items.filter((i) => i.mark === "miss").length), "misses"]);
  }
  for (const [value, label] of items) {
    const li = el("li");
    li.appendChild(el("span", value, "value"));
    li.appendChild(el("span", label, "label"));
    list.appendChild(li);
  }
  const skipped = Object.entries(data.skips);
  const line = $("result-line");
  line.textContent = skipped.length
    ? "Skipped: " + skipped.map(([rule, why]) => rule + " (" + why + ")").join("; ") + "."
    : "No rule was skipped.";
}

function renderRules(data) {
  const box = $("rules-box");
  box.hidden = data.mode !== "synthetic";
  $("rules").replaceChildren();
  if (data.mode !== "synthetic") return;
  const columns = ["Rule", "Precision", "Recall", "F1", "Labeled", "Flags", "Hits", "False alarms", "On another label", "Misses"];
  const rows = data.rules.map((r) => [
    cell(r.rule),
    cell(number(r.precision, rate3)),
    cell(number(r.recall, rate3)),
    cell(number(r.f1, rate3)),
    cell(whole.format(r.labeled)),
    cell(whole.format(r.flags)),
    cell(whole.format(r.tp)),
    cell(whole.format(r.fp)),
    cell(whole.format(r.other_label)),
    cell(whole.format(r.misses)),
  ]);
  const numeric = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  $("rules").appendChild(makeTable("Per rule scores", columns.map((label) => ({ label })), rows, numeric));
  const unscored = Object.entries(data.unscored);
  if (unscored.length) {
    const text = unscored.map(([k, n]) => k + " " + whole.format(n)).join(", ");
    $("rules").appendChild(el("p", "Labels of a type no rule scores: " + text + ".", "hint"));
  }
}

function benfordChart(b) {
  const w = 360;
  const h = 214;
  const left = 8;
  const bottom = 48;
  const top = 8;
  const plotH = h - bottom - top;
  const slot = (w - left * 2) / 9;
  const shares = b.counts.map((c) => (b.n ? c / b.n : 0));
  const max = Math.max(...shares, ...b.expected) * 1.1;
  const chart = svg("svg", { class: "chart", viewBox: "0 0 " + w + " " + h, width: w, height: h });
  chart.setAttribute("role", "img");
  chart.setAttribute("aria-labelledby", "bt-" + b.field + " bd-" + b.field);
  chart.appendChild(svg("title", { id: "bt-" + b.field }, "First digit shares for " + b.field));
  const summary = shares.map((s, i) => (i + 1) + ": " + share4.format(s) + " observed, " + share4.format(b.expected[i]) + " expected").join("; ");
  chart.appendChild(svg("desc", { id: "bd-" + b.field }, "Bars are observed shares, lines are Benford shares. " + summary + "."));
  chart.appendChild(svg("line", { class: "axis", x1: left, x2: w - left, y1: top + plotH, y2: top + plotH }));
  shares.forEach((s, i) => {
    const x = left + i * slot;
    const bh = (s / max) * plotH;
    chart.appendChild(svg("rect", { class: "bar", x: x + slot * 0.15, y: top + plotH - bh, width: slot * 0.7, height: bh }));
    const ey = top + plotH - (b.expected[i] / max) * plotH;
    chart.appendChild(svg("line", { class: "expected", x1: x + 2, x2: x + slot - 2, y1: ey, y2: ey }));
    chart.appendChild(svg("text", { x: x + slot / 2, y: top + plotH + 16, "text-anchor": "middle" }, String(i + 1)));
  });
  chart.appendChild(svg("text", { x: w / 2, y: h - 6, "text-anchor": "middle" }, "First digit. Bars: observed. Lines: Benford."));
  return chart;
}

function renderBenford(data) {
  const box = $("benford");
  box.replaceChildren();
  if (data.mode === "synthetic") {
    box.appendChild(el("p", "synthbiz amounts are uniform draws, so a Benford misfit on them means nothing.", "note"));
  }
  if (data.benford.length === 0) {
    box.appendChild(el("p", "Skipped: there is no amount column in the input."));
    return;
  }
  for (const b of data.benford) {
    box.appendChild(el("p", b.line, "status-line"));
    box.appendChild(benfordChart(b));
    const rows = b.counts.map((c, i) => [
      cell(i + 1),
      cell(whole.format(c)),
      cell(share4.format(b.n ? c / b.n : 0)),
      cell(share4.format(b.expected[i])),
    ]);
    const columns = ["Digit", "Count", "Share", "Expected"].map((label) => ({ label }));
    box.appendChild(makeTable("First digit table for " + b.field, columns, rows, [0, 1, 2, 3]));
    const tail = "Mean absolute deviation " + share4.format(b.mad) + " (" + b.mad_label + "). Chi-square " +
      number(b.chi_square, new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 })) +
      " with 8 degrees of freedom, p-value " + share4.format(b.p_value) + ". " + b.note;
    box.appendChild(el("p", tail, "hint"));
  }
}

function fillFilters(data) {
  const rule = $("filter-rule");
  rule.replaceChildren();
  rule.appendChild(new Option("all", ""));
  const names = [...new Set(data.items.map((i) => i.rule))];
  for (const n of names) rule.appendChild(new Option(n, n));
  $("filter-mark").value = "";
  $("filter-mark-box").hidden = data.mode !== "synthetic";
}

function renderItems() {
  const box = $("items");
  box.replaceChildren();
  if (!current) return;
  const rule = $("filter-rule").value;
  const mark = $("filter-mark").value;
  const all = current.items.filter((i) => (!rule || i.rule === rule) && (!mark || i.mark === mark));
  const shown = all.slice(0, MAX_ROWS_SHOWN);
  const note = shown.length < all.length
    ? "Showing the first " + whole.format(shown.length) + " of " + whole.format(all.length) + " lines. The download has every item."
    : whole.format(all.length) + " lines.";
  $("items-note").textContent = note;
  if (all.length === 0) {
    box.appendChild(el("p", "No items match. Change the filters."));
    return;
  }
  const columns = ["Mark", "Rule", "Table", "Unit", "Rows", "Reason"].map((label) => ({ label }));
  const rows = shown.map((i) => [
    cell(MARKS[i.mark] || i.mark, "mark-" + i.mark),
    cell(i.rule),
    cell(i.table),
    cell(i.unit_id),
    cell(i.row_ids),
    cell(i.reason, "reason"),
  ]);
  box.appendChild(makeTable("Items to check", columns, rows));
}

function setDownload(text) {
  const link = $("download");
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  link.href = downloadUrl;
  link.hidden = false;
}

function render(data) {
  current = data;
  renderSummary(data);
  renderRules(data);
  renderBenford(data);
  fillFilters(data);
  renderItems();
  setDownload(data.items_csv);
  $("results").hidden = false;
}

function toData(proxy) {
  const data = proxy.toJs({ dict_converter: Object.fromEntries });
  proxy.destroy();
  return data;
}

function busy(on) {
  for (const id of ["run-synthetic", "run-files"]) $(id).disabled = on || !demo;
}

async function pause() {
  await new Promise((resolve) => setTimeout(resolve, 20));
}

async function runSynthetic(event) {
  event.preventDefault();
  busy(true);
  setStatus("Running. The page can pause for a few seconds on a large run.");
  await pause();
  try {
    const args = [Number($("seed").value), Number($("months").value), $("size").value, Number($("rate").value)];
    const data = toData(demo.run_synthetic(...args));
    render(data);
    setStatus("Done. " + whole.format(data.items.filter((i) => i.mark !== "miss").length) + " items to check, " + data.info.labels + " planted labels.");
  } catch (e) {
    setStatus("Error: " + pyError(e) + " Change the input and run again.");
  }
  busy(false);
}

function wipe() {
  demo.prepare_folder(INPUT);
}

async function writeFiles() {
  wipe();
  for (const file of chosen) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    pyodide.FS.writeFile(INPUT + "/" + file.name, bytes);
  }
}

function matchName(table, names) {
  return names.find((n) => n.toLowerCase() === table + ".csv") || "";
}

function buildMapping() {
  const box = $("mapping");
  box.replaceChildren();
  const names = chosen.map((f) => f.name);
  for (const [table, list] of Object.entries(fields)) {
    const set = el("fieldset", undefined, "table-map");
    set.dataset.table = table;
    set.appendChild(el("legend", table));
    const first = el("div", undefined, "field first");
    first.appendChild(el("label", "File for " + table, undefined)).htmlFor = "file-" + table;
    const select = el("select");
    select.id = "file-" + table;
    select.autocomplete = "off";
    select.appendChild(new Option("(not used)", ""));
    for (const n of names) select.appendChild(new Option(n, n));
    select.value = matchName(table, names);
    first.appendChild(select);
    set.appendChild(first);
    const columns = el("div", undefined, "columns");
    columns.style.display = "contents";
    set.appendChild(columns);
    const draw = () => {
      columns.replaceChildren();
      const head = headers[select.value] || [];
      if (!select.value) return;
      for (const f of list) {
        const field = el("div", undefined, "field");
        const label = el("label", table + ": column for " + f);
        label.htmlFor = "col-" + table + "-" + f;
        const pick = el("select");
        pick.id = "col-" + table + "-" + f;
        pick.dataset.field = f;
        pick.autocomplete = "off";
        pick.appendChild(new Option("(choose a column)", ""));
        for (const h of head) pick.appendChild(new Option(h, h));
        pick.value = head.includes(f) ? f : "";
        field.appendChild(label);
        field.appendChild(pick);
        columns.appendChild(field);
      }
    };
    select.addEventListener("change", draw);
    draw();
    box.appendChild(set);
  }
}

async function onFiles() {
  chosen = Array.from($("file-input").files);
  headers = {};
  $("mapping").replaceChildren();
  $("run-files").disabled = true;
  if (chosen.length === 0) return;
  const total = chosen.reduce((sum, f) => sum + f.size, 0);
  if (total > MAX_TOTAL_BYTES) {
    setStatus("Error: these files are " + size1.format(total / 1e6) + " MB, more than the " + size1.format(MAX_TOTAL_BYTES / 1e6) + " MB this page reads. Use the command line for large files, or choose smaller files.");
    chosen = [];
    return;
  }
  setStatus("Reading the column names.");
  try {
    await writeFiles();
    for (const file of chosen) {
      headers[file.name] = demo.read_header(INPUT, file.name).toJs();
    }
    wipe();
    buildMapping();
    $("run-files").disabled = false;
    setStatus("Files read. Match each table to a file and each field to a column, then run.");
  } catch (e) {
    wipe();
    chosen = [];
    setStatus("Error: " + pyError(e) + " Fix the file and choose it again.");
  }
}

function collectTables() {
  const tables = {};
  for (const set of $("mapping").querySelectorAll("fieldset")) {
    const table = set.dataset.table;
    const file = set.querySelector("select").value;
    if (!file) continue;
    const columns = {};
    for (const pick of set.querySelectorAll("select[data-field]")) {
      if (!pick.value) {
        pick.focus();
        throw new Error("Choose a column for " + pick.dataset.field + " in " + table + ", then run again.");
      }
      columns[pick.dataset.field] = pick.value;
    }
    tables[table] = { file, columns };
  }
  return tables;
}

async function runFiles(event) {
  event.preventDefault();
  busy(true);
  let proxy = null;
  try {
    const tables = collectTables();
    setStatus("Running. The page can pause for a few seconds on a large file.");
    await pause();
    await writeFiles();
    proxy = pyodide.toPy(tables);
    const out = demo.run_files(INPUT, proxy, $("date-format").value, $("amounts").value);
    const data = toData(out);
    render(data);
    setStatus("Done. " + whole.format(data.items.length) + " items to check.");
  } catch (e) {
    const text = e && e.name === "Error" && !e.type ? e.message : pyError(e);
    setStatus("Error: " + text + (text.endsWith(".") ? "" : ". Fix the input and run again."));
  }
  if (proxy) proxy.destroy();
  wipe();
  busy(false);
}

function setMode() {
  const files = $("mode-files").checked;
  $("synthetic-form").hidden = files;
  $("files-form").hidden = !files;
}

async function loadWheels() {
  const response = await fetch("manifest.json");
  if (!response.ok) throw new Error("manifest.json is missing from this site");
  const manifest = await response.json();
  for (const name of manifest.wheels) {
    if (typeof name !== "string" || !WHEEL_NAME.test(name)) throw new Error("bad wheel name in manifest.json");
    setStatus("Loading " + name + ".");
    const wheel = await fetch("wheels/" + name);
    if (!wheel.ok) throw new Error(name + " could not be loaded");
    pyodide.unpackArchive(await wheel.arrayBuffer(), "wheel");
  }
  pyodide.runPython("import importlib\nimportlib.invalidate_caches()");
}

async function start() {
  try {
    pyodide = await loadPyodide({ indexURL: new URL("pyodide/", document.baseURI).href });
    await loadWheels();
    setStatus("Starting ledgercheck.");
    demo = pyodide.pyimport("ledgercheck.demo");
    pyodide.FS.mkdirTree(WORK);
    fields = toData(demo.table_fields());
    $("run-synthetic").disabled = false;
    setStatus("Ready. Nothing leaves this page.");
  } catch (e) {
    setStatus("Could not load the demo: " + String(e && e.message ? e.message : e) + " Reload the page to try again.");
  }
}

$("synthetic-form").addEventListener("submit", runSynthetic);
$("files-form").addEventListener("submit", runFiles);
$("file-input").addEventListener("change", onFiles);
$("filter-rule").addEventListener("change", renderItems);
$("filter-mark").addEventListener("change", renderItems);
for (const radio of document.querySelectorAll("input[name=mode]")) radio.addEventListener("change", setMode);
start();
