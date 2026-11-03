#!/usr/bin/env node
// Turn build/deck.resolved.json (written by scripts/prepare.py) into the finished PDF.
//
//   node render.mjs RUN_DIR [--deck FILE] [--out FILE.pdf] [--no-shots] [--no-pdf]
//
// Steps: build deck.html -> open it in headless Chrome over the DevTools protocol (no Playwright,
// no Puppeteer) -> wait for fonts -> shrink text that does not fit -> draw charts at their real
// size -> run layout QA -> print the PDF -> screenshot every slide plus a contact sheet.
// Writes build/deck.html, build/qa.json, build/shots/slide-NN.png, build/shots/contact-sheet.png
// and RUN_DIR/<TICKER>-teardown-<date>.pdf.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const W = 1600;
const H = 900;

// ---------- args ----------
function parseArgs(argv) {
  const a = { run: null, deck: null, out: null, shots: true, pdf: true };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === '--deck') a.deck = argv[++i];
    else if (x === '--out') a.out = argv[++i];
    else if (x === '--no-shots') a.shots = false;
    else if (x === '--no-pdf') a.pdf = false;
    else if (!a.run) a.run = x;
  }
  if (!a.run) {
    console.error('usage: node render.mjs RUN_DIR [--deck FILE] [--out FILE.pdf] [--no-shots] [--no-pdf]');
    process.exit(2);
  }
  a.run = path.resolve(a.run);
  a.deck = a.deck ? path.resolve(a.deck) : path.join(a.run, 'build', 'deck.resolved.json');
  return a;
}

// ---------- shared formatter (same code the charts use) ----------
const chartsSrc = fs.readFileSync(path.join(HERE, 'charts.js'), 'utf8');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(chartsSrc, sandbox);
const { fmtNum } = sandbox.TeardownCharts;

// ---------- html helpers ----------
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const rich = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
// Source numbers sit in the slide footer; inline markers only when meta.inline_refs is true (they clutter the text).
let SHOW_REFS = false;
const refs = (r) => (SHOW_REFS && r && r.length ? `<sup class="ref">${r.map(esc).join(', ')}</sup>` : '');
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function niceDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  return m ? `${+m[3]} ${MONTHS[+m[2] - 1]} ${m[1]}` : iso || '';
}

function bulletItem(b) {
  if (typeof b === 'string') return `<li>${rich(b)}</li>`;
  const lead = b.lead ? `<strong>${rich(b.lead)}</strong> ` : '';
  const sub = b.sub && b.sub.length ? `<ul class="sub">${b.sub.map((x) => `<li>${rich(x)}</li>`).join('')}</ul>` : '';
  return `<li>${lead}${rich(b.text)}${refs(b.refs)}${sub}</li>`;
}
const bulletList = (arr, cls = '') => (arr && arr.length ? `<ul class="bul ${cls}">${arr.map(bulletItem).join('')}</ul>` : '');
const paraList = (arr) => (arr && arr.length ? `<div class="para">${arr.map((b) => (typeof b === 'string'
  ? `<p>${rich(b)}</p>` : `<p>${b.lead ? `<strong>${rich(b.lead)}</strong> ` : ''}${rich(b.text)}${refs(b.refs)}</p>`)).join('')}</div>` : '');

// ---------- charts ----------
class ChartBag {
  constructor() { this.specs = []; }
  box(ch) {
    if (ch.kind === 'segmented-bar') return segmented(ch);
    const id = this.specs.length;
    this.specs.push(ch);
    const events = ch.kind === 'price' && ch.events && ch.events.length
      ? `<div class="events">${ch.events.map((e, k) => `<span><b>${k + 1}</b>${rich(e.label)}</span>`).join('')}</div>` : '';
    return `<figure class="chart">
      <div class="ct">${rich(ch.title)}</div>${ch.subtitle ? `<div class="cs">${rich(ch.subtitle)}</div>` : ''}
      <div class="plot" data-chart="${id}"></div>${events}
      ${ch.source ? `<div class="src">Source: ${rich(ch.source)}${refs(ch.refs)}</div>` : (ch.refs && ch.refs.length ? `<div class="src">Source: ${ch.refs.map(esc).join(', ')}</div>` : '')}
    </figure>`;
  }
}

const SEG_COLORS = ['#1F5FAE', '#D9622B', '#1B9E77', '#B9B3A6', '#8B877D'];
const ROLE_COLORS = { primary: '#1F5FAE', secondary: '#D9622B', tertiary: '#1B9E77', muted: '#B9B3A6', positive: '#2F7A3E', negative: '#B23B2E' };
function segmented(ch) {
  let parts = (ch.parts || []).filter((p) => p.value !== null && p.value !== undefined && p.value > 0);
  if (parts.length > 5) {
    const rest = parts.slice(4).reduce((a, p) => a + p.value, 0);
    parts = parts.slice(0, 4).concat([{ label: 'Other', value: rest, role: 'muted' }]);
  }
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  const unit = ch.unit || 'pct';
  const color = (p, i) => ROLE_COLORS[p.role] || SEG_COLORS[i];
  const bar = parts.map((p, i) => {
    const share = p.value / total;
    return `<span style="flex:${p.value};background:${color(p, i)}">${share >= 0.09 ? fmtNum(share, 'pct', ch.sym, true) : ''}</span>`;
  }).join('');
  const legend = parts.map((p, i) => `<div style="--c:${color(p, i)}"><div class="sl">${rich(p.label)}</div>
    <div class="sv">${unit === 'pct' ? fmtNum(p.value / (ch.of_total ? 1 : total), 'pct', ch.sym) : fmtNum(p.value, unit, ch.sym)}</div></div>`).join('');
  return `<figure class="chart">
    <div class="ct">${rich(ch.title)}</div>${ch.subtitle ? `<div class="cs">${rich(ch.subtitle)}</div>` : ''}
    <div class="segwrap"><div class="seg">${bar}</div><div class="seg-legend" style="--n:${parts.length}">${legend}</div></div>
    ${ch.source ? `<div class="src">Source: ${rich(ch.source)}${refs(ch.refs)}</div>` : ''}
  </figure>`;
}

// ---------- tables ----------
function tableHtml(t) {
  if (!t) return '';
  const header = t.header || t.columns || [];
  const rows = t.rows || [];
  // numbers right-aligned on one line; a column that is mostly words is left-aligned and wraps
  const isNum = (c) => typeof c === 'number' || /^[\s$€£¥−\-+(]*[\d.,]+\s*[%xXBMKkTbn)]*[\s\S]{0,4}$/.test(String(c ?? '').replace(/NT\$|n\/a/g, '0'));
  const align = t.col_align || header.map((_, i) => {
    if (i === 0) return 'left';
    const cells = rows.map((r) => r[i]).filter((c) => c !== undefined && c !== null && c !== '');
    return cells.length && cells.filter(isNum).length / cells.length < 0.6 ? 'left' : 'right';
  });
  let shade = null;
  if (t.heat_values && t.heat !== false) {
    shade = t.heat_values.map((r) => r.map(() => null));
    const ncol = Math.max(...t.heat_values.map((r) => r.length));
    const whole = t.from === 'sensitivity';
    const all = whole ? t.heat_values.flat().filter((v) => typeof v === 'number') : null;
    for (let c = 0; c < ncol; c++) {
      const vals = whole ? all : t.heat_values.map((r) => r[c]).filter((v) => typeof v === 'number');
      if (vals.length < 2) continue;
      const lo = Math.min(...vals);
      const hi = Math.max(...vals);
      t.heat_values.forEach((r, i) => {
        const v = r[c];
        if (typeof v === 'number' && hi > lo) shade[i][c] = 0.03 + 0.2 * ((v - lo) / (hi - lo));
      });
    }
  }
  const cc = t.center_cell;
  const th = header.map((h, i) => `<th class="${align[i] === 'left' ? 'al' : ''}">${rich(h)}</th>`).join('');
  const body = rows.map((r, i) => `<tr class="${i === t.highlight_row ? 'hl' : ''}">${r.map((c, j) => {
    const cls = [align[j] === 'left' ? 'al' : '', align[j] === 'left' && j > 0 ? 'wrap' : '', c === 'n/a' ? 'na' : '', cc && cc[0] === i && cc[1] === j ? 'center' : ''].join(' ').trim();
    const bg = shade && shade[i] && shade[i][j] ? ` style="background:rgba(31,95,174,${shade[i][j].toFixed(3)})"` : '';
    return `<td class="${cls}"${bg}>${rich(c)}</td>`;
  }).join('')}</tr>`).join('');
  return `<div class="tbl" data-fit="12.5"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table>
    ${t.note ? `<div class="note">${rich(t.note)}${refs(t.refs)}</div>` : ''}</div>`;
}

// ---------- shared blocks ----------
function kpiRow(kpis, cls = '') {
  if (!kpis || !kpis.length) return '';
  return `<div class="kpis ${cls}" style="--n:${kpis.length}">${kpis.map((k) => `<div class="kpi ${k.tone && k.tone !== 'neutral' ? 't-' + k.tone : ''}">
    <div class="kl">${rich(k.label)}</div><div class="kv" data-fitw="22">${rich(k.value)}</div>
    ${k.sub ? `<div class="ks">${rich(k.sub)}${refs(k.refs)}</div>` : ''}</div>`).join('')}</div>`;
}

function textBlock(s, cls = '', min = 19) {
  const inner = `${bulletList(s.bullets, s.bullet_columns === 2 ? 'two' : '')}${paraList(s.paragraphs)}`;
  if (!inner) return '';
  return `<div class="txt ${cls}" data-fit="${min}">${inner}</div>`;
}

function header(s) {
  return `<header class="hd">${s.kicker ? `<div class="kicker">${rich(s.kicker)}</div>` : ''}
    <h1 class="title" data-title>${rich(s.title)}</h1>${s.lead ? `<p class="lead">${rich(s.lead)}</p>` : ''}</header>`;
}
const bottomLine = (s) => (s.takeaway ? `<div class="bl"><span class="bl-k">Bottom line</span><p>${rich(s.takeaway)}</p></div>` : '');

function footer(s, deck) {
  const m = deck.meta;
  const used = s.refs_used || [];
  const src = used.length ? `Sources ${used.length > 10 ? used.slice(0, 10).join(', ') + ` and ${used.length - 10} more` : used.join(', ')} (full list at the end)` : '';
  return `<footer class="ft"><span class="ft-l">${esc(m.ticker)} · Equity teardown · ${esc(niceDate(m.as_of))}</span>
    <span class="ft-src">${esc(src)}</span><span class="ft-r">${s.page} / ${deck.total_pages}</span></footer>`;
}

function frame(s, deck, body, opts = {}) {
  return `<section class="slide l-${esc(s.layout)}" data-page="${s.page}" data-id="${esc(s.id)}" data-layout="${esc(s.layout)}">
    ${opts.noHeader ? '' : header(s)}${body}${opts.noBottom ? '' : bottomLine(s)}${opts.noFooter ? '' : footer(s, deck)}</section>`;
}

// ---------- layouts ----------
const PART_NUM = { part1: '01', part2: '02', part3: '03', part4: '04', thesis: '05', appendix: 'A' };

const LAYOUTS = {
  cover(s, deck, bag) {
    const m = deck.meta;
    const right = s.charts && s.charts.length ? bag.box(s.charts[0]) : `<div class="cv-mono">${esc(m.ticker)}</div>`;
    const conf = m.data_confidence ? ` Data confidence <b>${esc(m.data_confidence)}</b>.` : '';
    return `<section class="slide l-cover" data-page="${s.page}" data-id="${esc(s.id)}" data-layout="cover">
      <div class="cv"><div class="cv-l">
        <div class="kicker">${rich(s.kicker || `Equity teardown · ${m.exchange ? m.exchange + ': ' : ''}${m.ticker}`)}</div>
        <h1 data-title data-lines="3" data-min="60">${rich(s.title || m.company)}</h1>
        ${s.lead || m.subtitle ? `<div class="sub">${rich(s.lead || m.subtitle)}</div>` : ''}
        <div class="verdict"><div class="vk">Our read</div><div class="vv">${rich(m.verdict)}</div><div class="vl">${rich(m.verdict_line)}</div></div>
      </div>
      <div class="cv-r">${kpiRow(s.kpis)}${right}</div></div>
      <div class="cv-foot"><span>Prices as of <b>${esc(niceDate(m.as_of))}</b>.${conf}${m.fiscal_note ? ' ' + rich(m.fiscal_note) : ''}</span>
        <span><b>Not investment advice.</b> Research from public filings and market data.</span></div>
    </section>`;
  },

  roadmap(s, deck) {
    const items = s.items || [];
    const body = `<div class="bd"><div class="rm">${items.map((it, i) => `<div class="rm-i">
      <div class="rm-n">${String(i + 1).padStart(2, '0')}</div>
      <div><div class="rm-t">${rich(it.label)}</div>${it.kicker || it.note ? `<div class="rm-k">${rich(it.note || it.kicker)}</div>` : ''}</div>
      <div class="rm-p">p. ${it.page}</div></div>`).join('')}</div></div>`;
    return frame(s, deck, body);
  },

  divider(s, deck) {
    const num = s.number || PART_NUM[s.part] || '';
    const body = `<div class="dv"><div class="dv-num">${esc(num)}</div><div>
      ${s.kicker ? `<div class="kicker">${rich(s.kicker)}</div>` : ''}<h1 data-title data-lines="3" data-min="48">${rich(s.title)}</h1>
      ${s.lead ? `<p class="lead">${rich(s.lead)}</p>` : ''}${bulletList(s.bullets)}</div></div>`;
    return frame(s, deck, body, { noHeader: true, noBottom: true });
  },

  'exec-summary'(s, deck) {
    const m = deck.meta;
    const q = m.quality_score
      ? `<div class="badge"><div class="bk">Business quality</div><div class="bv">${Number(m.quality_score).toFixed(1)}<small> / 5</small></div>
         <div class="bs">Scorecard on page ${s.scorecard_page || 'in Part 1'}${m.data_confidence ? `. Data confidence ${esc(m.data_confidence)}` : ''}.</div></div>` : '';
    const body = `<div class="bd col">
      <div class="es-v"><div><div class="vk">Our read</div><div class="vv">${rich(m.verdict)}</div><div class="vl">${rich(m.verdict_line)}</div></div>${q}</div>
      ${kpiRow(s.kpis, 'small')}
      <div class="sw">
        <div class="txt" data-fit="19"><div class="swh good"><i></i>What is working</div>${bulletList(s.strengths)}</div>
        <div class="txt" data-fit="19"><div class="swh bad"><i></i>What could break</div>${bulletList(s.risks)}</div>
      </div></div>`;
    return frame(s, deck, body);
  },

  text(s, deck) {
    let inner;
    if (s.columns && s.columns.length) {
      inner = `<div class="cols" style="--n:${s.columns.length}">${s.columns.map((c) => `<div class="txt" data-fit="19">
        ${c.heading ? `<div class="colh">${rich(c.heading)}</div>` : ''}${bulletList(c.bullets)}</div>`).join('')}</div>`;
    } else {
      inner = textBlock(s, '', 15) || '<div></div>';
    }
    const body = `<div class="bd col">${kpiRow(s.kpis, 'small')}${inner}</div>`;
    return frame(s, deck, body);
  },

  'text-chart'(s, deck, bag) {
    const text = textBlock(s, 'side', 14);
    const charts = (s.charts || []).map((c) => bag.box(c)).join('');
    const chartCol = (s.charts || []).length > 1 ? `<div class="bd col" style="flex:1;gap:24px">${charts}</div>` : charts;
    const body = `<div class="bd">${s.chart_side === 'left' ? chartCol + text : text + chartCol}</div>`;
    return frame(s, deck, body);
  },

  chart(s, deck, bag) {
    const text = textBlock(s, 'narrow', 14);
    const body = `<div class="bd">${bag.box(s.charts[0])}${text}</div>`;
    return frame(s, deck, body);
  },

  'two-charts'(s, deck, bag) {
    const charts = (s.charts || []).slice(0, 2).map((c) => bag.box(c)).join('');
    const notes = s.bullets && s.bullets.length ? `<div class="txt" data-fit="19" style="flex:none;max-height:150px;font-size:17px">${bulletList(s.bullets, 'two')}</div>` : '';
    const body = `<div class="bd col"><div class="row">${charts}</div>${notes}</div>`;
    return frame(s, deck, body);
  },

  'kpis-chart'(s, deck, bag) {
    const text = textBlock(s, 'narrow', 14);
    const charts = (s.charts || []).map((c) => bag.box(c)).join('');
    const body = `<div class="bd col">${kpiRow(s.kpis)}<div class="row">${charts}${text}</div></div>`;
    return frame(s, deck, body);
  },

  table(s, deck) {
    const text = textBlock(s, 'narrow', 14);
    const body = `<div class="bd">${tableHtml(s.table)}${text}</div>`;
    return frame(s, deck, body);
  },

  'text-table'(s, deck) {
    const text = textBlock(s, 'side', 14);
    const body = `<div class="bd">${text}${tableHtml(s.table)}</div>`;
    return frame(s, deck, body);
  },

  cards(s, deck) {
    const cards = s.cards || [];
    const n = cards.length > 4 ? Math.ceil(cards.length / 2) : cards.length;
    const body = `<div class="bd col">${kpiRow(s.kpis, 'small')}<div class="cards" data-fit="15.5" style="--n:${n}">${cards.map((c) => `<div class="card">
      ${c.tag ? `<div class="tag">${rich(c.tag)}</div>` : ''}<h3>${rich(c.title)}</h3>${c.body ? `<p>${rich(c.body)}${refs(c.refs)}</p>` : ''}
      ${c.facts && c.facts.length ? `<ul class="facts">${c.facts.map((f) => `<li>${rich(f)}</li>`).join('')}</ul>` : ''}</div>`).join('')}</div></div>`;
    return frame(s, deck, body);
  },

  matrix(s, deck) {
    const mx = s.matrix || {};
    const pts = mx.points || [];
    const scale = Math.max(1, ...pts.flatMap((p) => [p.x, p.y]).filter((v) => typeof v === 'number')) > 1 ? 10 : 1;
    const q = mx.quadrants || [];
    const ql = (txt, pos) => (txt ? `<div class="ql" style="${pos}">${rich(txt)}</div>` : '');
    const xe = mx.x_ends || ['Low', 'High'];
    const ye = mx.y_ends || ['Low', 'High'];
    const grid = `<div class="mx-wrap">
      <div class="mx"><div class="qv"></div><div class="qh"></div>
        ${ql(q[0], 'left:0;top:0')}${ql(q[1], 'right:0;top:0;text-align:right')}${ql(q[2], 'left:0;bottom:0')}${ql(q[3], 'right:0;bottom:0;text-align:right')}
        ${pts.map((p) => {
          const x = Math.min(1, Math.max(0, p.x / scale));
          const y = Math.min(1, Math.max(0, p.y / scale));
          return `<div class="mx-pt ${p.highlight ? 'hi' : ''} ${x > 0.72 ? 'left' : ''}" style="left:${(x * 100).toFixed(1)}%;bottom:${(y * 100).toFixed(1)}%"><i></i><span>${rich(p.label)}</span></div>`;
        }).join('')}
      </div>
      <div class="mx-x"><span>${rich(xe[0])}</span><b>${rich(mx.x_label || '')}</b><span>${rich(xe[1])}</span></div>
      <div class="mx-y"><div><span>${rich(ye[0])}</span><b>${rich(mx.y_label || '')}</b><span>${rich(ye[1])}</span></div></div>
    </div>`;
    const body = `<div class="bd">${grid}${textBlock(s, '', 14)}</div>`;
    return frame(s, deck, body);
  },

  timeline(s, deck) {
    const items = s.timeline || [];
    const vertical = items.length > 5;
    const body = `<div class="bd col"><div class="tl ${vertical ? 'v' : ''}" data-fit="16" style="--n:${items.length}">${items.map((it) => `<div class="tl-i">
      <div class="tl-d">${rich(it.date)}</div><div class="tl-t">${rich(it.title)}</div>${it.body ? `<div class="tl-b">${rich(it.body)}${refs(it.refs)}</div>` : ''}</div>`).join('')}</div>
      ${s.bullets && s.bullets.length ? textBlock(s, '', 14) : ''}</div>`;
    return frame(s, deck, body);
  },

  scorecard(s, deck) {
    const rows = s.scorecard || [];
    const dots = (v) => {
      let h = '';
      for (let i = 1; i <= 5; i++) h += `<i class="${v >= i ? 'f' : v >= i - 0.5 ? 'h' : ''}"></i>`;
      return `<span class="dots">${h}<b>${Number(v).toFixed(1)}</b></span>`;
    };
    const avg = deck.meta.quality_score || (rows.length ? rows.reduce((a, r) => a + (r.score || 0), 0) / rows.length : null);
    const body = `<div class="bd"><div class="sc" data-fit="16">${rows.map((r) => `<div class="sc-row"><div class="sc-c">${rich(r.criterion)}</div>${dots(r.score)}
      <div class="sc-m">${rich(r.comment || '')}${refs(r.refs)}</div></div>`).join('')}
      ${avg ? `<div class="sc-row total"><div class="sc-c">Overall</div>${dots(avg)}<div class="sc-m">${rich(s.overall_note || 'Simple average of the criteria above.')}</div></div>` : ''}</div></div>`;
    return frame(s, deck, body);
  },

  thesis(s, deck) {
    const wl = (s.watchlist || []).map((b) => (typeof b === 'string' ? `<li><span>${rich(b)}</span></li>`
      : `<li><strong>${rich(b.lead || '')}</strong><span>${rich(b.text)}${refs(b.refs)}</span></li>`)).join('');
    const body = `<div class="bd"><div class="th">
      <div class="txt" data-fit="19"><div class="colh">${rich(s.left_heading || 'The thesis')}</div>${paraList(s.paragraphs)}${bulletList(s.bullets)}</div>
      <div class="txt" data-fit="15.5"><div class="colh">${rich(s.right_heading || 'What would change my mind')}</div><ul class="wl">${wl}</ul></div>
    </div></div>`;
    return frame(s, deck, body);
  },

  sources(s, deck) {
    const items = s.items || [];
    const body = `<div class="bd col" style="gap:0"><ol class="srcs" data-fit="11.5">${items.map((x) => `<li><span class="sid">${esc(x.id)}</span><span>${rich(x.title)}${x.publisher ? `. ${rich(x.publisher)}` : ''}${x.date ? `, ${esc(x.date)}` : ''}.${x.vendor ? '<span class="vend">vendor</span>' : ''}
      <span class="u">${esc(x.url)}</span></span></li>`).join('')}</ol>
      <p class="src-disc">Not investment advice. Research for education and discussion, built from public filings and market data as of ${esc(niceDate(deck.meta.as_of))}.</p></div>`;
    return frame(s, deck, body, { noBottom: true });
  },

  disclaimer(s, deck) {
    const paras = s.paragraphs && s.paragraphs.length ? s.paragraphs : DEFAULT_DISCLAIMER(deck.meta);
    const body = `<div class="bd"><div class="disc" data-fit="12.5">${paras.map((p) => `<p>${rich(typeof p === 'string' ? p : p.text)}</p>`).join('')}</div></div>`;
    return frame(s, deck, body, { noBottom: true });
  },
};

const DEFAULT_DISCLAIMER = (m) => [
  `This teardown of ${m.company} (${m.ticker}) is research for education and discussion. It is not investment advice, not a recommendation to buy or sell any security, and not an offer of any kind.`,
  `Financial figures come from the company's filings with the SEC (XBRL company facts and the filings themselves) or from its published annual reports. Market data comes from public price feeds as of ${niceDate(m.as_of)}. Figures labelled as estimates, scenarios or fair values are the teardown's own assumptions and can be wrong.`,
  'Every number on these pages is either computed from those sources by the pipeline or cited to the numbered source list. Sources can contain errors, restate their figures, or go out of date after the as-of date.',
  'Valuation ranges show what the stated assumptions imply. They are not price targets. Past returns do not predict future returns. Investing in single stocks can lose some or all of the money invested.',
  'Do your own research and consider speaking with a licensed adviser who knows your situation before making any investment decision.',
];

// ---------- pagination of the source list ----------
function expandSources(slides, sources) {
  const out = [];
  for (const s of slides) {
    if (s.layout !== 'sources') { out.push(s); continue; }
    const list = s.items || sources;
    // estimate lines per entry: ~78 chars per title line, ~92 per url line, at two columns of ~25 lines
    // two columns of ~650px: ~88 characters per title line at 13.5px, ~100 per url line at 12px,
    // ~36 lines per column. The list box also shrinks its text if the estimate runs over.
    const cost = (x) => Math.ceil(((x.title || '').length + (x.publisher || '').length + (x.date || '').length + 6) / 86)
      + Math.ceil((x.url || '').length / 98) + 0.5;
    const pages = [];
    let cur = [];
    let used = 0;
    const cap = 66;
    for (const x of list) {
      const c = cost(x);
      if (used + c > cap && cur.length) { pages.push(cur); cur = []; used = 0; }
      cur.push(x);
      used += c;
    }
    if (cur.length || !pages.length) pages.push(cur);
    pages.forEach((p, i) => out.push({ ...s, id: pages.length > 1 ? `${s.id}-${i + 1}` : s.id, items: p,
      title: pages.length > 1 ? `${s.title} (${i + 1} of ${pages.length})` : s.title }));
  }
  return out;
}

// ---------- build html ----------
function fontCss() {
  const fonts = JSON.parse(fs.readFileSync(path.join(HERE, 'fonts', 'fonts.json'), 'utf8'));
  return fonts.map((f) => {
    const b64 = fs.readFileSync(path.join(HERE, 'fonts', f.file)).toString('base64');
    return `@font-face{font-family:"${f.family}";font-style:normal;font-weight:${f.weight};font-display:block;src:url(data:font/woff2;base64,${b64}) format("woff2");unicode-range:${f.range};}`;
  }).join('\n');
}

function echartsPath() {
  const p = path.join(HERE, 'node_modules', 'echarts', 'dist', 'echarts.min.js');
  if (!fs.existsSync(p)) {
    console.error(`ECharts is missing. Run: npm install --prefix ${HERE}`);
    process.exit(2);
  }
  return p;
}

function buildHtml(deck) {
  SHOW_REFS = !!(deck.meta && deck.meta.inline_refs);
  deck.slides = expandSources(deck.slides, deck.sources || []);
  deck.slides.forEach((s, i) => { s.page = i + 1; });
  deck.total_pages = deck.slides.length;
  const dividers = deck.slides.filter((s) => s.layout === 'divider');
  for (const s of deck.slides) {
    if (s.layout === 'roadmap') {
      const notes = new Map((s.items || []).map((it) => [it.label, it.note]));
      s.items = dividers.map((d) => ({ label: d.title, kicker: d.kicker, note: notes.get(d.title) || d.lead || '', page: d.page }));
    }
  }
  const bag = new ChartBag();
  const html = deck.slides.map((s) => {
    const fn = LAYOUTS[s.layout];
    if (!fn) throw new Error(`slide ${s.id}: unknown layout "${s.layout}"`);
    return fn(s, deck, bag);
  }).join('\n');
  const m = deck.meta;
  const css = fs.readFileSync(path.join(HERE, 'templates', 'deck.css'), 'utf8');
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>${esc(m.company)} (${esc(m.ticker)}) equity teardown, ${esc(niceDate(m.as_of))}</title>
<style>${fontCss()}\n${css}</style>
<script src="${pathToFileURL(echartsPath()).href}"></script>
<script>${chartsSrc}</script>
<script>${fs.readFileSync(path.join(HERE, 'templates', 'page.js'), 'utf8')}</script>
<script type="application/json" id="chart-specs">${JSON.stringify(bag.specs).replace(/</g, '\\u003c')}</script>
</head><body>
${html}
</body></html>`;
}

// ---------- Chrome over the DevTools protocol ----------
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const c = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ];
  for (const p of c) if (fs.existsSync(p)) return p;
  throw new Error('Chrome or Chromium not found. Set CHROME_PATH to the browser binary.');
}

class CDP {
  constructor(url) {
    this.url = url; this.id = 0; this.pending = new Map(); this.handlers = new Set();
  }
  open() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(new Error('DevTools socket error ' + (e.message || '')));
      this.ws.onmessage = (ev) => {
        const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : Buffer.from(ev.data).toString());
        if (msg.id && this.pending.has(msg.id)) {
          const p = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) p.reject(new Error(`${p.method}: ${msg.error.message}`)); else p.resolve(msg.result);
        } else if (msg.method) {
          for (const h of this.handlers) h(msg);
        }
      };
    });
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    const m = { id, method, params };
    if (sessionId) m.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.ws.send(JSON.stringify(m));
    });
  }
  once(method, sessionId, timeout = 30000) {
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => { this.handlers.delete(h); reject(new Error(`timed out waiting for ${method}`)); }, timeout);
      const h = (m) => {
        if (m.method === method && (!sessionId || m.sessionId === sessionId)) {
          clearTimeout(t); this.handlers.delete(h); resolve(m.params);
        }
      };
      this.handlers.add(h);
    });
  }
  close() { try { this.ws.close(); } catch { /* already closed */ } }
}

async function launchChrome() {
  const bin = findChrome();
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'teardown-chrome-'));
  const proc = spawn(bin, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--disable-gpu', '--hide-scrollbars', '--force-color-profile=srgb',
    '--font-render-hinting=none', '--disable-extensions', '--allow-file-access-from-files', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let buf = '';
    const t = setTimeout(() => reject(new Error('Chrome did not start within 30s')), 30000);
    proc.stderr.on('data', (d) => {
      buf += d;
      const mt = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (mt) { clearTimeout(t); resolve(mt[1]); }
    });
    proc.on('exit', (code) => { clearTimeout(t); reject(new Error(`Chrome exited (${code}): ${buf.slice(-400)}`)); });
  });
  const cdp = new CDP(wsUrl);
  await cdp.open();
  const kill = () => {
    cdp.close();
    try { proc.kill('SIGKILL'); } catch { /* gone */ }
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* best effort */ }
  };
  return { cdp, kill };
}

async function openPage(cdp, url, width, height) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  await cdp.send('Page.enable', {}, sessionId);
  await cdp.send('Runtime.enable', {}, sessionId);
  await cdp.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false }, sessionId);
  const loaded = cdp.once('Page.loadEventFired', sessionId, 60000);
  await cdp.send('Page.navigate', { url }, sessionId);
  await loaded;
  const evaluate = async (expression) => {
    const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, sessionId);
    if (r.exceptionDetails) {
      throw new Error(`page error: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`);
    }
    return r.result.value;
  };
  return { sessionId, targetId, evaluate };
}

function pdfPageCount(buf) {
  const s = buf.toString('latin1');
  return (s.match(/\/Type\s*\/Page(?![s\w])/g) || []).length;
}

// ---------- main ----------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(args.deck)) {
    console.error(`no resolved deck at ${args.deck}. Run scripts/prepare.py first.`);
    process.exit(2);
  }
  const deck = JSON.parse(fs.readFileSync(args.deck, 'utf8'));
  if (deck.errors && deck.errors.length) {
    console.error(`warning: the resolved deck carries ${deck.errors.length} prepare errors; they will show as [[missing ...]] on the slides`);
  }
  const build = path.join(args.run, 'build');
  const shotsDir = path.join(build, 'shots');
  fs.mkdirSync(shotsDir, { recursive: true });
  const htmlPath = path.join(build, 'deck.html');
  fs.writeFileSync(htmlPath, buildHtml(deck));

  const t0 = Date.now();
  const { cdp, kill } = await launchChrome();
  try {
    const page = await openPage(cdp, pathToFileURL(htmlPath).href, W, H);
    await page.evaluate('document.fonts.ready.then(() => true)');
    const fitLog = await page.evaluate('window.__fit()');
    const charts = await page.evaluate('window.__renderCharts()');
    await page.evaluate('window.__fit()');
    const qa = await page.evaluate('window.__qa()');

    // save the finished page as static html (charts already drawn, scripts removed)
    const finalHtml = await page.evaluate(`(() => { const d = document.documentElement.cloneNode(true);
      d.querySelectorAll('script').forEach((s) => s.remove()); return '<!DOCTYPE html>' + d.outerHTML; })()`);
    fs.writeFileSync(htmlPath, finalHtml);

    let pdfPath = null;
    let pages = null;
    if (args.pdf) {
      const r = await cdp.send('Page.printToPDF', {
        printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false,
        marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
      }, page.sessionId);
      const buf = Buffer.from(r.data, 'base64');
      const m = deck.meta;
      pdfPath = args.out ? path.resolve(args.out) : path.join(args.run, `${String(m.ticker).replace(/[^\w.-]/g, '_')}-teardown-${m.as_of}.pdf`);
      fs.writeFileSync(pdfPath, buf);
      pages = pdfPageCount(buf);
    }

    const shots = [];
    if (args.shots) {
      for (const f of fs.readdirSync(shotsDir)) if (f.endsWith('.png')) fs.rmSync(path.join(shotsDir, f));
      const n = deck.slides.length;
      for (let i = 0; i < n; i++) {
        const r = await cdp.send('Page.captureScreenshot', {
          format: 'png', captureBeyondViewport: true, clip: { x: 0, y: i * H, width: W, height: H, scale: 1 },
        }, page.sessionId);
        const f = path.join(shotsDir, `slide-${String(i + 1).padStart(2, '0')}.png`);
        fs.writeFileSync(f, Buffer.from(r.data, 'base64'));
        shots.push(f);
      }
      // contact sheet: every slide as a thumbnail, to judge rhythm and variety at a glance
      const cols = 4;
      const tw = 400;
      const thh = 225;
      const gap = 16;
      const sheet = `<!DOCTYPE html><html><body style="margin:0;background:#E9E5DB;padding:${gap}px;display:grid;grid-template-columns:repeat(${cols},${tw}px);gap:${gap}px;width:${cols * tw + (cols + 1) * gap}px">
        ${shots.map((s, i) => `<div style="position:relative"><img src="${pathToFileURL(s).href}" style="width:${tw}px;height:${thh}px;display:block;box-shadow:0 1px 3px rgba(0,0,0,.18)">
        <span style="position:absolute;left:6px;top:6px;font:600 12px Arial;background:#15140F;color:#fff;padding:2px 6px;border-radius:3px">${i + 1}</span></div>`).join('')}</body></html>`;
      const sheetPath = path.join(build, 'contact-sheet.html');
      fs.writeFileSync(sheetPath, sheet);
      const rows = Math.ceil(n / cols);
      const sw = cols * tw + (cols + 1) * gap;
      const sh = rows * thh + (rows + 1) * gap;
      const sp = await openPage(cdp, pathToFileURL(sheetPath).href, sw, Math.min(sh, 4000));
      await sp.evaluate('Promise.all([...document.images].map((i) => i.complete ? 1 : new Promise((r) => { i.onload = i.onerror = r; })))');
      const r = await cdp.send('Page.captureScreenshot', {
        format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: sw, height: sh, scale: 1 },
      }, sp.sessionId);
      fs.writeFileSync(path.join(shotsDir, 'contact-sheet.png'), Buffer.from(r.data, 'base64'));
    }

    const counts = { error: 0, warn: 0, info: 0 };
    qa.slides.forEach((s) => s.issues.forEach((i) => { counts[i.level] = (counts[i.level] || 0) + 1; }));
    const report = {
      rendered_at: new Date().toISOString(), seconds: Math.round((Date.now() - t0) / 100) / 10,
      pdf: pdfPath, pdf_pages: pages, slides: deck.slides.length, fonts: qa.fonts, counts,
      charts, text_shrunk: fitLog, prepare_errors: deck.errors || [], qa: qa.slides.filter((s) => s.issues.length),
    };
    fs.writeFileSync(path.join(build, 'qa.json'), JSON.stringify(report, null, 1));

    console.log(`rendered ${deck.slides.length} slides in ${report.seconds}s`);
    if (pdfPath) console.log(`pdf: ${pdfPath} (${pages} pages)`);
    if (args.shots) console.log(`screenshots: ${shotsDir}/slide-NN.png and contact-sheet.png`);
    console.log(`fonts loaded: serif ${qa.fonts.serif}, sans ${qa.fonts.sans}`);
    console.log(`QA: ${counts.error} errors, ${counts.warn} warnings (details in build/qa.json)`);
    for (const s of report.qa) {
      for (const i of s.issues) if (i.level !== 'info') console.log(`  p${s.page} [${s.id}] ${i.level}: ${i.msg}`);
    }
    if (pages !== null && pages !== deck.slides.length) console.log(`WARNING: PDF has ${pages} pages but the deck has ${deck.slides.length} slides`);
  } finally {
    kill();
  }
}

main().catch((e) => { console.error(e.stack || String(e)); process.exit(1); });
