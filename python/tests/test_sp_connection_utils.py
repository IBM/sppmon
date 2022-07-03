"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2022. All Rights Reserved.

 IBM Spectrum Protect Family Software

 Licensed materials provided under the terms of the IBM International Program
 License Agreement. See the Software licensing materials that came with the
 IBM Program for terms and conditions.

 U.S. Government Users Restricted Rights:  Use, duplication or disclosure
 restricted by GSA ADP Schedule Contract with IBM Corp.

 ----------------------------------------------------------------------------------------------
SPDX-License-Identifier: Apache-2.0

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author (SppMon):
 Niels Korchinsky

Author (SpMon):
 Daniel Boros
 James Damgar
 Rob Elder
 Sean Jones
 Raymond Shum

Description:
 Contains unit tests for methods found in sp_connection_utils.py

Tests:
 test_init_paginated_query
 test_set_query_page_values
 test_set_query_values_with_base_statement
 test_set_query_values_with_full_statement
 test_set_query_read_only_clause
"""
from io import StringIO

import pytest

from spmonMethods.sp_dataclasses import SpRestQuery
from utils.sp_connection_utils import SpIteratorUtils


@pytest.fixture
def query_params() -> SpRestQuery:
    return SpRestQuery(
        query_id="query1",
        query="SELECT * FROM summary LIMIT 10",
        target_servers=["fusion"])


def test_init_paginated_query(query_params) -> None:
    expected_base_statement = f"SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM({query_params.query})) WHERE rowid "
    base_statement, base_statement_eol = SpIteratorUtils.init_paginated_query(query=query_params.query)
    assert base_statement.getvalue() == expected_base_statement
    assert base_statement_eol == 104


def test_set_query_page_values_with_base_statement(query_params) -> None:
    expected_statement = "SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid BETWEEN 1 AND 5"
    statement = StringIO()
    statement.write("SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid ")
    insertion_index = statement.tell()

    SpIteratorUtils.set_query_page_value(
        statement=statement,
        insertion_index=insertion_index,
        starting_record=1,
        page_size=5
    )

    assert expected_statement == statement.getvalue()


def test_set_query_page_values_with_full_statement(query_params) -> None:
    expected_statement = "SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid BETWEEN 6 AND 10"
    statement = StringIO()
    statement.write("SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid BETWEEN 1 AND 5 FOR READ ONLY WITH UR")

    SpIteratorUtils.set_query_page_value(
        statement=statement,
        insertion_index=104,
        starting_record=6,
        page_size=5
    )

    assert statement.getvalue() == expected_statement


def test_set_query_read_only_clause(query_params) -> None:
    expected_statement = "SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid BETWEEN 1 AND 5 FOR READ ONLY WITH UR"
    statement = StringIO()
    statement.write("SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM(SELECT * FROM summary LIMIT 10)) WHERE rowid BETWEEN 1 AND 5")

    SpIteratorUtils.set_query_read_only_clause(statement=statement)

    assert expected_statement == statement.getvalue()
