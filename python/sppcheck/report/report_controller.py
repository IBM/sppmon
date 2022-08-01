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

from ast import Compare
from datetime import datetime
from pathlib import Path
from os.path import exists, isfile
from typing import Dict, Any, Optional

from influx.database_tables import RetentionPolicy

from influx.influx_client import InfluxClient
from sppCheck.predictor.predictor_influx_connector import PredictorInfluxConnector
from sppCheck.report.picture_downloader import PictureDownloader
from sppCheck.report.comparer import Comparer, ComparisonSource

class ReportController:

    def __init__(
        self,
        influx_client: InfluxClient,
        dp_interval_hour: int,
        select_rp: RetentionPolicy,
        rp_timestamp: str,
        start_date: datetime,
        config_file: Dict[str, Any],
        predict_years: int,
        prediction_rp: Optional[RetentionPolicy],
        excel_rp: Optional[RetentionPolicy]) -> None:
        if not influx_client:
            raise ValueError("Logic Tool is not available, missing the influx_client")

        self.__influx_client: InfluxClient = influx_client

        self.__picture_generator = PictureDownloader(
            influx_client,
            select_rp, start_date,
            config_file,
            5,#predict_years,
            prediction_rp, excel_rp)

        self.__comparer = Comparer(
            influx_client,
            dp_interval_hour,
            select_rp,
            rp_timestamp,
            start_date,
            config_file,
            predict_years,
            prediction_rp,
            excel_rp
        )


    def __create_overview_table(self):
        pass

    def __create_individual_reports(self):

        result = self.__comparer.compare_metrics(
            base_metric_name="physical_capacity",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag= PredictorInfluxConnector.sppcheck_total_group_value,

            comp_metric_name="physical_pool_size",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value
        )
        used_vs_available_storage = self.__picture_generator.download_picture(210, 1000, 500, "used_vs_available_storage")

        #    Comparer.START,
        #    "physical_capacity",
        #    "vsnap_size_est_physical_subtotal",
        #    "Total"
        #    )
        pass



        # download total storage prediction
        #total_storage = self.__picture_generator.download_picture(183, 1000, 500, "total_storage")


    def __gen_pdf_file(self):
        pass

    def createPdfReport(self):

        individual_reports = self.__create_individual_reports()

        overview_table = self.__create_overview_table()

        self.__gen_pdf_file()
