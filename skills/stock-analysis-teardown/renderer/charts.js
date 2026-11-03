// Chart builders. Loaded as a classic script inside the headless Chrome page (global `echarts`),
// and into Node with vm for the shared number formatter. Charts are drawn with the SVG renderer in
// SSR mode, so text is measured with the real embedded fonts and the page holds static SVG before
// it is printed. No JavaScript runs in the finished PDF.
// Rules from the dataviz method: one y-axis only, bars <= 24px with 4px rounded data-ends,
// 2px lines with 8px end-dots ringed in the surface colour, hairline solid grids,
// highlight one series and grey the rest, legend only for two or more series.
// A PDF has no hover, so single-series charts with up to 8 bars carry value labels
// and line charts label their last point.

const THEME = {
  paper: '#F6F3EC',
  ink: '#15140F',
  ink2: '#4A4740',
  muted: '#8B877D',
  grid: '#E3DED2',
  axis: '#CBC4B4',
  roles: {
    primary: '#1F5FAE',
    secondary: '#D9622B',
    tertiary: '#1B9E77',
    muted: '#B9B3A6',
    positive: '#2F7A3E',
    negative: '#B23B2E',
  },
  order: ['primary', 'secondary', 'tertiary'],
  font: 'Inter, "Helvetica Neue", Arial, sans-serif',
};

const MINUS = '−';

function fmtNum(v, unit = 'num', sym = '$', compact = false) {
  if (v === null || v === undefined || Number.isNaN(v)) return '';
  const s = v < 0 ? MINUS : '';
  const a = Math.abs(v);
  const n = (x, d) => x.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  switch (unit) {
    case 'pct': return `${s}${n(a * 100, compact || a * 100 >= 100 ? 0 : 1)}%`;
    case 'pp': return `${v < 0 ? MINUS : '+'}${n(a * 100, 1)} pp`;
    case 'x': return `${s}${n(a, compact || a >= 100 ? 0 : 1)}x`;
    case 'ps': return `${s}${sym}${n(a, a >= 1000 || compact ? 0 : 2)}`;
    case 'days': return `${s}${n(a, 0)}`;
    case 'shares_m': return `${s}${n(a, 0)}M`;
    case 'ratio': return `${s}${n(a, 2)}`;
    case 'money_m':
      if (a === 0) return `${sym}0`;
      if (a >= 1e6) return `${s}${sym}${n(a / 1e6, 1)}T`;
      if (a >= 1000) return `${s}${sym}${n(a / 1000, compact ? (a >= 10000 ? 0 : 1) : (a >= 10000 ? 1 : 2))}B`.replace('.00B', 'B');
      return `${s}${sym}${n(a, 0)}M`;
    default:
      if (a >= 1e6) return `${s}${n(a / 1e6, 1)}M`;
      if (a >= 1e4) return `${s}${n(a / 1e3, 0)}K`;
      return `${s}${n(a, a < 10 && a % 1 ? 1 : 0)}`;
  }
}

function axisFmt(unit, sym, values) {
  const nums = (values || []).filter((v) => typeof v === 'number' && !Number.isNaN(v));
  if (!nums.length || !['x', 'ps', 'num', 'pct', 'ratio'].includes(unit)) return (v) => fmtNum(v, unit, sym, true);
  const k = unit === 'pct' ? 100 : 1;
  const step = ((Math.max(...nums) - Math.min(...nums)) * k) / 4;
  const d = step >= 2 || step === 0 ? 0 : step >= 0.2 ? 1 : 2;
  const MINUS = '\u2212';
  return (v) => {
    const a = Math.abs(v * k);
    const t = a.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
    const s = v < 0 ? MINUS : '';
    if (unit === 'pct') return `${s}${t}%`;
    if (unit === 'x') return `${s}${t}x`;
    if (unit === 'ps') return `${s}${sym}${t}`;
    return `${s}${t}`;
  };
}

function colorFor(role, i) {
  return THEME.roles[role] || THEME.roles[THEME.order[i % THEME.order.length]];
}

function base(ch, w, h, opts = {}) {
  const top = (opts.legend ? 44 : 18);
  return {
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: THEME.font, color: THEME.ink2, fontSize: 14 },
    grid: { left: 8, right: opts.rightPad ?? 28, top, bottom: opts.bottom ?? 8, containLabel: true },
    legend: opts.legend ? {
      top: 0, left: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 12, itemGap: 22,
      textStyle: { color: THEME.ink2, fontSize: 14, fontFamily: THEME.font },
    } : undefined,
  };
}

function valueAxis(unit, sym, extra = {}, values) {
  return {
    type: 'value',
    axisLabel: { color: THEME.muted, fontSize: 13, formatter: axisFmt(unit, sym, values), fontFamily: THEME.font },
    splitLine: { lineStyle: { color: THEME.grid, width: 1, type: 'solid' } },
    axisLine: { show: false }, axisTick: { show: false },
    splitNumber: 4,
    ...extra,
  };
}

function catAxis(cats, extra = {}) {
  return {
    type: 'category', data: cats,
    axisLabel: { color: THEME.ink2, fontSize: 14, fontFamily: THEME.font, interval: 0, hideOverlap: true },
    axisLine: { lineStyle: { color: THEME.axis, width: 1 } },
    axisTick: { show: false },
    ...extra,
  };
}

function barItem(v, color) {
  return { value: v, itemStyle: { color, borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] } };
}

function hbarItem(v, color) {
  return { value: v, itemStyle: { color, borderRadius: v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] } };
}

function emphasisIndex(cats, highlight) {
  if (!highlight) return -1;
  return cats.indexOf(highlight);
}

function optBar(ch, w, h) {
  const cats = ch.categories || [];
  const series = ch.series || [];
  const multi = series.length > 1;
  const stacked = ch.kind === 'stacked-bar' || ch.kind === 'stacked-100';
  const sym = ch.sym || '$';
  let data = series.map((s) => s.data.map((v) => (v === null || v === undefined ? null : v)));
  let unit = ch.unit || 'num';
  if (ch.kind === 'stacked-100') {
    const totals = cats.map((_, j) => data.reduce((acc, d) => acc + (d[j] || 0), 0));
    data = data.map((d) => d.map((v, j) => (totals[j] ? (v || 0) / totals[j] : null)));
    unit = 'pct';
  }
  const hi = emphasisIndex(cats, ch.highlight);
  const labelAll = !multi && cats.length <= 8;
  const o = base(ch, w, h, { legend: multi });
  o.xAxis = catAxis(cats);
  o.yAxis = valueAxis(unit, sym, ch.kind === 'stacked-100' ? { max: 1 } : {}, data.flat());
  o.series = series.map((s, i) => {
    const color = colorFor(s.role, i);
    return {
      name: s.name, type: 'bar', stack: stacked ? (s.stack || 'all') : undefined, itemStyle: { color },
      barMaxWidth: 24, barGap: '30%', barCategoryGap: multi && !stacked ? '38%' : '45%',
      data: data[i].map((v, j) => {
        const c = hi >= 0 && j !== hi && !multi ? THEME.roles.muted : color;
        const it = barItem(v, c);
        if (stacked) {
          const top = i === series.length - 1;
          it.itemStyle.borderRadius = top ? [4, 4, 0, 0] : 0;
          it.itemStyle.borderColor = THEME.paper; it.itemStyle.borderWidth = 2;
        }
        return it;
      }),
      label: {
        show: stacked ? false : (labelAll || (multi && !stacked)),
        position: 'outside', distance: 6,
        color: THEME.ink, fontSize: multi ? 12 : 14, fontFamily: THEME.font, fontWeight: 500,
        formatter: (p) => {
          if (p.value === null || p.value === undefined || p.value === 0) return '';
          if (multi && p.dataIndex !== cats.length - 1) return '';
          return fmtNum(p.value, unit, sym);
        },
      },
    };
  });
  o.series.forEach((s) => {
    s.data.forEach((d) => { if (d.value < 0) d.label = { position: 'bottom' }; });
  });
  if (stacked) {
    // total on top of each stack
    const totals = cats.map((_, j) => data.reduce((acc, d) => acc + (d[j] || 0), 0));
    if (ch.kind === 'stacked-bar') {
      o.series.push({ type: 'bar', stack: 'all', data: totals.map(() => 0), barMaxWidth: 24, silent: true,
        label: { show: true, position: 'top', color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
          formatter: (p) => fmtNum(totals[p.dataIndex], unit, sym) }, itemStyle: { color: 'transparent' } });
    } else {
      // label each segment of the latest column with its share
      o.series.forEach((s, i) => {
        s.label = { show: true, position: 'inside', color: '#fff', fontSize: 12, fontWeight: 600, fontFamily: THEME.font,
          formatter: (p) => (p.dataIndex === cats.length - 1 || p.dataIndex === 0) && p.value > 0.08 ? fmtNum(p.value, 'pct', sym, true) : '' };
      });
    }
  }
  if (o.legend) o.legend.data = series.map((s) => s.name);
  addAnnotations(o, ch, cats);
  return o;
}

function optHbar(ch, w, h) {
  const s = ch.series[0];
  const pairs = ch.categories.map((c, i) => [c, s.data[i]]).filter((p) => p[1] !== null && p[1] !== undefined);
  if (ch.sort !== false) pairs.sort((a, b) => a[1] - b[1]);
  const cats = pairs.map((p) => p[0]);
  const hi = ch.highlight;
  const o = base(ch, w, h, { rightPad: 70 });
  o.yAxis = catAxis(cats, { axisLine: { show: false } });
  o.xAxis = valueAxis(ch.unit, ch.sym, { splitNumber: 4 }, pairs.map((p) => p[1]));
  o.series = [{
    type: 'bar', barMaxWidth: 22, barCategoryGap: '40%',
    data: pairs.map(([c, v]) => hbarItem(v, !hi || c === hi ? colorFor(s.role, 0) : THEME.roles.muted)),
    label: { show: true, position: 'right', color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
      formatter: (p) => fmtNum(p.value, ch.unit, ch.sym) },
  }];
  return o;
}

function optLine(ch, w, h) {
  const cats = ch.categories || [];
  const series = ch.series || [];
  const multi = series.length > 1;
  const o = base(ch, w, h, { legend: multi, rightPad: 64 });
  o.xAxis = catAxis(cats, { boundaryGap: false });
  o.yAxis = valueAxis(ch.unit, ch.sym, { scale: !!ch.scale }, series.flatMap((s) => s.data));
  o.series = series.map((s, i) => {
    const color = colorFor(s.role, i);
    const last = s.data.reduce((acc, v, j) => (v !== null && v !== undefined ? j : acc), -1);
    return {
      name: s.name, type: 'line', data: s.data, connectNulls: false,
      lineStyle: { width: 2, color, cap: 'round', join: 'round' },
      itemStyle: { color, borderColor: THEME.paper, borderWidth: 2 },
      symbol: 'circle', symbolSize: 8, showSymbol: true,
      areaStyle: ch.kind === 'area' ? { color, opacity: 0.1 } : undefined,
      label: { show: true, position: 'right', distance: 8, color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
        formatter: (p) => (p.dataIndex === last ? fmtNum(p.value, ch.unit, ch.sym) : '') },
      markLine: i === 0 && hasNegative(series) ? zeroLine() : undefined,
    };
  });
  addAnnotations(o, ch, cats);
  return o;
}

function hasNegative(series) {
  return series.some((s) => s.data.some((v) => v < 0));
}

function zeroLine() {
  return { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: THEME.axis, width: 1, type: 'solid' }, data: [{ yAxis: 0 }] };
}

function addAnnotations(o, ch, cats) {
  const ann = ch.annotations || [];
  if (!ann.length || !o.series.length) return;
  o.series[0].markPoint = {
    symbol: 'circle', symbolSize: 1, silent: true,
    data: ann.filter((a) => cats.includes(a.at)).map((a) => {
      const j = cats.indexOf(a.at);
      const vals = (ch.series || []).map((s) => s.data[j]).filter((v) => v !== null && v !== undefined);
      return {
        coord: [a.at, Math.max(...vals, 0)],
        label: { show: true, position: 'top', distance: 26, formatter: a.text, color: THEME.ink2, fontSize: 12, fontFamily: THEME.font,
          backgroundColor: THEME.paper, padding: [2, 4], width: 150, overflow: 'break', lineHeight: 15 },
      };
    }),
  };
}

function optWaterfall(ch, w, h) {
  // Floating bars drawn as stacks. ECharts stacks positive and negative values separately,
  // so every bar is split into its part above zero and its part below zero, each on its own
  // transparent base. That keeps bars that cross zero (or sit wholly below it) in the right place.
  const steps = ch.steps || [];
  let running = 0;
  const cats = [], spans = [], signed = [];
  steps.forEach((s) => {
    cats.push(s.label);
    if (s.total) {
      const v = s.value !== null && s.value !== undefined ? s.value : running;
      running = v;
      spans.push({ lo: Math.min(0, v), hi: Math.max(0, v), kind: 'total' });
      signed.push(v);
    } else {
      const v = s.value || 0;
      const start = running;
      running += v;
      spans.push({ lo: Math.min(start, running), hi: Math.max(start, running), kind: v >= 0 ? 'up' : 'down' });
      signed.push(v);
    }
  });
  const n = spans.length;
  const blank = () => new Array(n).fill(null);
  const basePos = blank(), baseNeg = blank();
  const parts = { total: [blank(), blank()], up: [blank(), blank()], down: [blank(), blank()] };
  spans.forEach((sp, j) => {
    const [pos, neg] = parts[sp.kind];
    if (sp.hi > 0) { // portion above zero
      const lo = Math.max(sp.lo, 0);
      basePos[j] = lo; pos[j] = sp.hi - lo;
    }
    if (sp.lo < 0) { // portion below zero
      const hi = Math.min(sp.hi, 0);
      baseNeg[j] = hi; neg[j] = sp.lo - hi;
    }
    if (sp.hi === sp.lo) { basePos[j] = sp.hi; pos[j] = 0; }
  });
  const o = base(ch, w, h);
  o.xAxis = catAxis(cats, { axisLabel: { color: THEME.ink2, fontSize: 13, interval: 0, width: Math.max(80, (w - 80) / cats.length - 8), overflow: 'break', fontFamily: THEME.font } });
  o.yAxis = valueAxis(ch.unit, ch.sym);
  const color = { total: THEME.roles.primary, up: THEME.roles.positive, down: THEME.roles.negative };
  o.series = [
    { type: 'bar', stack: 'w', data: basePos, itemStyle: { color: 'transparent' }, silent: true, barMaxWidth: 40 },
    { type: 'bar', stack: 'w', data: baseNeg, itemStyle: { color: 'transparent' }, silent: true, barMaxWidth: 40 },
  ];
  ['total', 'up', 'down'].forEach((k) => {
    parts[k].forEach((arr, side) => o.series.push({ type: 'bar', stack: 'w', data: arr, barMaxWidth: 40,
      itemStyle: { color: color[k], borderRadius: side === 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] } }));
  });
  // value labels sit just above the top of each bar
  o.series.push({ type: 'scatter', data: spans.map((sp, j) => [j, sp.hi]), symbolSize: 0, silent: true, z: 10,
    label: { show: true, position: 'top', distance: 6, color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
      formatter: (p) => fmtNum(signed[p.dataIndex], ch.unit, ch.sym) } });
  return o;
}

function optSankey(ch, w, h) {
  const colors = {
    Revenue: THEME.roles.primary, 'Gross profit': THEME.roles.primary, 'Operating income': THEME.roles.tertiary,
    'Cost of revenue': THEME.roles.muted, 'R&D': THEME.roles.muted, 'SG&A': THEME.roles.muted, 'Other operating costs': THEME.roles.muted,
  };
  const totals = {};
  (ch.links || []).forEach((l) => { totals[l.target] = (totals[l.target] || 0) + l.value; totals[l.source] = Math.max(totals[l.source] || 0, 0); });
  const rev = (ch.links || []).filter((l) => l.source === 'Revenue').reduce((a, l) => a + l.value, 0);
  totals.Revenue = rev;
  return {
    animation: false,
    textStyle: { fontFamily: THEME.font },
    series: [{
      type: 'sankey', left: 8, right: 230, top: 12, bottom: 12, nodeWidth: 16, nodeGap: 16, nodeAlign: 'left',
      layoutIterations: 0, draggable: false,
      data: (ch.nodes || []).map((n) => ({ name: n.name, itemStyle: { color: colors[n.name] || THEME.roles.muted, borderWidth: 0 } })),
      links: (ch.links || []).map((l) => ({ ...l, lineStyle: { color: colors[l.target] === THEME.roles.muted ? THEME.roles.muted : (colors[l.target] || THEME.roles.primary), opacity: 0.22, curveness: 0.5 } })),
      label: {
        color: THEME.ink, fontSize: 14, fontFamily: THEME.font, position: 'right',
        formatter: (p) => `{n|${p.name}}\n{v|${fmtNum(totals[p.name], 'money_m', ch.sym)}  ·  ${fmtNum(totals[p.name] / rev, 'pct')}}`,
        rich: { n: { fontSize: 14, fontWeight: 600, color: THEME.ink, fontFamily: THEME.font, lineHeight: 18 },
          v: { fontSize: 13, color: THEME.ink2, fontFamily: THEME.font, lineHeight: 16 } },
      },
    }],
  };
}

function optScatter(ch, w, h) {
  const pts = ch.points || [];
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const pad = (arr, f) => {
    const lo = Math.min(...arr);
    const hi = Math.max(...arr);
    const span = hi - lo || Math.abs(hi) || 1;
    return { min: lo - span * f, max: hi + span * f };
  };
  const xr = pad(xs, 0.12);
  const yr = pad(ys, 0.15);
  const o = base(ch, w, h, { rightPad: 90, bottom: 30 });
  o.grid.top = 40;
  o.grid.left = 16;
  o.xAxis = valueAxis(ch.x_unit || 'pct', ch.sym, {
    name: ch.x_label, nameLocation: 'middle', nameGap: 32, nameTextStyle: { color: THEME.ink2, fontSize: 13, fontFamily: THEME.font },
    min: xr.min, max: xr.max, axisLine: { show: true, lineStyle: { color: THEME.axis } },
  }, [xr.min, xr.max]);
  o.yAxis = valueAxis(ch.unit || 'x', ch.sym, {
    name: ch.y_label, nameLocation: 'end', nameGap: 14,
    nameTextStyle: { color: THEME.ink2, fontSize: 13, fontFamily: THEME.font, align: 'left', padding: [0, 0, 0, -30] },
    min: yr.min, max: yr.max,
  }, [yr.min, yr.max]);
  o.series = [{
    type: 'scatter', symbolSize: 14,
    data: pts.map((p) => ({
      value: [p.x, p.y], name: p.label,
      itemStyle: { color: p.highlight ? THEME.roles.primary : THEME.roles.muted, borderColor: THEME.paper, borderWidth: 2 },
      label: { show: true, position: 'right', distance: 8, formatter: p.label, color: p.highlight ? THEME.ink : THEME.ink2,
        fontWeight: p.highlight ? 600 : 400, fontSize: 13, fontFamily: THEME.font },
    })),
    labelLayout: { hideOverlap: false, moveOverlap: 'shiftY' },
  }];
  return o;
}

function optFootball(ch, w, h) {
  const bars = (ch.bars || []).filter((b) => b.low !== null && b.high !== null).reverse();
  const cats = bars.map((b) => b.label);
  const kindColor = { dcf: THEME.roles.primary, market: THEME.roles.muted, peers: THEME.roles.secondary, history: THEME.roles.tertiary, analysts: THEME.roles.muted };
  const o = base(ch, w, h, { rightPad: 60 });
  o.yAxis = catAxis(cats, { axisLine: { show: false }, axisLabel: { color: THEME.ink2, fontSize: 14, fontFamily: THEME.font, width: 260, overflow: 'break' } });
  // A range that dips below zero is drawn as two pieces: the part below zero stacks left of the
  // axis and the part above zero stacks right, so neither end is clipped or shifted.
  const anyNeg = bars.some((b) => Math.min(b.low, b.high) < 0);
  o.xAxis = valueAxis('ps', ch.sym, anyNeg ? { scale: false } : { scale: false, min: 0 });
  const lo = (b) => Math.min(b.low, b.high), hi = (b) => Math.max(b.low, b.high);
  const label = (pos, key) => ({ show: true, position: pos, color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
    formatter: (p) => fmtNum(bars[p.dataIndex][key], 'ps', ch.sym, true) });
  const colorOf = (b) => kindColor[b.kind] || THEME.roles.primary;
  o.series = [
    { type: 'bar', stack: 'ff', data: bars.map((b) => (lo(b) >= 0 ? lo(b) : 0)), itemStyle: { color: 'transparent' }, silent: true, barMaxWidth: 22,
      label: { ...label('insideRight', 'low'), color: THEME.ink2, fontWeight: 400,
        formatter: (p) => (lo(bars[p.dataIndex]) >= 0 ? fmtNum(bars[p.dataIndex].low, 'ps', ch.sym, true) : '') } },
    { type: 'bar', stack: 'ff', barMaxWidth: 22,
      data: bars.map((b) => (lo(b) < 0 ? { value: lo(b), itemStyle: { color: colorOf(b), borderRadius: [4, 0, 0, 4] } } : null)),
      label: { ...label('left', 'low'), color: THEME.ink2, fontWeight: 400 } },
    { type: 'bar', stack: 'ff', barMaxWidth: 22,
      data: bars.map((b) => ({ value: hi(b) - Math.max(lo(b), 0), itemStyle: { color: colorOf(b), borderRadius: lo(b) < 0 ? [0, 4, 4, 0] : 4 } })),
      label: { ...label('right', 'high') },
      markLine: ch.price ? {
        silent: true, symbol: 'none', lineStyle: { color: THEME.ink, width: 1.5, type: 'solid' },
        label: { formatter: `Price ${fmtNum(ch.price, 'ps', ch.sym)}`, color: THEME.ink, fontSize: 13, fontWeight: 600, fontFamily: THEME.font, position: 'end' },
        data: [{ xAxis: ch.price }],
      } : undefined },
  ];
  const mids = bars.map((b) => (b.mid ? [b.mid, b.label] : null)).filter(Boolean);
  if (mids.length) {
    o.series.push({ type: 'scatter', data: mids, symbol: 'circle', symbolSize: 10, z: 5,
      itemStyle: { color: THEME.paper, borderColor: THEME.ink, borderWidth: 2 } });
  }
  return o;
}

function optPrice(ch, w, h) {
  const dates = ch.dates || [];
  const multi = (ch.series || []).length > 1;
  const o = base(ch, w, h, { legend: multi, rightPad: 70 });
  o.xAxis = {
    type: 'category', data: dates, boundaryGap: false,
    axisLabel: { color: THEME.ink2, fontSize: 13, fontFamily: THEME.font,
      interval: (i) => i === 0 || dates[i].slice(0, 4) !== dates[i - 1].slice(0, 4), formatter: (v) => v.slice(0, 4) },
    axisLine: { lineStyle: { color: THEME.axis } }, axisTick: { show: false },
  };
  o.yAxis = valueAxis(ch.unit || 'ps', ch.sym, { scale: true }, (ch.series || []).flatMap((s) => s.data));
  if ((ch.events || []).length) o.grid.top = Math.max(o.grid.top, 30);
  o.series = (ch.series || []).map((s, i) => {
    const color = colorFor(s.role, i);
    const last = s.data.length - 1;
    return {
      name: s.name, type: 'line', data: s.data, showSymbol: false, symbol: 'circle', symbolSize: 8,
      lineStyle: { width: 2, color }, itemStyle: { color, borderColor: THEME.paper, borderWidth: 2 },
      label: { show: true, position: 'right', color: THEME.ink, fontSize: 13, fontWeight: 500, fontFamily: THEME.font,
        formatter: (p) => (p.dataIndex === last ? fmtNum(p.value, ch.unit || 'ps', ch.sym) : '') },
      endLabel: undefined,
      markLine: i === 0 && (ch.events || []).length ? {
        silent: true, symbol: 'none', lineStyle: { color: THEME.axis, width: 1, type: 'solid' },
        label: { show: true, position: 'end', rotate: 0, distance: 6, color: THEME.ink, fontSize: 12, fontWeight: 600, fontFamily: THEME.font },
        data: (ch.events || []).map((e, k) => {
          const idx = dates.findIndex((d) => d >= e.date);
          return idx < 0 ? null : { xAxis: idx, label: { formatter: `${k + 1}` } };
        }).filter(Boolean),
      } : undefined,
    };
  });
  return o;
}

function renderChart(ch, w, h) {
  let opt;
  switch (ch.kind) {
    case 'bar': case 'stacked-bar': case 'stacked-100': case 'maturity-ladder': opt = optBar(ch, w, h); break;
    case 'hbar': opt = optHbar(ch, w, h); break;
    case 'line': case 'area': opt = optLine(ch, w, h); break;
    case 'waterfall': opt = optWaterfall(ch, w, h); break;
    case 'sankey': opt = optSankey(ch, w, h); break;
    case 'scatter': opt = optScatter(ch, w, h); break;
    case 'football-field': opt = optFootball(ch, w, h); break;
    case 'price': opt = optPrice(ch, w, h); break;
    default: throw new Error(`unknown chart kind ${ch.kind}`);
  }
  const chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width: w, height: h });
  chart.setOption(opt);
  const svg = chart.renderToSVGString();
  chart.dispose();
  return svg;
}

(typeof window !== 'undefined' ? window : globalThis).TeardownCharts = { renderChart, fmtNum, THEME };
