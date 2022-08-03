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

class OverviewTable:

    def __init__(self, start_date: datetime, end_date: datetime) -> None:
        self.__start_date = start_date
        self.__end_date = end_date


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
                    else:
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

    def create_table(self, caption: str, metrics_list: OverviewDataStruct):

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
