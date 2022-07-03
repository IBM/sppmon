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
 Contains unit tests for methods found in sp_utils.py

Tests:
 test_get_top_level_dict
 test_get_capture_timestamp
 test_load_dataclass_from_dict
"""
import pytest

from dataclasses import asdict
from utils.sp_utils import SpUtils
from spmonMethods.sp_dataclasses import SpRestQuery


def test_get_top_level_dict() -> None:
    list_with_nested_dict = [[{"test": {"nested": "dict"}}]]
    assert isinstance(SpUtils.get_top_level_dict(list_with_nested_dict), dict)

    list_with_no_dict = [[]]
    with pytest.raises(ValueError):
        SpUtils.get_top_level_dict(list_with_no_dict)


def test_get_capture_timestamp_sec_key() -> None:
    time_key: str
    time_key, _ = SpUtils.get_capture_timestamp_sec()
    assert time_key.startswith("spmon")


def test_load_dataclass_from_dict() -> None:
    query_dict = {
        "query_id": "test_id",
        "query": "test_query",
        "target_servers": ["test_server"]
    }

    query_dataclass = SpUtils.build_dataclass_from_dict(
        dataclass=SpRestQuery,
        param_dict=query_dict
    )

    for key, value in query_dict.items():
        assert value == asdict(query_dataclass).get(key)

