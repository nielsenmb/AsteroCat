"""Opt-in browser checks against the same MySQL integration fixture."""

import csv
import io
import os
from pathlib import Path
import shutil
import threading

import pytest
from werkzeug.serving import make_server

from asterocat.app import create_app


@pytest.mark.skipif(not os.environ.get('ASTEROCAT_TEST_BROWSER'), reason='Browser test is opt-in.')
def test_browser_workflows(mysql_settings, tmp_path):
    """Exercise searches, provenance, missing metadata, plots and CSV exports.

    Parameters
    ----------
    mysql_settings : dict
        Isolated MySQL fixture.
    tmp_path : pathlib.Path
        Directory for downloaded CSV files.
    """
    playwright = pytest.importorskip('playwright.sync_api')
    application = create_app({'TESTING': True, 'MYSQL': mysql_settings})
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(executable_path=shutil.which('chromium'),
                                        args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1500, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function(
                "document.querySelector('#db-stats').textContent.includes('publications')")
            assert page.locator('#teff-min').is_disabled()
            assert not page.get_by_text('Instrument', exact=True).count()
            page.uncheck('#online-lookup')
            page.fill('#q-input', 'KIC123')
            page.click('#search-btn')
            page.wait_for_function("document.querySelector('#result-count').textContent === '3'")
            assert page.locator('#results-body tr.result-row').count() == 3
            page.locator('#results-body input').first.check()
            assert page.locator('#selected-count').inner_text() == '1 selected'
            with page.expect_download() as pending:
                page.click('#export-selected-btn')
            download = pending.value
            selected = list(csv.DictReader(io.StringIO(Path(download.path()).read_text())))
            assert selected[0]['pipeline'] == 'pipe1'
            assert selected[0]['teff'] == '-1'
            assert 'dnu' in selected[0]
            # Detail lookups keep aliases and all analysis sets; Teff remains absent.
            page.locator('.target-link').first.click()
            page.wait_for_selector('#target-body details')
            assert 'alpha Test' in page.locator('#target-body').inner_text()
            page.click('#target-close')
            # Same-publication/pipeline matching rules survive the browser request path.
            page.fill('#numax-min','100'); page.fill('#numax-max','100')
            page.fill('#dnu-min','10'); page.fill('#dnu-max','10')
            page.click('#search-btn')
            page.wait_for_function("document.querySelector('#result-count').textContent === '1'")
            with page.expect_download() as pending:
                page.click('#export-btn')
            full = list(csv.DictReader(io.StringIO(Path(pending.value.path()).read_text())))
            assert len(full) == 1 and full[0]['pipeline'] == 'pipe1'
            # Plot and box export must describe the same record as the table.
            page.click('#tab-plot')
            page.wait_for_selector('.fg-pt', timeout=30000)
            assert page.locator('.fg-pt').count() == 1
            box = page.locator('.brush .overlay').bounding_box()
            page.mouse.move(box['x'], box['y'])
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'], box['y'] + box['height'])
            page.mouse.up()
            page.wait_for_selector('#selection-modal.open')
            with page.expect_download() as pending:
                page.click('#selection-export')
            plot = list(csv.DictReader(io.StringIO(Path(pending.value.path()).read_text())))
            for column in ('cid', 'bibcode', 'pipeline', 'frequency_units'):
                assert plot[0][column] == full[0][column]
            for column in ('numax', 'e_numax', 'dnu', 'e_dnu', 'teff', 'e_teff'):
                assert float(plot[0][column]) == float(full[0][column])
            page.click('#selection-close')
            page.click('#tab-table')
            # A missing name stays empty through export and plot state changes.
            page.fill('#q-input','not a target')
            page.click('#search-btn')
            page.wait_for_function("document.querySelector('#result-count').textContent === '0'")
            assert page.locator('#export-btn').is_disabled()
            page.click('#reset-btn')
            assert page.locator('#selected-count').inner_text() == ''
            # List aliases deduplicate but preserve two pipelines in one publication.
            path = tmp_path / 'targets.txt'
            path.write_text('KIC123\nalpha Test\nunknown\n')
            page.set_input_files('#batch-file-input', path)
            page.click('#batch-search-btn')
            page.wait_for_function("document.querySelector('#result-count').textContent === '3'")
            assert 'Same target:' in page.locator('#batch-warnings').inner_text()
            assert 'Not found: unknown' in page.locator('#batch-warnings').inner_text()
            page.click('summary:text-is("Publications")')
            page.click('#toggle-sources')
            page.click('#search-btn')
            page.wait_for_function("document.querySelector('#result-count').textContent === '0'")
            assert not errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=10)
