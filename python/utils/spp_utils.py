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

This Module provides helper methods used across all sppmon modules.
You may implement new static/class helper methods in here.

Classes:
    SppUtils
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
from argparse import Namespace
from inspect import getsourcefile
from numbers import Number
from os.path import abspath, exists, join
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any, Dict, List, Optional, Tuple, Union

from utils.exception_utils import ExceptionUtils

LOGGER = logging.getLogger("sppmon")

class SppUtils:
    """Wrapper for general purpose themed helper methods. You may implement new methods in here.

    Attributes:
        verbose - to be set in sppmon.
        capture_time_key - name of the unique capture time stamp.

    Methods:
        read_file - Reads parameters from the JSON file and returns a JSON dict.
        get_cfg_params - Wrapper method to check if the arguments of the config file are correct.
        get_actual_time_sec - returns the actual time as timestamp in seconds.
        get_capture_timestamp_sec - Returns Tuple of the capturetimestamp name and value.
        epoch_time_to_seconds - Converts timestamp from any epoch-format into epoch-seconds.
        get_nested_kv - Acquire a nested key-value pair from a dict with possible sub-dicts.
        parse_unit - Parses a str or number into the lowest unit.

    """

    # class variable
    verbose: bool = False
    """whether to verbose print, set in sppmon.py"""

    capture_time_key: str = "sppmonCaptureTimestampS"
    """name of the single timestamp capture to allow same naming within the db"""

    @staticmethod
    def set_logger(logger_path: str, logger_name: str, debug: bool = False) -> None:
        """Sets global logger for stdout and file logging.

        Changes logger acquired by LOGGER_NAME.

        Args:
            logger_path (str): Path to the existing logging file
            logger_name (str): Name of the logger

        Raises:
            ValueError: Unable to open logger
        """

        try:
            file_handler = logging.FileHandler(logger_path)
        except Exception as error:
            # TODO here: Right exception, how to print this error?
            print("unable to open logger", file=sys.stderr)
            raise ValueError("Unable to open Logger") from error

        file_handler_fmt = logging.Formatter(
            '%(asctime)s:[PID %(process)d]:%(levelname)s:%(module)s.%(funcName)s> %(message)s')
        file_handler.setFormatter(file_handler_fmt)
        if(debug):
            file_handler.setLevel(logging.DEBUG)
        else:
            file_handler.setLevel(logging.ERROR)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    @classmethod
    def check_pid_file(cls, pid_file_path: str, ARGS: Namespace) -> bool:
        if(cls.verbose):
            LOGGER.info("Checking for other running instances with same arguments")
        LOGGER.debug(f"PID-File path: {pid_file_path}")
        try: # global try block


            #### Check for existing PID's ####

            try: # open file block
                with open(pid_file_path, "rt", encoding="utf8") as file:
                    file_content = file.read()
                    LOGGER.debug(f"> Content of PID-File: {file_content}")
                    match_list = re.findall(r"\s?(\d+)\s(Namespace\([^\)]+\))\s?", file_content)
            except FileNotFoundError:
                pass  # no file created yet
                match_list = []
                # skip the next section

            #### Delete existing, but already completed PID's ####
            # If any instance is still running, check for same args

            deleted_processes: List[str] = []
            for match_pid, match_args in match_list:

                if(os.name == 'nt'): # windows
                    args = ['tasklist', '/FI', f"PID eq {match_pid}"]
                else: # linux
                    args = ['ps', '-p', str(match_pid)]
                LOGGER.debug(f">> Running subprocess with following args: {args}")
                try:
                    result = subprocess.run(args, capture_output=True)
                    result_stdout = result.stdout
                    LOGGER.debug(f">> Output of subprocess: {result_stdout}")
                    if result.stderr:
                        ExceptionUtils.error_message(f"Subprocess has error output, probably another SPPMon version running: {result.stderr}")
                    if(re.search(match_pid, str(result_stdout))):
                        LOGGER.debug(f">> Found a still running process with PID {match_pid} and arguments: {match_args}")

                        if match_args.strip() == str(ARGS).strip():
                            LOGGER.debug(f">> Instance with PID {match_pid} has the same arguments as this execution: {match_args}")
                            # ABORT - Another instance is running with the same args
                            return False

                    deleted_processes.append(match_pid)
                except CalledProcessError as error:
                    ExceptionUtils.exception_info(error,
                    f"Error when checking for PID {match_pid} with own PID {os.getpid()}, please report to develop team. Used command: {args}")

            # delete processes which did get killed, not often called
            # initialize file_str
            file_str: str = ""
            if(deleted_processes):
                LOGGER.debug(f"> Found {len(deleted_processes)} Ids to delete: {deleted_processes}")
                # re-open in case of a newly started program during longer subprocess execution
                # still possibility to overwrite, but smaller
                with open(pid_file_path, "rt", encoding="utf8") as file:
                    file_str = file.read()

                # iterate over PIDs and delete the entries in the string
                for pid in deleted_processes:
                    file_str = re.sub(rf"\s?({pid})\s(Namespace\([^\)]+\))\s?", "", file_str)

            #### Appending own PID to pid file ####
            LOGGER.debug(f"> Appending own PID with args to PID-File.")
            # new line at start to separate from previous entry. Otherwise removed with the strip.
            file_str += f"\n{os.getpid()} {str(ARGS)}"
            LOGGER.debug(f"> new content of PID file: {file_str}")

            # always write your own pid into it
            LOGGER.debug("> Writing new PID-Lines into the PID file")
            with open(pid_file_path, "wt", encoding="utf8") as file:
                # Strip to avoid multiple white spaces at start or end of file.
                file.write(file_str.strip())
            return True
        except Exception as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("Error when checking pid file")

    @staticmethod
    def remove_pid_file(pid_file_path: str, ARGS: Namespace) -> None:
        try:
            with open(pid_file_path, "rt", encoding="utf8") as file:
                file_str = file.read()
                LOGGER.debug(f"> Current content of PID file: {file_str}")

            # remove the pid entry of this execution
            new_file_str = file_str.replace(f"{os.getpid()} {str(ARGS)}", "").strip()
            LOGGER.debug(f"> New content of PID file: {new_file_str}")
            if(not new_file_str.strip()):
                LOGGER.debug(f"> Removing PID file")
                os.remove(pid_file_path)
            else:
                LOGGER.debug(f"> Overwriting PID file")
                with open(pid_file_path, "wt", encoding="utf8") as file:
                    file.write(new_file_str)
        except Exception as error:
            ExceptionUtils.exception_info(error, "Error when removing pid_file")

    @staticmethod
    def mk_logger_file(conf_file_path: str, log_dir_name: str,  file_ending: str) -> str:
        """returns a filepath to spectrum-protect-sppmon/sppmonLogs/FILE out of the config file + a new file ending.

        Creates both parent dirs and log file.

        Args:
            conf_file (str): name of the config file incl. path
            file_ending (str): the new file ending

        Returns:
            str: full path to the file
        """
        if(conf_file_path):
            # get full Path without links
            real_path = os.path.realpath(conf_file_path)

            # get everything behind the last slash
            config_name = os.path.basename(real_path)

            # get name without file ending by taking the second last item
            try:
                config_name = config_name.split('.')[-2]
            except IndexError as error:
                ExceptionUtils.exception_info(error, "The config-file seems to not have a correct file ending")
                raise ValueError("Unable to read the config file due a error within the specified path.")

            logger_file_name = config_name + file_ending
        else:
            logger_file_name = "no_config_file" + file_ending

        # gets location of defined function -> it is defined here, dummy function
        sppmon_path = getsourcefile(lambda: 0)
        if(not sppmon_path):
            raise ValueError("Unable to determine log path from script")
        # log_path = -> spectrum-protect-sppmon/python/utils/spp_utils.py
        sppmon_path = join(sppmon_path, "..", "..", "..")
        sppmon_path = abspath(sppmon_path)

        logger_dir_path = join(sppmon_path, log_dir_name)
        logger_dir_path = abspath(logger_dir_path)
        # create if not existent
        Path(logger_dir_path).mkdir(parents=True, exist_ok=True)

        logger_file_path = join(logger_dir_path, logger_file_name)

        if(not exists(logger_file_path)):
            Path(logger_file_path).touch()

        return logger_file_path

    @classmethod
    def read_conf_file(cls, config_file_path: str) -> Dict[str, Any]:
        """Reads parameters from the JSON file and returns a JSON dict.

        Arguments:
            config_file_path {str} -- path to the .cong file

        Raises:
            ValueError: no config file specified.
            ValueError: file not consistent.
            ValueError: file not found.

        Returns:
            Dict[str, Any] -- Config file as JSON dict
        """
        # read parameters from JSON file and returns JSON dictionary if file exists and
        # structure is consistent
        if(config_file_path is None):
            raise ValueError("ERROR:   missing parameter, no config file specified, ... aborting program")
        try:
            with open(config_file_path, "r", encoding="utf8") as config_file:
                try:
                    settings = json.load(config_file)
                except json.decoder.JSONDecodeError as error:  # type: ignore
                    ExceptionUtils.exception_info(error=error)  # type: ignore
                    raise ValueError(f"parameter file '{config_file_path}' not consistent") from error

        except FileNotFoundError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError(f"parameter file '{config_file_path}' not found") from error

        return settings

    @classmethod
    def get_cfg_params(cls, param_dict: Dict[str, Union[List[Dict[str, Any]], Dict[str, Any]]],
                       param_name: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Wrapper method to check if the arguments of the config file are correct.

        Arguments:
            param_dict {Dict[str, Union[List[Dict[str, Any]], Dict[str, Any]]]} -- auth file as json dict.
            param_name {str} -- name of the elem you want to query.

        Raises:
            ValueError: no param dict given or not of type dict
            ValueError: no param name given or not string
            ValueError: no config found for param name or completely empty
            ValueError: config found is not a dict or list.
            ValueError: parameters within the config are none.

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]] -- The selected config without none values.
        """
        if(not param_dict):
            raise ValueError("param_dict is empty or None")
        if(not param_name):
            raise ValueError("need param name to get element")

        cfg = param_dict.get(param_name, None)
        if(not cfg):
            raise ValueError("{param_name} config does not exist or is empty".format(param_name=param_name))
        if(not isinstance(cfg, (dict, list))):
            raise ValueError(f"config under {param_name} is not a dict or a list: {cfg}")
        if(None in cfg):
            raise ValueError('Parameters within {param_name} are None: {dict}'.format(param_name=param_name, dict=cfg))

        return cfg

    @staticmethod
    def get_actual_time_sec() -> int:
        """returns the actual time as timestamp in seconds."""
        return int(round(time.time()))

    @classmethod
    def get_capture_timestamp_sec(cls) -> Tuple[str, int]:
        """Returns Tuple of the capturetimestamp name and value"""
        return cls.capture_time_key, cls.get_actual_time_sec()

    @staticmethod
    def to_epoch_secs(time_stamp: Union[str, int, float]) -> int:
        """Converts timestamp from any epoch-format into epoch-seconds precision.

        Arguments:
            time_stamp {Union[str, int, float]} -- timestamp to be converted.

        Raises:
            ValueError: unsupported type

        Returns:
            int -- epoch timestamp in second format
        """
        if(isinstance(time_stamp, str)):
            time_stamp = time_stamp.strip(" ")
            if(re.match(r"\d+", time_stamp)):
                time_stamp = int(time_stamp)
            elif(re.match(r"\d+\.\d+", time_stamp)):
                time_stamp = float(time_stamp)
        if(not isinstance(time_stamp, (int, float))):
            raise ValueError("unsupported timestamp type")

        # convert ms or ns to seconds
        # that is the limit to ms format
        while(time_stamp >= 99999999999):
            time_stamp /= 1000

        return int(time_stamp)

    @staticmethod
    def get_nested_kv(key_name: str, nested_dict: Dict[str, Any]) -> Tuple[str, Optional[Any]]:
        """Acquire a nested key-value pair from a dict with possible sub-dicts.

        Travels along the dynamic path defined in keyName to the result.
        If the path does not exist returns the searched key and None.

        Arguments:
            keyName {str} -- Path to the value wanted
            nested_dict {Dict[str, Any]} -- dictionary with values being other dictionaries or the result.

        Raises:
            ValueError: no str key given.
            ValueError: no dict given.

        Returns:
            Tuple[str, Optional[Any]] -- key with the searched result or None if not found
        """
        if(not key_name):
            raise ValueError("need path to key as string to find elem.")
        if(not nested_dict):
            raise ValueError("need dictionary to find elem within it")

        # split into multiple sub-levels
        key_list = key_name.split('.')

        sub_dict: Union[Any, Dict[str, Any]] = nested_dict

        # go deeper until result is found
        # at least one key available due arg check above
        for key in key_list:

            # path is available -> go on
            if(sub_dict):

                # sub_dict is now either another sub_dict or the result
                sub_dict = sub_dict.get(key, None)

            # path is wrong or not existent
            else:
                # return wanted key and None
                return (key_list[-1], None)

        # key is now lowest level with right value
        return (key_list[-1], sub_dict)

    __display_datatype = 1 # Bytes are displayed as bytes
    __datatypes: Dict[str, Union[float, int]] = {
        'no type':          1,

        # Percent
        '%':                1,

        # DATA
        # assumed its byte, not bit
        'b':                pow(2, 0) / __display_datatype,

        'k':                pow(2, 10) / __display_datatype,
        'kb':               pow(10, 3) / __display_datatype,
        'kib':              pow(2, 10) / __display_datatype,

        #'m':               pow(2, 20) / __display_datatype, NOTE: Duplicate key, unused anyway
        'mib':              pow(2, 20) / __display_datatype,
        'mib/s':            pow(2, 20) / __display_datatype,
        'mb':               pow(10, 6) / __display_datatype,
        'mbps':             pow(10, 6) / __display_datatype,

        'g':                pow(2, 30) / __display_datatype,
        'gib':              pow(2, 30) / __display_datatype,
        'gb':               pow(10, 9) / __display_datatype,
        'gbps':             pow(10, 9) / __display_datatype,

        't':                pow(2, 40) / __display_datatype,
        'tb':               pow(10, 12) / __display_datatype,
        'tib':              pow(2, 40) / __display_datatype,

        # TIME

        'second(s)':        pow(60, 0),
        'second':           pow(60, 0),
        's':                pow(60, 0),

        'min(s)':           pow(60, 1),
        'm':                pow(60, 1),

        'hour(s)':          pow(60, 2),
        'h':                pow(60, 2),

        'd':                pow(60, 2) * 24,

        'w':                pow(60, 2) * 24 * 7,
    }

    @classmethod
    def get_unit_multiplier(cls, unit: str) -> Union[float, int]:
        return cls.__datatypes[unit.lower()]


    @classmethod
    def parse_unit(
            cls, data: Union[str, Number], given_unit: Optional[str] = None,
            delimiter: str = " ") -> Optional[Union[int, Number]]:
        """Parses a str or number into the lowest unit.

        Specify a delimiter if used, default splitting to a single space.
        Only specify `given unit` if the unit is not within the data itself.
        specify `unit_start_pos` if the unit is within data without delimiter.
        check dict `datatypes` for parsable units.

        Arguments:
            data {Union[str, Number]} -- data w/wo unit to be parsed.

        Keyword Arguments:
            given_unit {Optional[str]} -- specify if no unit is given. (default: {None})
            delimiter {str} -- delimiter to split val and unit (default: {" "})

        Raises:
            ValueError: no string or number value given
            ValueError: delimiter is None
            ValueError: index error while parsing
            ValueError: no datatype known in `datatypes`
            ValueError: value is not numeric

        Returns:
            Optional[Union[int, Number]] -- Either the data in lowest unit or None if it failed.
        """

        if(not data):
            return None
        if(isinstance(data, Number)):
            return data

        if(not isinstance(data, str)):
            raise ValueError("need string value to parse unit")
        if(data == 'null'):
            return None
        if(delimiter is None):
            raise ValueError("delimiter cannot be None")

        data_parts = list(map(lambda part: part.strip(" "), data.split(delimiter)))

        i: int = 0
        final_value: Union[int, float] = 0

        while(i < len(data_parts)):
            value = data_parts[i]
            i += 1
            unit = 'no type'

            # get correct value and unit
            if(given_unit):
                unit = given_unit
            else:
                unit_match = re.match(r"(-?\d+(?:\.\d+)?)([a-zA-Z]+)", value)
                if(unit_match):
                    value = unit_match.group(1)
                    if(unit_match.group(2)):
                        unit = unit_match.group(2)
                elif(i < len(data_parts)):
                    unit_match = re.match(r"(\D+)", data_parts[i])
                    if(unit_match and unit_match.group(1)):
                        unit = unit_match.group(1)
                        i += 1
            try:
                unit_multiplier = cls.get_unit_multiplier(unit)
            except KeyError as error:
                raise ValueError("no known datatype for value with given unit", value, unit, data_parts, error)

            # convert value
            if(re.match(r"^-?\d+$", value)):
                value = int(value)
            elif(re.match(r"^-?\d+\.\d+$", value)):
                value = float(value)
            else:
                raise ValueError("value is not numeric", value)

            final_value += value * unit_multiplier

        return round(final_value)
