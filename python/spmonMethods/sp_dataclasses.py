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

Author:
 Daniel Boros
 James Damgar
 Rob Elder
 Sean Jones
 Raymond Shum

Description:
 TODO: Add description

Classes:
 SpInfluxParams
 SpInfluxTableDefinition
 SpRestResponsePage
 SpRestQuery
 SpServerParams
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class SpInfluxParams:
    """InfluxDB 2.x connection parameters."""
    bucket: str = ""
    org: str = ""
    token: str = ""
    srv_address: str = ""
    srv_port: str = ""


@dataclass(
    frozen=True
)
class SpInfluxTableDefinition:
    """Table definitions associated with one or more queries. Used as key in SpInfluxClient.__insert_buffer"""
    datetime: str = ""
    fields: list[str] = field(default_factory=list)
    measurement: str = ""
    tags: list[str] = field(default_factory=list)

    def __hash__(self):
        return hash((self.datetime, self.measurement))


@dataclass
class SpRestResponsePage:
    """Contains values of interest from OC's JSON formatted REST API response. Associated with
    SpInfluxTableDefinition on insert to InfluxDB as value in SpInfluxClient.__insert_buffer"""
    query_id: str = ""
    host: str = ""
    hdr: list[str] = field(default_factory=dict)
    items: list[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class SpRestQuery:
    """Holds query, identifier and servers to issue against."""
    query: str = ""
    query_id: str = ""
    target_servers: list[str] = field(default_factory=list)


@dataclass
class SpServerParams:
    """Contains connection parameters for SP OC hub server"""
    username: str = ""
    password: str = ""
    srv_address: str = ""
    srv_port: str = ""


