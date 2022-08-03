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

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sppCheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from sppCheck.report.comparer import (Comparer, ComparisonPoints,
                                      ComparisonSource)
from sppCheck.report.picture_downloader import PictureDownloader

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class IndividualReports:

    @property
    def overview_table_data(self):
        return self.__overview_table_data

    def __init__(
        self,
        comparer: Comparer,
        picture_downloader: PictureDownloader,
        start_date: datetime,
        end_date: datetime):

        self.__start_date = start_date
        self.__end_date = end_date
        self.__comparer = comparer
        self.__picture_downloader = picture_downloader

        # filled during the individual reports, to be used for overview table
        self.__overview_table_data: List[
            Tuple[
                str, # description of the metric
                bool, # True = positive values are good, False = positive values are bad
                Dict[ # data of the metric
                    ComparisonPoints, # different time points to compare, columns of the table
                    Optional[   # if the collection failed, it is none
                        Tuple[
                            int,        # timestamp
                            int,        # time diff between both timestamps in seconds
                            int|float,  # value difference between the points
                            int         # percent of metric one to metric two (90 to 75 -> 78%)
                            ]]]
            ]
        ] = []



    def create_storage_report(self):
        LOGGER.info(">> Creating the storage report.")
        # compare used vs available space
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="physical_pool_size",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,

            comp_metric_name="physical_capacity",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag= PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_table_data.append( ("available vs used storage data", True, avail_vs_used_result))

        # download full scale view with lines
        avail_vs_used_storage_lines_full_width = 1000
        avail_vs_used_storage_lines_full_height = 500
        avail_vs_used_storage_lines_full = self.__picture_downloader.download_picture(
            panelId=220,
            width=avail_vs_used_storage_lines_full_width,
            height=avail_vs_used_storage_lines_full_height,
            file_name="available_vs_used_storage_lines_full")

        # download small scale view free and used %
        avail_vs_used_storage_one_year_width = 1000
        avail_vs_used_storage_one_year_height = 500
        avail_vs_used_storage_one_year = self.__picture_downloader.download_picture(
            panelId=210,
            width=avail_vs_used_storage_one_year_width,
            height=avail_vs_used_storage_one_year_height,
            file_name="available_vs_used_storage_one_year",
            relative_from_years=1,
            relative_to_years=1)

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vsnap_size_est_w_reserve",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="physical_pool_size",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_table_data.append( ("required vs existing storage data", False, excel_vs_existing_result))

        # download full scale view
        excel_vs_existing_storage_full_width = 1000
        excel_vs_existing_storage_full_height = 500
        excel_vs_existing_storage_full = self.__picture_downloader.download_picture(
            panelId=226,
            width=excel_vs_existing_storage_full_width,
            height=excel_vs_existing_storage_full_height,
            file_name="excel_vs_existing_storage_full")


        return f"""
<h3> Storage Report </h3>
<img src="{avail_vs_used_storage_one_year}" alt="available_vs_used_storage_one_year" width="{avail_vs_used_storage_one_year_width}" height="{avail_vs_used_storage_one_year_height}">
<h4> Panel description </h4>
<p>
    This report shows the expected free Storage space. <br />
    The value is calculated of the prediction for one year. <br />
    The Graphs display the range of now - 1 to now + 1 year. <br />
</p>
<h4> Value meaning </h4>
<p>
    A positive value means that free space is still available at the point of the prediction. <br />
    A negative value displays the minimum anticipated value required of extension of the storage capacity. <br />
    The percent values are displayed to allow an impression of the value to total ratio. <br />
</p>

<img src="{avail_vs_used_storage_lines_full}" alt="avail_vs_used_storage_lines_full" width="{avail_vs_used_storage_lines_full_width}" height="{avail_vs_used_storage_lines_full_height}">
<h4> Panel description </h4>
<p>
    This report shows the development of the used (blue), available (purple) and expected Storage space with (red) and without reserve (yellow). <br />
    A prediction function is used to forecast the values after the current date ({date.today().isoformat()}). <br/>
    The Graphs display the full life cycle of {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}. <br />
</p>
<h4> Value meaning </h4>
<p>
    A positive value means that free space is still available at the point of the prediction. <br />
    A negative value displays the minimum anticipated value required of extension of the storage capacity. <br />
    The percent values are displayed to allow an impression of the value to total ratio. <br />
</p>

<img src="{excel_vs_existing_storage_full}" alt="excel_vs_existing_storage_full" width="{excel_vs_existing_storage_full_width}" height="{excel_vs_existing_storage_full_height}">
<h4> Panel description </h4>
<p>
    This report shows the current total existing Storage space, compared to the required space according to the Blueprint vSnap Sizer sheets. <br />
    The value is calculated of the prediction at the end of the expected lifetime. <br />
    The Graphs display the full life cycle of {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}. <br />
</p>
<h4> Value meaning </h4>
<p>
    A positive value means the system was set up with more space then required by the Sizer sheet. <br />
    A negative value displays the difference required to reach the anticipated size. <br />
</p>
"""

    def create_server_memory_report(self):
        LOGGER.info(">> Creating the server memory report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_memory",
            base_table=ComparisonSource.PREDICTION,

            comp_metric_name="used_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_table_data.append( ("available vs used server memory", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_memory",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_table_data.append( ("required vs existing server memory", False, excel_vs_existing_result))

        return ""

    def create_vsnap_count_report(self):
        LOGGER.info(">> Creating the vSnap count report.")

        excel_vs_avail_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vsnap_count",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="vsnap_count",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_table_data.append( ("required vs existing vSnaps", False, excel_vs_avail_result))

        return ""

    def create_vadp_count_report(self):
        LOGGER.info(">> Creating the VADP count report.")

        excel_vs_avail_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vadp_count_total",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="vadp_count_total",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_table_data.append( ("required vs existing VADPs", False, excel_vs_avail_result))

        return ""

    def create_server_catalog_config_report(self):
        LOGGER.info(">> Creating the server configuration catalog report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="Configuration",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Configuration",
        )
        self.overview_table_data.append( ("available vs used server configuration catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Configuration",
        )
        self.overview_table_data.append( ("required vs existing server configuration catalog space", False, excel_vs_existing_result))

        return ""

    def create_server_recovery_config_report(self):
        LOGGER.info(">> Creating the server recovery catalog report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="Recovery",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Recovery",
        )
        self.overview_table_data.append( ("available vs used server recovery catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Recovery",
        )
        self.overview_table_data.append( ("required vs existing server recovery catalog space", False, excel_vs_existing_result))

        return ""

    def create_server_system_config_report(self):
        LOGGER.info(">> Creating the server system catalog report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="System",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="System",
        )
        self.overview_table_data.append( ("available vs used server system catalog space", True, avail_vs_used_result))

        return ""

    def create_server_file_config_report(self):
        LOGGER.info(">> Creating the server file catalog report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="File",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="File",
        )
        self.overview_table_data.append( ("available vs used server file catalog space", True, avail_vs_used_result))

        return ""
