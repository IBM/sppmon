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

from __future__ import annotations
from datetime import datetime
import logging
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union

# ignore the warning since major changes are required, wont change anything now.
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd

from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from influx.influx_queries import Keyword, SelectionQuery
from numpy import float64
from pandas import Series, Timestamp
from sppCheck.predictor.predictor_interface import PredictorInterface
from sppCheck.predictor.statsmodel_ets_predictor import \
    StatsmodelEtsPredictor
from utils.sppcheck_utils import SppcheckUtils
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)


class PredictorInfluxConnector:

    sppcheck_table_name: ClassVar[str] = "sppcheck_data"
    sppcheck_value_name: ClassVar[str] = "data"
    sppcheck_metric_tag: ClassVar[str] = "metric_name"
    sppcheck_group_tag: ClassVar[str] = "grouping_tag"
    sppcheck_group_tag_name: ClassVar[str] = "grouping_tag_name"
    sppcheck_total_group_value: ClassVar[str] = "Total"

    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                 select_rp: RetentionPolicy, report_rp: RetentionPolicy,
                 forecast_years: float, start_date: datetime) -> None:

        self.__influx_client: InfluxClient = influx_client

        self.__predictorI: PredictorInterface = StatsmodelEtsPredictor()
        self.__dp_interval_hour = dp_interval_hour
        self.__select_rp = select_rp
        self.__forecast_years = forecast_years
        self.__start_date_timestamp = round(start_date.timestamp())
        self.__report_rp = report_rp

        LOGGER.debug(f"> dp_interval_hour: {dp_interval_hour}, select_rp: {select_rp}, forecast_years: {forecast_years}")
        LOGGER.debug(f"> start_date_timestamp: {self.__start_date_timestamp}, dp_interval_hour: {dp_interval_hour}")
        LOGGER.debug(f"> report_rp: {report_rp}")



    def predict_data(
        self,
        table_name: str,
        value_or_count_key: str,
        description: str,
        metric_name: str,
        re_save_historic: bool,
        save_total: bool,
        group_tags: Optional[List[str]] = None,
        use_count_query: bool = False,
        repeat_last: bool = False
        ) -> None:

        LOGGER.info(f">> Starting prediction of the {description}.")
        LOGGER.debug(f">> table_name: {table_name}, value_count_key: {value_or_count_key}, metric_name: {metric_name}")
        LOGGER.debug(f">> re_save_historic: {re_save_historic}, save_total: {save_total}, group_tags: {group_tags}, use_count_query: {use_count_query}")

        #### Generate the query ###
        if use_count_query:
            history_query = self.__generate_count_query(
                table_name=table_name,
                group_tags=group_tags,
                count_key=value_or_count_key
            )
        else:
            history_query = self.__generate_query(
                table_name=table_name,
                value_key=value_or_count_key,
                group_tags=group_tags)

        LOGGER.debug(f">> Generated query: {history_query}")

        LOGGER.debug(f">> group_tags before extracting escapes: {group_tags}")
        # issue: reserved identifiers like "name" require escapes in influx, but the result isn't escaped anymore
        if group_tags:
            for i in range(len(group_tags)):
                group_tags[i] = group_tags[i].replace("\"", "")
        LOGGER.debug(f">> group_tags after extracting escapes: {group_tags}")
        LOGGER.debug(f">> Generated query after extracting escapes: {history_query}")

        #### Send the query #####

        result = self.__influx_client.send_selection_query(history_query)
        result_list: List[Tuple[ # list: different tag groups
            Tuple[str, Optional[Dict[str, str]]], # tablename, dict of grouping tags (empty if not grouped)
            Generator[Dict[str, Any], None, None] # result of the selection query
        ]] = result.items() # type: ignore

        #                                # optional tag-dict    # list with dicts: values
        tag_data_tuple = list(map(lambda tuple: (tuple[0][1] , list(tuple[1])), result_list))

        if not tag_data_tuple:
            raise ValueError(f"No {description} data is available within the InfluxDB. Aborting prediction.")

        #### Iterate over the results ####

        LOGGER.info(f">> Successfully requested data for the {description}, starting prediction progress.")

        self.__prepare_predict_insert_iterate(
            tag_data_tuple=tag_data_tuple,
            description=description,
            metric_name=metric_name,
            group_tags=group_tags,
            re_save_historic=re_save_historic,
            save_total=save_total,
            repeat_last=repeat_last
        )

        LOGGER.info(f">> Finished the prediction for the {description}, flushing the data a last time.")

        # make sure to flush
        self.__influx_client.flush_insert_buffer()

    def __generate_query(self, table_name: str, value_key: str, group_tags: Optional[List[str]]) -> SelectionQuery:

        LOGGER.debug(f">> Generating regular query for table {table_name}, value_key {value_key}, group_tags {group_tags}.")

        table = self.__influx_client.database[table_name]

        fields = [f"{value_key} AS {self.sppcheck_value_name}"]
        # tags for re-insert information of the predicted data
        fields.extend(map('\"{}\"'.format, table.tags))

        # copy required to avoid side effects on the data.
        group_list = None
        if group_tags:
            group_list = group_tags.copy()

        return SelectionQuery(
            Keyword.SELECT,
            table_or_query=table,
            alt_rp=self.__select_rp,
            fields=fields,
            order_direction="ASC",
            group_list=group_list,
            where_str=f"time > {self.__start_date_timestamp}s" # s for second precision
            )


    def __generate_count_query(self, table_name: str, count_key: str, group_tags: Optional[List[str]]) -> SelectionQuery:

        LOGGER.debug(f">> Generating count query for table {table_name}, count_key {count_key}, group_tags {group_tags}.")

        query_table = self.__influx_client.database[table_name]

        group_list = [f"time({self.__dp_interval_hour}h)"]
        if group_tags:
            group_list.extend(group_tags)

        inner_query = SelectionQuery(
            Keyword.SELECT,
            table_or_query=query_table,
            alt_rp=self.__select_rp,
            fields=["*"],
            order_direction="ASC",
            where_str=f"time > {self.__start_date_timestamp}s"  # s for second precision
            )

        return SelectionQuery(
            Keyword.SELECT,
            table_or_query=inner_query,
            fields=[f"COUNT(DISTINCT({count_key})) AS {self.sppcheck_value_name}"],
            order_direction="ASC",
            group_list=group_list,
            where_str=f"time > {self.__start_date_timestamp}s"  # s for second precision
            )


    def __prepare_predict_insert_iterate(self,
                               tag_data_tuple: List[Tuple[
                                                Optional[Dict[str, str]], # dict of grouping tags
                                                List[Dict[str, Any]] # result of the selection query
                               ]],
                               description: str,
                               metric_name: str,
                               group_tags: Optional[List[str]],
                               re_save_historic: bool,
                               save_total: bool,
                               repeat_last: bool):

        LOGGER.debug(f">> len of tag_data_tuple: {len(tag_data_tuple)}")

        total_historic_series: Series = Series(dtype=float64)
        for (tag_dict, data) in tag_data_tuple:
            try:

                LOGGER.debug(f">>> Tags: {tag_dict}")
                LOGGER.debug(f">>> Len of data: {len(data)}")

                if not data:
                    raise ValueError(f"Error: the result list is empty for {description}")

                # if grouped, the tag_dict 1. exists 2. contains tag_name: tag_value
                if group_tags and not tag_dict:
                    raise ValueError(f"Error: There is no grouping information available for {description} with example data {data[0]}")

                LOGGER.debug(f">>> Example [0] of data: {data[0]}")

                #### collect meta information for the re-insertion ####
                # get tags for the sppcheck_data table
                insert_tags: Dict[str, Optional[str]] = {
                    self.sppcheck_metric_tag: metric_name,
                    "site": data[0].get("site", None),
                    "siteName": data[0].get("siteName", None)
                }

                # add grouping and update site information
                if group_tags and tag_dict:
                    # if there is site in, dont save the grouping tag but the site metadata.
                    if "site" in group_tags: # this does also include "siteName" due to the "site"
                        # overwrites values from tag_dict
                        insert_tags.update(tag_dict)
                    else:

                        insert_tags[self.sppcheck_group_tag] = tag_dict[group_tags[0]]
                        if len(group_tags) > 1:
                            insert_tags[self.sppcheck_group_tag_name] = tag_dict[group_tags[1]]
                        # must be grouped ID first, then name

                        # if multiple (countable) are allowed, add copies of the row below.

                LOGGER.debug(f">>> Insert_tags: {insert_tags}")

                #### extract the data for the prediction  ####

                try:
                    historic_values: Dict[int, Union[int, float]] = {x["time"]: x[self.sppcheck_value_name] for x in data}
                except KeyError as error:
                    ExceptionUtils.exception_info(error)
                    raise ValueError(f"Missing value key {self.sppcheck_value_name} in requested data from the InfluxDB. Is a \"AS\"-Clause missing in the query?")
                # prepare the data and set the frequency

                if group_tags and tag_dict:
                    LOGGER.info(f">>> {description}: Preparing the data in group {group_tags[0]}={tag_dict[group_tags[0]]} for prediction.")
                else:
                    LOGGER.info(f">>> {description}: Preparing the data for prediction.")

                data_series = self.__predictorI.data_preparation(historic_values, self.__dp_interval_hour)

                # sum the individual results for a final total value
                if group_tags and save_total:
                    # fill required for initial setup -> or everything is NaN
                    total_historic_series = total_historic_series.add(data_series, fill_value=0)

                # Count: The DB does not have historic data, since it is aggregated on query -> save it.
                # insert into new table with clear identification, not old one.
                if re_save_historic:

                    if group_tags and tag_dict:
                        LOGGER.info(f">>> {description}: Saving historic data of the group {group_tags[0]}={tag_dict[group_tags[0]]}.")
                    else:
                        LOGGER.info(f">>> {description}: Saving historic data.")

                    SppcheckUtils.insert_series(
                        self.__influx_client,
                        report_rp=self.__report_rp,
                        prediction_result=data_series,
                        table_name=self.sppcheck_table_name,
                        value_key=self.sppcheck_value_name,
                        insert_tags=insert_tags)

                #### predict data for the next x years ####

                if group_tags and tag_dict:
                    LOGGER.info(f">>> Predicting the data for {description} in group {group_tags[0]}={tag_dict[group_tags[0]]}.")
                else:
                    LOGGER.info(f">>> Predicting the data for {description}.")

                if repeat_last:
                    prediction_result = self.static_prediction(data_series, self.__forecast_years)
                else:
                    prediction_result = self.__predictorI.predict_data(data_series, self.__forecast_years)

                LOGGER.info(f">>> Finished the prediction, continuing to insert the data into the InfluxDB.")
                # save the prediction with the new meta data
                SppcheckUtils.insert_series(
                    self.__influx_client,
                    report_rp=self.__report_rp,
                    prediction_result=prediction_result,
                    table_name=self.sppcheck_table_name,
                    value_key=self.sppcheck_value_name,
                    insert_tags=insert_tags)

            except ValueError as error:
                ExceptionUtils.exception_info(error, f"Skipping {description} group with {group_tags}={tag_dict}.")

        # only save if grouped, since then there are multiple series summed up
        if group_tags and save_total:

            insert_tags = {
                self.sppcheck_metric_tag: metric_name,
                self.sppcheck_group_tag: self.sppcheck_total_group_value,
                self.sppcheck_group_tag_name: self.sppcheck_total_group_value,
                "site": self.sppcheck_total_group_value,
                "siteName": self.sppcheck_total_group_value}

            LOGGER.info(f">> Saving summarized historic values.")

            # insert summed historical data first
            SppcheckUtils.insert_series(
                self.__influx_client,
                report_rp=self.__report_rp,
                prediction_result=total_historic_series,
                table_name=self.sppcheck_table_name,
                value_key=self.sppcheck_value_name,
                insert_tags=insert_tags)

            LOGGER.info(f">> Predicting the summarized data of the {description}.")

            # insert total data prediction
            if repeat_last:
                    prediction_result = self.static_prediction(total_historic_series, self.__forecast_years)
            else:
                prediction_result = self.__predictorI.predict_data(total_historic_series, self.__forecast_years)

            LOGGER.info(f">> Finished the prediction, continuing to insert the data into the InfluxDB.")

            SppcheckUtils.insert_series(
                self.__influx_client,
                report_rp=self.__report_rp,
                prediction_result=prediction_result,
                table_name=self.sppcheck_table_name,
                value_key=self.sppcheck_value_name,
                insert_tags=insert_tags)

    def static_prediction(self,
                     data_series: Series,
                     forecast_years: float) -> Series:

        LOGGER.debug("Using a static prediction")

        # read the frequency to calculate how many data points needs to be forecasted
        try:
            # convert to hour
            dp_freq_hour: float = data_series.index.freq.nanos / 3600000000000 # type: ignore
        except AttributeError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("The data series is corrupted, no frequency at the index available", data_series.index)

        hours_last_data = (datetime.now() - data_series.index.max()).total_seconds() / (60 * 60)
        # discard if the data is older than 7 days and 3 times the frequency
        # May some data points fail, therefore this grace period
        if hours_last_data > 24 * 7 and hours_last_data > dp_freq_hour * 3:
            raise ValueError("This set of data is too old to be used")

        LOGGER.debug(f"forecasting using {len(data_series)} data points")

        last_timestamp = data_series.last_valid_index()
        last_value = data_series.get(last_timestamp)

        # this issues a warning if not ignored when importing
        # prediction should start +1x freq from the last one.
        start_timestamp: Timestamp = last_timestamp + last_timestamp.freq.delta

        # get count of data points required
        forecast_dp_count = round((forecast_years * 365 * 24) / dp_freq_hour)

        # get a time range with all required indices
        forecast_indices = pd.date_range(start=start_timestamp, periods=forecast_dp_count, freq=f"{dp_freq_hour}H") # type: ignore

        # create a series with all the same value
        prediction_series = Series([last_value]*forecast_dp_count, forecast_indices)

        return prediction_series