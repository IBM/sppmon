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
 TODO: Add description

Classes:
 SpInfluxUtils
 TimeKeyValue
"""
import logging

from enum import Enum
from dateutil.parser import parse, ParserError
from typing import Dict, Any

LOGGER = logging.getLogger("spmon")


class TimeKeyValue(Enum):
    """Represents possible values for time keys returned by the OC. More can be
    added here if applicable. Example: [[{"COL_NAME":{"DATE": "2022-01-02",...},...}]]
    """
    DATE = "date"
    SECS = "secs"


class SpInfluxUtils:
    """Wrapper for methods used by SpInfluxClient.

    Methods:
        format_db2_time_key: Formats OC's returned time key & values to a format acceptable to InfluxDB

    """

    @staticmethod
    def format_db2_time_key(record: Dict[str, Any],
                            time_key: str) -> None:
        """Takes and formats the OC's response for a given time key. Takes the entry
        of interest within a dictionary and assigns it as the new value to a given time
        key. The time key is what the user assigns to be the primary key when inserting
        into InfluxDB.

        Example:
            Response = [[{"COL_NAME":{"DATE":2022-01-02,...},...}]]
            After formatting, Response = [[{"COL_NAME": "2022-01-02"},...}]]

        Args:
            record {Dict[str, Any]}: JSON formatted response from the OC. A single record from a page.
            time_key {str}: String representing the time_key of the record.
        """
        if time_key not in list(record.keys()):
            raise ValueError(f"{time_key} is not present in the record dictionary")

        # time_key has already been processed or key is incorrect
        if not isinstance(time_entry := record.get(time_key), dict):
            return

        # A date is converted to epoch seconds and assigned as the value of time_key
        # InfluxDBClient can take care of this. Leaving logic here in case necessary to enforce
        # nanosecond precision in the future.
        if time_entry.get(date := TimeKeyValue.DATE.value):
            try:
                record[time_key] = time_entry.get(date)
                record_date_time_value = parse(record.get(time_key))
                epoch_seconds_value = str(record_date_time_value.timestamp()).split(".")[0]
                record[time_key] = int(epoch_seconds_value)
            except (ValueError, ParserError) as dateutil_parsing_error:
                raise ValueError("Unsupported date value. Cannot parse.")
        # If already in epoch seconds, assign as the value of time_key without modification
        elif time_entry.get(secs := TimeKeyValue.SECS.value):
            record[time_key] = time_entry.get(secs)
        else:
            raise ValueError("Unsupported date/time subkey value. Cannot parse.")
