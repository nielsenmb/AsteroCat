"""Isolated MySQL fixtures shared by API and browser integration tests."""

import os
import uuid

import pymysql
import pytest


@pytest.fixture(scope='module')
def mysql_settings():
    """Provision an ephemeral database on an explicitly selected test server.

    Yields
    ------
    dict
        Connection settings for the isolated schema.
    """
    if not os.environ.get('ASTEROCAT_TEST_MYSQL_PORT'):
        pytest.skip('Set ASTEROCAT_TEST_MYSQL_PORT to run MySQL integration tests.')
    settings = dict(host='127.0.0.1', port=int(os.environ['ASTEROCAT_TEST_MYSQL_PORT']),
                    user=os.environ.get('ASTEROCAT_TEST_MYSQL_USER', 'root'),
                    password=os.environ.get('ASTEROCAT_TEST_MYSQL_PASSWORD', ''))
    database = 'asterocat_test_' + uuid.uuid4().hex
    admin = pymysql.connect(**settings, charset='utf8mb4', autocommit=True)
    cursor = admin.cursor()
    cursor.execute(f'CREATE DATABASE `{database}` CHARACTER SET utf8mb4 '
                   'COLLATE utf8mb4_general_ci')
    cursor.execute(f'USE `{database}`')
    cursor.execute('CREATE TABLE cids (ID VARCHAR(100) PRIMARY KEY, CID VARCHAR(100))')
    for table in ('p', 'g', 'mixed', 'rotmag'):
        cursor.execute(f'CREATE TABLE {table} (CID VARCHAR(100), Obsname VARCHAR(30), '
                       'value DOUBLE, err DOUBLE, units VARCHAR(10), pipeline VARCHAR(50), '
                       'bibcode VARCHAR(30), PRIMARY KEY (CID, Obsname, pipeline, bibcode))')
    cursor.execute('CREATE TABLE modes (CID VARCHAR(100), ell INT, n_p INT, n_g INT, '
                   'freq DOUBLE, freq_err DOUBLE, freq_units VARCHAR(10), '
                   '`Γ` DOUBLE, `Γ_err` DOUBLE, `Γ_units` VARCHAR(10), '
                   'A DOUBLE, A_err DOUBLE, A_units VARCHAR(10), pipeline VARCHAR(50), '
                   'bibcode VARCHAR(30), PRIMARY KEY (CID, ell, freq, pipeline, bibcode))')
    cursor.executemany('INSERT INTO cids VALUES (%s, %s)', [
        ('KIC 123', 'A'), ('alpha Test', 'A'), ("O\'Brien", 'A'),
        ('KIC 456', 'B'), ('literal%_name', 'A'), ('HD 9', 'G'), ('HD 10', 'M')])
    cursor.executemany('INSERT INTO p VALUES (%s,%s,%s,%s,%s,%s,%s)', [
        ('A', 'νmax', 100, 2, 'μHz', 'pipe1', 'pub1'),
        ('A', 'Δν', 10000, 500, 'nHz', 'pipe1', 'pub1'),
        ('A', 'νmax', 200, 4, 'uHz', 'pipe2', 'pub1'),
        ('A', 'Δν', 20, 1, 'uHz', 'pipe2', 'pub1'),
        ('A', 'νmax', 300, 6, 'uHz', 'pipe1', 'pub2'),
        ('A', 'Δν', 30, 1, 'uHz', 'pipe1', 'pub2'),
        ('B', 'νmax', 100, -1, 'uHz', 'pipe1', 'pub1'),
        ('B', 'Δν', -1, -1, 'nHz', 'pipe1', 'pub1'),
        ('B', 'νmax', -1, -1, 'uHz', 'pipe1', 'pub2'),
        ('B', 'Δν', 10, 1, 'uHz', 'pipe1', 'pub2'),
        ('B', 'Δν', 8, None, 'uHz', '', 'pub3')])
    cursor.execute("INSERT INTO g VALUES ('G','ΔΠ1',80,2,'s','','pub1')")
    cursor.execute("INSERT INTO rotmag VALUES ('A','δνrot_g',500,-1,'nHz','pipe1','pub1')")
    cursor.execute("INSERT INTO modes VALUES ('M',1,-1,-15,100000,100,'nHz',-1,-1,'nHz',"
                   "4,0.2,'SNR','pipe3','pub4')")
    try:
        yield {**settings, 'database': database}
    finally:
        cursor.execute(f'DROP DATABASE `{database}`')
        admin.close()


