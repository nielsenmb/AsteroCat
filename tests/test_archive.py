"""Unit and MySQL integration tests for the archive browser.

Set ASTEROCAT_TEST_MYSQL_PORT to enable integration checks against an isolated
loopback MySQL server. Each run creates and removes its own temporary database.
"""

import csv
import io

import pymysql
import pytest

from asterocat.app import create_app
from asterocat.database import Archive, connect, frequency, parse_filters


@pytest.mark.parametrize('units,factor', [('uHz', 1), ('μHz', 1), ('µHz', 1),
                                         ('nHz', .001), ('mHz', 1000), ('Hz', 1e6)])
def test_frequency_conversion_and_missing(units, factor):
    """Verify numeric conversion and preservation of absent values.

    Parameters
    ----------
    units : str
        Source unit.
    factor : float
        Expected conversion factor.
    """
    assert frequency(2, units) == 2 * factor
    assert frequency(-1, units) == -1
    assert frequency(None, units) == -1


@pytest.mark.parametrize('filters', [
    {'numax_min': 'nan'}, {'dnu_max': 'inf'}, {'dnu_min': 10, 'dnu_max': 5},
    {'teff_min': 4000}, {'instrument': 'TESS'}, {'sort_col': 'x; DROP TABLE p'},
    {'cids': 123}, {'sources': ['ok', 4]},
])
def test_invalid_filters(filters):
    """Reject unsupported or invalid search requests.

    Parameters
    ----------
    filters : dict
        Invalid filter values.
    """
    with pytest.raises((ValueError, TypeError)):
        parse_filters(filters)


@pytest.fixture
def archive(mysql_settings):
    """Open a read-only data-access session.

    Parameters
    ----------
    mysql_settings : dict
        Test database settings.

    Yields
    ------
    Archive
        Archive query object.
    """
    connection = connect(mysql_settings)
    try:
        yield Archive(connection)
    finally:
        connection.close()


@pytest.fixture
def client(mysql_settings):
    """Build a Flask client bound to the test database.

    Parameters
    ----------
    mysql_settings : dict
        Test database settings.

    Returns
    -------
    FlaskClient
        Application test client.
    """
    return create_app({'TESTING': True, 'MYSQL': mysql_settings}).test_client()


@pytest.mark.parametrize('name', ['KIC123', 'kic_123', 'KIC 123', 'alpha Test', "O'Brien", 'A'])
def test_aliases(archive, name):
    """Resolve names without duplicating results through aliases.

    Parameters
    ----------
    archive : Archive
        Test archive.
    name : str
        Alternate name for A.
    """
    assert archive.resolve(name) == ['A']
    result = archive.search(parse_filters({'q': name}))
    assert result['total'] == 3
    assert {row['cid'] for row in result['results']} == {'A'}


def test_literal_wildcards_and_missing_names(archive):
    """Keep SQL wildcard characters literal and missing queries empty.

    Parameters
    ----------
    archive : Archive
        Test archive.
    """
    assert archive.resolve('%_') == ['A']
    assert archive.resolve("' OR 1=1 --") == []
    assert archive.search(parse_filters({'q': 'does not exist'}))['total'] == 0
    assert archive.search(parse_filters({'cids': []}))['total'] == 0
    assert archive.search(parse_filters({'sources': []}))['total'] == 0


def test_combined_ranges_require_same_publication_and_pipeline(archive):
    """Avoid matches assembled from unrelated measurements.

    Parameters
    ----------
    archive : Archive
        Test archive.
    """
    filters = parse_filters(dict(numax_min=100, numax_max=100, dnu_min=10, dnu_max=10))
    rows = archive.search(filters)['results']
    assert [(r['cid'], r['bibcode'], r['pipeline']) for r in rows] == [('A','pub1','pipe1')]
    assert rows[0]['e_dnu'] == .5
    assert rows[0]['teff'] == rows[0]['e_teff'] == -1
    assert archive.search(parse_filters({**filters, 'dnu_min':20, 'dnu_max':20}))['total'] == 0


def test_missing_quantities_and_stable_pagination(archive):
    """Preserve incomplete sets and exclude missing quantities from ranges.

    Parameters
    ----------
    archive : Archive
        Test archive.
    """
    rows = archive.search(parse_filters({}))['results']
    assert len(rows) == 8
    assert any(row['cid'] == 'G' for row in rows)
    assert any(row['cid'] == 'M' for row in rows)
    paged = [archive.search(parse_filters({}), limit=1, offset=i)['results'][0]
             for i in range(len(rows))]
    assert paged == rows
    assert all(row['dnu'] != -1 for row in archive.search(parse_filters({'dnu_max':100}))['results'])
    assert archive.search(parse_filters({'dnu_max':-1}))['total'] == 0


def test_details_preserve_provenance_units_and_sentinels(archive):
    """Normalize frequency data but preserve amplitudes and signed mode orders.

    Parameters
    ----------
    archive : Archive
        Test archive.
    """
    detail = archive.details('M')
    mode = detail['modes'][0]
    assert (mode['freq'], mode['freq_err'], mode['freq_units']) == (100, .1, 'uHz')
    assert mode['Γ'] == mode['Γ_err'] == -1
    assert mode['n_g'] == -15
    assert (mode['A'], mode['A_units']) == (4, 'SNR')
    assert (mode['pipeline'], mode['bibcode']) == ('pipe3', 'pub4')
    measurements = archive.details('A')['measurements']
    rotation = next(row for row in measurements if row['table'] == 'rotmag')
    assert rotation['value'] == .5 and rotation['err'] == -1


def test_read_only_session(archive):
    """Reject mutations even when the test login has administrative privileges.

    Parameters
    ----------
    archive : Archive
        Test archive.
    """
    with pytest.raises(pymysql.MySQLError):
        archive.rows("UPDATE p SET value=999 WHERE CID='A'")


def test_table_plot_export_and_batch_agree(client):
    """Use identical provenance, filters and ordering in every workflow.

    Parameters
    ----------
    client : FlaskClient
        Test browser API client.
    """
    filters = {'q':'alpha Test', 'numax_min':90, 'numax_max':210, 'sources':['pub1']}
    table = client.post('/api/search', json=filters).get_json()
    plot = client.post('/api/plot/foreground', json=filters).get_json()
    exported = client.post('/api/export', json=filters)
    csv_rows = list(csv.DictReader(io.StringIO(exported.data.decode())))
    assert table['results'] == plot['results']
    assert [(r['cid'],r['bibcode'],r['pipeline']) for r in csv_rows] == [
        (r['cid'],r['bibcode'],r['pipeline']) for r in table['results']]
    assert all(r['frequency_units'] == 'uHz' and r['teff'] == '-1' for r in csv_rows)
    batch = client.post('/api/resolve', json={'names':['KIC123','alpha Test','unknown']}).json
    assert batch['cids'] == ['A']
    assert batch['missing'] == ['unknown']
    assert batch['duplicates'] == {'A':['KIC123','alpha Test']}
    assert client.get('/api/search?q=KIC123').json['total'] == 3
    assert client.get('/api/target/A').json['aliases']
    assert client.get('/api/sources').status_code == 200


@pytest.mark.parametrize('body', [{'limit':-1}, {'limit':1.5}, {'offset':-2},
                                  {'numax_min':'NaN'}, {'teff_min':3000}])
def test_api_validation(client, body):
    """Return an explicit client error for invalid pagination and filters.

    Parameters
    ----------
    client : FlaskClient
        Test API client.
    body : dict
        Invalid request.
    """
    assert client.post('/api/search', json=body).status_code == 400
