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

from calendar import month
from datetime import datetime, timedelta
from enum import Enum, auto, unique
import logging
from multiprocessing.sharedctypes import Value
from typing import Dict, Any, Generator, List, Optional, Tuple, Type, Union

from influx.database_tables import Datatype, RetentionPolicy
from dateutil.relativedelta import relativedelta

from influx.influx_client import InfluxClient
from influx.influx_queries import Keyword, SelectionQuery
from sppCheck.excel.excel_controller import ExcelController
from sppCheck.predictor.predictor_influx_connector import PredictorInfluxConnector
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class ComparisonSource(Enum):
    PREDICTION = auto()
    EXCEL = auto()
    #HISTORIC = auto()

@unique
class ComparisonPoints(Enum):
    START = auto()
    NOW = auto()
    ONE_YEAR = auto()
    END = auto()

class Comparer:

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

        self.__prediction_table = influx_client.database[PredictorInfluxConnector.sppcheck_table_name]


        self.__historic_rp = select_rp
        self.__prediction_rp = prediction_rp
        self.__excel_rp = excel_rp

        ################ Prepare timestamps #########################

        # FEATURE-Request (NK): Make the now-date dependent on the prediction RP

        # from date is absolute min in case user wants to cut off data in front
        start_base_date = start_date
        now_base_date = datetime.now()
        # IMPORTANT: timedelta day"s" is important -> relative
        one_year_base_date = now_base_date + timedelta(days=365)
        # reduce it by 30 days to make sure if there is data, is is returned.
        # the minor reduce will not cause any harm
        end_base_date = now_base_date + relativedelta(years=predict_years) - relativedelta(months=1)


        self.__time_clause_mapping = {
            ComparisonPoints.START: Comparer.prepare_time_clauses(start_base_date),
            ComparisonPoints.NOW: Comparer.prepare_time_clauses(now_base_date),
            ComparisonPoints.ONE_YEAR: Comparer.prepare_time_clauses(one_year_base_date),
            ComparisonPoints.END: Comparer.prepare_time_clauses(end_base_date)
        }

    @staticmethod
    def prepare_time_clauses(base_date: datetime):

        timestamp_min = round(base_date.timestamp())
        timestamp_max = round((base_date + relativedelta(months=3)).timestamp())
        # take a big span to make sure there are results for user error, then take first
        return f"time > {timestamp_min}s and time < {timestamp_max}s "


    def compare_metrics(self,
                   base_metric_name: str, base_table: ComparisonSource, base_group_tag: Optional[str],
                   comp_metric_name: str, comp_table: ComparisonSource, comp_group_tag: Optional[str]):

        LOGGER.info(f">> Start of comparison of metric {base_metric_name} with metric {comp_metric_name}.")

        base_points = self.__query_comparison_points(
            base_metric_name, base_table, base_group_tag
        )

        comp_points = self.__query_comparison_points(
            comp_metric_name, comp_table, comp_group_tag
        )

        result_dict: Dict[ComparisonPoints, Optional[Tuple[int, int|float, int]]] = {}
        for time_point in ComparisonPoints:
            try:
                LOGGER.debug(f"Comparing time point {time_point}")
                base_tuple = base_points[time_point]
                comp_tuple = comp_points[time_point]

                if not base_tuple or not comp_tuple:
                    # do not throw, it is not that critical. Only write a message and continue
                    result_dict[time_point] = None
                    LOGGER.debug(f"base_tuple: {base_tuple}, comp_tuple: {comp_tuple}")
                    ExceptionUtils.error_message(f"Could not compare metrics at time point {time_point.name} because either metric has no data.")
                    continue

                (base_timestamp, base_value_uncasted) = base_tuple
                (comp_timestamp, comp_value_uncasted) = comp_tuple

                # get same type for both values
                if isinstance(base_value_uncasted, float):
                    base_value = float(base_value_uncasted)
                    comp_value = float(comp_value_uncasted)
                else: # re-casting does no harm
                    base_value = int(base_value_uncasted)
                    comp_value  = int(comp_value_uncasted)

                # epoch is seconds since 1970, therefore this diff is the difference between both points which can asap be used
                # we use seconds precision
                LOGGER.debug(f"base_timestamp: {base_timestamp}, comp_timestamp: {comp_timestamp}")
                diff_timestamp = base_timestamp - comp_timestamp
                diff_value = base_value - comp_value
                LOGGER.debug(f"diff_timestamp: {diff_timestamp}, diff_value: {diff_value}")
                # precision of int is enough
                # how much % of the base value is the comp value -> comp 75, base 90 -> diff 83%
                diff_percent = round((comp_value / base_value) * 100)
                LOGGER.debug(f"diff_percent: {diff_percent}")

                result_dict[time_point] = (diff_timestamp, diff_value, diff_percent)
            except ValueError as error:
                ExceptionUtils.exception_info(error, f"Failed to compare metric for time point {time_point.name}")
                result_dict[time_point] = None

        LOGGER.info(f">> Finished comparison.")
        return result_dict



    def __query_comparison_points(self, metric_name: str, table_source: ComparisonSource, group_tag: Optional[str]):

        LOGGER.debug(f"Querying comparison points for metric_name={metric_name}, table={table_source.name}, group_tag={group_tag}")

        results: Dict[ComparisonPoints, Optional[Tuple[int, str|int|float]]] = {}
        for time_point in ComparisonPoints:
            LOGGER.debug(f"Querying comparison point for time_point = {time_point.name}")
            results[time_point] = self.__query_comparison_point(
                self.__time_clause_mapping[time_point],
                metric_name,
                table_source,
                group_tag
            )

        LOGGER.debug("Finished all comparison points")

        return results


    def __query_comparison_point(self, time_clause: str, metric_name: str, table_source: ComparisonSource, group_tag: Optional[str]):

        where_str = time_clause

        if table_source is ComparisonSource.PREDICTION:
            alt_rp = self.__prediction_rp
            where_str += f"AND {PredictorInfluxConnector.sppcheck_metric_tag} = '{metric_name}' "
            if group_tag:
                where_str += f"AND {PredictorInfluxConnector.sppcheck_group_tag} = '{group_tag}' "
        elif table_source is ComparisonSource.EXCEL:
            alt_rp = self.__excel_rp
            where_str += f"AND {ExcelController.sppcheck_excel_metric_tag} = '{metric_name}' "
        ### historic not implemented yet ###

        LOGGER.debug(f"where_str: {where_str}")
        selection_query = SelectionQuery(
            keyword=Keyword.SELECT,
            table_or_query=self.__prediction_table,
            alt_rp=alt_rp,
            fields=[PredictorInfluxConnector.sppcheck_value_name],
            where_str=where_str
            )
        LOGGER.debug(selection_query.to_query())

        result = self.__influx_client.send_selection_query(selection_query)
        result_list: List[Tuple[ # list: different tag groups
            Tuple[str, Optional[Dict[str, str]]], # tablename, dict of grouping tags (empty if not grouped)
            Generator[Dict[str, str|int|float], None, None] # result of the selection query
        ]] = result.items() # type: ignore

        # Tablename is not required since it is static
        # group tags are not supported yet
         # do not abort, exception handling later
        if not result_list:
            LOGGER.debug(f"No data is available for metric {metric_name}.")
            return None

        # FEATURE-Request (NK): Allow multiple grouping clauses
        # also just the first item required, closest to the selected time period
        result_dict = next(result_list[0][1], None)

        # do not abort, exception handling later
        if not result_dict:
            LOGGER.debug(f"No data is available for metric {metric_name} within the selected grouping clause.")
            return None

        # cast timestamp into int, though this should never happen...
        if not isinstance(result_dict["time"], int):
            LOGGER.warning(f"Casting timestamp from type {type(result_dict['time'])} into int.")
            result_dict["time"] = int(result_dict["time"])

        result_tuple = (result_dict["time"], result_dict["data"])

        return result_tuple
