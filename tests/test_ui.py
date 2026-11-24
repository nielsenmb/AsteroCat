"""Opt-in DOM interaction checks using the real Flask and MySQL query path."""

import os
import subprocess
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from asterocat.app import create_app


@pytest.mark.skipif(not os.environ.get('ASTEROCAT_TEST_UI'), reason='DOM test is opt-in.')
def test_ui_workflows(mysql_settings):
    """Run the JavaScript interactions against the test database over HTTP.

    Parameters
    ----------
    mysql_settings : dict
        Isolated MySQL database settings.
    """
    server = make_server('127.0.0.1', 0, create_app({'MYSQL':mysql_settings}), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = {**os.environ, 'ASTEROCAT_TEST_UI_URL':f'http://127.0.0.1:{server.server_port}'}
        subprocess.run(['node','--test','tests/ui.test.mjs'], env=environment,
                       cwd=Path(__file__).resolve().parents[1], check=True, timeout=90)
    finally:
        server.shutdown()
        thread.join(timeout=10)
