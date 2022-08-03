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
from typing import Any, Dict, List, Optional

from dateutil.relativedelta import relativedelta
from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from sppCheck.report.comparer import Comparer, ComparisonPoints
from sppCheck.report.individual_reports import IndividualReports
from sppCheck.report.picture_downloader import PictureDownloader

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

        if not prediction_rp or not excel_rp or predict_years is None:
            raise ValueError("Automatic selection of the latest prediction or excel retention policy not supported yet. \n" +\
                             "Please only generate the Report in conjunction with the other SPPCheck functionalities")

        self.__influx_client: InfluxClient = influx_client
        self.__temp_file_path = Path("sppcheck", "report", "temp_files", "report.html")

        self.__start_date = start_date
        self.__end_date = datetime.now() + relativedelta(years=predict_years)


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


    def __create_overview_table(self):

        LOGGER.info("> Starting to create an overview table")

        metrics_list = self.__individual_reports.overview_table_data

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
                    (timestamp, time_diff, value_diff, percent_value) = data_tuple

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
        table_report = f"""
<table>
    <caption>
        This table shows the overview of all supported metrics. <br/>
        The values show, based on the scale of 0-100+% how the system is performing with each metric. <br/>
        The color code shows whether the value is good or negative, depending on the context of the metric. <br/>
        Each metric is explained in detail in the lower sections.
    </caption>
    <tr>
        <th> Metric Name </th>
        <th> {ComparisonPoints.START.value} ({self.__start_date.date().isoformat()}) </th>
        <th> {ComparisonPoints.NOW.value} ({date.today().isoformat()}) </th>
        <th> {ComparisonPoints.ONE_YEAR.value} ({(date.today() + relativedelta(years=1)).isoformat()}) </th>
        <th> {ComparisonPoints.END.value} ({self.__end_date.date().isoformat()}) </th>
    </tr>
    {table_rows_str}
</table>
"""

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
            if(method_name == "__init__"):
                continue

            LOGGER.debug(f">> executing function {method_name}")
            full_individual_report_str += method()

        LOGGER.info("> Finished creating reports for each metric")

        return full_individual_report_str





    def __gen_pdf_file(self, individual_reports: str, overview_table: str):

        LOGGER.info("> Starting to generate a temporary file for pdf creation process.")

        total_report = f"""
<!DOCTYPE html>
<html>
<body>

<h1><img width="40" height="40" src="SpectrumProtectPlus-dark.svg"/> SPPCheck Report for SPP-System "{self.__influx_client.database.name}"</h1>
<h4>Created on {date.today().isoformat()}</h4>

<h2> Overview Table </h2>
{overview_table}

<h2> Individual Reports </h2>
{individual_reports}

</body>
</html>
"""

        with open(self.__temp_file_path, 'wt') as file:
            file.write(total_report)

        LOGGER.info("> Finished generating the temporary file.")
        pass

    def createPdfReport(self):

        individual_reports = self.__create_individual_reports()

        overview_table = self.__create_overview_table()

        self.__gen_pdf_file(individual_reports, overview_table)
