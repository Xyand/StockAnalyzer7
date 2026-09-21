/* StockAnalyzer7 front end.
   No build step and no chart library: the charts are inline SVG, which keeps
   the whole app runnable from a single local server with no network access. */

'use strict';

const state = {
  portfolio: null,
  analysis: null,
  lookthrough: null,
  yoyMode: 'market',
  scaleMode: 'report',
  baseCount: 20,
};

const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const kid of kids) if (kid !== null && kid !== undefined) node.append(kid);
  return node;
};
const svgEl = (tag, attrs = {}) => {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  return node;
};

// ---------------------------------------------------------------- formatting

const currency = (v, digits = 0) =>
  v === null || v === undefined
    ? '—'
    : new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: state.analysis?.summary?.base_currency || 'USD',
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(v);

const pct = (v, digits = 1) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(digits)}%`;

const signedPct = (v, digits = 1) =>
  v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;

const signClass = (v) => (v === null || v === undefined ? '' : v >= 0 ? 'pos' : 'neg');

const num = (v, digits = 2) =>
  v === null || v === undefined
    ? '—'
    : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(v);

// ------------------------------------------------------------- diverging ramp

/** Color for a return value on the diverging scale.
 *  Poles are lightness-matched blue (gain) and red (loss) with a near-neutral
 *  midpoint, so equal gains and losses carry equal visual weight. The numeric
 *  value is always printed alongside, so color is never the only channel. */
function divergingColor(value, cap = 0.4) {
  if (value === null || value === undefined) return 'transparent';
  const css = getComputedStyle(document.documentElement);
  const f = (name) => parseFloat(css.getPropertyValue(name));
  const t = Math.min(Math.abs(value) / cap, 1);
  const positive = value >= 0;
  const hue = positive ? f('--div-hue-pos') : f('--div-hue-neg');
  const cEnd = positive ? f('--div-c-pos') : f('--div-c-neg');
  const lMid = f('--div-l-mid');
  const lEnd = f('--div-l-end');
  const cMid = f('--div-c-mid');
  // Ease the ramp so small returns stay readable instead of washing out.
  const e = Math.sqrt(t);
  return `oklch(${(lMid + (lEnd - lMid) * e).toFixed(4)} ${(cMid + (cEnd - cMid) * e).toFixed(4)} ${hue})`;
}

// ------------------------------------------------------------------ tooltip

const tooltip = $('tooltip');
function showTooltip(event, title, rows) {
  tooltip.replaceChildren(
    el('div', { class: 't-title', text: title }),
    ...rows.map(([k, v]) => el('div', { class: 't-row' }, el('span', { text: k }), el('b', { text: v }))),
  );
  tooltip.hidden = false;
  const box = tooltip.getBoundingClientRect();
  const x = Math.min(event.clientX + 14, window.innerWidth - box.width - 8);
  const y = Math.max(8, Math.min(event.clientY + 14, window.innerHeight - box.height - 8));
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}
const hideTooltip = () => { tooltip.hidden = true; };
document.addEventListener('scroll', hideTooltip, true);

// ------------------------------------------------------------------- notices

function setNotices(messages, kind = 'notice') {
  const box = $('notices');
  box.replaceChildren();
  for (const message of messages) {
    box.append(el('div', { class: `notice ${kind}`, text: message }));
  }
}
function addNotice(message, kind = 'info') {
  $('notices').append(el('div', { class: `notice ${kind}`, text: message }));
}

// ---------------------------------------------------------------------- API

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep the status line */ }
    throw new Error(detail);
  }
  return response.json();
}

function busy(button, on) {
  if (!button) return;
  button.disabled = on;
  if (on) {
    button.dataset.label = button.textContent;
    button.replaceChildren(el('span', { class: 'spinner' }), document.createTextNode(' Working…'));
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
}

// ------------------------------------------------------------ portfolio edit

function renderEditor() {
  const body = $('lots-table').querySelector('tbody');
  body.replaceChildren();
  const lots = state.portfolio?.lots || [];
  $('holdings-editor').hidden = lots.length === 0;
  $('analyze').disabled = lots.length === 0;
  $('save-portfolio').disabled = lots.length === 0;
  $('export-csv').disabled = lots.length === 0;

  lots.forEach((lot, index) => {
    body.append(el('tr', {},
      el('td', {}, el('span', { class: 'sym', text: lot.symbol })),
      el('td', { class: 'num', text: num(lot.quantity, 4) }),
      el('td', { class: 'num', text: lot.cost_per_share === null || lot.cost_per_share === undefined
        ? '—' : lot.cost_per_share.toFixed(2) }),
      el('td', { text: lot.purchase_date || '—' }),
      el('td', { text: lot.account || '—' }),
      el('td', {}, el('button', {
        class: 'tiny ghost', text: 'Remove', title: `Remove this ${lot.symbol} lot`,
        onclick: () => { state.portfolio.lots.splice(index, 1); renderEditor(); },
      })),
    ));
  });

  for (const [code, amount] of Object.entries(state.portfolio?.cash || {})) {
    body.append(el('tr', {},
      el('td', {}, el('span', { class: 'sym', text: 'Cash' }),
        el('span', { class: 'co', text: code })),
      el('td', { class: 'num', text: '—' }),
      el('td', { class: 'num', text: '—' }),
      el('td', { text: '—' }),
      el('td', { text: '—' }),
      el('td', {},
        el('span', { class: 'co', text: currency(amount) }),
        el('button', {
          class: 'tiny ghost', text: 'Remove', title: `Remove the ${code} cash balance`,
          onclick: () => { delete state.portfolio.cash[code]; renderEditor(); },
        })),
    ));
  }
}

function addLot() {
  const symbol = $('new-symbol').value.trim().toUpperCase();
  const quantity = parseFloat($('new-qty').value);
  if (!symbol || !Number.isFinite(quantity) || quantity === 0) {
    addNotice('A lot needs a symbol and a non-zero quantity.', 'error');
    return;
  }
  const cost = parseFloat($('new-cost').value);
  state.portfolio = state.portfolio || { name: 'My Portfolio', base_currency: 'USD', lots: [], cash: {} };
  state.portfolio.lots.push({
    symbol,
    quantity,
    cost_per_share: Number.isFinite(cost) ? cost : null,
    purchase_date: $('new-date').value || null,
    account: $('new-account').value.trim() || null,
  });
  for (const id of ['new-symbol', 'new-qty', 'new-cost', 'new-date']) $(id).value = '';
  setNotices([]);
  renderEditor();
}

// -------------------------------------------------------------------- KPIs

function renderKpis() {
  const s = state.analysis.summary;
  const lt = state.lookthrough;
  const tiles = [
    { label: 'Portfolio value', value: currency(s.total_value), hero: true,
      delta: `${s.holdings_count} holdings · cost ${currency(s.total_cost)}` },
    { label: 'Unrealized gain', value: currency(s.unrealized_pl),
      delta: signedPct(s.unrealized_pl_pct), cls: signClass(s.unrealized_pl) },
    { label: 'Annualized (XIRR)', value: signedPct(s.annualized_return),
      delta: 'money-weighted, all lots', cls: signClass(s.annualized_return) },
    { label: 'Last 12 months', value: signedPct(s.ttm_return),
      delta: 'value-weighted across holdings', cls: signClass(s.ttm_return) },
  ];
  if (lt) {
    tiles.push({
      label: 'Top 10 base assets',
      value: pct(lt.top10_concentration),
      delta: 'of the portfolio, after look-through',
    });
  }
  $('kpis').replaceChildren(...tiles.map((t) => el('div', { class: `kpi${t.hero ? ' hero' : ''}` },
    el('div', { class: 'label', text: t.label }),
    el('div', { class: `value ${t.cls || ''}`, text: t.value }),
    el('div', { class: 'delta', text: t.delta }),
  )));
}

// ----------------------------------------------------------- returns tables

function renderReturnsTable() {
  const table = $('returns-table');
  const years = state.analysis.years;
  const mode = state.yoyMode;

  table.querySelector('thead').replaceChildren(el('tr', {},
    el('th', { text: 'Holding' }),
    ...years.map((y) => el('th', { class: 'num', text: String(y) })),
  ));

  const body = table.querySelector('tbody');
  body.replaceChildren();
  for (const holding of state.analysis.holdings) {
    const byYear = new Map(holding.yearly.map((r) => [r.year, r]));
    const cells = years.map((year) => {
      const row = byYear.get(year);
      const value = row ? (mode === 'market' ? row.market_return : row.position_return) : null;
      if (value === null || value === undefined) {
        return el('td', { class: 'yoy' }, el('span', { class: 'cell empty', text: '·' }));
      }
      const cell = el('span', {
        class: `cell${row.partial ? ' partial' : ''}`,
        text: signedPct(value, 1),
      });
      cell.style.background = divergingColor(value);
      const td = el('td', { class: 'yoy' }, cell);
      td.addEventListener('mousemove', (e) => showTooltip(e, `${holding.symbol} · ${year}`, [
        ['Security return', signedPct(row.market_return)],
        ['My return', signedPct(row.position_return)],
        ...(row.partial ? [['Note', 'partial year']] : []),
      ]));
      td.addEventListener('mouseleave', hideTooltip);
      return td;
    });

    body.append(el('tr', {},
      el('td', {},
        el('span', { class: 'sym', text: holding.symbol }),
        el('span', { class: 'co', text: holding.name || '' })),
      ...cells,
    ));
  }
}

function renderPerfTable() {
  const table = $('perf-table');
  table.querySelector('thead').replaceChildren(el('tr', {},
    el('th', { text: 'Holding' }),
    el('th', { class: 'num', text: 'Shares' }),
    el('th', { class: 'num', text: 'Price' }),
    el('th', { class: 'num', text: 'Value' }),
    el('th', { class: 'num', text: 'Weight' }),
    el('th', { class: 'num', text: 'Cost basis' }),
    el('th', { class: 'num', text: 'Gain' }),
    el('th', { class: 'num', text: 'Gain %' }),
    el('th', { class: 'num', text: '12-month' }),
    el('th', { class: 'num', text: 'Annualized' }),
    el('th', { class: 'num', text: 'Held' }),
  ));

  const body = table.querySelector('tbody');
  body.replaceChildren();
  const holdings = [...state.analysis.holdings].sort((a, b) => (b.market_value || 0) - (a.market_value || 0));
  for (const h of holdings) {
    body.append(el('tr', {},
      el('td', {},
        el('span', { class: 'sym', text: h.symbol }),
        el('span', { class: 'co', text: h.name || '' })),
      el('td', { class: 'num', text: num(h.quantity, 4) }),
      el('td', { class: 'num', text: currency(h.price, 2) }),
      el('td', { class: 'num', text: currency(h.market_value) }),
      el('td', { class: 'num', text: pct(h.weight) }),
      el('td', { class: 'num', text: currency(h.cost_basis) }),
      el('td', { class: `num ${signClass(h.unrealized_pl)}`, text: currency(h.unrealized_pl) }),
      el('td', { class: `num ${signClass(h.unrealized_pl_pct)}`, text: signedPct(h.unrealized_pl_pct) }),
      el('td', { class: `num ${signClass(h.ttm_market_return)}`, text: signedPct(h.ttm_market_return) }),
      el('td', { class: `num ${signClass(h.annualized_return)}`, text: signedPct(h.annualized_return) }),
      el('td', { class: 'num', text: h.holding_period_days ? `${(h.holding_period_days / 365).toFixed(1)}y` : '—' }),
    ));
  }

  const s = state.analysis.summary;
  const foot = el('tfoot', {}, el('tr', {},
    el('td', { text: 'Total' }),
    el('td', {}), el('td', {}),
    el('td', { class: 'num', text: currency(s.total_value) }),
    el('td', { class: 'num', text: '100.0%' }),
    el('td', { class: 'num', text: currency(s.total_cost) }),
    el('td', { class: `num ${signClass(s.unrealized_pl)}`, text: currency(s.unrealized_pl) }),
    el('td', { class: `num ${signClass(s.unrealized_pl_pct)}`, text: signedPct(s.unrealized_pl_pct) }),
    el('td', { class: `num ${signClass(s.ttm_return)}`, text: signedPct(s.ttm_return) }),
    el('td', { class: `num ${signClass(s.annualized_return)}`, text: signedPct(s.annualized_return) }),
    el('td', {}),
  ));
  table.querySelector('tfoot')?.remove();
  table.append(foot);
}

// ------------------------------------------------------ base asset bar chart

/** Choose gridline positions that land on readable percentages.
 *  Returns the axis maximum and the number of intervals, picking a step that
 *  yields three to five gridlines — so the axis reads 0/5/10/15/20% rather
 *  than 0/5.4/10.9/16.3%. */
function niceAxis(value, total) {
  if (!total || value <= 0) return { max: value || 1, count: 4 };
  const share = value / total;
  const steps = [0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25];
  for (const step of steps) {
    const count = Math.ceil(share / step - 1e-9);
    if (count >= 3 && count <= 5) return { max: step * count * total, count };
  }
  return { max: total, count: 4 };
}

const ROW_HEIGHT = 30;
const LABEL_WIDTH = 190;
const VALUE_WIDTH = 96;

/** Horizontal stacked bars: direct holding and fund-held exposure per asset.
 *  Two series, so a legend is always shown (it lives in the HTML above the
 *  chart) and each bar carries its own value label. */
function renderBaseChart() {
  const container = $('base-chart');
  container.replaceChildren();
  const report = state.lookthrough.report;
  const rows = report.by_asset.slice(0, state.baseCount);
  if (!rows.length) {
    container.append(el('p', { class: 'hint', text: 'Nothing to break down.' }));
    return;
  }

  const axis = niceAxis(Math.max(...rows.map((r) => r.value)), report.total_value);
  const max = axis.max;
  const height = rows.length * ROW_HEIGHT + 34;
  const svg = svgEl('svg', {
    viewBox: `0 0 900 ${height}`, preserveAspectRatio: 'xMinYMin meet', role: 'img',
    'aria-label': `Effective exposure to the ${rows.length} largest base assets`,
  });
  const plotLeft = LABEL_WIDTH;
  const plotWidth = 900 - LABEL_WIDTH - VALUE_WIDTH;
  const scale = (v) => (max > 0 ? (v / max) * plotWidth : 0);

  // Recessive gridlines on the chosen tick step.
  for (let i = 0; i <= axis.count; i += 1) {
    const x = plotLeft + (plotWidth * i) / axis.count;
    svg.append(svgEl('line', {
      class: i === 0 ? 'axis-line' : 'grid-line',
      x1: x, x2: x, y1: 18, y2: height - 16,
    }));
    const tick = svgEl('text', { class: 'tick-label', x, y: 12, 'text-anchor': i === 0 ? 'start' : 'middle' });
    const tickShare = (max * i) / axis.count / report.total_value;
    // One decimal only when the step itself is finer than a whole percent.
    const digits = max / axis.count / report.total_value < 0.0095 ? 1 : 0;
    tick.textContent = `${(tickShare * 100).toFixed(digits)}%`;
    svg.append(tick);
  }

  rows.forEach((row, index) => {
    const y = 22 + index * ROW_HEIGHT;
    const barY = y + 5;
    const barH = 14;
    const undisclosed = row.key.startsWith('__unresolved__');

    const group = svgEl('g', { class: 'bar-row' });
    group.append(svgEl('rect', {
      class: 'bar-bg', x: 0, y, width: 900, height: ROW_HEIGHT - 2, fill: 'transparent',
    }));

    const label = svgEl('text', { class: 'bar-label', x: 0, y: barY + 11 });
    label.textContent = row.label.length > 26 ? `${row.label.slice(0, 25)}…` : row.label;
    if (undisclosed) label.setAttribute('fill', 'var(--text-muted)');
    group.append(label);

    if (undisclosed) {
      // A single gray bar: this is the part of a fund nobody published.
      group.append(svgEl('rect', {
        x: plotLeft, y: barY, width: Math.max(scale(row.value), 2), height: barH,
        rx: 3, fill: 'var(--series-other)', 'fill-opacity': 0.45,
      }));
    } else {
      const directWidth = scale(row.direct_value);
      const indirectWidth = scale(row.indirect_value);
      if (directWidth > 0) {
        group.append(svgEl('rect', {
          x: plotLeft, y: barY, width: Math.max(directWidth, 2), height: barH,
          rx: 3, fill: 'var(--series-1)',
        }));
      }
      if (indirectWidth > 0) {
        // 2px surface gap between the two segments.
        const gap = directWidth > 0 ? 2 : 0;
        group.append(svgEl('rect', {
          x: plotLeft + directWidth + gap, y: barY,
          width: Math.max(indirectWidth - gap, 2), height: barH,
          rx: 3, fill: 'var(--series-2)',
        }));
      }
    }

    const value = svgEl('text', {
      class: 'bar-value', x: 900, y: barY + 11, 'text-anchor': 'end',
    });
    value.textContent = `${pct(row.weight, 2)}  ${currency(row.value)}`;
    group.append(value);

    group.addEventListener('mousemove', (e) => showTooltip(e, row.label, [
      ['Effective value', currency(row.value)],
      ['Share of portfolio', pct(row.weight, 2)],
      ...(undisclosed ? [] : [
        ['Held directly', currency(row.direct_value)],
        ['Through funds', currency(row.indirect_value)],
      ]),
      ...Object.entries(row.sources).slice(0, 5).map(([k, v]) => [`  via ${k}`, currency(v)]),
    ]));
    group.addEventListener('mouseleave', hideTooltip);
    svg.append(group);
  });

  container.append(svg);
}

function renderBaseTable() {
  const table = $('base-table');
  table.querySelector('thead').replaceChildren(el('tr', {},
    el('th', { text: 'Base asset' }),
    el('th', { class: 'num', text: 'Effective value' }),
    el('th', { class: 'num', text: 'Weight' }),
    el('th', { class: 'num', text: 'Direct' }),
    el('th', { class: 'num', text: 'Via funds' }),
    el('th', { text: 'Comes from' }),
  ));
  const body = table.querySelector('tbody');
  body.replaceChildren();
  for (const row of state.lookthrough.report.by_asset) {
    const sources = Object.entries(row.sources)
      .map(([k, v]) => `${k} (${currency(v)})`)
      .join(', ');
    body.append(el('tr', {},
      el('td', {},
        el('span', { class: 'sym', text: row.key.startsWith('__unresolved__') ? '—' : row.key }),
        el('span', { class: 'co', text: row.label })),
      el('td', { class: 'num', text: currency(row.value) }),
      el('td', { class: 'num', text: pct(row.weight, 2) }),
      el('td', { class: 'num', text: row.direct_value ? currency(row.direct_value) : '—' }),
      el('td', { class: 'num', text: row.indirect_value ? currency(row.indirect_value) : '—' }),
      el('td', {}, el('span', { class: 'co', style: 'max-width:340px', text: sources })),
    ));
  }
}

// ------------------------------------------------------- allocation stacks

const SERIES_VARS = ['--series-1', '--series-2', '--series-3', '--series-4',
  '--series-5', '--series-6', '--series-7', '--series-8'];

/** Part-to-whole across a handful of categories: one horizontal stacked bar,
 *  categorical hues in fixed slot order, everything past the eighth folded
 *  into a single "Other" segment rather than given an invented ninth hue. */
function renderAllocation(containerId, rows, total) {
  const container = $(containerId);
  container.replaceChildren();
  if (!rows.length) {
    container.append(el('p', { class: 'hint', text: 'No data.' }));
    return;
  }

  const named = [];
  let otherValue = 0;
  for (const row of rows) {
    const isUnknown = row.key === 'unknown';
    if (!isUnknown && named.length < SERIES_VARS.length) named.push(row);
    else otherValue += row.value;
  }
  const segments = named.map((row, i) => ({
    label: row.label, value: row.value, weight: row.weight, color: `var(${SERIES_VARS[i]})`,
  }));
  if (otherValue > 0) {
    segments.push({
      label: rows.some((r) => r.key === 'unknown') && named.length >= rows.length - 1
        ? 'Not disclosed / unclassified' : 'Other',
      value: otherValue,
      weight: total ? otherValue / total : 0,
      color: 'var(--series-other)',
    });
  }

  const stack = el('div', { class: 'stack', role: 'img',
    'aria-label': segments.map((s) => `${s.label} ${pct(s.weight)}`).join(', ') });
  for (const segment of segments) {
    const seg = el('div', { class: 'seg' });
    seg.style.width = `${Math.max(segment.weight * 100, 0.4)}%`;
    seg.style.background = segment.color;
    seg.addEventListener('mousemove', (e) => showTooltip(e, segment.label, [
      ['Value', currency(segment.value)],
      ['Share', pct(segment.weight, 2)],
    ]));
    seg.addEventListener('mouseleave', hideTooltip);
    stack.append(seg);
  }

  const legend = el('div', { class: 'stack-legend' });
  for (const segment of segments) {
    const swatch = el('span', { class: 'swatch' });
    swatch.style.background = segment.color;
    swatch.style.width = '10px';
    swatch.style.height = '10px';
    swatch.style.borderRadius = '2px';
    legend.append(el('div', { class: 'item' },
      swatch,
      el('span', { class: 'name' },
        el('span', { class: 'name-text', text: segment.label }),
        el('span', { class: 'pct', text: `${pct(segment.weight, 1)} · ${currency(segment.value)}` })),
    ));
  }

  container.append(stack, legend);
}

// ------------------------------------------------------------ fund coverage

function renderCoverage() {
  const table = $('coverage-table');
  const report = state.lookthrough.report;
  table.querySelector('thead').replaceChildren(el('tr', {},
    el('th', { text: 'Fund' }),
    el('th', { class: 'num', text: 'Holdings visible' }),
    el('th', { text: 'Source' }),
    el('th', { text: 'Status' }),
  ));
  const body = table.querySelector('tbody');
  body.replaceChildren();

  const symbols = Object.keys(report.fund_coverage);
  if (!symbols.length) {
    body.append(el('tr', {}, el('td', { colspan: 4 },
      el('span', { class: 'co', text: 'No funds in this portfolio were broken down.' }))));
    return;
  }
  for (const symbol of symbols) {
    const covered = report.fund_coverage[symbol];
    const complete = covered >= 0.97;
    body.append(el('tr', {},
      el('td', {}, el('span', { class: 'sym', text: symbol })),
      el('td', { class: 'num', text: pct(covered) }),
      el('td', {}, el('span', { class: 'co', text: report.fund_sources[symbol] || '—' })),
      el('td', {}, el('span', {
        class: complete ? 'pos' : '',
        text: complete ? 'Complete' : 'Top holdings only — upload the issuer file',
      })),
    ));
  }
}

// ------------------------------------------------------------------ actions

async function analyze(button) {
  if (!state.portfolio?.lots?.length) return;
  busy(button, true);
  setNotices([]);
  try {
    const query = state.scaleMode === 'scale' ? '?scale_to_full=true' : '';
    const [analysis, lookthrough] = await Promise.all([
      api('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.portfolio),
      }),
      api(`/api/lookthrough${query}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.portfolio),
      }),
    ]);
    state.analysis = analysis;
    state.lookthrough = lookthrough;
    renderAll();
  } catch (error) {
    addNotice(`Analysis failed: ${error.message}`, 'error');
  } finally {
    busy(button, false);
  }
}

function renderAll() {
  $('results').hidden = false;
  $('empty-state').hidden = true;

  renderKpis();
  renderReturnsTable();
  renderPerfTable();

  const report = state.lookthrough.report;
  renderBaseChart();
  renderBaseTable();
  renderAllocation('alloc-class', report.by_asset_class, report.total_value);
  renderAllocation('alloc-sector', report.by_sector, report.total_value);
  renderAllocation('alloc-country', report.by_country, report.total_value);
  renderCoverage();

  const warnings = [...new Set([...(state.analysis.warnings || []), ...(report.warnings || [])])];
  setNotices(warnings.slice(0, 12));
  if (warnings.length > 12) {
    addNotice(`…and ${warnings.length - 12} more data notes.`);
  }
  if (report.unresolved_value > 0) {
    addNotice(
      `${pct(report.unresolved_value / report.total_value)} of the portfolio sits inside funds `
      + 'whose full holdings are not published here. Upload the issuers\' holdings files on the '
      + '"Fund data quality" tab to resolve it.',
      'info',
    );
  }
}

function switchTab(id) {
  for (const tab of document.querySelectorAll('.tab')) {
    const selected = tab.id === id;
    tab.setAttribute('aria-selected', String(selected));
    $(tab.getAttribute('aria-controls')).hidden = !selected;
  }
}

// ------------------------------------------------------------------- wiring

async function loadSample() {
  state.portfolio = await api('/api/sample-portfolio');
  renderEditor();
  await analyze($('analyze'));
}

async function importCsvText(text, filename) {
  const form = new FormData();
  form.append('file', new Blob([text], { type: 'text/csv' }), filename);
  const result = await api('/api/portfolio/import', { method: 'POST', body: form });
  state.portfolio = result.portfolio;
  renderEditor();
  setNotices(result.warnings || []);
  await analyze($('analyze'));
}

function init() {
  $('theme-toggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : current === 'light' ? 'dark'
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('sa7-theme', next); } catch { /* private mode */ }
    if (state.analysis) { renderReturnsTable(); }
  });
  try {
    const saved = localStorage.getItem('sa7-theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
  } catch { /* private mode */ }

  // Legend swatches for the diverging scale.
  $('lg-neg').style.background = divergingColor(-0.35);
  $('lg-zero').style.background = divergingColor(0);
  $('lg-pos').style.background = divergingColor(0.35);

  $('load-sample').addEventListener('click', async (e) => {
    const button = e.currentTarget;
    busy(button, true);
    try {
      await loadSample();
    } catch (error) {
      addNotice(`Could not load the sample: ${error.message}`, 'error');
    } finally {
      busy(button, false);
    }
  });
  $('analyze').addEventListener('click', (e) => analyze(e.currentTarget));
  $('add-lot').addEventListener('click', addLot);

  $('csv-input').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      await importCsvText(await file.text(), file.name);
    } catch (error) {
      addNotice(`Could not import that file: ${error.message}`, 'error');
    }
    event.target.value = '';
  });

  $('holdings-input').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    const symbol = $('holdings-symbol').value.trim().toUpperCase();
    if (!file) return;
    if (!symbol) {
      addNotice('Enter the fund\'s ticker before uploading its holdings file.', 'error');
      event.target.value = '';
      return;
    }
    try {
      const form = new FormData();
      form.append('file', file);
      const result = await api(`/api/holdings-file/${encodeURIComponent(symbol)}`, { method: 'POST', body: form });
      addNotice(
        `${symbol}: loaded ${result.holdings} holdings covering ${pct(result.covered_weight)} of the fund.`,
        'info',
      );
      if (state.portfolio) await analyze($('analyze'));
    } catch (error) {
      addNotice(`Could not read that holdings file: ${error.message}`, 'error');
    }
    event.target.value = '';
  });

  $('save-portfolio').addEventListener('click', async () => {
    const name = prompt('Save this portfolio as:', state.portfolio?.name || 'default');
    if (!name) return;
    try {
      await api('/api/portfolio/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio: state.portfolio, name }),
      });
      addNotice(`Saved as "${name}".`, 'info');
    } catch (error) {
      addNotice(`Save failed: ${error.message}`, 'error');
    }
  });

  $('load-saved').addEventListener('click', async () => {
    try {
      const saved = await api('/api/portfolio/list');
      if (!saved.length) { addNotice('Nothing saved yet.', 'info'); return; }
      const name = prompt(`Saved portfolios:\n${saved.map((p) => `  ${p.name}`).join('\n')}\n\nOpen which?`, saved[0].name);
      if (!name) return;
      const portfolio = await api(`/api/portfolio?name=${encodeURIComponent(name)}`);
      if (!portfolio) { addNotice(`No portfolio named "${name}".`, 'error'); return; }
      state.portfolio = portfolio;
      renderEditor();
      await analyze($('analyze'));
    } catch (error) {
      addNotice(`Could not open it: ${error.message}`, 'error');
    }
  });

  $('export-csv').addEventListener('click', () => {
    const lines = ['symbol,quantity,cost_per_share,purchase_date,account'];
    for (const lot of state.portfolio.lots) {
      lines.push([lot.symbol, lot.quantity, lot.cost_per_share ?? '', lot.purchase_date ?? '', lot.account ?? ''].join(','));
    }
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    const link = el('a', { href: url, download: 'portfolio.csv' });
    link.click();
    URL.revokeObjectURL(url);
  });

  $('yoy-mode').addEventListener('change', (e) => {
    state.yoyMode = e.target.value;
    if (state.analysis) renderReturnsTable();
  });
  $('scale-mode').addEventListener('change', (e) => {
    state.scaleMode = e.target.value;
    if (state.portfolio) analyze($('analyze'));
  });
  $('base-count').addEventListener('change', (e) => {
    state.baseCount = parseInt(e.target.value, 10);
    if (state.lookthrough) renderBaseChart();
  });

  for (const tab of document.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => switchTab(tab.id));
  }

  api('/api/health').then((health) => {
    const badge = $('provider-badge');
    badge.hidden = false;
    badge.classList.toggle('warn', health.degraded || health.provider === 'fixtures');
    $('provider-text').textContent = health.provider === 'fixtures'
      ? 'Offline demo data'
      : `Live data · ${health.provider}`;
    for (const note of health.notes || []) addNotice(note);
  }).catch(() => { /* the app still works without the badge */ });
}

document.addEventListener('DOMContentLoaded', init);
