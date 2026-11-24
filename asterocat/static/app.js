'use strict';
const $ = id => document.getElementById(id);
const COLORS = ['#5b8dee','#a78bfa','#34d399','#fbbf24','#f87171','#38bdf8','#fb923c','#e879f9'];
const CSV_COLUMNS = ['cid','bibcode','pipeline','numax','e_numax','dnu','e_dnu',
                     'frequency_units','teff','e_teff'];
const selected = new Map();
let page = {results: [], total: 0, offset: 0, limit: 200};
let active = {sort_col: 'cid', sort_dir: 'asc'};
let sources = null;
let batchNames = [];
let requestVersion = 0;
let plotVersion = 0;
let detailVersion = 0;
let background = new Map();
let hasSearch = false;

const esc = value => String(value ?? '').replace(/[&<>"']/g,
  char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const key = row => JSON.stringify([row.cid, row.bibcode, row.pipeline]);
const valid = value => value !== null && value !== undefined && value !== -1 && Number.isFinite(+value);
const fmt = (value, digits=3) => valid(value) ? Number(value).toFixed(digits) : '—';
const ref = code => code ? `<a href="https://ui.adsabs.harvard.edu/abs/${encodeURIComponent(code)}" target="_blank" rel="noopener">${esc(code)}</a>` : '—';
const status = text => { $('status').textContent = text; };

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function filtersFromControls() {
  const filters = {sort_col: active.sort_col, sort_dir: active.sort_dir};
  for (const quantity of ['numax', 'dnu']) {
    for (const bound of ['min', 'max']) {
      const value = $(`${quantity}-${bound}`).value;
      if (value !== '') filters[`${quantity}_${bound}`] = value;
    }
  }
  if (sources !== null) {
    const checked = [...document.querySelectorAll('input[name=source]:checked')].map(el => el.value);
    if (checked.length !== sources.length) filters.sources = checked;
  }
  return filters;
}

async function loadSources() {
  try {
    sources = await api('/api/sources');
    $('db-stats').textContent = `${sources.length} publications · ${sources.reduce((n,s) => n+s.n,0).toLocaleString()} measurement sets`;
    $('source-list').innerHTML = sources.map((s, i) => `<label class="source-item">
      <input type="checkbox" name="source" value="${esc(s.bibcode)}" checked>
      <span class="source-dot" style="background:${COLORS[i % COLORS.length]}"></span>
      <span>${esc(s.bibcode)}</span><span class="source-count">${s.n.toLocaleString()}</span></label>`).join('');
  } catch (error) { $('db-stats').textContent = 'Database unavailable'; status(error.message); }
}

async function search(names=null) {
  const version = ++requestVersion;
  const candidate = filtersFromControls();
  const query = $('q-input').value.trim();
  status('Searching…');
  $('batch-warnings').textContent = '';
  try {
    if (names || query) {
      const result = await api('/api/resolve', {
        names: names || [query], online: $('online-lookup').checked
      });
      if (version !== requestVersion) return;
      candidate.cids = result.cids;
      const warnings = [];
      if (result.missing.length) warnings.push(`Not found: ${result.missing.join(', ')}`);
      if (result.lookup_errors.length) warnings.push(`SIMBAD unavailable for: ${result.lookup_errors.join(', ')}`);
      for (const [cid, aliases] of Object.entries(result.duplicates)) {
        warnings.push(`Same target: ${aliases.join(', ')} → ${cid}`);
      }
      $('batch-warnings').textContent = warnings.join('\n');
    }
    const data = await api('/api/search', {...candidate, limit: page.limit, offset: 0});
    if (version !== requestVersion) return;
    active = candidate;
    hasSearch = true;
    ++plotVersion;
    $('plot-svg').innerHTML = '';
    $('plot-legend').textContent = '';
    $('active-filters').textContent = names ? `${names.length} input targets` : query;
    render(data);
    status('');
    if ($('plot-panel').classList.contains('visible')) drawPlot();
  } catch (error) { if (version === requestVersion) status(error.message); }
}

async function loadPage(offset, candidate=active) {
  const version = ++requestVersion;
  status('Loading…');
  try {
    const data = await api('/api/search', {...candidate, limit: page.limit, offset});
    if (version !== requestVersion) return;
    active = candidate;
    render(data);
    status('');
  } catch (error) { if (version === requestVersion) status(error.message); }
}

function render(data) {
  page = data;
  $('result-count').textContent = data.total.toLocaleString();
  $('page-info').textContent = `page ${Math.floor(data.offset/data.limit)+1} of ${Math.max(1,Math.ceil(data.total/data.limit))}`;
  $('prev-btn').disabled = data.offset === 0;
  $('next-btn').disabled = data.offset + data.limit >= data.total;
  $('export-btn').disabled = data.total === 0;
  $('results-body').innerHTML = data.results.length ? data.results.map((row, i) => `<tr class="result-row" data-index="${i}">
    <td><input type="checkbox" class="row-cb" aria-label="Select ${esc(row.cid)}" ${selected.has(key(row)) ? 'checked' : ''}></td>
    <td><a href="#" class="target-link" data-cid="${esc(row.cid)}">${esc(row.cid)}</a></td>
    <td>${ref(row.bibcode)}</td><td>${ref(row.pipeline)}</td>
    ${['numax','e_numax','dnu','e_dnu','teff','e_teff'].map(c => `<td class="num-cell">${fmt(row[c])}</td>`).join('')}
    </tr>`).join('') : '<tr><td colspan="10" class="state-msg">No results.</td></tr>';
  document.querySelectorAll('#results-body tr.result-row').forEach(tr => {
    const row = page.results[+tr.dataset.index];
    tr.classList.toggle('selected', selected.has(key(row)));
    tr.addEventListener('click', event => {
      if (event.target.closest('a')) return;
      const box = tr.querySelector('input');
      if (event.target !== box) box.checked = !box.checked;
      if (box.checked) selected.set(key(row), row); else selected.delete(key(row));
      tr.classList.toggle('selected', box.checked);
      selectionState();
    });
  });
  selectionState();
  document.querySelectorAll('th[data-col]').forEach(th => {
    th.classList.toggle('sort-asc', th.dataset.col === active.sort_col && active.sort_dir === 'asc');
    th.classList.toggle('sort-desc', th.dataset.col === active.sort_col && active.sort_dir === 'desc');
    th.setAttribute('aria-sort', th.dataset.col === active.sort_col ?
      (active.sort_dir === 'asc' ? 'ascending' : 'descending') : 'none');
  });
}

function selectionState() {
  $('selected-count').textContent = selected.size ? `${selected.size} selected` : '';
  $('export-selected-btn').disabled = !selected.size;
  const count = page.results.filter(row => selected.has(key(row))).length;
  $('select-all-cb').checked = page.results.length > 0 && count === page.results.length;
  $('select-all-cb').indeterminate = count > 0 && count < page.results.length;
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportRows(rows, filename) {
  const cell = value => '"' + String(value ?? -1).replace(/"/g, '""') + '"';
  const lines = [CSV_COLUMNS.join(',')];
  for (const row of rows) lines.push(CSV_COLUMNS.map(c => cell(row[c])).join(','));
  download(new Blob([lines.join('\r\n')], {type:'text/csv;charset=utf-8'}), filename);
}

async function exportAll() {
  $('export-btn').disabled = true;
  status('Exporting…');
  try {
    const response = await fetch('/api/export', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(active)});
    if (!response.ok) throw new Error((await response.json()).error);
    download(await response.blob(), 'asterocat_results.csv');
    status('Export complete.');
  } catch (error) { status(error.message); }
  finally { $('export-btn').disabled = !page.total; }
}

function measurementTable(rows) {
  return `<table><thead><tr><th>Publication</th><th>Pipeline</th><th>numax (uHz)</th>
    <th>e_numax</th><th>dnu (uHz)</th><th>e_dnu</th><th>Teff (K)</th><th>e_Teff</th></tr></thead><tbody>` +
    rows.map(row => `<tr><td>${ref(row.bibcode)}</td><td>${ref(row.pipeline)}</td>` +
      ['numax','e_numax','dnu','e_dnu','teff','e_teff'].map(c => `<td>${fmt(row[c])}</td>`).join('') + '</tr>').join('') + '</tbody></table>';
}

function weightedMean(rows, column) {
  const usable = rows.filter(row => valid(row[column]) && row[column] > 0);
  let sum = 0, weights = 0;
  for (const row of usable) {
    const err = row[`e_${column}`];
    const sigma = valid(err) && err > 0 ? err : 0.1 * row[column];
    const weight = 1 / (sigma * sigma);
    sum += weight * row[column]; weights += weight;
  }
  return weights > 0 ? sum / weights : -1;
}

async function openTarget(cid) {
  const version = ++detailVersion;
  $('target-title').textContent = cid;
  $('target-body').textContent = 'Loading…';
  $('target-modal').classList.add('open');
  try {
    const detail = await api(`/api/target/${encodeURIComponent(cid)}`);
    if (version !== detailVersion) return;
    const mean = ['numax','dnu'].map(c => `${c}: ${fmt(weightedMean(detail.results,c))} uHz`).join('; ');
    $('target-body').innerHTML = `<p>${esc(detail.aliases.join(' · '))}</p>
      ${measurementTable(detail.results)}
      <p>Weighted means: ${mean}. Indicative only; missing uncertainties use 10% of the value.</p>
      <details><summary>All seismic observables (${detail.measurements.length})</summary><table>
      <thead><tr><th>Observable</th><th>Value</th><th>Error</th><th>Units</th><th>Publication</th><th>Pipeline</th></tr></thead><tbody>
      ${detail.measurements.map(r => `<tr><td>${esc(r.Obsname)}</td><td>${fmt(r.value)}</td><td>${fmt(r.err)}</td><td>${esc(r.units)}</td><td>${ref(r.bibcode)}</td><td>${ref(r.pipeline)}</td></tr>`).join('')}
      </tbody></table></details>
      <details><summary>Individual modes (${detail.modes.length})</summary><table>
      <thead><tr><th>ell</th><th>n_p</th><th>n_g</th><th>Frequency (uHz)</th><th>Error</th><th>Linewidth (uHz)</th><th>Error</th><th>Amplitude</th><th>Error</th><th>Publication</th><th>Pipeline</th></tr></thead><tbody>
      ${detail.modes.map(r => `<tr>${['ell','n_p','n_g','freq','freq_err','Γ','Γ_err','A','A_err'].map(c => `<td>${['ell','n_p','n_g'].includes(c) ? esc(r[c]) : fmt(r[c])}</td>`).join('')}<td>${ref(r.bibcode)}</td><td>${ref(r.pipeline)}</td></tr>`).join('')}
      </tbody></table></details>`;
  } catch (error) { if (version === detailVersion) $('target-body').textContent = error.message; }
}

async function drawPlot() {
  const version = ++plotVersion;
  const x = $('x-col').value, y = $('y-col').value;
  const xlog = $('x-log').checked, ylog = $('y-log').checked;
  const xinv = $('x-inv').checked, yinv = $('y-inv').checked;
  const colorColumn = $('color-col').value;
  const filters = {...active};
  status('Loading plot…');
  $('plot-svg').innerHTML = '';
  $('plot-legend').textContent = '';
  try {
    if (typeof d3 === 'undefined') throw new Error('Plot library could not load. Check your internet connection and reload.');
    const bgKey = `${x}:${y}`;
    if (!background.has(bgKey)) {
      const data = await api('/api/plot/background', {x_col:x, y_col:y});
      background.set(bgKey, data.results);
    }
    let foreground = [], offset = 0, total = Infinity;
    while (offset < total) {
      const data = await api('/api/plot/foreground', {...filters, x_col:x, y_col:y, offset});
      if (version !== plotVersion) return;
      foreground.push(...data.results);
      total = data.total;
      if (!data.results.length) break;
      offset += data.results.length;
    }
    if (version !== plotVersion) return;
    const usable = row => valid(row[x]) && valid(row[y]) &&
      (!xlog || row[x] > 0) && (!ylog || row[y] > 0);
    const bg = background.get(bgKey).filter(usable);
    const fg = foreground.filter(usable);
    const all = bg.concat(fg);
    if (!all.length) { status('No available measurements for these axes.'); return; }
    const width = Math.max($('plot-wrap').clientWidth, 400), height = Math.max($('plot-wrap').clientHeight, 400);
    const margin = {top:20,right:20,bottom:55,left:75};
    const w = width-margin.left-margin.right, h = height-margin.top-margin.bottom;
    const extent = column => {
      let [lo,hi] = d3.extent(all, row => row[column]);
      if (lo === hi) { lo = lo > 0 ? lo*0.9 : lo-1; hi = hi > 0 ? hi*1.1 : hi+1; }
      return [lo,hi];
    };
    const xs = (xlog ? d3.scaleLog() : d3.scaleLinear()).domain(extent(x)).range(xinv ? [w,0] : [0,w]).nice();
    const ys = (ylog ? d3.scaleLog() : d3.scaleLinear()).domain(extent(y)).range(yinv ? [0,h] : [h,0]).nice();
    const svg = d3.select('#plot-svg').attr('width',width).attr('height',height);
    const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`);
    g.append('g').attr('transform',`translate(0,${h})`).call(d3.axisBottom(xs).ticks(6));
    g.append('g').call(d3.axisLeft(ys).ticks(6));
    g.append('text').attr('x',w/2).attr('y',h+42).attr('fill','currentColor').text(`${x} (uHz)`);
    g.append('text').attr('transform','rotate(-90)').attr('x',-h/2).attr('y',-55).attr('fill','currentColor').text(`${y} (uHz)`);
    const colors = d3.scaleOrdinal(COLORS).domain([...new Set(fg.map(r => r[colorColumn]))].sort());
    g.selectAll('.bg-pt').data(bg).enter().append('circle').attr('class','bg-pt')
      .attr('cx',r => xs(r[x])).attr('cy',r => ys(r[y])).attr('r',1.8).attr('fill','#6b7499').attr('opacity',0.3);
    g.selectAll('.fg-pt').data(fg).enter().append('circle').attr('class','fg-pt')
      .attr('cx',r => xs(r[x])).attr('cy',r => ys(r[y])).attr('r',3).attr('fill',r => colors(r[colorColumn]));
    const brush = d3.brush().extent([[0,0],[w,h]]).on('end', event => {
      if (!event.selection) return;
      const [[x0,y0],[x1,y1]] = event.selection;
      const points = fg.filter(r => xs(r[x]) >= x0 && xs(r[x]) <= x1 && ys(r[y]) >= y0 && ys(r[y]) <= y1);
      if (!points.length) return;
      $('selection-title').textContent = `${points.length} selected measurement sets`;
      $('selection-body').innerHTML = measurementTable(points);
      $('selection-export').onclick = () => exportRows(points, 'asterocat_plot_selection.csv');
      $('selection-modal').classList.add('open');
    });
    g.append('g').attr('class','brush').call(brush);
    $('plot-legend').innerHTML = colors.domain().map(code => `<span class="legend-item"><span class="legend-dot" style="background:${colors(code)}"></span>${esc(code || 'Unknown pipeline')}</span>`).join('');
    status(`${fg.length.toLocaleString()} matching measurement sets plotted.`);
  } catch (error) { if (version === plotVersion) status(error.message); }
}

$('search-btn').onclick = () => search();
for (const id of ['q-input','numax-min','numax-max','dnu-min','dnu-max']) {
  $(id).onkeydown = event => { if (event.key === 'Enter') search(); };
}
$('prev-btn').onclick = () => loadPage(Math.max(0,page.offset-page.limit));
$('next-btn').onclick = () => loadPage(page.offset+page.limit);
document.querySelectorAll('th[data-col]').forEach(th => {
  th.onclick = () => {
    if (!hasSearch) return;
    const sort = {sort_col:th.dataset.col, sort_dir:active.sort_col === th.dataset.col && active.sort_dir === 'asc' ? 'desc' : 'asc'};
    loadPage(0,{...active,...sort});
  };
});
$('select-all-cb').onchange = event => {
  for (const row of page.results) {
    if (event.target.checked) selected.set(key(row),row); else selected.delete(key(row));
  }
  render(page);
};
$('export-btn').onclick = exportAll;
$('export-selected-btn').onclick = () => exportRows([...selected.values()], 'asterocat_selected.csv');
$('toggle-sources').onclick = () => {
  const boxes = [...document.querySelectorAll('input[name=source]')];
  const value = !boxes.every(box => box.checked);
  boxes.forEach(box => { box.checked = value; });
};
$('batch-file-input').onchange = async event => {
  const file = event.target.files[0];
  batchNames = file ? (await file.text()).split(/\r?\n/).map(s => s.trim()).filter(Boolean) : [];
  $('batch-search-btn').disabled = !batchNames.length;
};
$('batch-search-btn').onclick = () => search(batchNames);
$('reset-btn').onclick = () => {
  ++requestVersion; ++plotVersion;
  active = {sort_col:'cid',sort_dir:'asc'};
  hasSearch = false; selected.clear();
  for (const id of ['q-input','numax-min','numax-max','dnu-min','dnu-max']) $(id).value = '';
  document.querySelectorAll('input[name=source]').forEach(el => { el.checked = true; });
  $('batch-warnings').textContent = ''; $('active-filters').textContent = '';
  $('plot-svg').innerHTML = ''; $('plot-legend').textContent = '';
  render({results:[],total:0,offset:0,limit:200});
  status('');
};
$('tab-table').onclick = () => {
  $('table-panel').classList.remove('hidden'); $('plot-panel').classList.remove('visible');
  $('tab-table').classList.add('active'); $('tab-plot').classList.remove('active');
};
$('tab-plot').onclick = () => {
  $('table-panel').classList.add('hidden'); $('plot-panel').classList.add('visible');
  $('tab-table').classList.remove('active'); $('tab-plot').classList.add('active');
  drawPlot();
};
$('plot-btn').onclick = drawPlot;
for (const id of ['x-col','y-col','x-log','y-log','x-inv','y-inv','color-col']) $(id).onchange = drawPlot;
document.addEventListener('click', event => {
  const link = event.target.closest('.target-link');
  if (link) { event.preventDefault(); openTarget(link.dataset.cid); }
});
for (const kind of ['target','selection']) {
  $(`${kind}-close`).onclick = () => $(`${kind}-modal`).classList.remove('open');
  $(`${kind}-modal`).onclick = event => {
    if (event.target === $(`${kind}-modal`)) $(`${kind}-modal`).classList.remove('open');
  };
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') document.querySelectorAll('.modal-backdrop').forEach(el => el.classList.remove('open'));
});
loadSources();
