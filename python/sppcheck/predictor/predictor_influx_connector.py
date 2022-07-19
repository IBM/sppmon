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
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union


from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from influx.influx_queries import Keyword, SelectionQuery
from numpy import float64
from pandas import Series
from sppCheck.predictor.predictor_interface import PredictorInterface
from sppCheck.predictor.statsmodel_ets_predictor import \
    StatsmodelEtsPredictor
from utils.sppcheck_utils import SizingUtils
from utils.exception_utils import ExceptionUtils


class PredictorInfluxConnector:

    sppcheck_table_name: ClassVar[str] = "sppcheck_data"
    sppcheck_value_name: ClassVar[str] = "data"
    sppcheck_metric_tag: ClassVar[str] = "metric_name"
    sppcheck_group_tag: ClassVar[str] = "grouping_tag"
    sppcheck_group_tag_name: ClassVar[str] = "grouping_tag_name"

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

    def predict_data(
        self,
        table_name: str,
        value_or_count_key: str,
        description: str,
        metric_name: str,
        re_save_historic: bool,
        save_total: bool,
        group_tag: Optional[str] = None,
        use_count_query: bool = False
        ) -> None:

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
        result_list: List[Tuple[ # list: different tag groups
            Tuple[str, Optional[Dict[str, str]]], # tablename, dict of grouping tags (empty if not grouped)
            Generator[Dict[str, Any], None, None] # result of the selection query
        ]] = result.items() # type: ignore

        #                                # optional tag-dict    # list with dicts: values
        tag_data_tuple = list(map(lambda tuple: (tuple[0][1] , list(tuple[1])), result_list))

        if not tag_data_tuple:
            raise ValueError(f"No {description} is available within the InfluxDB.")

        #### Iterate over the results ####

        self.__prepare_predict_insert_iterate(
            tag_data_tuple=tag_data_tuple,
            description=description,
            metric_name=metric_name,
            group_tag=group_tag,
            re_save_historic=re_save_historic,
            save_total=save_total
        )

        # make sure to flush
        self.__influx_client.flush_insert_buffer()

    def __generate_query(self, table_name: str, value_key: str, group_tag: Optional[str]) -> SelectionQuery:

        table = self.__influx_client.database[table_name]

        fields = [f"{value_key} AS {self.sppcheck_value_name}"]
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


    def __prepare_predict_insert_iterate(self,
                               tag_data_tuple: List[Tuple[
                                                Optional[Dict[str, str]], # dict of grouping tags
                                                List[Dict[str, Any]] # result of the selection query
                               ]],
                               description: str,
                               metric_name: str,
                               group_tag: Optional[str],
                               re_save_historic: bool,
                               save_total: bool):


        total_historic_series: Series = Series(dtype=float64)
        for (tag_dict, data) in tag_data_tuple:
            try:

                if not data:
                    raise ValueError(f"Error: the result list is empty for {description}")

                # if grouped, the tag_dict 1. exists 2. contains tag_name: tag_value
                if group_tag and not tag_dict:
                    raise ValueError(f"Error: There is no grouping information available for {description} with example data {data[0]}")

                #### collect meta information for the re-insertion ####
                # get tags for the sppcheck_data table
                insert_tags: Dict[str, Optional[str]] = {
                    self.sppcheck_metric_tag: metric_name,
                    "site": data[0].get("site", None),
                    "siteName": data[0].get("siteName", None)
                }

                # add grouping and update site information
                if group_tag and tag_dict:
                    # if there is site in, dont save the grouping tag but the site metadata.
                    if "site" in group_tag: # this does also include "siteName" due to the "site"
                        # overwrites values from tag_dict
                        insert_tags.update(tag_dict)
                    else:

                        # issue: reserved identifiers like "name" require escapes in influx, but the result isn't escaped anymore
                        # therefore just take the value and avoid an access by tag_dict[group_tag], there should only be one
                        insert_tags[self.sppcheck_group_tag] = list(tag_dict.values())[0]
                        if len(tag_dict) > 1:
                            insert_tags[self.sppcheck_group_tag_name] = list(tag_dict.values())[1]
                        # must be grouped ID first, then name

                        # if multiple (countable) are allowed, add copies of the row below.

                #### extract the data for the prediction  ####

                try:
                    historic_values: Dict[int, Union[int, float]] = {x["time"]: x[self.sppcheck_value_name] for x in data}
                except KeyError as error:
                    ExceptionUtils.exception_info(error)
                    raise ValueError(f"Missing value key {self.sppcheck_value_name} in requested data from the InfluxDB. Is a \"AS\"-Clause missing in the query?")
                # prepare the data and set the frequency
                data_series = self.__predictorI.data_preparation(historic_values, self.__dp_interval_hour)

                # sum the individual results for a final total value
                if save_total:
                    # fill required for initial setup -> or everything is NaN
                    total_historic_series = total_historic_series.add(data_series, fill_value=0)

                # Count: The DB does not have historic data, since it is aggregated on query -> save it.
                # insert into new table with clear identification, not old one.
                if re_save_historic:
                    SizingUtils.insert_series(
                        self.__influx_client,
                        report_rp=self.__report_rp,
                        prediction_result=data_series,
                        table_name=self.sppcheck_table_name,
                        value_key=self.sppcheck_value_name,
                        insert_tags=insert_tags)

                #### predict data for the next x years ####

                prediction_result = self.__predictorI.predict_data(data_series, self.__forecast_years)
                # save the prediction with the new meta data
                SizingUtils.insert_series(
                    self.__influx_client,
                    report_rp=self.__report_rp,
                    prediction_result=prediction_result,
                    table_name=self.sppcheck_table_name,
                    value_key=self.sppcheck_value_name,
                    insert_tags=insert_tags)

            except ValueError as error:
                ExceptionUtils.exception_info(error, f"Skipping {description} group with {group_tag}={tag_dict}.")

        # only save if grouped, since then there are multiple series summed up
        if group_tag and save_total:

            insert_tags = {
                self.sppcheck_metric_tag: metric_name,
                self.sppcheck_group_tag: "Total",
                self.sppcheck_group_tag_name: "Total",
                "site": "Total",
                "siteName": "Total"}

            # insert summed historical data first
            SizingUtils.insert_series(
                self.__influx_client,
                report_rp=self.__report_rp,
                prediction_result=total_historic_series,
                table_name=self.sppcheck_table_name,
                value_key=self.sppcheck_value_name,
                insert_tags=insert_tags)

            # insert total data prediction
            prediction_result = self.__predictorI.predict_data(total_historic_series, self.__forecast_years)
            SizingUtils.insert_series(
                self.__influx_client,
                report_rp=self.__report_rp,
                prediction_result=prediction_result,
                table_name=self.sppcheck_table_name,
                value_key=self.sppcheck_value_name,
                insert_tags=insert_tags)
