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

Description:
 TODO

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Niels Korschinsky
"""
from __future__ import annotations

import functools
import logging
import os
import sys
import time
from argparse import ArgumentError, ArgumentParser
from datetime import datetime
from typing import Dict, NoReturn, Union

from influx.database_tables import RetentionPolicy
from influx.definitions import Definitions
from influx.influx_client import InfluxClient
from sppCheck.excel.excel_controller import ExcelController
from sppCheck.generator.fakedata_controller import FakeDataController
from sppCheck.predictor.predictor_controller import PredictorController
from sppCheck.report.report_controller import ReportController
from utils.exception_utils import ExceptionUtils
from utils.methods_utils import MethodUtils
from utils.spp_utils import SppUtils
from utils.sppcheck_utils import Themes

# Version:
VERSION = "1.0.1  (2022/08/30)"


# ----------------------------------------------------------------------------
# command line parameter parsing
# ----------------------------------------------------------------------------
parser = ArgumentParser(
    exit_on_error=False,
    description="""
SPPCheck is a system requirement verification and prediction tool aiming to enhance the existing functionality by verifying whether a system was set up correctly according to IBM's recommendations and predicting its future development.
It focuses on the storage consumption of all associated vSnaps and the server's memory and catalog space and is open to future expansion of its capabilities.
SPPCheck re-uses the existing components and integrates SPPMons core engine while offering a PDF report besides the typical Grafana Dashboard.
""",
    epilog="For feature-requests or bug-reports please visit https://github.com/IBM/spectrum-protect-sppmon")

# required options
parser.add_argument("--cfg", dest="configFile", required=True, help="REQUIRED: Specify the JSON configuration file for influxDB login purposes")
parser.add_argument("--startDate", dest="startDate", required=True, help="REQUIRED: Start date of the system in format \"YYYY-MM-DD\", e.g. startDate=2019-01-29")

# sheet options
parser.add_argument("--sheet", dest="sheetPath", help="Path to filled sizing sheet, parsing the contents into the InfluxDB. Requires args: --sizerVersion")
parser.add_argument("--sizerVersion", dest="sizerVersion", help="Specify the version of the vSnap sizer sheet, e.g v1.0 or v2.1.1")

# generation
parser.add_argument("--genFakeData", dest="genFakeData", action="store_true", help="Generate fake data. Automatically uses the fake data for all other arguments")
parser.add_argument("--predictYears", dest="predictYears", type=int, help="Predict the development for the next x years")
parser.add_argument("--pdfReport", dest="pdfReport", action="store_true", help="Create a new PDF report based on the prediction")

# generation options
parser.add_argument("--latestData", dest="latestData", action="store_true", help="Create predictions, reports, and fake data using only the latest 90 day data, but at a higher frequency(<6h)")
parser.add_argument("--fakeData", dest="fakeData", action="store_true", help="Use existing fake data to create any reports")
parser.add_argument("--theme", dest="theme", type=str, help="Optional: Chose the theme of the PDF report. Options: 'light' (default), 'dark', or 'sppcheck'")

# general purpose options
parser.add_argument("-v", '--version', action='version', version="Spectrum Protect Plus Check (SPPCheck) version " + VERSION)


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
        print("> Error when reading SPPCheck's arguments.", file=sys.stderr)
        print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
        print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(exit_code)
except ArgumentError as error:
    print(error.message)
    print("> Error when reading SPPCheck's arguments.", file=sys.stderr)
    print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
    print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(ERROR_CODE_CMD_ARGS)


class SPPCheck:
    """TODO

    Attributes:


    Methods:


    """

    def __init__(self):
        self.log_path: str = ""
        """path to logger, set in set_logger."""
        self.pid_file_path: str = ""
        """path to pid_file, set in check_pid_file."""

        # set class variables
        # Methods: not necessary in sppcheck, but done to avoid any later programming errors.
        MethodUtils.verbose = True
        SppUtils.verbose = True

        try:
            self.log_path = SppUtils.mk_logger_file(ARGS.configFile, "sppcheckLogs", ".log")
            # always save all debug information into the log, they are not printed
            SppUtils.set_logger(self.log_path, LOGGER_NAME, debug=True)

            self.start_counter = time.perf_counter()
            LOGGER.debug("\n\n NEW SPPCHECK EXECUTION \n")
            LOGGER.debug(f"running script version: {VERSION}")
            LOGGER.debug(f"cmdline options: {ARGS}")
            LOGGER.debug("\n")

            LOGGER.info("Starting SPPCheck")

            self.pid_file_path = SppUtils.mk_logger_file(ARGS.configFile, "sppcheckLogs", ".pid_file")
            if(not SppUtils.check_pid_file(self.pid_file_path, ARGS)):
                ExceptionUtils.error_message("Another instance of SPPCheck with the same args is running")
                self.exit(ERROR_CODE_START_ERROR)

            LOGGER.info("Setting up configurations")
            self.setup_args()
        except ValueError as error:
            ExceptionUtils.exception_info(error=error, extra_message="Exiting startup process due to critical failure")
            self.exit(ERROR_CODE_START_ERROR)


    def setup_args(self) -> None:
        # Temporary features / Deprecated

        ## None ##

        # ### Special dependencies between arguments ###
        # Important: ignores config file, this is done via required components

        # trigger, if not all are true or all are false
        if bool(ARGS.sheetPath) and not (bool(ARGS.sizerVersion) and bool(ARGS.startDate)):
            ExceptionUtils.error_message("> Using --sheetPath without associated --sizerVersion or --startDate arg. Aborting.")
            self.exit(ERROR_CODE_CMD_ARGS)
        if bool(ARGS.sizerVersion) and not (bool(ARGS.sheetPath) and bool(ARGS.startDate)):
            ExceptionUtils.error_message("> Using --sizerVersion without associated --sheetPath or --startDate arg. Aborting.")
            self.exit(ERROR_CODE_CMD_ARGS)

        if ARGS.latestData and not (ARGS.predictYears or  ARGS.genFakeData):
            ExceptionUtils.error_message("Warning: the --latestData flag only works in conjunction with --predictYears or --genFakeData. Aborting")
            self.exit(ERROR_CODE_CMD_ARGS)

        if ARGS.fakeData and not (ARGS.predictYears or ARGS.pdfReport):
            ExceptionUtils.error_message("Warning: the --fakeData flag only works in conjunction with --predictYears or --pdfReport. Aborting")
            self.exit(ERROR_CODE_CMD_ARGS)

        if ARGS.theme and not ARGS.pdfReport:
            ExceptionUtils.error_message("Warning: the --theme flag only works in conjunction with --pdfReport. Aborting")
            self.exit(ERROR_CODE_CMD_ARGS)

        # ### Trigger init of components ###

        if ARGS.startDate:
            try:
                self.start_date = datetime.fromisoformat(ARGS.startDate)
            except Exception as ex:
                ExceptionUtils.exception_info(ex, "Unable to parse the date from the --startDate argument")
                self.exit(ERROR_CODE_CMD_ARGS)

        if ARGS.theme:
            try:
                self.__theme = Themes(str(ARGS.theme).lower())
            except Exception as ex:
                ExceptionUtils.exception_info(ex, "Unable to parse the theme from the --theme argument. Is a valid argument chosen?")
                self.exit(ERROR_CODE_CMD_ARGS)
        else:
            self.__theme = Themes.LIGHT

        if not ARGS.configFile:
            ExceptionUtils.error_message("missing config file, aborting")
            self.exit(ERROR_CODE_CMD_ARGS)

        self.config_file = SppUtils.read_conf_file(config_file_path=ARGS.configFile)

        # number 0 is false, so that is ok.
        if ARGS.predictYears:
            try:
                self.__predict_years = int(ARGS.predictYears)
            except Exception as error:
                ExceptionUtils.exception_info(error, "The arg --predictYears does not have a numeric value")
                self.exit(ERROR_CODE_CMD_ARGS)
        else:
            self.__predict_years = None

        self.__influx_client = InfluxClient(self.config_file)
        """client used to connect to the influxdb, set in setup_critical_configs."""
        self.__influx_client.connect()

        date = datetime.now().isoformat("_", "seconds")
        # replace to avoid query error in influxdb
        self.__rp_timestamp = f"{date}".replace("-", "_").replace(":","_")

        if ARGS.latestData:
            LOGGER.info("> LatestData argument detected: Using only the data of the latest 90 days.")
            self.__dp_interval_hour = 6
            self.__datagen_range_days = min(90, (datetime.today() - self.start_date).days)
            self.__select_rp = Definitions.RP_DAYS_90()
            self.__rp_timestamp = "latest_" + self.__rp_timestamp
        else:
            self.__dp_interval_hour = 168
            self.__datagen_range_days = (datetime.today() - self.start_date).days
            self.__select_rp = Definitions.RP_INF()

        # overwrite select RP if fakedata should be used
        self.__fakedata_rp_name = "fakeData"
        if ARGS.fakeData or ARGS.genFakeData:
            LOGGER.info("> FakeData argument detected: Preparing the generation of fake data.")
            self.__select_rp = RetentionPolicy(self.__fakedata_rp_name, self.__influx_client.database, "INF")
            self.__rp_timestamp = "fake_" + self.__rp_timestamp

        LOGGER.info(f"> Using the retention policy timestamp {self.__rp_timestamp}")

    def store_script_metrics(self) -> None:
        """Stores script metrics into influxdb. To be called before exit.

        Does not raise any exceptions, skips if influxdb is missing.
        """
        LOGGER.info("Storing script metrics")
        try:
            if(not self.__influx_client):
                raise ValueError("no influxClient set up")
            insert_dict: Dict[str, Union[str, int, float, bool]] = {}

            # add version nr, api calls are needed
            insert_dict["sppcheck_version"] = VERSION
            insert_dict["influxdb_version"] = self.__influx_client.version

            # end total sppcheck runtime
            end_counter = time.perf_counter()
            insert_dict['duration'] = int((end_counter - self.start_counter) * 1000)

            # add arguments of sppcheck
            for (key, value) in vars(ARGS).items():
                # Value is either string, int, true or false/None
                if(value is not None):
                    insert_dict[key] = value

            # save occurred errors
            error_count = len(ExceptionUtils.stored_errors)
            insert_dict['errorCount'] = error_count
            # save list as str if not empty
            if(ExceptionUtils.stored_errors):
                insert_dict['errorMessages'] = str(ExceptionUtils.stored_errors)

            # get end timestamp
            (time_key, time_val) = SppUtils.get_capture_timestamp_sec()
            insert_dict[time_key] = time_val

            # save the metrics
            self.__influx_client.insert_dicts_to_buffer(
                table_name="sppcheck_metrics",
                list_with_dicts=[insert_dict]
            )
            self.__influx_client.flush_insert_buffer()
            LOGGER.info("Stored script metrics successfully")

            if(error_count < len(ExceptionUtils.stored_errors)):
                ExceptionUtils.error_message(
                    "A non-critical error occurred while storing script metrics. \n\
                    This error can't be saved into the DB, it's only displayed within the logs.")
        except ValueError as error:
            ExceptionUtils.exception_info(
                error=error,
                extra_message="Error when storing sppcheck metrics, skipping this step. Possible insert-buffer data loss")

    def exit(self, error_code: int = SUCCESS_CODE) -> NoReturn:
        """Executes finishing tasks and exits of SPPCheck. To be called every time.

        Executes finishing tasks and displays error messages.
        Specify only error message if something did went wrong.
        Use Error codes specified at top of module.
        Does NOT return.

        Keyword Arguments:
            error {int} -- Error code if a error occurred. (default: {0})
        """

        # error with the command line arguments
        # dont store runtime here
        if(error_code == ERROR_CODE_CMD_ARGS):
            parser.print_help()
            sys.exit(ERROR_CODE_CMD_ARGS)  # unreachable?
        if(error_code == ERROR_CODE_START_ERROR):
            ExceptionUtils.error_message("Error when starting SPPCheck. Please review the errors above")
            sys.exit(ERROR_CODE_START_ERROR)

        script_end_time = SppUtils.get_actual_time_sec()
        LOGGER.debug("Script end time: %d", script_end_time)

        try:
            self.store_script_metrics()

            if(self.__influx_client):
                self.__influx_client.disconnect()

        except ValueError as error:
            ExceptionUtils.exception_info(error=error, extra_message="Error occurred while exiting SPPCheck")
            error_code = ERROR_CODE

        SppUtils.remove_pid_file(self.pid_file_path, ARGS)

        # Both error-clauses are actually the same, but for possibility of an split between error cases
        # always last due being true for any number != 0
        if error_code == ERROR_CODE or error_code:
            ExceptionUtils.error_message("\n\n!!! Error occurred while executing SPPCheck, aborting the functionality. !!!\n")
        elif ExceptionUtils.stored_errors:
            print(f"\n\n!!! Script completed. Total of {len(ExceptionUtils.stored_errors)} errors occurred during the execution. Check Messages above. !!!\n")
        else:
            LOGGER.info("\n\n!!! Script completed without any errors !!!\n")

        print(f"Check log for details: grep \"PID {os.getpid()}\" {self.log_path} > sppcheck.log.{os.getpid()}")
        sys.exit(error_code)

    def main(self):
        LOGGER.info("Starting argument execution")

        excel_rp = None
        if bool(ARGS.sheetPath):
            LOGGER.info("Starting the Excel Reader module")
            try:
                excel_reader = ExcelController(
                    ARGS.sheetPath, ARGS.sizerVersion,
                    self.__influx_client, self.start_date,
                    self.__dp_interval_hour,
                    self.__rp_timestamp)
                excel_rp = excel_reader.report_rp
                excel_reader.parse_insert_sheet()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="CRITICAL: Top-level-error when reading and inserting the excel sheet data.")

        if ARGS.genFakeData:
            LOGGER.info("Starting the FakeData module")
            try:
                fakedata_controller = FakeDataController(
                    self.__influx_client, self.__dp_interval_hour,
                    self.__datagen_range_days, self.__fakedata_rp_name)
                fakedata_controller.gen_fake_data()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="CRITICAL: Top-level-error when reading the generating storage data.")

        prediction_rp = None
        if self.__predict_years:
            LOGGER.info(f"Starting the Prediction module to predict the next {self.__predict_years} years.")
            try:
                predictor_controller = PredictorController(
                    self.__influx_client, self.__dp_interval_hour,
                    self.__select_rp, self.__rp_timestamp,
                    self.__predict_years, self.start_date)
                prediction_rp = predictor_controller.report_rp
                predictor_controller.predict_all_data()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="CRITICAL: Top-level-error when creating predicting Data")

        if ARGS.pdfReport:
            LOGGER.info("Starting the PDF-Report module")
            try:
                report_controller = ReportController(
                    self.__influx_client,
                    self.__select_rp,
                    self.start_date,
                    self.config_file,
                    self.__predict_years,
                    prediction_rp,
                    excel_rp,
                    self.__theme
                    )
                report_controller.createPdfReport()
            except Exception as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message="CRITICAL: Top-level-error when creating PDF report")


        LOGGER.info("Finished all argument executions, starting to exit the program.")

        self.exit()


if __name__ == "__main__":
    SPPCheck().main()
