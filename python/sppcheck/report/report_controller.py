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

from datetime import datetime
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

        if not prediction_rp or not excel_rp:
            raise ValueError("Automatic selection of the latest prediction or excel retention policy not supported yet. \n" +\
                             "Please only generate the Report in conjunction with the other SPPCheck functionalities")

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
        self.__create_storage_report()
        pass

    def __create_storage_report(self):
        # compare used vs available space
        available_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="physical_pool_size",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,

            comp_metric_name="physical_capacity",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag= PredictorInfluxConnector.sppcheck_total_group_value,
        )
        # download full scale view
        available_vs_used_storage_full = self.__picture_generator.download_picture(
            210, 1000, 500,
            "available_vs_used_storage_full")
        # download small scale view
        available_vs_used_storage_one_year = self.__picture_generator.download_picture(
            210, 1000, 500,
            "available_vs_used_storage_one_year",
            relative_from_years=1,
           relative_to_years=1)

        excel_vs_available_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vsnap_size_est_w_reserve",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="physical_pool_size",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag= PredictorInfluxConnector.sppcheck_total_group_value,
        )
        # download full scale view
        excel_vs_available_storage_full = self.__picture_generator.download_picture(
            226, 1000, 500,
            "excel_vs_available_storage_full")


        pass



    def __gen_pdf_file(self):
        pass

    def createPdfReport(self):

        individual_reports = self.__create_individual_reports()

        overview_table = self.__create_overview_table()

        self.__gen_pdf_file()
