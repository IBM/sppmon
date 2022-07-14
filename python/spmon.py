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
 ConfigDataclass
 RequiredFile
 SpMon
"""

import logging
import sys
import time

from enum import Enum, unique, auto
from spConnection.sp_rest_client import SpRestClient
from spInflux.sp_influx_client import SpInfluxClient
from spmonMethods.sp_dataclasses import \
    SpServerParams, SpInfluxParams
from spmonMethods.sp_ingest import SpIngestMethods
from typing import Any, Dict, NoReturn, Optional
from utils.exception_utils import ExceptionUtils
from utils.sp_utils import SpUtils
from utils.spp_utils import SppUtils

# Using Global Logger from SPPMon
LOGGER_NAME = "spmon"
LOGGER = logging.getLogger(LOGGER_NAME)

# Define error codes
ERROR_CODE_START_ERROR: int = 3
ERROR_CODE_CMD_ARGS: int = 2
ERROR_CODE: int = 1
SUCCESS_CODE: int = 0

VERSION = "0.0.0 (2022/06/20)"


@unique
class RequiredFile(Enum):
    """Declares the types of configuration files SpMon expects to exist for
    configuration purposes.
    """
    CONFIG = "CONFIG"
    QUERIES = "QUERIES"


class SpMon:
    """Main-File of SpMon.

        Attributes:
            Final contents TBD

        Methods:
            exit: Cleanly ends remaining connections or active processes and exits the program.
            read_required_file: Loads configuration files into dictionaries.

        TODO:
            - Implement applicable configuration options users may expect if coming from SppMon
            - Implement critical missing methods (such as exit)
    """

    enable_server_discovery: bool = True
    """Override user-defined target_servers in spqueries.json. Instead, query all connected servers."""

    starting_page_size: int = 5000
    """Page size of paginated response from the REST API endpoint"""

    def __init__(self, args):
        """Reads necessary configuration files and initializes REST and Influx clients.

        TODO:
            - Validation for necessary configuration files.
            - Emulate SppMon methods for:
              - set_critical_configs
              - set_optional_configs
        """
        self.args = args
        """Arguments passed from the parser in mon.py"""
        self.rest_client: Optional[SpRestClient] = None
        """Client used to connect to the OC Hub server."""
        self.influx_client: Optional[SpInfluxClient] = None
        """Client used to connect to the InfluxDB 2.x server"""

        # Logging (refactored from SPP)
        self.log_path: str = ""
        """path to logger, set in set_logger."""
        self.pid_file_path: str = ""
        """path to pid_file, set in check_pid_file."""

        self.log_path = SppUtils.mk_logger_file(self.args.configFile, ".log")
        SppUtils.set_logger(self.log_path, LOGGER_NAME, self.args.debug)

        LOGGER.info("Starting SPMon")

        self.pid_file_path = SppUtils.mk_logger_file(self.args.configFile, ".pid_file")
        if not SppUtils.check_pid_file(self.pid_file_path, self.args):
            ExceptionUtils.error_message("Another instance of spmon with the same args is running")
            self.exit(ERROR_CODE_START_ERROR)

        time_stamp_name, time_stamp = SppUtils.get_capture_timestamp_sec()
        self.start_counter = time.perf_counter()
        LOGGER.debug("\n\n")
        LOGGER.debug(f"running script version: {VERSION}")
        LOGGER.debug(f"cmdline options: {self.args}")
        LOGGER.debug(f"{time_stamp_name}: {time_stamp}")
        LOGGER.debug("")

        # Check/load required files (refactored from SPP)
        self.config_file = self.read_required_file(RequiredFile.CONFIG)
        self.queries_file = self.read_required_file(RequiredFile.QUERIES)

        # Initialize Config Dataclasses
        self.sp_server_params: SpServerParams = SpUtils.build_dataclass_from_dict(
            param_dict=self.config_file.get("spServer"),
            dataclass=SpServerParams
        )
        self.sp_influx_server_params: SpInfluxParams = SpUtils.build_dataclass_from_dict(
            param_dict=self.config_file.get("spInfluxDB"),
            dataclass=SpInfluxParams
        )

        # Initialize REST and Influx Clients.
        self.rest_client = SpRestClient(
            server_params=self.sp_server_params,
            starting_page_size=self.starting_page_size,
            discover_target_servers=self.enable_server_discovery
        )

        self.influx_client = SpInfluxClient(
            sp_influx_server_params=self.sp_influx_server_params
        )

        # Initialize SpMon methods
        self.ingest_methods = SpIngestMethods(
            influx_client=self.influx_client,
            rest_client=self.rest_client
        )

        self.ingest_methods.load_definitions(
            queries_file=self.queries_file
        )

        # TODO: Move to setup critical configs
        self.influx_client.connect()

    def read_required_file(self, file_type: RequiredFile) -> Dict[str, Any]:
        """Reads mandatory configuration files and returns values as a dict. It is a
        wrapper over SppMon utilities:
            SppUtils.read_conf_file
            ExceptionUtils

        It supports two cases:
            CONFIG - config_files/spconnections_default.conf
            QUERIES - spconnection/spqueries.json

        Args:
            file_type {RequiredFile}: CONFIG or QUERY

        Returns:
            dict -- dict with key, value pairs loaded from the configuration files

        TODO:
            - May not be necessary due to use of dataclasses. Consider either
              having this method perform validation or generalizing it to
              accept a file_path instead.
        """
        if file_type is RequiredFile.CONFIG:
            file_path: str = self.args.configFile
        else:
            file_path = self.args.queryFile

        required_file: Dict[str | Any] = {}
        file_name: str = file_type.value.lower()

        if not file_path:
            ExceptionUtils.error_message(f"missing {file_name} file, aborting")
            self.exit(error_code=ERROR_CODE_CMD_ARGS)
        try:
            required_file = SppUtils.read_conf_file(config_file_path=file_path)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error,
                                          extra_message=f"Error when trying to read {file_name} file, unable to read")
            self.exit(error_code=ERROR_CODE_START_ERROR)

        return required_file

    def exit(self, error_code: int = SUCCESS_CODE) -> NoReturn:
        """Method stub. Should cleanly close running processes before exiting the tool.

        Args:
            error_code: TODO - Add description

        TODO:
            - Refactor code from SppMon and emulate behavior.
        """
        self.influx_client.disconnect()
        sys.exit(error_code)

    def main(self) -> None:
        """Main method for the SpMon code path.

        TODO:
            - Add error handling for processes
        """
        LOGGER.info("Entering SPMon main method.")

        # Process user defined queries: Get response from OC & ingest to InfluxDB
        self.ingest_methods.cache_user_queries()
        self.influx_client.flush_insert_buffer()

        self.exit()
        LOGGER.info("Exiting SPMon main method.")
