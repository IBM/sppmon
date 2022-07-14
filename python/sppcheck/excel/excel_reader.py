"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2021, 2022. All Rights Reserved.

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
    Module with excel-reader. Contains all functionality around reading and writing from the vSnap sizer excel files.

Classes:
    ExcelReader
"""

from __future__ import annotations

import re
from datetime import datetime
from logging import getLogger
from math import isnan
from os.path import exists
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple, Union

import influx.influx_client as ic
from pandas import (DataFrame, DateOffset, DatetimeIndex, ExcelFile, Series,
                    date_range, read_excel)
from pandas.core.frame import DataFrame
from sppCheck.excel.excel_dict_builder import ExcelDictBuilder
from utils.sppcheck_utils import SizingUtils
from utils.exception_utils import ExceptionUtils
from utils.spp_utils import SppUtils

LOGGER_NAME = 'sppmon'
LOGGER = getLogger(LOGGER_NAME)

class ExcelReader:
    """TODO"""

    @property
    def report_rp(self):
        return self.__report_rp

    sppcheck_excel_table_name: ClassVar[str] = "sppcheck_excel_data"
    sppcheck_excel_value_name: ClassVar[str] = "data"
    sppcheck_excel_tag_name: ClassVar[str] = "metric_name"

    def __init__(self, sheet_path: str, sizer_version: str,
                 influx_client: ic.InfluxClient, start_date: datetime,
                 dp_freq_hour: int, rp_timestamp: str) -> None:
        """TODO"""

        if(not sheet_path):
            raise ValueError("A excel sheet file is required to setup the Excel reader.")
        if(not exists(sheet_path)):
            raise ValueError(f"The excel sheet does not exits: {sheet_path}")

        suffix = Path(sheet_path).suffix

        if(suffix != ".xlsb" and suffix != ".xlsx"):
            raise ValueError("The excel sheet has an incorrect fileending, only `.xlsb` and `.xlsx` is allowed")
        self.__sheet_path = sheet_path


        if(not sizer_version):
            raise ValueError("The vSnap Sizer sheet version is required for selecting the correct parsing structure.")
        if not re.match(r"^v\d+(\.\d+)+$", sizer_version):
            raise ValueError("The version is not in the correct format of \"v1.0\".")

        json_structure_path = Path("sppcheck","json_structures")

        excel_structure_name = "excel_structure"
        excel_structure_path = json_structure_path.joinpath(f"{excel_structure_name}_{sizer_version}.json")
        if(not exists(excel_structure_path)):
            raise ValueError(f"The excel structure file does not exits: {excel_structure_path}")
        self.__excel_structure_path = excel_structure_path

        if not influx_client:
            raise ValueError("Excel Reader is not available, missing the influx_client")

        self.__influx_client = influx_client
        self.__start_date = start_date
        self.__dp_freq_hour = dp_freq_hour
        self.__report_rp = SizingUtils.create_unique_rp(self.__influx_client, "excel", rp_timestamp)

    def parse_insert_sheet(self):
        mapping = self.__read_sheet()
        self.__insert_sheet(mapping)

    def __read_sheet(self) -> Dict[str, Tuple[Optional[str], Series]]:

        with ExcelFile(self.__sheet_path) as xls:
            sizing_results: DataFrame = read_excel(xls, "Sizing Results")

        #### Trim sheet and optimize access ####

        # rename column to have accurate naming
        colum_names: List[Union[str, int]] = ["A", "name", "alt_unit", "unit"]
        # years from 1 to 8
        colum_names.extend([x for x in range(1, 8 + 1)])
        sizing_results.columns = colum_names

        # it starts at 2, since the first two lines are empty
        sizing_results.drop(index=[0,1], inplace=True)
        # the first column (A) is always empty, needs to be removed
        sizing_results.drop(columns="A", inplace=True)

        #### Transform the sheet into pre-defined dictionary with variable-name to years projection
        # columns: name - alt_unit - unit - 1...8
        return self.__extract_sheet(sizing_results)

    def __insert_sheet(self, mapping: Dict[str, Tuple[Optional[str], Series]]):

        # freq = "A" means yearly, but uses end of month
        # therefore unique dateoffset
        date_index: DatetimeIndex = date_range(start = self.__start_date, freq=DateOffset(years=1), periods = 8)

        for excel_key, (unit, projection) in mapping.items():
            try:
                if unit:
                    unit_multiplier = SppUtils.get_unit_multiplier(unit)
                    projection: Series = projection.map(lambda x: x * unit_multiplier) # type: ignore

                # save the id for the metric
                insert_tags = {self.sppcheck_excel_tag_name: excel_key}

                projection.index = date_index.copy(deep=True)
                # mean is required to align the timestamps, other functions like fill with na didn't work
                expanded_projection: Series = projection.resample(f"{self.__dp_freq_hour}H").mean()
                # interpolate over time index
                interpolated_projection = expanded_projection.interpolate("time")
                if not isinstance(interpolated_projection, Series):
                    raise ValueError(f"Failed to interpolate the projection for key {excel_key}")
                try:
                    SizingUtils.insert_series(
                        influx_client=self.__influx_client,
                        report_rp=self.__report_rp,
                        prediction_result=interpolated_projection,
                        table_name=self.sppcheck_excel_table_name,
                        value_key=self.sppcheck_excel_value_name,
                        insert_tags=insert_tags)

                except KeyError as error:
                    ExceptionUtils.exception_info(error)
                    raise ValueError(f"No default dict definition exists for the table {self.sppcheck_excel_table_name}.")


            except ValueError as error:
                ExceptionUtils.exception_info(error, f"Skipping the key {excel_key} due to an error.")

    def __extract_sheet(self, results: DataFrame) -> Dict[str, Tuple[Optional[str], Series]]:

        builder = ExcelDictBuilder(self.__excel_structure_path)

        for _, series in results.iterrows():
            try:
                name = series["name"]
                # empty rows are nan
                if isinstance(name, float) and isnan(name):
                    continue
                # all values are string, need to be parsed
                if not isinstance(name, str):
                    raise ValueError(f"Name '{name}' is of unexpected type: {type(name)}")

                # trim name to avoid space issues
                name = name.strip()

                # search the name and adjust the level accordingly
                builder.adjust_level(name)
                builder.save(name, series)

            except ValueError as error:
                LOGGER.error(error.args[0])
                LOGGER.error(f"args: {error.args[1:]}")

        unused_list: List[str] = builder.get_unused_items()
        if unused_list:
            LOGGER.error("There were items, which were not found within the excel sheet. Please verify the excel sheet for changes!")
        for item in unused_list:
            LOGGER.error(item)

        if builder.missing_items:
            LOGGER.error("There were items, which were not found within the json struct. Please verify the excel sheet for changes!")
        for item in builder.missing_items:
            LOGGER.error(item)

        return builder.result
