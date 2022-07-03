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
 Contains unit tests for methods found in sp_rest_client.py

Tests:
 test_get_url
"""
import pytest

import requests
from spConnection.sp_rest_client import SpRestClient, SpRestIterator
from spmonMethods.sp_dataclasses import SpRestQuery, SpServerParams


@pytest.fixture
def server_params() -> SpServerParams:
    return SpServerParams(
        username="user",
        password="pass",
        srv_address="fake.com",
        srv_port="11090")


@pytest.fixture
def rest_client(server_params) -> SpRestClient:
    return SpRestClient(
        server_params=server_params,
        starting_page_size=5,
    )


def test_get_url(rest_client) -> None:
    url_no_target = rest_client.get_url()
    expected_url_no_target = "https://fake.com:11090/oc/api/cli/issueConfirmedCommand"
    assert url_no_target == expected_url_no_target

    url_with_target = rest_client.get_url(target_server="SpokeServer")
    expected_url_with_target = "https://fake.com:11090/oc/api/cli/issueConfirmedCommand/SpokeServer"
    assert url_with_target == expected_url_with_target


