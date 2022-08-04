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

import inspect
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dateutil.relativedelta import relativedelta
from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from sppCheck.excel.excel_controller import ExcelController
from sppCheck.predictor.predictor_controller import PredictorController
from sppCheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from sppCheck.report.comparer import Comparer
from sppCheck.report.individual_reports import IndividualReports, OverviewDataStruct
from sppCheck.report.table_creator import TableCreator
from sppCheck.report.picture_downloader import PictureDownloader
from utils.sppcheck_utils import SppcheckUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class ReportController:

    def __init__(
        self,
        influx_client: InfluxClient,
        select_rp: RetentionPolicy,
        start_date: datetime,
        config_file: Dict[str, Any],
        predict_years: Optional[int],
        prediction_rp: Optional[RetentionPolicy],
        excel_rp: Optional[RetentionPolicy]) -> None:
        if not influx_client:
            raise ValueError("Logic Tool is not available, missing the influx_client")

        self.__system_name = influx_client.database.name

        if not prediction_rp:
            prediction_rp = SppcheckUtils.choose_latest_rp(influx_client, PredictorController.rp_prefix)

        if not excel_rp:
            excel_rp = SppcheckUtils.choose_latest_rp(influx_client, ExcelController.rp_prefix)

        if predict_years is None:
            self.__end_date = SppcheckUtils.choose_latest_data(influx_client, PredictorInfluxConnector.sppcheck_table_name, prediction_rp)
        else:
            self.__end_date = datetime.now() + relativedelta(years=predict_years)
        LOGGER.debug(f"end_date: {self.__end_date}")

        self.__start_date = start_date

        self.__temp_file_path = Path("sppcheck", "report", "temp_files", "report.html")
        LOGGER.debug(f"relative temp file path: {self.__temp_file_path}")
        self.__rel_spp_icon_path = Path("..", "SpectrumProtectPlus-dark.svg")
        LOGGER.debug(f"relative spp icon file path: {self.__rel_spp_icon_path}")

        picture_downloader = PictureDownloader(
            influx_client,
            select_rp, start_date,
            config_file,
            self.__end_date,
            prediction_rp, excel_rp)

        comparer = Comparer(
            influx_client,
            select_rp,
            start_date,
            self.__end_date,
            prediction_rp,
            excel_rp
        )

        self.__individual_reports = IndividualReports(
            comparer,
            picture_downloader,
            start_date,
            self.__end_date
        )

        self.__table_creator = TableCreator(
            start_date,
            self.__end_date
        )


    def __create_overview_table(self):

        LOGGER.info("> Starting to create an overview table")

        table_report = self.__table_creator.create_overview_table(
            self.__individual_reports.overview_used_data,
            self.__individual_reports.overview_setup_data
        )

        LOGGER.info("> Finished creating an overview table")
        return table_report

    def __create_individual_reports(self):

        LOGGER.info("> Starting to create reports for each metric")

        # this functionality is based that the module only contains create methods
        # otherwise you can also filter by the prefix "create"
        # originally: add all methods to a list to get executed -> annoying when forgetting to add
        full_individual_report_str = ""
        method_list_tuple = inspect.getmembers(self.__individual_reports, predicate=inspect.ismethod)

        for (method_name, method) in method_list_tuple:
            # skip out private methods and init method -> single underscore, not double
            if method_name.startswith("_"):
                continue

            LOGGER.debug(f">> executing function {method_name}")
            individual_report = method()
            if individual_report: # only add if there is actually content, otherwise empty pages are added.
                full_individual_report_str += f"""
<div style="page-break-after: always;">
 {individual_report}
</div>
"""

        LOGGER.info("> Finished creating reports for each metric")

        return full_individual_report_str

    def __gen_pdf_file(self, individual_reports: str, overview_table: str):

        LOGGER.info("> Starting to generate the temporary HTML-File.")

        total_report = f"""
<!DOCTYPE html>
<html>
<body>

<div>
    <h1><img width="40" height="40" src="{self.__rel_spp_icon_path}"/> SPPCheck Report for SPP-System "{self.__system_name}"</h1>
    <p>Created on {datetime.now().isoformat(timespec="seconds")}</p>
</div>
<div style="page-break-after: always;">
    <h2> Overview over all Metrics </h2>
    {overview_table}
</div>
<div>
    <h2> Individual Reports </h2>
    {individual_reports}
</div>

</body>
</html>
"""

        with open(self.__temp_file_path, 'wt') as file:
            file.write(total_report)

        LOGGER.info("> Finished generating the temporary HTML file.")
        pass

    def createPdfReport(self):

        individual_reports = self.__create_individual_reports()

        overview_table = self.__create_overview_table()

        self.__gen_pdf_file(individual_reports, overview_table)
