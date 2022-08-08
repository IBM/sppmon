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
from typing import ClassVar, Dict, List, Optional, Tuple

from sppCheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from sppCheck.report.comparer import (Comparer, ComparisonPoints,
                                      ComparisonSource)
from sppCheck.report.picture_downloader import PictureDownloader

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

OverviewDataStruct = List[
        Tuple[
            str, # id/name of the metric for reference purposes
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
    str: id/name of the metric for reference purposes
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

    # easier change if all needs to be changed
    value_meaning_header: ClassVar[str] = "<h5> Value meaning </h5>"
    panel_description_header: ClassVar[str] = "<h5> Panel description </h5>"

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

        # used to switch between sections back and forth
        self.__swap_section = False

        self.__start_date = start_date
        self.__end_date = end_date
        self.__comparer = comparer
        self.__picture_downloader = picture_downloader

        # filled during the individual reports, to be used for overview table
        self.__overview_used_data: OverviewDataStruct = []

        # filled during the individual reports, to be used for overview table
        self.__overview_setup_data: OverviewDataStruct = []

    def __report_structure_regular(self,
                            report_name: str,

                            full_graph_panel_id: Optional[int] = None,
                            full_graph_width: int = 1000,
                            full_graph_height: int = 500,
                            full_graph_with_reserve: bool = False,
                            full_graph_description: str = "",

                            one_year_used_panel_id: Optional[int] = None,
                            one_year_used_width: int = 3000,
                            one_year_used_height: int = 1500,
                            one_year_used_description: str = "",

                            full_excel_panel_id: Optional[int] = None,
                            full_excel_width: int = 3000,
                            full_excel_height: int = 1500,
                            full_excel_description: str = ""):

        #### prepare data: download pictures ####
        if full_graph_panel_id:
            full_graph_filename = self.__picture_downloader.download_picture(
                panel_id=full_graph_panel_id,
                width=full_graph_width,
                height=full_graph_height,
                file_name=report_name + "_full_graph")
        else:
            full_graph_filename = None

        if one_year_used_panel_id:
            one_year_used_filename = self.__picture_downloader.download_picture(
                panel_id=one_year_used_panel_id,
                width=one_year_used_width,
                height=one_year_used_height,
                relative_from_years=1,
                relative_to_years=1,
                file_name=report_name + "_one_year_used")
        else:
            one_year_used_filename = None

        if full_excel_panel_id:
            full_excel_filename = self.__picture_downloader.download_picture(
                panel_id=full_excel_panel_id,
                width=full_excel_width,
                height=full_excel_height,
                file_name=report_name + "_full_excel")
        else:
            full_excel_filename = None

        #### Prepare template text ####

        # different text for reserve in graph and missing it
        value_description_graph_w_reserve = f"""
The <span style="color:red">red line</span> represents the recommended space with reserve, with the <span style="color:orange">orange line</span> omits the reserve. <br />
This is the space recommended according to the Blueprint vSnap Sizer sheets for the system to last until this day. <br />
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

        #### Prepare section swapping ####
        if self.__swap_section:
            section_class = "middle_section_a"
        else:
            section_class = "middle_section_b"
        self.__swap_section = not self.__swap_section

        subsection_swap = True
        subsection_class_a = "inner_section_a"
        subsection_class_b = "inner_section_b"
        # set on first call
        current_subsection = ""

        #### Build the structure ####

        structure = f"""
<div class="{section_class}">
<h3 id="{report_name}"> {report_name} </h3>
"""
        if full_graph_filename:
            # swapping background color
            if subsection_swap:
                current_subsection = subsection_class_a
            else:
                current_subsection = subsection_class_b
            subsection_swap = not subsection_swap

            structure += f"""
<div class="{current_subsection}">
<h4> Full Life-Cycle Overview </h4>
<img class="my_img individual_report_img" src="{full_graph_filename}" alt="{full_graph_filename}">
{self.panel_description_header}
<p>
    {full_graph_description}
</p>
{self.value_meaning_header}
<p>
    The <span style="color:purple">purple line</span> represents the <span style="color:purple">currently available</span> space, while the <span style="color:blue">blue line</span> represents the <span style="color:blue">used</span> space. <br />
    Therefore, the point where the <span style="color:red">lines cross</span> is the date where the system will <span style="color:red">fail</span>. <br />
    This assumes that the available space is not increased any further, since this requires a manual interaction. <br />
    The point of failure can be delayed by increasing the available space. <br />
    However, if the lines never cross, the space can be reduced accordingly. <br />
    A prediction function is used to forecast the trend for the systems remaining life cycle after the current date ({date.today().isoformat()}). <br/>
    <br />
    {value_description_graph_w_reserve if full_graph_with_reserve else value_description_graph}
</p>
</div>
"""
        if one_year_used_filename:

            # swapping background color
            if subsection_swap:
                current_subsection = subsection_class_a
            else:
                current_subsection = subsection_class_b
            subsection_swap = not subsection_swap

            structure += f"""
<div class="{current_subsection}">
<h4> One-Year Summary </h4>
<img class="my_img individual_report_img" src="{one_year_used_filename}" alt="{one_year_used_filename}">
{self.panel_description_header}
<p>
    {one_year_used_description}
</p>

{self.value_meaning_header}
<p>
    A <span style="color:green"> positive value </span> means that space is still <span style="color:green">free</span> after one year. <br />
    A <span style="color:red">negative value</span> indicates the expected minimum value by which the <span style="color:red">capacity must be upgraded</span>. <br />
    The percent values are displayed to allow an impression of the value to total ratio. <br />
</p>
</div>
"""
        if full_excel_filename:

            # swapping background color
            if subsection_swap:
                current_subsection = subsection_class_a
            else:
                current_subsection = subsection_class_b
            subsection_swap = not subsection_swap

            structure += f"""
<div class="{current_subsection}">
<h4> Setup-Check </h4>
<img class="my_img individual_report_img" src="{full_excel_filename}" alt="{full_excel_filename}">
{self.panel_description_header}
<p>
    {full_excel_description}
</p>

{self.value_meaning_header}
<p>
    A <span style="color:green">positive value</span> means the system was set up with <span style="color:green">more space than recommended</span> by the Sizer sheet. <br />
    A <span style="color:red">negative value</span> indicates the <span style="color:red">difference required</span> to reach the recommended size of the Sizer sheets. <br />
    <br />
    Even if this Panels shows a negative value, the system can run correctly - it is just designed smaller than initial anticipated. <br />
    However, this also works the other way around:  <br />
    A correct setup does not promise that the system will last the whole anticipated life-cycle.  <br />
    Please check the used-data panels for such a forecast. <br />
</p>
</div>
"""
        # close the section div
        structure +=f"""
</div>"""
        return structure


    def __report_structure_count(self,
                            report_name: str,

                            full_graph_panel_id: Optional[int] = None,
                            full_graph_width: int = 3000,
                            full_graph_height: int = 1500,
                            full_graph_description: str = "",

                            one_year_existing_panel_id: Optional[int] = None,
                            one_year_existing_width: int = 3000,
                            one_year_existing_height: int = 1500,
                            one_year_existing_description: str = ""
                            ):
        # this method only takes two metrics with different texts

        #### prepare data: download pictures ####
        if full_graph_panel_id:
            full_graph_filename = self.__picture_downloader.download_picture(
                panel_id=full_graph_panel_id,
                width=full_graph_width,
                height=full_graph_height,
                file_name=report_name + "_full_graph")
        else:
            full_graph_filename = None

        if one_year_existing_panel_id:
            one_year_existing_filename = self.__picture_downloader.download_picture(
                panel_id=one_year_existing_panel_id,
                width=one_year_existing_width,
                height=one_year_existing_height,
                relative_from_years=1,
                relative_to_years=1,
                file_name=report_name + "_one_year_existing")
        else:
            one_year_existing_filename = None

        #### Prepare template text ####

        #### Prepare section swapping ####
        if self.__swap_section:
            section_class = "middle_section_a"
        else:
            section_class = "middle_section_b"
        self.__swap_section = not self.__swap_section

        subsection_swap = True
        subsection_class_a = "inner_section_a"
        subsection_class_b = "inner_section_b"
        # set on first call
        current_subsection = ""

        #### Build the structure ####

        structure = f"""
<div class="{section_class}">
<h3 id="{report_name}"> {report_name} </h3>
"""
        if full_graph_filename:

            # swapping background color
            if subsection_swap:
                current_subsection = subsection_class_a
            else:
                current_subsection = subsection_class_b
            subsection_swap = not subsection_swap

            structure += f"""
<div class="{current_subsection}">
<h4> Full Life-Cycle Overview </h4>
<img class="my_img individual_report_img" src="{full_graph_filename}" alt="{full_graph_filename}">
{self.panel_description_header}
<p>
    {full_graph_description}
</p>
{self.value_meaning_header}
<p>
    The <span style="color:blue">blue line</span> represents the <span style="color:blue">currently existing</span> systems.
    The <span style="color:orange">orange line</span> represents the recommended count of systems. <br />
    This is the count recommended according to the Blueprint vSnap Sizer sheets for the SPP-System to last until its end of life cycle. <br />
    If the <span style="color:blue">blue line</span> is below this line, the system has <span style="color:red">too few Systems</span> set up than recommended. <br />
    However, if the <span style="color:blue">blue line</span> is above the <span style="color:orange">orange line</span>, the system <span style="color:green">more Systems</span> set up than recommend. <br />
    After the current date a static count of the currently existing Systems is assumed ({date.today().isoformat()}). <br/>
</p>
</div>
"""
        if one_year_existing_filename:

            # swapping background color
            if subsection_swap:
                current_subsection = subsection_class_a
            else:
                current_subsection = subsection_class_b
            subsection_swap = not subsection_swap

            structure += f"""
<div class="{current_subsection}">
<h4> One-Year Summary </h4>
<img class="my_img individual_report_img" src="{one_year_existing_filename}" alt="{one_year_existing_filename}">
{self.panel_description_header}
<p>
    {one_year_existing_description}
</p>

{self.value_meaning_header}
<p>
    The "Existing" count is always green. <br/>
    Colored distinctions are only made based on the "Setup Check Difference".
    A <span style="color:green"> positive value </span> means that <span style="color:green">more Systems</span> than recommended are set up after one year. <br />
    A <span style="color:red">negative value</span> indicates the recommend minimum value how many more Systems <span style="color:red">need to be added</span>. <br />
    After the current date a static count of the currently existing Systems is assumed ({date.today().isoformat()}). <br/>
</p>
</div>
"""
        # close the section div
        structure +=f"""
</div>"""

        return structure


    def create_storage_report(self):
        report_name="Storage Report"

        LOGGER.info(f">> Creating the {report_name}.")

        # compare used vs available space
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="physical_pool_size",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,

            comp_metric_name="physical_capacity",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag= PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_used_data.append( (report_name, "used storage space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vsnap_size_est_w_reserve",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="physical_pool_size",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_setup_data.append( (report_name, "existing vs. recommended storage space", False, excel_vs_existing_result))

        return self.__report_structure_regular(
            report_name="Storage Report",
            full_graph_panel_id=220,
            full_graph_with_reserve=True, # this is the only metric using a reserve-excel-metric
            full_graph_description = f"""
This report shows the development of the <span style="color:blue">used</span>, <span style="color:purple">available</span> and recommended Storage space <span style="color:red">with</span> and <span style="color:orange">without reserve</span>. <br />
For this prediction, the values of all individual vSnaps are summarized into a single statistic. <br/>
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
""",

            one_year_used_panel_id=210,
            one_year_used_description = f"""
This report shows the anticipated free Storage space and the expected usage percentage relative to the available space. <br />
All values are taken from the prediction graph, limited to the following year.  <br />
The Graphs display the range from now - 1 to now + 1 year. <br />
""",

            full_excel_panel_id=226,
            full_excel_description = f"""
This report shows the total currently existing Storage space relative to the recommended space according to the Blueprint vSnap Sizer sheets at the end of the system lifetime. <br />
All values are taken from the prediction graph of the system's entire life cycle. <br />
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
"""
        )


    def create_server_memory_report(self):
        report_name="Server Memory Report"

        LOGGER.info(f">> Creating the {report_name}.")

        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_memory",
            base_table=ComparisonSource.PREDICTION,

            comp_metric_name="used_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_used_data.append( (report_name, "used server memory", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_memory",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_memory",
            comp_table=ComparisonSource.PREDICTION,
        )
        self.overview_setup_data.append( (report_name, "existing vs. recommended server memory", False, excel_vs_existing_result))

        return self.__report_structure_regular(
            report_name=report_name,
            full_graph_panel_id=196,

            full_graph_with_reserve=False,
            full_graph_description = f"""
This report shows the development of the <span style="color:blue">used</span>, <span style="color:purple">available</span> and <span style="color:orange">recommended</span> Server Memory. <br />
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
""",

            one_year_used_panel_id=211,
            one_year_used_description = f"""
This report shows the anticipated free Server Memory and the expected usage percentage relative to the available memory. <br />
All values are taken from the prediction graph, limited to the following year.  <br />
The Graphs display the range from now - 1 to now + 1 year. <br />
""",

            full_excel_panel_id=227,
            full_excel_description = f"""
This report shows the currently existing Server Memory relative to the recommended Memory according to the Blueprint vSnap Sizer sheets at the end of the system lifetime. <br />
All values are taken from the prediction graph of the system's entire life cycle. <br />
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
"""
        )

    def create_vsnap_count_report(self):
        report_name="vSnap Server Count Report"

        LOGGER.info(f">> Creating the {report_name}.")

        excel_vs_avail_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vsnap_count",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="vsnap_count",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_setup_data.append( (report_name, "existing vs. recommended vSnaps", False, excel_vs_avail_result))

        return self.__report_structure_count(
            report_name=report_name,
            full_graph_panel_id=185,
            full_graph_description = f"""
This report shows the development of the <span style="color:blue">existing</span> and <span style="color:orange">recommended</span> count of vSnap Servers. <br />
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
""",

            one_year_existing_panel_id=232,

            one_year_existing_description = f"""
This report shows the count of the currently existing vSnap systems associated with the SPP-System and difference to the recommended count by the Blueprint vSnap Sizer sheets. <br />
All values are taken from the prediction graph, limited to the following year.  <br />
The Graphs display the range from now - 1 to now + 1 year. <br />
"""
        )

    def create_vadp_count_report(self):
        report_name="VADP Proxy Count Report"

        LOGGER.info(f">> Creating the {report_name}.")

        excel_vs_avail_result = self.__comparer.compare_metrics(
            base_metric_name="primary_vadp_count_total",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="vadp_count_total",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag=PredictorInfluxConnector.sppcheck_total_group_value,
        )
        self.overview_setup_data.append( (report_name, "existing vs. recommended VADPs", False, excel_vs_avail_result))

        return self.__report_structure_count(
            report_name=report_name,
            full_graph_panel_id=218,
            full_graph_description = f"""
This report shows the development of the <span style="color:blue">existing</span> and <span style="color:orange">recommended</span> count of VADP Proxies. <br />
The Graphs display the entire life cycle from {self.__start_date.date().isoformat()} to {self.__end_date.date().isoformat()}.  <br />
""",

            one_year_existing_panel_id=233,
            one_year_existing_description = f"""
This report shows the count of the currently existing VADP proxies associated with the SPP-System and difference to the recommended count by the Blueprint vSnap Sizer sheets. <br />
All values are taken from the prediction graph, limited to the following year.  <br />
The Graphs display the range from now - 1 to now + 1 year. <br />
"""
        )

    def create_server_catalog_config_report(self):
        report_name = "Server Configuration Catalog Report"

        LOGGER.info(f">> Creating the {report_name}.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="Configuration",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Configuration",
        )
        self.overview_used_data.append( (report_name, "used server configuration catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Configuration",
        )
        self.overview_setup_data.append((report_name, "existing vs. recommended server configuration catalog space", False, excel_vs_existing_result))

        return ""

    def create_server_recovery_config_report(self):
        report_name = "Server Recovery Catalog Report"

        LOGGER.info(f">> Creating the {report_name}.")
        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="Recovery",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Recovery",
        )
        self.overview_used_data.append( (report_name, "used server recovery catalog space", True, avail_vs_used_result))

        excel_vs_existing_result = self.__comparer.compare_metrics(
            base_metric_name="spp_config_catalog",
            base_table=ComparisonSource.EXCEL,

            comp_metric_name="total_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="Recovery",
        )
        self.overview_setup_data.append( (report_name, "existing vs. recommended server recovery catalog space", False, excel_vs_existing_result))

        return ""

    def create_server_system_config_report(self):
        report_name = "Server System Catalog Report"

        LOGGER.info(f">> Creating the {report_name}.")

        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="System",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="System",
        )
        self.overview_used_data.append( (report_name, "used server system catalog space", True, avail_vs_used_result))

        return ""

    def create_server_file_config_report(self):
        report_name = "Server File Catalog Report"

        LOGGER.info(f">> Creating the {report_name}.")

        # compare used vs available memory
        avail_vs_used_result = self.__comparer.compare_metrics(
            base_metric_name="total_server_catalogs",
            base_table=ComparisonSource.PREDICTION,
            base_group_tag="File",

            comp_metric_name="used_server_catalogs",
            comp_table=ComparisonSource.PREDICTION,
            comp_group_tag="File",
        )
        self.overview_used_data.append( (report_name, "used server file catalog space", True, avail_vs_used_result))

        return ""
