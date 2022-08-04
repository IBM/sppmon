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
from sppCheck.report.individual_reports import OverviewDataStruct

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class TableCreator:

    def __init__(self, start_date: datetime, end_date: datetime) -> None:
        self.__start_date = start_date
        self.__end_date = end_date

    def create_overview_table(self, overview_used_data: OverviewDataStruct, overview_setup_data: OverviewDataStruct):

        used_table_caption = """
<caption>
    This table shows the overview of all supported metrics displaying usage statistics. <br/>
    The values show, based on the scale of 0-100+% how the system is performing with each metric. <br/>
    <br/>
    A value <span style="color:green">below 100%</span> means that the currently available space <span style="color:green">is sufficient</span> for the time period of the column. <br/>
    A value <span style="color:red">above 100%</span> means that the currently available space is not sufficient, <span style="color:red">requiring an upgrade</span>. <br/>
    If "NA" is displayed, no data is available for this date due to various reasons. <br/>
    The distinctions are supported by the color code: <span style="color:green">green</span> for sufficient and <span style="color:red">red</span> if an upgrade is required. <br/>
    Please refer to the sections below for a more detailed explanation and view. <br/>
</caption>
"""
        setup_table_caption = """
<caption>
    This table shows the overview of all supported metrics displaying setup-check statistics. <br/>
    The values show, based on the scale of 0-100+% how the system is set up compared to the Blueprint vSnap sizer Sheet recommendations. <br/>
    <br/>
    A value <span style="color:green">above 100%</span> means that the currently available space <span style="color:green">is higher</span> than required. <br/>
    A value <span style="color:red">below 100%</span> means that the currently available space is not sufficient compared to the recommendation, <span style="color:red">requiring an upgrade</span>. <br/>
    If "NA" is displayed, no data is available for this date due to various reasons. <br/>
    The distinctions are supported by the color code: <span style="color:green">green</span> for sufficient and <span style="color:red">red</span> if an upgrade is recommended. <br/>
    Please refer to the sections below for a more detailed explanation and view. <br/>
    <br/>
    Please be aware that even if a value below 100% is shown, the system can run correctly - it is just designed smaller than initial anticipated. <br />
    However, this also works the other way around: A correct setup does not promise that the system will last the whole anticipated life-cycle.  <br />
    Please check the used-data panels for such a forecast. <br />
</caption>
"""
        table_report = f"""
<h3> Usage Statistics </h3>
{self.__create_table(used_table_caption, overview_used_data)}
<h3> Set up Check </h3>
{self.__create_table(setup_table_caption, overview_setup_data)}
"""

        return table_report

    def __create_table_rows(self, metrics_list: OverviewDataStruct):

        table_rows_lst: List[str] = []
        for (metric_name, positive_interpretation, data_dict) in metrics_list:
            row_data_lst: List[str] = []
            for time_point in ComparisonPoints:
                data_tuple = data_dict[time_point]
                if not data_tuple:
                    # no data available
                    percent_str = "NA"
                    color = "orange"
                else:
                    # other values unused
                    #(timestamp, time_diff, value_diff, percent_value)
                    (_, _, _, percent_value) = data_tuple

                    percent_str = f"{percent_value}%"

                    # decide coloring according to value and mapping
                    if percent_value < 100:
                        if positive_interpretation:
                            color = "green"
                        else:
                            color = "red"
                    else: # value above 100%
                        if positive_interpretation:
                            color = "red"
                        else:
                            color = "green"
                # append each column to the row list
                row_data_lst.append(f"""<td style="color:{color};"> {percent_str} </td>""")

            # convert each column to a row string, append to the total row list.
            row_data_str="\n".join(row_data_lst)
            table_rows_lst.append(f"""
    <tr>
        <td> {metric_name} </td>
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
<table>
    {caption}
    <tr>
        <th> Metric Name </th>
        <th>
            {ComparisonPoints.START.value} <br/>
            ({self.__start_date.date().isoformat()})
        </th>
        <th>
            {ComparisonPoints.NOW.value} <br/>
            ({date.today().isoformat()})
        </th>
        <th>
            {ComparisonPoints.ONE_YEAR.value} <br/>
            ({(date.today() + relativedelta(years=1)).isoformat()})
        </th>
        <th>
            {ComparisonPoints.END.value} <br/>
            ({self.__end_date.date().isoformat()})
        </th>
    </tr>
    {rows_str}
</table>
"""
