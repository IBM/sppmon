"""
(C) IBM Corporation 2020

Description:
 Monitoring and long-term reporting for IBM Spectrum Protect Plus.
 Provides a data bridge from SPP to InfluxDB and provides visualization dashboards via Grafana.

 This program provides functions to query IBM Spectrum Protect Plus Servers,
 VSNAP, VADP and other servers via REST API and ssh. This data is stored into a InfluxDB database.

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Daniel Wendler
 Niels Korschinsky

 changelog:
 02/06/2020 version 0.2   tested with SPP 10.1.5
 02/13/2020 version 0.25  improved debug logging & url encoding
 02/20/2020 version 0.31  added function to add / modify REST API url parameters
                          added jobLogDetails function to capture joblogs and store in Influx DB
 03/24/2020 version 0.4   migrated to Influxdb
 04/15/2020 version 0.6   reworked all files with exception handling
 04/16/2020 version 0.6.1 Hotfixing vmStats table
 04/16/2020 version 0.6.2 Split into multiple tables
 04/17/2020 version 0.6.3 New Catalog Statistics and Reduced JobLogs store to only Summary.
 04/18/2020 version 0.6.4 Parsing two new JobLogID's
 04/20/2020 version 0.6.4.1 Minor change to jobLogs
 04/22/2020 version 0.6.5 Improved SSH Commands and added new Stats via ssh
 04/23/2020 version 0.7   New module structure
 04/27/2020 version 0.7.1 Fixes to index errors breaking the execution.
 04/27/2020 version 0.7.2 Reintroduced all joblogs and added --minimumLogs
 04/30/2020 version 0.8   Reworked Exception system, intorduces arg grouping
 05/07/2020 version 0.8.1 Part of the documentation and typing system, renamed programm args
 05/14/2020 version 0.8.2 Cleanup and full typing
 05/18/2020 version 0.9   Documentation finished and some bugfixes.
 05/19/2020 version 0.9.1 Moved future import into main file.
 06/02/2020 version 0.9.2 Fixed df ssh command, introduced CLOUDPROXY and shortend ssh.py file.
 06/03/2020 version 0.9.3 Introduces --hourly, grafana changes and small bugfixes
 07/16/2020 version 0.9.4 Shift of the --joblogs to --daily as expected
 07/16/2020 version 0.9.5 Dynamically shift of the pagesize for any kind of get-API requests
 08/02/2020 version 0.10.0 Introducing Retention Policies and Continuous Queries, breaking old tables
 08/25/2020 version 0.10.1 Fixes to Transfer Data, Parse Unit and Top-SSH-Command parsing
 09/01/2020 version 0.10.2 Parse_Unit fixes (JobLogs) and adjustments on timeout
 11/10/2020 version 0.10.3 Introduced --loadedSystem argument and moved --minimumLogs to deprecated
 12/07/2020 version 0.10.4 Included SPP 10.1.6 addtional job information features and some bugfixes
 12/29/2020 version 0.10.5 Replaced ssh 'top' command by 'ps' command to bugfix truncating data
 01/22/2021 version 0.10.6 Removed `--processStats`, integrated in `--ssh` plus Server/vSnap `df` root recording
 01/22/2021 version 0.10.7 Replaced `transfer_data` by `copy_database` with improvements
 01/28/2021 version 0.11   Copy_database now also creates the database with RP's if missing.
 01/29/2021 version 0.12   Implemented --test function, also disabeling regular setup on certain args
 02/09/2021 version 0.12.1 Hotfix job statistic and --test now also checks for all commands individually
 02/07/2021 version 0.13   Implemented additional Office365 Joblog parsing
 02/10/2021 version 0.13.1 Fixes to partial send(influx), including influxdb version into stats
 03/29/2021 version 0.13.2 Fixes to typing, reducing error messages and tracking code for NaN bug
 07/06/2021 version 0.13.3 Hotfixing version endpoint for SPP 10.1.8.1
 07/09/2021 version 0.13.4 Hotfixing storage execption, chaning top-level execption handling to reduce the need of further hotfixes
 08/06/2021 version 0.13.5 Fixing PS having unituitive CPU-recording, reintroducing TOP to collect CPU informations only
 07/14/2021 version 0.13.6 Optimizing CQ's, reducing batch size and typo fix within cpuram table
 07/27/2021 version 0.13.7 Streamlining --test arg and checking for GrafanaReader on InfluxSetup
 08/02/2021 version 0.13.8 Enhancement and replacement of the ArgumentParser and clearer config-file error messages
 08/10/2021 version 0.13.9 Rework of the JobLogs and fix of Log-Filter.
 08/18/2021 version 0.14   Added install script and fixed typo in config file, breaking old config files.
 08/22/2021 version 0.15   Added --fullLogs argument and reduced regular/loaded joblog query to SUMMARY-Only
"""
from __future__ import annotations

import functools
import logging
import os
import re
import subprocess
import sys
import time
from argparse import ArgumentError, ArgumentParser
from subprocess import CalledProcessError
from typing import Any, Dict, List, NoReturn, Optional, Union

from influx.influx_client import InfluxClient
from sppConnection.api_queries import ApiQueries
from sppConnection.rest_client import RestClient
from sppmonMethods.jobs import JobMethods
from sppmonMethods.protection import ProtectionMethods
from sppmonMethods.ssh import SshMethods
from sppmonMethods.system import SystemMethods
from sppmonMethods.testing import TestingMethods
from utils.connection_utils import ConnectionUtils
from utils.execption_utils import ExceptionUtils
from utils.methods_utils import MethodUtils
from utils.spp_utils import SppUtils

# Version:
VERSION = "0.15.0  (2021/08/22)"


# ----------------------------------------------------------------------------
# command line parameter parsing
# ----------------------------------------------------------------------------
parser = ArgumentParser(
    # exit_on_error=False, TODO: Enable in python version 3.9
    description=
    """Monitoring and long-term reporting for IBM Spectrum Protect Plus.
 Provides a data bridge from SPP to InfluxDB and provides visualization dashboards via Grafana.

 This program provides functions to query IBM Spectrum Protect Plus Servers,
 VSNAP, VADP and other servers via REST API and ssh. This data is stored into a InfluxDB database.""",
 epilog="For feature-requests or bug-reports please visit https://github.com/IBM/spectrum-protect-sppmon")

parser.add_argument("-v", '--version', action='version', version="Spectrum Protect Plus Monitoring (SPPMon) version " + VERSION)

parser.add_argument("--cfg", required=True, dest="configFile", help="REQUIRED: specify the JSON configuration file")
parser.add_argument("--verbose", dest="verbose", action="store_true", help="print to stdout")
parser.add_argument("--debug", dest="debug", action="store_true", help="save debug messages")
parser.add_argument("--test", dest="test", action="store_true", help="tests connection to all components")

parser.add_argument("--constant", dest="constant", action="store_true",
                  help="execute recommended constant functions: (ssh, cpu, sppCatalog)")

parser.add_argument("--hourly", dest="hourly", action="store_true",
                  help="execute recommended hourly functions: (constant + jobs, vadps, storages)")

parser.add_argument("--daily", dest="daily", action="store_true",
                  help="execute recommended daily functions: (hourly +  joblogs, vms, slaStats, vmStats)")

parser.add_argument("--all", dest="all", action="store_true", help="execute all functions: (daily + sites)")

parser.add_argument("--jobs", dest="jobs", action="store_true", help="store job history")
parser.add_argument("--jobLogs", dest="jobLogs", action="store_true",
                  help="retrieve detailed information per job (job-sessions)")

parser.add_argument("--loadedSystem", dest="loadedSystem", action="store_true",
                  help="Special settings for loaded systems, increasing API-request timings.")

parser.add_argument("--fullLogs", dest="fullLogs", action="store_true",
                  help="Requesting any kind of Joblogs instead of the default SUMMARY-Logs.")

parser.add_argument("--ssh", dest="ssh", action="store_true", help="execute monitoring commands via ssh")

parser.add_argument("--vms", dest="vms", action="store_true", help="store vm statistics (hyperV, vmWare)")
parser.add_argument("--vmStats", dest="vmStats", action="store_true", help="calculate vm statistic from catalog data")
parser.add_argument("--slaStats", dest="slaStats", action="store_true", help="calculate vm's and applications per SLA")

parser.add_argument("--vadps", dest="vadps", action="store_true", help="store VADPs statistics")
parser.add_argument("--storages", dest="storages", action="store_true", help="store storages (vsnap) statistics")

parser.add_argument("--sites", dest="sites", action="store_true", help="store site settings")
parser.add_argument("--cpu", dest="cpu", action="store_true", help="capture SPP server CPU and RAM utilization")
parser.add_argument("--sppcatalog", dest="sppcatalog", action="store_true", help="capture Spp-Catalog Storage usage")

parser.add_argument("--copy_database", dest="copy_database",
                  help="Copy all data from .cfg database into a new database, specified by `copy_database=newName`. Delete old database with caution.")


# DEPRECATED AREA
#TODO removed in Version 1.1.
parser.add_argument("--minimumLogs", dest="minimumLogs", action="store_true",
                  help="DEPRECATED, use '--loadedSystem' instead. To be removed in v1.1")
parser.add_argument("--processStats", dest="processStats", action="store_true",
                  help="DEPRECATED, use '--ssh' instead")
parser.add_argument("--create_dashboard", dest="create_dashboard", action="store_true",
                  help="DEPRECATED: Just import the regular dashboard instead, choose datasource within Grafana. To be removed in v1.1")
parser.add_argument("--dashboard_folder_path", dest="dashboard_folder_path",
                  help="DEPRECATED: Just import the regular dashboard instead, choose datasource within Grafana. To be removed in v1.1")

print = functools.partial(print, flush=True)

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

ERROR_CODE_START_ERROR: int = 3
ERROR_CODE_CMD_ARGS: int = 2
ERROR_CODE: int = 1
SUCCESS_CODE: int = 0

try:
    ARGS = parser.parse_args()
except SystemExit as exit_code:
    if(exit_code.code != SUCCESS_CODE):
        print("> Error when reading SPPMon arguments.", file=sys.stderr)
        print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
        print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(exit_code)
except ArgumentError as error:
    print(error.message)
    print("> Error when reading SPPMon arguments.", file=sys.stderr)
    print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
    print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(ERROR_CODE_CMD_ARGS)

class SppMon:
    """Main-File for the sppmon. Only general functions here and calls for sub-modules.

    Attributes:
        log_path - path to logger, set in set_logger
        pid_file_path - path to pid_file, set in check_pid_file
        config_file
        See below for full list

    Methods:
        set_logger - Sets global logger for stdout and file logging.
        set_critial_configs - Sets up any critical infrastructure.
        set_optional_configs - Sets up any optional infrastructure.
        store_script_metrics - Stores script metrics into influxb.
        exit - Executes finishing tasks and exits sppmon.

    """

    # set class variables
    MethodUtils.verbose = ARGS.verbose
    SppUtils.verbose = ARGS.verbose

    # ###### API-REST page settings  ###### #
    # ## IMPORTANT NOTES ## #
    # please read the documentation before adjusting values.
    # if unsure contact the sppmon develop team before adjusting

    # ## Recommend changes for loaded systems ##

    # Use --loadedSystem if sppmon causes big CPU spikes on your SPP-Server
    # CAUTION: using --loadedSystem causes some data to not be recorded.
    # all changes adjusts settings to avoid double running mongodb jobs.
    # Hint: make sure SPP-mongodb tables are correctly indexed.

    # Priority list for manual changes:

    # Only if unable to connect at all:
    # 1. Increase initial_connection_timeout

    # Small/Medium Spikes:

    # finetune `default` variables:
    # 1. increase timeout while decreasing preferred send time (timeout disable: None)
    # 2. increase timeout reduction (0-0.99)
    # 3. decrease scaling factor (>1)

    # Critical/Big Spikes:

    # CAUTION Reduce Recording: causes less Joblogs-Types to be recorded
    # 1. Enable `--loadedSystem`
    # 2. finetune `loaded`-variables (see medium spikes 1-3)
    # 3. Reduce JobLog-Types (min only `SUMMARY`)

    # Other finetuning mechanics (no data-loss):
    # 1. decrease allowed_send_delta (>=0)
    # 2. decrease starting pagesize (>1)

    initial_connection_timeout: float = 6.05
    """Time spend waiting for the initial connection, slightly larger than 3 multiple"""

    pref_send_time: int = 30
    """preferred query send time in seconds"""
    loaded_pref_send_time: int = 20
    """desired send time per query in seconds for loaded systems"""

    max_scaling_factor: float = 3.5
    """max scaling factor of the pagesize increase per request"""
    loaded_max_scaling_factor: float = 3.5
    """max scaling factor of the pagesize increase per request for loaded systems"""

    allowed_send_delta: float = 0.1
    """delta of send allowed before adjustments are made to the pagesize in %"""
    loaded_allowed_send_delta: float = 0.1
    """delta of send allowed before adjustments are made to the pagesize in % on loaded systems"""

    request_timeout: int | None = 60
    """timeout for api-requests"""
    loaded_request_timeout: int | None = 360
    """timeout on loaded systems"""

    timeout_reduction: float = 0.7
    """reduce of the actual pagesize on timeout in percent"""
    loaded_timeout_reduction: float = 0.95
    """reduce of the actual pagesize on timeout in percent on loaded systems"""

    max_send_retries: int = 3
    """Count of retries before failing request. Last one is min size. 0 to disable."""
    loaded_max_send_retries: int = 1
    """Count of retries before failing request on loaded systems. Last one is min size. 0 to disable."""

    starting_page_size: int = 50
    """starting page size for dynamical change within rest_client"""
    loaded_starting_page_size: int = 10
    """starting page size for dynamical change within rest_client on loaded systems"""

    min_page_size: int = 5
    """minimum size of a rest-api page"""
    loaded_min_page_size: int = 1
    """minimum size of a rest-api page on loaded systems"""

    # possible options: '["INFO","DEBUG","ERROR","SUMMARY","WARN"]'
    joblog_types = ["SUMMARY"]
    """joblog query types on normal running systems"""
    full_joblog_types = ["INFO", "DEBUG", "ERROR", "SUMMARY", "WARN"]
    """jobLog types to be requested on full logs."""

    # String, cause of days etc
    # ### DATALOSS if turned down ###
    job_log_retention_time = "60d"
    """Configured spp log rentation time, logs get deleted after this time."""

    # set later in each method, here to avoid missing attribute
    influx_client: Optional[InfluxClient] = None
    rest_client: Optional[RestClient] = None
    api_queries: Optional[ApiQueries] = None
    system_methods: Optional[SystemMethods] = None
    job_methods: Optional[JobMethods] = None
    protection_methods: Optional[ProtectionMethods] = None
    ssh_methods: Optional[SshMethods] = None

    def __init__(self):
        self.log_path: str = ""
        """path to logger, set in set_logger."""
        self.pid_file_path: str = ""
        """path to pid_file, set in check_pid_file."""

        self.set_logger()

        LOGGER.info("Starting SPPMon")
        if(not self.check_pid_file()):
            ExceptionUtils.error_message("Another instance of sppmon with the same args is running")
            self.exit(ERROR_CODE_START_ERROR)

        time_stamp_name, time_stamp = SppUtils.get_capture_timestamp_sec()
        self.start_counter = time.perf_counter()
        LOGGER.debug("\n\n")
        LOGGER.debug(f"running script version: {VERSION}")
        LOGGER.debug(f"cmdline options: {ARGS}")
        LOGGER.debug(f"{time_stamp_name}: {time_stamp}")
        LOGGER.debug("")

        if(not ARGS.configFile):
            ExceptionUtils.error_message("missing config file, aborting")
            self.exit(error_code=ERROR_CODE_CMD_ARGS)
        try:
            self.config_file = SppUtils.read_conf_file(config_file_path=ARGS.configFile)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error, extra_message="Error when trying to read Config file, unable to read")
            self.exit(error_code=ERROR_CODE_START_ERROR)

        LOGGER.info("Setting up configurations")
        self.setup_args()
        self.set_critial_configs(self.config_file)
        self.set_optional_configs(self.config_file)

    def set_logger(self) -> None:
        """Sets global logger for stdout and file logging.

        Changes logger aquired by LOGGER_NAME.

        Raises:
            ValueError: Unable to open logger

        """
        self.log_path = SppUtils.mk_logger_file(ARGS.configFile, ".log")

        try:
            file_handler = logging.FileHandler(self.log_path)
        except Exception as error:
            # TODO here: Right exception, how to print this error?
            print("unable to open logger", file=sys.stderr)
            raise ValueError("Unable to open Logger") from error


        file_handler_fmt = logging.Formatter(
            '%(asctime)s:[PID %(process)d]:%(levelname)s:%(module)s.%(funcName)s> %(message)s')
        file_handler.setFormatter(file_handler_fmt)
        if(ARGS.debug):
            file_handler.setLevel(logging.DEBUG)
        else:
            file_handler.setLevel(logging.ERROR)


        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)

        logger = logging.getLogger(LOGGER_NAME)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)


    def check_pid_file(self) -> bool:
        if(ARGS.verbose):
            LOGGER.info("Checking for other SPPMon instances")
        self.pid_file_path = SppUtils.mk_logger_file(ARGS.configFile, ".pid_file")
        try:
            try:
                file = open(self.pid_file_path, "rt")
                match_list = re.findall(r"(\d+) " + str(ARGS), file.read())
                file.close()
                deleted_processes: List[str] = []
                for match in match_list:
                    # add spaces to make clear the whole number is matched
                    match = f' {match} '
                    try:
                        if(os.name == 'nt'):
                            args = ['ps', '-W']
                        else:
                            args = ['ps', '-p', match]
                        result = subprocess.run(args, check=True, capture_output=True)
                        if(re.search(match, str(result.stdout))):
                            return False
                        # not in there -> delete entry
                        deleted_processes.append(match)
                    except CalledProcessError as error:
                        deleted_processes.append(match)

                # delete processes which did get killed, not often called
                if(deleted_processes):
                    file = open(self.pid_file_path, "rt")
                    file_str = file.read()
                    file.close()
                    options = str(ARGS)
                    for pid in deleted_processes:
                        file_str = file_str.replace(f"{pid} {options}", "")
                    # do not delete if empty since we will use it below
                    file = open(self.pid_file_path, "wt")
                    file.write(file_str.strip())
                    file.close()

            except FileNotFoundError:
                pass # no file created yet

            # always write your own pid into it
            file = open(self.pid_file_path, "at")
            file.write(f"{os.getpid()} {str(ARGS)}")
            file.close()
            return True
        except Exception as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("Error when checking pid file")

    def remove_pid_file(self) -> None:
        try:
            file = open(self.pid_file_path, "rt")
            file_str = file.read()
            file.close()
            new_file_str = file_str.replace(f"{os.getpid()} {str(ARGS)}", "").strip()
            if(not new_file_str.strip()):
                os.remove(self.pid_file_path)
            else:
                file = open(self.pid_file_path, "wt")
                file.write(new_file_str)
                file.close()
        except Exception as error:
            ExceptionUtils.exception_info(error, "Error when removing pid_file")


    def set_critial_configs(self, config_file: Dict[str, Any]) -> None:
        """Sets up any critical infrastructure, to be called within the init.

        Be aware not everything may be initalized on call time.
        Add config here if the system should abort if it is missing.

        Arguments:
            config_file {Dict[str, Any]} -- Opened Config file
        """
        if(not config_file):
            ExceptionUtils.error_message("missing or empty config file, aborting")
            self.exit(error_code=ERROR_CODE_START_ERROR)
        try:
            # critical components only
            self.influx_client = InfluxClient(config_file)

            if(not self.ignore_setup):
                # delay the connect into the testing phase
                self.influx_client.connect()

        except ValueError as err:
            ExceptionUtils.exception_info(error=err, extra_message="error while setting up critical config. Aborting")
            self.influx_client = None # set none, otherwise the variable is undeclared
            self.exit(error_code=ERROR_CODE)

    def set_optional_configs(self, config_file: Dict[str, Any]) -> None:
        """Sets up any optional infrastructure, to be called within the init.

        Be aware not everything may be initalized on call time.
        Add config here if the system should not abort if it is missing.

        Arguments:
            config_file {Dict[str, Any]} -- Opened Config file
        """

        if(not config_file):
            ExceptionUtils.error_message("missing or empty config file, aborting.")
            self.exit(error_code=ERROR_CODE_START_ERROR)
        if(not self.influx_client):
            ExceptionUtils.error_message("Influx client is somehow missing. aborting")
            self.exit(error_code=ERROR_CODE)

        # ############################ REST-API #####################################
        try:
            ConnectionUtils.verbose = ARGS.verbose
            # ### Loaded Systems part 1/2 ### #
            if(ARGS.minimumLogs or ARGS.loadedSystem):
                # Setting pagesize scaling settings
                ConnectionUtils.timeout_reduction = self.loaded_timeout_reduction
                ConnectionUtils.allowed_send_delta = self.loaded_allowed_send_delta
                ConnectionUtils.max_scaling_factor = self.loaded_max_scaling_factor

                # Setting RestClient request settings.
                self.rest_client = RestClient(
                    config_file=config_file,
                    initial_connection_timeout=self.initial_connection_timeout,
                    pref_send_time=self.loaded_pref_send_time,
                    request_timeout=self.loaded_request_timeout,
                    max_send_retries=self.loaded_max_send_retries,
                    starting_page_size=self.loaded_starting_page_size,
                    min_page_size=self.loaded_min_page_size,
                    verbose=ARGS.verbose
                )
            else:
                ConnectionUtils.timeout_reduction = self.timeout_reduction
                ConnectionUtils.allowed_send_delta = self.allowed_send_delta
                ConnectionUtils.max_scaling_factor = self.max_scaling_factor

                # Setting RestClient request settings.
                self.rest_client = RestClient(
                    config_file=config_file,
                    initial_connection_timeout=self.initial_connection_timeout,
                    pref_send_time=self.pref_send_time,
                    request_timeout=self.request_timeout,
                    max_send_retries=self.max_send_retries,
                    starting_page_size=self.starting_page_size,
                    min_page_size=self.min_page_size,
                    verbose=ARGS.verbose
                )

            self.api_queries = ApiQueries(self.rest_client)
            if(not self.ignore_setup):
                # delay the connect into the testing phase
                self.rest_client.login()

        except ValueError as error:
            ExceptionUtils.exception_info(error=error, extra_message="REST-API is not available due Config error")
            # Required to declare variable
            self.rest_client = None
            self.api_queries = None

        # ######################## System, Job and Hypervisor Methods ##################
        try:
            # explicit ahead due dependency
            self.system_methods = SystemMethods(self.influx_client, self.api_queries, ARGS.verbose)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error)

        # ### Full Logs ### #
        if(ARGS.fullLogs):
            given_log_types = self.full_joblog_types
        else:
            given_log_types = self.joblog_types

        try:
            auth_rest: Dict[str, Any] = SppUtils.get_cfg_params(param_dict=config_file, param_name="sppServer") # type: ignore
            # TODO DEPRECATED TO BE REMOVED IN 1.1
            self.job_log_retention_time = auth_rest.get("jobLog_rentation", auth_rest.get("jobLog_retention", self.job_log_retention_time))
            # TODO New once 1.1 is live
            #self.job_log_retention_time = auth_rest.get("jobLog_retention", self.job_log_retention_time)

            self.job_methods = JobMethods(
                self.influx_client, self.api_queries, self.job_log_retention_time,
                given_log_types, ARGS.verbose)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error)

        try:
            # dependen on system methods
            self.protection_methods = ProtectionMethods(self.system_methods, self.influx_client, self.api_queries,
                                                        ARGS.verbose)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error)

        # ############################### SSH #####################################
        if(self.ssh and not self.ignore_setup):
            try:
                # set from None to methods once finished
                self.ssh_methods = SshMethods(
                    influx_client=self.influx_client,
                    config_file=config_file,
                    verbose=ARGS.verbose)

            except ValueError as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="SSH-Commands are not available due Config error")
                # Variable needs to be declared
                self.ssh_methods = None
        else:
            # Variable needs to be declared
            self.ssh_methods = None


    def setup_args(self) -> None:
        """This method set up all required parameters and transforms arg groups into individual args.
        """
        # ## call functions based on cmdline parameters

        # Temporary features / Deprecated

        if(ARGS.minimumLogs):
            ExceptionUtils.error_message(
                "DEPRECATED: using deprecated argument '--minumumLogs'. Use to '--loadedSystem' instead.")
        if(ARGS.processStats):
            ExceptionUtils.error_message(
                "DEPRECATED: using deprecated argument '--minumumLogs'. Use to '--ssh' instead.")

        # ignore setup args
        self.ignore_setup: bool = (
            ARGS.create_dashboard or bool(ARGS.dashboard_folder_path) or
            ARGS.test
                                  )
        if(self.ignore_setup):
            ExceptionUtils.error_message("> WARNING: An option for a utility operation has been specified.  Bypassing normal SPPMON operation.")

        if((ARGS.create_dashboard or bool(ARGS.dashboard_folder_path)) and not
           (ARGS.create_dashboard and bool(ARGS.dashboard_folder_path))):
           ExceptionUtils.error_message("> Using --create_dashboard without associated folder path. Aborting.")
           self.exit(ERROR_CODE_CMD_ARGS)

        # incremental setup, higher executes all below
        all_args: bool = ARGS.all
        daily: bool = ARGS.daily or all_args
        hourly: bool = ARGS.hourly or daily
        constant: bool = ARGS.constant or hourly

        # ######## All Methods #################

        self.sites: bool = ARGS.sites or all_args

        # ######## Daily Methods ###############

        self.vms: bool = ARGS.vms or daily
        self.job_logs: bool = ARGS.jobLogs or daily
        self.sla_stats: bool = ARGS.slaStats or daily
        self.vm_stats: bool = ARGS.vmStats or daily

        # ######## Hourly Methods ##############

        self.jobs: bool = ARGS.jobs or hourly
        self.vadps: bool = ARGS.vadps or hourly
        self.storages: bool = ARGS.storages or hourly
        # ssh vsnap pools ?

        # ######## Constant Methods ############

        self.ssh: bool = ARGS.ssh or constant
        self.cpu: bool = ARGS.cpu or constant
        self.spp_catalog: bool = ARGS.sppcatalog or constant

    def store_script_metrics(self) -> None:
        """Stores script metrics into influxb. To be called before exit.

        Does not raise any exceptions, skips if influxdb is missing.
        """
        LOGGER.info("Storing script metrics")
        try:
            if(not self.influx_client):
                raise ValueError("no influxClient set up")
            insert_dict: Dict[str, Union[str, int, float, bool]] = {}

            # add version nr, api calls are needed
            insert_dict["sppmon_version"] = VERSION
            insert_dict["influxdb_version"] = self.influx_client.version
            if(self.rest_client):
                try:
                    (version_nr, build) = self.rest_client.get_spp_version_build()
                    insert_dict["spp_version"] = version_nr
                    insert_dict["spp_build"] = build
                except ValueError as error:
                    ExceptionUtils.exception_info(error=error, extra_message="could not query SPP version and build.")

            # end total sppmon runtime
            end_counter = time.perf_counter()
            insert_dict['duration'] = int((end_counter-self.start_counter)*1000)

            # add arguments of sppmon
            for (key, value) in vars(ARGS).items():
                # Value is either string, true or false/None
                if(value):
                    insert_dict[key] = value

            # save occured errors
            error_count = len(ExceptionUtils.stored_errors)
            if(error_count > 0):
                ExceptionUtils.error_message(f"total of {error_count} exception/s occured")
            insert_dict['errorCount'] = error_count
            # save list as str if not empty
            if(ExceptionUtils.stored_errors):
                insert_dict['errorMessages'] = str(ExceptionUtils.stored_errors)

            # get end timestamp
            (time_key, time_val) = SppUtils.get_capture_timestamp_sec()
            insert_dict[time_key] = time_val

            # save the metrics
            self.influx_client.insert_dicts_to_buffer(
                table_name="sppmon_metrics",
                list_with_dicts=[insert_dict]
            )
            self.influx_client.flush_insert_buffer()
            LOGGER.info("Stored script metrics sucessfull")
            # + 1 due the "total of x exception/s occured"
            if(error_count + 1 < len(ExceptionUtils.stored_errors)):
                ExceptionUtils.error_message(
                    "A non-critical error occured while storing script metrics. \n\
                    This error can't be saved into the DB, it's only displayed within the logs.")
        except ValueError as error:
            ExceptionUtils.exception_info(
                error=error,
                extra_message="Error when storing sppmon-metrics, skipping this step. Possible insert-buffer data loss")

    def exit(self, error_code: int = SUCCESS_CODE) -> NoReturn:
        """Executes finishing tasks and exits sppmon. To be called every time.

        Executes finishing tasks and displays error messages.
        Specify only error message if something did went wrong.
        Use Error codes specified at top of module.
        Does NOT return.

        Keyword Arguments:
            error {int} -- Errorcode if a error occured. (default: {0})
        """

        # error with the command line arguments
        # dont store runtime here
        if(error_code == ERROR_CODE_CMD_ARGS):
            parser.print_help()
            sys.exit(ERROR_CODE_CMD_ARGS) # unreachable?
        if(error_code == ERROR_CODE_START_ERROR):
            ExceptionUtils.error_message("Error when starting SPPMon. Please review the errors above")
            sys.exit(ERROR_CODE_START_ERROR)

        script_end_time = SppUtils.get_actual_time_sec()
        LOGGER.debug("Script end time: %d", script_end_time)

        try:
            if(not self.ignore_setup):
                self.store_script_metrics()

                if(self.influx_client):
                    self.influx_client.disconnect()
                if(self.rest_client):
                    self.rest_client.logout()

        except ValueError as error:
            ExceptionUtils.exception_info(error=error, extra_message="Error occured while exiting sppmon")
            error_code = ERROR_CODE

        self.remove_pid_file()

        # Both error-clauses are actually the same, but for possiblility of an split between error cases
        # always last due beeing true for any number != 0
        if(error_code == ERROR_CODE or error_code):
            ExceptionUtils.error_message("Error occured while executing sppmon")
        elif(not self.ignore_setup):
            LOGGER.info("\n\n!!! script completed !!!\n")

        print(f"check log for details: grep \"PID {os.getpid()}\" {self.log_path} > sppmon.log.{os.getpid()}")
        sys.exit(error_code)

    def main(self):

        LOGGER.info("Starting argument execution")

        if(not self.influx_client):
            ExceptionUtils.error_message("somehow no influx client is present even after init")
            self.exit(ERROR_CODE)

        # ##################### SYSTEM METHODS #######################
        if(self.sites and self.system_methods):
            try:
                self.system_methods.sites()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting sites, skipping them all")

        if(self.cpu and self.system_methods):
            try:
                self.system_methods.cpuram()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when collecting cpu stats, skipping them all")

        if(self.spp_catalog and self.system_methods):
            try:
                self.system_methods.sppcatalog()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when collecting file system stats, skipping them all")

        # ####################### JOB METHODS ########################
        if(self.jobs and self.job_methods):
            # store all jobs grouped by jobID
            try:
                self.job_methods.get_all_jobs()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting jobs, skipping them all")

        if(self.job_logs and self.job_methods):
            # store all job logs per job session instance
            try:
                self.job_methods.job_logs()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting job logs, skipping them all")

        # ####################### SSH METHODS ########################
        if(self.ssh and self.ssh_methods):
            # execute ssh statements for, VSNAP, VADP, other ssh hosts
             # store all job logs per job session instance
            try:
                self.ssh_methods.ssh()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when excecuting ssh commands, skipping them all")

        # ################### HYPERVISOR METHODS #####################
        if(self.vms and self.protection_methods):
            try:
                self.protection_methods.store_vms()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting all VMs, skipping them all")

        if(self.sla_stats and self.protection_methods):
            # number of VMs per SLA and sla dumps
            try:
                self.protection_methods.vms_per_sla()
                self.protection_methods.sla_dumps()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting and computing VMs per sla, skipping them all")

        if(self.vm_stats and self.protection_methods):
            # retrieve and calculate VM inventory summary
            try:
                self.protection_methods.create_inventory_summary()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when creating inventory summary, skipping them all")

        if(self.vadps and self.protection_methods):
            try:
                self.protection_methods.vadps()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when requesting vadps, skipping them all")

        if(self.storages and self.protection_methods):
            try:
                self.protection_methods.storages()
                self.influx_client.flush_insert_buffer()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when collecting storages, skipping them all")

        # ###################### OTHER METHODS #######################

        if(ARGS.copy_database):
            try:
                self.influx_client.copy_database(ARGS.copy_database)
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when coping database.")

        # ################### NON-SETUP-METHODS #######################

        if(ARGS.test):
            try:
                TestingMethods.test_connection(self.config_file, self.influx_client, self.rest_client)
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when testing connection.")

        # DEPRECATED TODO REMOVE NEXT VERSION
        if(ARGS.create_dashboard):
            try:
                ExceptionUtils.error_message(
                    "This method is deprecated. You do not need to manually create a dashboard anymore.\n" +
                    "Please just select the datasource when importing the regular 14-day dashboard in grafana.\n" +
                    "Devs may adjust their dashboard to be generic with the scripts/generifyDashboard.py script.")
            except ValueError as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="Top-level-error when creating dashboard")

        self.exit()

if __name__ == "__main__":
    SppMon().main()
