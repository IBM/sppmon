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
from typing import List

from dateutil.relativedelta import relativedelta
from sppCheck.report.comparer import ComparisonPoints
from sppCheck.report.individual_reports import IndividualReports, OverviewDataStruct
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class TableCreator:

    def __init__(self, start_date: datetime, end_date: datetime) -> None:
        self.__start_date = start_date
        self.__end_date = end_date

    def create_overview_table(self, overview_used_data: OverviewDataStruct, overview_setup_data: OverviewDataStruct):

        #### Prepare Table captions ####

        used_table_caption = f"""
<caption class="my_caption">
    {IndividualReports.panel_description_header}
    <p>
    This table shows the overview of all supported metrics displaying usage statistics. <br/>
    The values show, based on the scale of 0-100+% how the system is performing with each metric. <br/>
    </p>

    {IndividualReports.value_meaning_header}
    <p>
    A value <span class="my_text_positive_value">below 100%</span> means that the currently available space <span class="my_text_good">is sufficient</span> for the time period of the column. <br/>
    A value <span class="my_text_negative_value">above 100%</span> means that the currently available space is not sufficient, <span class="my_text_bad">requiring an upgrade</span>. <br/>
    If <span class="my_text_neutral_value">"NA"</span> is displayed, no data is available for this date due to various reasons. <br/>
    The distinctions are supported by the color code: <span class="my_text_positive_value">green</span> for sufficient and <span class="my_text_negative_value">red</span> if an upgrade is required. <br/>
    Please refer to the sections below for a more detailed explanation and view. <br/>
    </p>
</caption>
"""
        setup_table_caption = f"""
<caption class="my_caption">
    {IndividualReports.panel_description_header}
    <p>
    This table shows the overview of all supported metrics displaying setup-check statistics. <br/>
    The values show, based on the scale of 0-100+% how the system is set up compared to the Blueprint vSnap sizer Sheet recommendations. <br/>
    </p>

    {IndividualReports.value_meaning_header}
    <p>
    A value <span class="my_text_positive_value">above 100%</span> means that the currently available space <span class="my_text_good">is higher</span> than required. <br/>
    A value <span class="my_text_negative_value">below 100%</span> means that the currently available space is not sufficient compared to the recommendation, <span class="my_text_bad">requiring an upgrade</span>. <br/>
    If <span class="my_text_neutral_value">"NA"</span> is displayed, no data is available for this date due to various reasons. <br/>
    The distinctions are supported by the color code: <span class="my_text_positive_value">green</span> for sufficient and <span class="my_text_negative_value">red</span> if an upgrade is recommended. <br/>
    Please refer to the sections below for a more detailed explanation and view. <br/>
    <br/>
    Please be aware that even if a value below 100% is shown, the system can run correctly - it is just designed smaller than initial anticipated. <br />
    However, this also works the other way around: A correct setup does not promise that the system will last the whole anticipated life-cycle.  <br />
    Please check the used-data panels for such a forecast. <br />
    </p>
</caption>
"""
        #### Create both tables ####
        try:
            usage_table = self.__create_table(used_table_caption, overview_used_data)
        except ValueError as error:
            ExceptionUtils.exception_info(error, f"Failed to create the usage table, skipping it.")
            usage_table = f"""<h4> <span style="color:red"> Failed to create the usage Table </span> </h4>"""

        try:
            setup_table = self.__create_table(setup_table_caption, overview_setup_data)
        except ValueError as error:
            ExceptionUtils.exception_info(error, f"Failed to create the set up table, skipping it.")
            setup_table = f"""<h4> <span style="color:red"> Failed to create the set up Table </span> </h4>"""

        #### Combine the tables to a Section

        table_report = f"""
<div class="inner_section_table_a">
    <h3> Usage Statistics </h3>
    {usage_table}
</div>

<div class="inner_section_table_b">
    <h3> Set up Check </h3>
    {setup_table}
</div>
"""

        return table_report

    def __create_table_rows(self, metrics_list: OverviewDataStruct):

        table_rows_lst: List[str] = []
        for (metric_name, metric_description, positive_interpretation, data_dict) in metrics_list:
            row_data_lst: List[str] = []
            for time_point in ComparisonPoints:
                data_tuple = data_dict[time_point]
                if not data_tuple:
                    # no data available
                    percent_str = "NA"
                    table_class = "table-warning my_na_table"
                else:
                    # other values unused
                    #(timestamp, time_diff, value_diff, percent_value)
                    (_, _, _, percent_value) = data_tuple

                    percent_str = f"{percent_value}%"

                    # decide coloring according to value and mapping
                    if percent_value < 100:
                        if positive_interpretation:
                            table_class = "table-success my_good_table"
                        else:
                            table_class = "table-danger my_bad_table"
                    else: # value above 100%
                        if positive_interpretation:
                            table_class = "table-danger my_bad_table"
                        else:
                            table_class = "table-success my_good_table"
                # append each column to the row list
                row_data_lst.append(f"""<td class="my_td {table_class}">{percent_str}</td>""")

            # convert each column to a row string, append to the total row list.
            row_data_str="\n".join(row_data_lst)
            table_rows_lst.append(f"""
    <tr>
        <td class="my_td table-light my_table_metrics_name" > <a href="#{metric_name}"> {metric_description}</a> </td>
        {row_data_str}
    </tr>
"""         )
        # End of the metric iteration

        # now compute the whole table
        table_rows_str = "\n".join(table_rows_lst)
        return table_rows_str

    def __create_table(self, caption: str, metrics_list: OverviewDataStruct):

        rows_str = self.__create_table_rows(metrics_list)

        return f"""
<table class="my_table table table-light table-bordered caption-bottom">
    {caption}
    <thead>
        <tr class=" my_td">
            <th class="my_table_header" > Metric Name </th>
            <th class="my_table_header" >
                {ComparisonPoints.START.value} <br/>
                ({self.__start_date.date().isoformat()})
            </th>
            <th class="my_table_header" >
                {ComparisonPoints.NOW.value} <br/>
                ({date.today().isoformat()})
            </th>
            <th class="my_table_header" >
                {ComparisonPoints.ONE_YEAR.value} <br/>
                ({(date.today() + relativedelta(years=1)).isoformat()})
            </th>
            <th class="my_table_header" >
                {ComparisonPoints.END.value} <br/>
                ({self.__end_date.date().isoformat()})
            </th>
        </tr>
    </thead>
    {rows_str}
</table>
"""
