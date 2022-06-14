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
 Niels Korschinsky

Description:
    TODO

Classes:
    TODO
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import influx.database_tables as d_t
import influx.influx_client as i_c
from numpy import isnan
from pandas import Series
from utils.exception_utils import ExceptionUtils


class SizingUtils:

    default_tag_value = "Total"

    @staticmethod
    def create_unique_rp(influx_client: i_c.InfluxClient, prefix: str, rp_timestamp: Optional[str] = None) -> d_t.RetentionPolicy:
        ### Create my own RP to distinct the data

        rp_name = prefix
        if rp_timestamp:
            rp_name += "_" + rp_timestamp

        created_rp = d_t.RetentionPolicy(rp_name, influx_client.database, "INF")
        influx_client.create_rp(created_rp)

        return created_rp

    @classmethod
    def insert_series(
        cls,
        influx_client: i_c.InfluxClient,
        report_rp: d_t.RetentionPolicy,
        prediction_result: Series,
        table_name: str,
        value_key: str,
        replacement_tags: Optional[Dict[str, Any]] = None):

        if not replacement_tags:
            default_dict = {}
        else:
            default_dict = replacement_tags.copy()
        for tag_name in influx_client.database[table_name].tags:
            default_dict.setdefault(tag_name, cls.default_tag_value)

        insert_list = SizingUtils.__insert_preparation(prediction_result, default_dict, value_key)
        influx_client.insert_dicts_to_buffer(
            table_name,
            insert_list,
            report_rp
        )

    @staticmethod
    def __insert_preparation(prediction_result: Series, default_dict: Dict[str, Any], value_key: str):

        insert_list: List[Dict[str, Any]] = []

        nan_count = 0
        for (timestamp, value) in prediction_result.items():
            if isnan(value):
                # skip if the value is nan
                nan_count += 1
                continue

            # copy required for each loop to avoid side effects
            insert_dict = default_dict.copy()
            # convert Timestamp into epoch time
            insert_dict["time"] = round(timestamp.timestamp())
            insert_dict[value_key] = round(value)

            insert_list.append(insert_dict)

        if(nan_count > 0):
            ExceptionUtils.error_message(f"{nan_count} values of total {len(prediction_result)} were nan, skipping them. {default_dict}")

        return insert_list
