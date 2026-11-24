import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInContext} from 'node:vm';
import {JSDOM} from 'jsdom';
import * as d3 from 'd3';

const base = process.env.ASTEROCAT_TEST_UI_URL;

test('table, batch, selection, detail, plot and export use consistent filters', {skip:!base}, async () => {
  const dom = new JSDOM(readFileSync('asterocat/static/index.html','utf8'), {
    url:base, runScripts:'outside-only', pretendToBeVisual:true
  });
  const w = dom.window;
  globalThis.document = w.document;
  w.d3 = d3;
  w.fetch = (path, options) => fetch(new URL(path,base), options);
  w.Blob = Blob;
  const blobs = new Map(), downloads = [];
  w.URL.createObjectURL = blob => { const url = `blob:${blobs.size}`; blobs.set(url,blob); return url; };
  w.URL.revokeObjectURL = () => {};
  const anchorClick = w.HTMLAnchorElement.prototype.click;
  w.HTMLAnchorElement.prototype.click = function() {
    if (this.download) downloads.push({filename:this.download,blob:blobs.get(this.href)});
    else anchorClick.call(this);
  };
  const errors = [];
  w.addEventListener('error', e => errors.push(e.message));
  const $ = id => w.document.getElementById(id);
  const wait = async predicate => {
    const deadline = Date.now()+15000;
    while (!predicate()) {
      if (Date.now()>deadline) throw new Error(`UI timed out: ${$('status').textContent}`);
      await new Promise(resolve => setTimeout(resolve,10));
    }
  };
  const fill = (id, value) => { $(id).value = value; };
  const click = id => $(id).click();
  try {
    runInContext(readFileSync('asterocat/static/app.js','utf8'), dom.getInternalVMContext());
    await wait(() => $('db-stats').textContent.includes('publications'));
    assert.equal($('teff-min').disabled,true);
    assert.equal(w.document.querySelector('[name=instrument]'),null);
    $('online-lookup').checked=false;
    fill('q-input','KIC123');
    click('search-btn');
    await wait(() => $('result-count').textContent==='3');
    const select = w.document.querySelector('#results-body input');
    select.click();
    assert.equal($('selected-count').textContent,'1 selected');
    click('export-selected-btn');
    const selected = await downloads.at(-1).blob.text();
    assert.match(selected,/pipeline,numax,e_numax,dnu,e_dnu/);
    assert.match(selected,/"A","pub1","pipe1"/);
    w.document.querySelector('.target-link').click();
    await wait(() => $('target-body').querySelector('details'));
    assert.match($('target-body').textContent,/alpha Test/);
    click('target-close');
    // Pagination uses the active filters and selection persists across pages.
    runInContext('page.limit=1',dom.getInternalVMContext());
    await w.loadPage(0);
    click('next-btn');
    await wait(() => $('page-info').textContent==='page 2 of 3');
    assert.match($('results-body').textContent,/pipe2/);
    w.document.querySelector('#results-body input').click();
    assert.equal($('selected-count').textContent,'2 selected');
    click('prev-btn');
    await wait(() => $('page-info').textContent==='page 1 of 3');
    assert.equal(w.document.querySelector('#results-body input').checked,true);
    // Reset page size for the rest of the workflows.
    runInContext('page.limit=200',dom.getInternalVMContext());
    fill('numax-min','100'); fill('numax-max','100');
    fill('dnu-min','10'); fill('dnu-max','10');
    click('search-btn');
    await wait(() => $('result-count').textContent==='1');
    click('export-btn');
    await wait(() => downloads.length===2);
    const full = await downloads.at(-1).blob.text();
    assert.equal(full.trim().split(/\r?\n/).length,2);
    assert.match(full,/A,pub1,pipe1/);
    click('tab-plot');
    await wait(() => w.document.querySelector('.fg-pt'));
    assert.equal(w.document.querySelectorAll('.fg-pt').length,1);
    const overlay = w.document.querySelector('.brush .overlay');
    const width = +overlay.getAttribute('width'), height = +overlay.getAttribute('height');
    overlay.dispatchEvent(new w.MouseEvent('mousedown',{bubbles:true,clientX:0,clientY:0,view:w}));
    w.dispatchEvent(new w.MouseEvent('mousemove',{bubbles:true,clientX:width,clientY:height,view:w}));
    w.dispatchEvent(new w.MouseEvent('mouseup',{bubbles:true,clientX:width,clientY:height,view:w}));
    assert.equal($('selection-modal').classList.contains('open'),true);
    await new Promise(resolve => setTimeout(resolve,0)); // D3 ends drag click suppression.
    click('selection-export');
    const plot = await downloads.at(-1).blob.text();
    assert.equal(plot.trim().split(/\r?\n/).length,2);
    assert.match(plot,/"A","pub1","pipe1"/);
    click('selection-close'); click('tab-table');
    fill('q-input','not a target'); click('search-btn');
    await wait(() => $('result-count').textContent==='0');
    assert.equal($('export-btn').disabled,true);
    click('reset-btn');
    assert.equal($('selected-count').textContent,'');
    await w.search(['KIC123','alpha Test','unknown']);
    assert.equal($('result-count').textContent,'3');
    assert.match($('batch-warnings').textContent,/Same target:/);
    assert.match($('batch-warnings').textContent,/Not found: unknown/);
    // Source filtering applies to name searches, lists, exports and plotting.
    click('toggle-sources');
    await w.search(['KIC123']);
    assert.equal($('result-count').textContent,'0');
    assert.deepEqual(errors,[]);
  } finally { dom.window.close(); }
});
