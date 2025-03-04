"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2020, 2021. All Rights Reserved.

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
    This Module provides helper methods for the influx module.
    You may implement new static/class helper methods in here.

Classes:
    InfluxUtils
"""
import re
import logging
from typing import Dict, Tuple, Union, Any, List

from utils.spp_utils import SppUtils
from utils.exception_utils import ExceptionUtils

LOGGER = logging.getLogger("sppmon")


class InfluxUtils:
    """ Influx related util methods. Those can be reused, placed here to make them easier to use/find.

    Attributes:
       time_key_names - default used time_key names

    Methods:
        escape_chars - Escapes chars to a even number of escape signs. Only adds escape signs.
        check_time_literal - Checks whether the str is consistent as influxdb time literal
        transform_time_literal - Transforms a time literal into hour/min/seconds literal.
        default_split - Splits the dict into tags/fields/timestamp according to the format of value.
    """
    time_key_names: List[str] = ['time', SppUtils.capture_time_key, "logTime"]
    """default time_key names."""

    @staticmethod
    def check_time_literal(value: str) -> bool:
        """Checks whether the str is consistent as influxdb time literal

        Args:
            value (str): time literal to be checked

        Raises:
            ValueError: No value given
            ValueError: Not a string given

        Returns:
            bool: true if it is consistent
        """
        if(not value):
            raise ValueError("need value to verify time literal")
        if(not isinstance(value, str)):
            raise ValueError("type of the value for time literal check is not str")
        if(re.match(r"^(\d+(?:[uµsmhdw]|(?:ns)|(?:ms)))+$", value)):
            return True
        return False

    @staticmethod
    def transform_time_literal(value: str, single_vals: bool = False) -> Union[str, Tuple[int, int, int]]:
        """Transforms a time literal into hour/min/seconds literal.

        Checks before if the literal is valid.

        Args:
            value (str): time literal to be transformed
            single_vals (bool, optional): whether the result should be a tuple. Defaults to False.

        Raises:
            ValueError: no value given
            ValueError: not a str given
            ValueError: value is no time literal

        Returns:
            Union[str, Tuple[int, int, int]]: influxdb time literal in 0h0m0s format or values as tuple
        """
        if(not value):
            raise ValueError("need a value to verify the time literal")
        if(not isinstance(value, str)):
            raise ValueError("type of the value for time literal transform is not str")
        if(not re.match(r"^(\d+(?:[smhdw]))+$", value)):
            if(value.lower() == "inf"):
                return "0s"
            raise ValueError("value does not pass the time literal check", value)

        match_list = re.findall(r"((\d+)([a-z]+))", value)
        time_s = 0
        for (_, numbers, unit) in match_list: # full is first, but unused
            time_s += SppUtils.parse_unit(numbers, unit)

        hours = int(time_s / pow(60, 2))
        time_s = time_s % pow(60, 2)

        mins = int(time_s / pow(60, 1))
        seconds = int(time_s % pow(60, 1))
        if(single_vals):
            return (hours, mins, seconds)
        return f"{hours}h{mins}m{seconds}s"


    @staticmethod
    def escape_chars(value: Any, replace_dict: Dict[str, str]) -> str:
        """Escapes chars to a even number of escape signs. Only adds escape signs.

        TODO: Probably buggy with filenames, need to redo again.

        Arguments:
            value {str} -- string which should get escaped
            replace_dict {Dict[str, str]} -- Mapping of chars with replacement

        Raises:
            ValueError: No replacement mapping is given

        Returns:
            str -- the changed string
        """
        if(not replace_dict):
            raise ValueError("need dict with char/replacement to replace something")

        if(not isinstance(value, str)):
            value = f'{value}'.format(value)

        escaped = value.translate(str.maketrans(replace_dict))

        return escaped

    @classmethod
    def default_split(cls, mydict: Dict[str, Any]) -> Tuple[
            Dict[str, str], Dict[str, Union[float, int, bool, str]], Union[str, int, None]]:
        """Do not use this method on purpose! Pre-Defining a table is highly recommended.
        Splits the dict into tags/fields/timestamp according to the format of value.

        Strings without spaces are tags
        Strings with spaces or double-quotations are fields
        any number or boolean is a field
        if no field is found a dummy field is inserted with a warning and a debug message.

        Arguments:
            mydict {dict} -- dict with columns as keys. None values are ignored

        Raises:
            ValueError: Dictionary is not provided or empty

        Returns:
            (dict, dict, int) -- Tuple of tags, fields and timestamp
        """
        if(not mydict):
            raise ValueError("at least one entry is required to split")

        ExceptionUtils.error_message("WARNING: Using default split method, one table is set up only temporary")
        LOGGER.debug(f"default split args: {mydict}")

        # In case only fields are recognized
        fields: Dict[str, Union[float, int, bool, str]] = {}
        tags: Dict[str, str] = {}
        time_stamp: Any = None

        for(key, value) in mydict.items():
            if(value is None):
                # skip if no value
                continue

                # Check timestamp value if it matches any of predefined time names
            if(key in cls.time_key_names):

                # self defined logtime has higher priority, only it allows a rewrite
                if(not time_stamp or key == 'logTime'):
                    time_stamp = value

                # continue in any case to avoid double insert
                continue

            if(isinstance(value, (float, int, bool))):
                fields[key] = value
            # Make a string out of Lists/Dicts
            if(not isinstance(value, str)):
                value = '\"{}\"'.format(value)

            if(re.search(r"[\s\[\]\{\}\"]", value)):
                fields[key] = value
            else:
                tags[key] = value

        # at least one field is required to insert.
        if(not fields):
            ExceptionUtils.error_message(f"missing field in {mydict}")
            fields["MISSING_FIELD"] = 42

        if(time_stamp is None):
            ExceptionUtils.error_message(f"No timestamp value gathered when using default split, using current time: {mydict}")
            time_stamp = SppUtils.get_actual_time_sec()

        return (tags, fields, time_stamp)
