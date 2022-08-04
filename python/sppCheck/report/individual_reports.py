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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sppCheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from sppCheck.report.comparer import (Comparer, ComparisonPoints,
                                      ComparisonSource)
from sppCheck.report.picture_downloader import PictureDownloader

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

OverviewDataStruct = List[
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
    ]
"""
Tuple[
    str: description of the metric,
    bool: True = positive values are good, False = positive values are bad,
    Dict:  data of the metric
        ComparisonPoints: different time points to compare, columns of the table
        Optional: if the collection failed, it is none
            Tuple
                int: timestamp
                int: time diff between both timestamps in seconds
                int|float: value difference between the points
                int: percent of metric one to metric two (90 to 75 -> 78%)
]]]]]
"""

class IndividualReports:

    @property
    def overview_used_data(self):
        return self.__overview_used_data

    @property
    def overview_setup_data(self):
        return self.__overview_setup_data

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
        self.__overview_used_data: OverviewDataStruct = []

        # filled during the individual reports, to be used for overview table
        self.__overview_setup_data: OverviewDataStruct = []

    def __report_structure(self,
                            report_name: str,

                            full_graph_filename: Optional[Path] = None,
                            full_graph_width: int = 0,
                            full_graph_height: int = 0,
                            full_graph_description: str = "",

                            one_year_used_filename: Optional[Path] = None,
                            one_year_used_width: int = 0,
                            one_year_used_height: int = 0,
                            one_year_used_with_reserve: bool = False,
                            one_year_used_description: str = "",

                            full_excel_filename: Optional[Path] = None,
                            full_excel_width: int = 0,
                            full_excel_height: int = 0,
                            full_excel_description: str = ""):

        # easier change if all needs to be changed
        value_meaning_header = "<h5> Value meaning </h5>"
        panel_description_header = "<h5> Panel description </h5>"

        # different text for reserve in graph and missing it
        value_description_graph_w_reserve = f"""
The <span style="color:red">red line</span> represents the recommended space with reserve, with the <span style="color:orange">orange line</span> omits the reserve. <br />
This is the space required according to the Blueprint vSnap Sizer sheets for the system to last until this day. <br />
If the <span style="color:blue">blue line</span> is below these lines, the system is developing <span style="color:green">slower</span> than anticipated. <br />
If it is between these lines, it is developing just as expected. <br />
However, if the <span style="color:blue">blue line</span> is above the <span style="color:red">red line</span>, the system is developing <span style="color:red">quicker</span> than anticipated. <br />
"""
        value_description_graph = f"""
The <span style="color:orange">orange line</span> represents the recommended space. <br />
This is the space recommended according to the Blueprint vSnap Sizer sheets for the system to last until this day. <br />
If the <span style="color:blue">blue line</span> is below this line, the system is developing <span style="color:green">slower</span> than anticipated. <br />
However, if the <span style="color:blue">blue line</span> is above the <span style="color:orange">orange line</span>, the system is developing <span style="color:red">quicker</span> than anticipated. <br />
"""

        structure = f"""
<h3> {report_name} </h3>
"""
        if full_graph_filename:
            structure += f"""
<h4> Full Life-Cycle Overview </h4>
<img src="{full_graph_filename}" alt="{full_graph_filename}" width="{full_graph_width}" height="{full_graph_height}">
{panel_description_header}
<p>
    {full_graph_description}
</p>
{value_meaning_header}
<p>
    The <span style="color:purple">purple line</span> represents the currently available space, while the <span style="color:blue">blue line</span> represents the used space. <br />
    Therefore, the point where the <span style="color:red">lines cross</span> is the date where the system will <span style="color:red">fail</span>. <br />
    This assumes that the available space is not increased any further, since this is a manual interaction. <br />
    The point of failure can be delayed by increasing the available space. <br />
    However, if the lines never cross, the space can be reduced accordingly. <br />
    <br />
    {value_description_graph_w_reserve if one_year_used_with_reserve else value_description_graph}
</p>
"""
        if one_year_used_filename:
            structure += f"""
<h4> One-Year Summary </h4>
<img src="{one_year_used_filename}" alt="{one_year_used_filename}" width="{one_year_used_width}" height="{one_year_used_height}">
{panel_description_header}
<p>
    {one_year_used_description}
</p>

{value_meaning_header}
<p>
    A <span style="color:green"> positive value </span> means that space is still <span style="color:green">free</span> after one year. <br />
    A <span style="color:red">negative value</span> indicates the expected minimum value by which the <span style="color:red">capacity must be upgraded</span>. <br />
    The percent values are displayed to allow an impression of the value to total ratio. <br />
</p>
"""
        if full_excel_filename:
            structure += f"""
<h4> Setup-Check </h4>
<img src="{full_excel_filename}" alt="{full_excel_filename}" width="{full_excel_width}" height="{full_excel_height}">
{panel_description_header}
<p>
    {full_excel_description}
</p>

{value_meaning_header}
<p>
    A <span style="color:green">positive value</span> means the system was set up with <span style="color:green">more space than recommended</span> by the Sizer sheet. <br />
    A <span style="color:red">negative value</span> indicates the <span style="color:red">difference required</span> to reach the recommended size of the Sizer sheets. <br />
    <br />
    Even if this Panels shows a negative value, the system can run correctly - it is just designed smaller than initial anticipated. <br />
    However, this also works the other way around:  <br />
    A correct setup does not promise that the system will last the whole anticipated life-cycle.  <br />
    Please check the used-data panels for such a forecast. <br />
</p>
"""
        return structure

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
        self.overview_used_data.append( ("used storage space", True, avail_vs_used_result))

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
        self.overview_setup_data.append( ("existing vs. required storage space", False, excel_vs_existing_result))

        # download full scale view
        excel_vs_existing_storage_full_width = 1000
        excel_vs_existing_storage_full_height = 500
        excel_vs_existing_storage_full = self.__picture_downloader.download_picture(
            panelId=226,
            width=excel_vs_existing_storage_full_width,
            height=excel_vs_existing_storage_full_height,
            file_name="excel_vs_existing_storage_full")

        return self.__report_structure(
            report_name="Storage Report",
            full_graph_filename = avail_vs_used_storage_lines_full,
            full_graph_width = avail_vs_used_storage_lines_full_width,
            full_graph_height =avail_vs_used_storage_lines_full_height,
            full_graph_description = f"""
This report shows the development of the <span style="color:blue">used</span>, <span style="color:purple">available</span> and expected Storage space <span style="color:red">with</span> and <span style="color:orange">without reserve</span>. <br />
A prediction function is used to forecast the values after the current date ({date.today().isoformat()}). <br/>
The Graphs display the full life cycle of {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}. <br />
""",

            one_year_used_filename = avail_vs_used_storage_one_year,
            one_year_used_width = avail_vs_used_storage_one_year_width,
            one_year_used_height = avail_vs_used_storage_one_year_height,
            one_year_used_with_reserve=True,
            one_year_used_description = f"""
This report shows the expected free Storage space. <br />
The value is calculated of the prediction for the next year. <br />
The Graphs display the range of now - 1 to now + 1 year. <br />
""",

            full_excel_filename = excel_vs_existing_storage_full,
            full_excel_width = excel_vs_existing_storage_full_width,
            full_excel_height = excel_vs_existing_storage_full_height,
            full_excel_description = f"""
This report shows the current total existing Storage space, compared to the required space according to the Blueprint vSnap Sizer sheets. <br />
The value is calculated of the prediction at the end of the expected lifetime. <br />
The Graphs display the full life cycle of {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}. <br />
"""
        )


    def create_server_memory_report(self):
        LOGGER.info(">> Creating the server memory report.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_memory",
            base_table=ComparisonSource.PREDICTION,

            comp_metric_name="used_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_used_data.append( ("used server memory", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_memory",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_setup_data.append( ("existing vs. required server memory", False, excel_vs_existing_result))

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
        self.overview_setup_data.append( ("existing vs. required vSnaps", False, excel_vs_avail_result))

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
        self.overview_setup_data.append( ("existing vs. required VADPs", False, excel_vs_avail_result))

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
        self.overview_used_data.append( ("used server configuration catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Configuration",
        )
        self.overview_setup_data.append( ("existing vs. required server configuration catalog space", False, excel_vs_existing_result))

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
        self.overview_used_data.append( ("used server recovery catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Recovery",
        )
        self.overview_setup_data.append( ("existing vs. required server recovery catalog space", False, excel_vs_existing_result))

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
        self.overview_used_data.append( ("used server system catalog space", True, avail_vs_used_result))

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
        self.overview_used_data.append( ("used server file catalog space", True, avail_vs_used_result))

        return ""
