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
from datetime import datetime
from enum import Enum, unique
import logging
import re
from sys import prefix

from typing import Any, Dict, Generator, List, Optional, Tuple

from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from numpy import isnan
from pandas import Series
from influx.influx_queries import Keyword, SelectionQuery
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

@unique
class Themes(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SPPCHECK = "sppcheck"

class SppcheckUtils:

    @staticmethod
    def choose_latest_data(influx_client: InfluxClient, table_name: str, retention_policy: RetentionPolicy):

        LOGGER.info(f">> Choosing the date of the last data present within {retention_policy}.{table_name} ")

        query = SelectionQuery(
            keyword=Keyword.SELECT,
            fields=[],
            table_or_query=influx_client.database[table_name],
            alt_rp=retention_policy,
            order_direction="DESC",
            limit=1
        )

        result = influx_client.send_selection_query(query)
        result_list: List[Tuple[ # list: different tag groups
            Tuple[str, Optional[Dict[str, str]]], # tablename, dict of grouping tags (empty if not grouped)
            Generator[Dict[str, Any], None, None] # result of the selection query
        ]] = result.items() # type: ignore

        if not result_list:
            raise ValueError(f"No data is available within the table.")

        items_list = list(result_list[0][1])

        if not items_list:
            raise ValueError(f"No data is available within the table.")

        item_timestamp: int = items_list[0]["time"]
        LOGGER.debug(f">> Extracted timestamp {item_timestamp}")

        return datetime.fromtimestamp(item_timestamp)



    @staticmethod
    def choose_latest_rp(influx_client: InfluxClient, rp_prefix: str ):

        LOGGER.info(f">> Choosing the latest retention policy with the prefix {rp_prefix}.")

        rp_dict_full = influx_client.get_list_rp(influx_client.database.name)
        latest_timestamp = None
        latest_rp_name = None

        for rp_name in rp_dict_full.keys():
            LOGGER.debug(f"Checking if RP {rp_name} matches the prefix {prefix}.")

            match = re.match(
                # this does not include UTC offset
                fr"(?:[A-Za-z_]+)?{rp_prefix}(?:[A-Za-z_]+)?(\d+)_(\d+)_(\d+)_(\d+)_(\d+)_(\d+)\s*",
                     rp_name)

            if not match:
                continue
            timestamp = datetime(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
                hour=int(match.group(4)),
                minute=int(match.group(5)),
                second=int(match.group(6)),
            ).timestamp()

            LOGGER.debug(f"Found matching RP: {rp_name}.")

            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest_rp_name = rp_name
                LOGGER.debug("Replaced latest RP.")

        if not latest_rp_name:
            raise ValueError(f"Could not determine a retention policy with the prefix '{rp_prefix}'")

        matching_rp = rp_dict_full[latest_rp_name]
        LOGGER.debug(f"Creating retention policy based on following data: {matching_rp}")
        return RetentionPolicy(
            name=matching_rp["name"],
            database=influx_client.database,
            duration=matching_rp["duration"],
            replication=matching_rp["replicaN"],
            shard_duration=matching_rp["shardGroupDuration"],
            default=matching_rp["default"]
        )

    @staticmethod
    def create_unique_rp(influx_client: InfluxClient, prefix: str, rp_timestamp: Optional[str] = None) -> RetentionPolicy:
        ### Create my own RP to distinct the data

        rp_name = prefix
        if rp_timestamp:
            rp_name += "_" + rp_timestamp

        created_rp = RetentionPolicy(rp_name, influx_client.database, "INF")
        influx_client.create_rp(created_rp)

        return created_rp

    @classmethod
    def insert_series(
        cls,
        influx_client: InfluxClient,
        report_rp: RetentionPolicy,
        prediction_result: Series,
        table_name: str,
        value_key: str,
        insert_tags: Dict[str, Any]):

        insert_list: List[Dict[str, Any]] = []

        nan_count = 0
        for (timestamp, value) in prediction_result.items():
            if isnan(value):
                # skip if the value is nan
                nan_count += 1
                continue

            # copy required for each loop to avoid side effects
            insert_dict = insert_tags.copy()
            # convert Timestamp into epoch time
            insert_dict["time"] = round(timestamp.timestamp())
            insert_dict[value_key] = round(value)

            insert_list.append(insert_dict)

        if(nan_count > 0):
            ExceptionUtils.error_message(f"{nan_count} values of a total of {len(prediction_result)} values were nan, skipping them. {insert_tags}")

        influx_client.insert_dicts_to_buffer(
            table_name,
            insert_list,
            report_rp
        )