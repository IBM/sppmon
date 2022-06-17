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

from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union


from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from influx.influx_queries import Keyword, SelectionQuery
from numpy import float64
from pandas import Series
from sppcheck.predictor.predictor_interface import PredictorInterface
from sppcheck.predictor.statsmodel_ets_predictor import \
    StatsmodelEtsPredictor
from utils.sppcheck_utils import SizingUtils
from utils.exception_utils import ExceptionUtils


class PredictorInfluxConnector:

    sppcheck_table_name: ClassVar[str] = "sppcheck_data"
    sppcheck_value_name: ClassVar[str] = "data"
    sppcheck_tag_name: ClassVar[str] = "data_type"

    @property
    def report_rp(self) -> RetentionPolicy:
        return self.__report_rp

    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                 select_rp: RetentionPolicy, rp_timestamp: str,
                 forecast_years: float) -> None:
        if not influx_client:
            raise ValueError("PredictorController is not available, missing the influx_client")
        self.__influx_client: InfluxClient = influx_client

        self.__predictorI: PredictorInterface = StatsmodelEtsPredictor()
        self.__dp_interval_hour = dp_interval_hour
        self.__select_rp = select_rp
        self.__forecast_years = forecast_years

        self.__report_rp = SizingUtils.create_unique_rp(self.__influx_client,"prediction", rp_timestamp)

    def __generate_query(self, table_name: str, value_key: str, group_tag: Optional[str]) -> SelectionQuery:

        table = self.__influx_client.database[table_name]

        fields = [value_key]
        # tags for re-insert information of the predicted data
        fields.extend(map('\"{}\"'.format, table.tags))

        if group_tag:
            group_list = [group_tag]
        else:
            group_list = None

        return SelectionQuery(
            Keyword.SELECT,
            table_or_query=table,
            alt_rp=self.__select_rp,
            fields=fields,
            order_direction="ASC",
            group_list=group_list
            )


    def __generate_count_query(self, table_name: str, group_tag: Optional[str], count_key: str) -> SelectionQuery:

        query_table = self.__influx_client.database[table_name]

        group_list = [f"time({self.__dp_interval_hour}h)"]
        if group_tag:
            group_list.append(group_tag)

        inner_query = SelectionQuery(
            Keyword.SELECT,
            table_or_query=query_table,
            alt_rp=self.__select_rp,
            fields=["*"],
            order_direction="ASC",
            )

        return SelectionQuery(
            Keyword.SELECT,
            table_or_query=inner_query,
            fields=[f"COUNT(DISTINCT({count_key})) AS {self.sppcheck_value_name}"],
            order_direction="ASC",
            group_list=group_list
            )


    def predict_data(
        self,
        table_name: str,
        value_or_count_key: str,
        description: str,
        group_tag: Optional[str] = None,
        data_type: Optional[str] = None,
        use_count_query: bool = False,
        no_grouped_total: bool = False) -> None:

        if use_count_query and not data_type:
            raise ValueError("using count query without saving into a new table is not allowed")

        #### Generate the query ###
        if use_count_query:
            history_query = self.__generate_count_query(
                table_name=table_name,
                group_tag=group_tag,
                count_key=value_or_count_key
            )
        else:
            history_query = self.__generate_query(
                table_name=table_name,
                value_key=value_or_count_key,
                group_tag=group_tag)

        #### Send the query #####

        result = self.__influx_client.send_selection_query(history_query)
        tag_tuples: List[Tuple[
            Tuple[str, Optional[Dict[str, str]]], # tablename, dict of grouping tags (empty if not grouped)
            Generator[Dict[str, Any], None, None] # result of the selection query
        ]] = result.items() # type: ignore

        if not tag_tuples:
            raise ValueError(f"No {description} is available within the InfluxDB.")

        #### Iterate over the results / single result ####

        # prepare variables for re-insert
        # if data_type is used, insert the data in a special SPPCheck table
        if data_type:
            insert_value_key = self.sppcheck_value_name
            replacement_tags = {self.sppcheck_tag_name:data_type}
            insert_table_name = self.sppcheck_table_name
        else:
            insert_value_key = value_or_count_key
            replacement_tags = {}
            insert_table_name = table_name

        # single result
        if not group_tag:
            # get the values out of the generator
            historic_values: Dict[int, Union[int, float]] = {x["time"]: x[insert_value_key] for x in tag_tuples[0][1]}
            data_series = self.__predictorI.data_preparation(historic_values, self.__dp_interval_hour)

            prediction_result = self.__predictorI.predict_data(data_series, self.__forecast_years)

            SizingUtils.insert_series(
                self.__influx_client,
                self.__report_rp,
                prediction_result,
                insert_table_name,
                insert_value_key,
                replacement_tags)

        else: # grouped result

            total_historic_series: Series = Series(dtype=float64)
            for ((_, tag_dict), data) in tag_tuples:
                try:
                    result_list = list(data)

                    # retain tags for re-insertion into insert-table, only take them if they are tags
                    instance_tags = {k:v for (k,v) in result_list[0].items() if k in self.__influx_client.database[insert_table_name].tags}
                    # in count clause the grouped tag is not always included -> add it
                    if tag_dict:
                        instance_tags.update(tag_dict)

                    try:
                        historic_values: Dict[int, Union[int, float]] = {x["time"]: x[insert_value_key] for x in result_list}
                    except KeyError as error:
                        ExceptionUtils.exception_info(error)
                        raise ValueError(f"Missing value key {insert_value_key} in requested data from the InfluxDB. Is a \"AS\"-Clause missing in the query?")
                    data_series = self.__predictorI.data_preparation(historic_values, self.__dp_interval_hour)

                    if not no_grouped_total:
                        # fill required for initial setup -> or everything is NaN
                        total_historic_series = total_historic_series.add(data_series, fill_value=0)

                    # if it is a count, save the old values to have the aggregated values
                    # only count: Other values are directly available
                    if use_count_query and data_type:
                        SizingUtils.insert_series(
                            self.__influx_client,
                            self.__report_rp,
                            data_series,
                            insert_table_name,
                            insert_value_key,
                            instance_tags | replacement_tags)

                    # predict next x years
                    prediction_result = self.__predictorI.predict_data(data_series, self.__forecast_years)
                    SizingUtils.insert_series(
                        self.__influx_client,
                        self.__report_rp,
                        prediction_result,
                        insert_table_name,
                        insert_value_key,
                        instance_tags | replacement_tags) # python 3.9 feature: merge of two dicts

                except ValueError as error:
                    ExceptionUtils.exception_info(error, f"Skipping {description} group with {group_tag}={tag_dict}.")

            if not no_grouped_total:
                # insert summed historical data first
                SizingUtils.insert_series(
                    self.__influx_client,
                    self.__report_rp,
                    total_historic_series,
                    insert_table_name,
                    insert_value_key,
                    replacement_tags)

                # insert total data prediction
                prediction_result = self.__predictorI.predict_data(total_historic_series, self.__forecast_years)
                SizingUtils.insert_series(
                    self.__influx_client,
                    self.__report_rp,
                    prediction_result,
                    insert_table_name,
                    insert_value_key,
                    replacement_tags)


        self.__influx_client.flush_insert_buffer()
