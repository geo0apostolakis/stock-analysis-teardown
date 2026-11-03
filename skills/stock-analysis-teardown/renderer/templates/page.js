// Runs inside the headless Chrome page, called step by step from render.mjs over CDP.
// Nothing here runs on its own, and render.mjs strips the scripts before saving deck.html.
(function () {
  const px = (v) => parseFloat(v) || 0;

  function lines(el) {
    const cs = getComputedStyle(el);
    return Math.round(el.getBoundingClientRect().height / px(cs.lineHeight));
  }

  function overflowing(el) {
    return el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
  }

  // 1. Shrink text that does not fit. Titles keep to two lines, boxes marked data-fit keep their
  //    height, single-line values marked data-fitw keep their width. Every shrink is logged for QA.
  window.__fit = function () {
    const log = [];
    document.querySelectorAll('[data-title]').forEach((el) => {
      const max = +(el.dataset.lines || 2);
      const min = +(el.dataset.min || 32);
      let fs = px(getComputedStyle(el).fontSize);
      let guard = 0;
      while (lines(el) > max && fs > min && guard++ < 40) { fs -= 1; el.style.fontSize = fs + 'px'; }
    });
    document.querySelectorAll('[data-fit]').forEach((el) => {
      const min = +(el.dataset.fit || 15);
      let fs = px(getComputedStyle(el).fontSize);
      const start = fs;
      let guard = 0;
      while (overflowing(el) && fs > min && guard++ < 60) { fs -= 0.5; el.style.fontSize = fs + 'px'; }
      if (fs < start) log.push({ slide: el.closest('.slide').dataset.page, from: start, to: fs });
    });
    document.querySelectorAll('[data-fitw]').forEach((el) => {
      let fs = px(getComputedStyle(el).fontSize);
      const min = +(el.dataset.fitw || 22);
      let guard = 0;
      while (el.scrollWidth > el.clientWidth + 1 && fs > min && guard++ < 40) { fs -= 1; el.style.fontSize = fs + 'px'; }
    });
    return log;
  };

  // 2. Draw every chart at the size its box ended up with, using the loaded web fonts for text metrics.
  window.__renderCharts = async function () {
    await Promise.all(['400 14px Inter', '500 14px Inter', '600 14px Inter', '600 20px "Source Serif 4"']
      .map((f) => document.fonts.load(f)));
    const specs = JSON.parse(document.getElementById('chart-specs').textContent);
    const out = [];
    document.querySelectorAll('.plot[data-chart]').forEach((el) => {
      const ch = specs[el.dataset.chart];
      const r = el.getBoundingClientRect();
      const w = Math.floor(r.width);
      const h = Math.floor(r.height);
      try {
        el.innerHTML = window.TeardownCharts.renderChart(ch, w, h);
        out.push({ id: el.dataset.chart, kind: ch.kind, w, h });
      } catch (e) {
        el.innerHTML = '<div class="chart-err">Chart failed: ' + String(e.message).replace(/</g, '&lt;') + '</div>';
        out.push({ id: el.dataset.chart, kind: ch.kind, error: String(e.message) });
      }
    });
    return out;
  };

  function rectsOverlap(a, b, pad) {
    return a.left < b.right - pad && b.left < a.right - pad && a.top < b.bottom - pad && b.top < a.bottom - pad;
  }

  // ECharts overflow:'break' draws each wrapped line as its own <text> under one
  // parent <g>. Those lines share a parent; different axis ticks do not.
  function sameWrappedLabel(a, b) {
    return a.x.parentNode && a.x.parentNode === b.x.parentNode;
  }

  // 3. Look for the things a reader would notice: clipped or overflowing text, titles that run long,
  //    charts squeezed into small boxes, labels that collide, numbers that never got filled in.
  window.__qa = function () {
    const slides = [];
    document.querySelectorAll('.slide').forEach((s) => {
      const issues = [];
      const add = (level, msg) => issues.push({ level, msg });
      const snippet = (el) => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70);
      const sr = s.getBoundingClientRect();

      s.querySelectorAll('[data-fit]').forEach((el) => {
        const over = el.scrollHeight - el.clientHeight;
        if (over > 1) add('error', `text does not fit, ${over}px too tall even at ${el.style.fontSize || 'base size'}: "${snippet(el)}"`);
        else if (el.style.fontSize && px(el.style.fontSize) <= +(el.dataset.fit || 15)) add('warn', `text shrunk to the minimum size (${el.style.fontSize}); cut words: "${snippet(el)}"`);
        if (el.scrollWidth > el.clientWidth + 1) add('error', `content wider than its box: "${snippet(el)}"`);
      });
      s.querySelectorAll('.bd, .cv, .dv').forEach((bd) => {
        if (bd.scrollHeight > bd.clientHeight + 2) add('error', `slide body overflows by ${bd.scrollHeight - bd.clientHeight}px`);
      });
      if (s.scrollHeight > s.clientHeight + 2) add('error', 'slide content is taller than the page');
      const t = s.querySelector('[data-title]');
      if (t) {
        const n = lines(t);
        if (n > 2) add('warn', `title runs to ${n} lines; shorten it`);
        if (t.style.fontSize) add('info', `title shrunk to ${t.style.fontSize}`);
      }
      s.querySelectorAll('.kv').forEach((k) => {
        if (k.scrollWidth > k.clientWidth + 1) add('error', `KPI value clipped: "${snippet(k)}"`);
      });
      s.querySelectorAll('.tbl').forEach((tb) => {
        if (tb.scrollWidth > tb.clientWidth + 1) add('error', `table wider than its box by ${tb.scrollWidth - tb.clientWidth}px`);
      });
      // anything poking out past the content edge
      const right = sr.right - 40;
      s.querySelectorAll('.hd, .bd *:not(svg *), .bl').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.width && r.right > right + 1 && !el.closest('.plot')) add('error', `element runs past the right margin: "${snippet(el)}"`);
      });
      s.querySelectorAll('.plot').forEach((p) => {
        const pr = p.getBoundingClientRect();
        const name = (p.closest('.chart')?.querySelector('.ct')?.innerText || 'chart').trim();
        if (pr.height < 180) add('warn', `chart "${name}" only has ${Math.round(pr.height)}px of height`);
        if (pr.width < 260) add('warn', `chart "${name}" only has ${Math.round(pr.width)}px of width`);
        const svg = p.querySelector('svg');
        if (!svg) { add('error', `chart "${name}" did not render`); return; }
        const texts = [...svg.querySelectorAll('text')].filter((x) => (x.textContent || '').trim());
        const rects = texts.map((x) => ({ x, r: x.getBoundingClientRect() }));
        const seen = new Set();
        for (let i = 0; i < rects.length; i++) {
          const a = rects[i];
          if (a.r.left < pr.left - 2 || a.r.right > pr.right + 2 || a.r.top < pr.top - 2 || a.r.bottom > pr.bottom + 2) {
            add('warn', `chart "${name}": label "${a.x.textContent.trim()}" is cut off at the chart edge`);
          }
          for (let j = i + 1; j < rects.length; j++) {
            const b = rects[j];
            if (sameWrappedLabel(a, b)) continue;
            if (rectsOverlap(a.r, b.r, 2)) {
              const key = a.x.textContent + '|' + b.x.textContent;
              if (seen.has(key)) continue;
              seen.add(key);
              add('warn', `chart "${name}": labels overlap ("${a.x.textContent.trim()}" and "${b.x.textContent.trim()}")`);
            }
          }
        }
      });
      if (/\{\{\s*m:|\[\[missing|\[\[bad/.test(s.innerText)) add('error', 'an unresolved number token is printed on the slide');
      // keep the list short: the designer reads every line
      const capped = issues.slice(0, 14);
      if (issues.length > 14) capped.push({ level: 'info', msg: `${issues.length - 14} more issues on this slide` });
      slides.push({ page: +s.dataset.page, id: s.dataset.id, layout: s.dataset.layout, issues: capped });
    });
    const fonts = {
      serif: document.fonts.check('600 40px "Source Serif 4"'),
      sans: document.fonts.check('400 20px Inter'),
    };
    return { slides, fonts };
  };
})();
