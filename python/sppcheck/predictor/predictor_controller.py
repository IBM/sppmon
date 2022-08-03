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

from datetime import datetime
import logging
from typing import ClassVar
from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from sppCheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from utils.exception_utils import ExceptionUtils
from utils.sppcheck_utils import SppcheckUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class PredictorController:

    rp_prefix: ClassVar[str] = "prediction"

    @property
    def report_rp(self):
        return self.__report_rp


    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                 select_rp: RetentionPolicy, rp_timestamp: str,
                 forecast_years: float, start_date: datetime) -> None:
        if not influx_client:
            raise ValueError("PredictorController is not available, missing the influx_client")

        self.__report_rp = SppcheckUtils.create_unique_rp(influx_client, self.rp_prefix, rp_timestamp)

        LOGGER.debug(f"> Using report RP {self.__report_rp}")

        self.__predictor_influx_connector = PredictorInfluxConnector(
            influx_client,
            dp_interval_hour,
            select_rp,
            self.__report_rp,
            forecast_years,
            start_date,
        )

    def predict_all_data(self):

        LOGGER.info("> Starting the prediction of all metrics.")

        function_list = [
            self.__predict_physical_capacity,
            self.__predict_physical_pool_size,
            self.__predict_vsnap_quantity,
            self.__predict_total_vadp_quantity,
            self.__predict_total_server_memory,
            self.__predict_used_server_memory,
            self.__predict_used_server_catalogs,
            self.__predict_total_server_catalogs
        ]

        for function in function_list:
            try:
                function()
            except ValueError as error:
                ExceptionUtils.exception_info(error, f"IMPORTANT: Error when predicting {function.__name__}, skipping it.")

        LOGGER.info("Completed the prediction of all metrics.")

    def __predict_physical_capacity(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="storages",
            value_or_count_key="used",
            description="Storage used capacity",
            group_tags=["storageId", "hostAddress"],
            metric_name="physical_capacity",
            save_total=True,

            ##
            use_count_query=False,
            #re_save_historic=False # Changed due to the report-generation accessing only one RP.
            re_save_historic=True,
            repeat_last=False
        )

    def __predict_physical_pool_size(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="storages",
            value_or_count_key="total",
            description="Storage pool size",
            group_tags=["storageId", "hostAddress"],
            metric_name="physical_pool_size",
            save_total=True,
            repeat_last=True,

            ##
            use_count_query=False,
            #re_save_historic=False # Changed due to the report-generation accessing only one RP.
            re_save_historic=True
        )

    def __predict_vsnap_quantity(self):
        self.__predictor_influx_connector.predict_data(
            table_name="storages",
            value_or_count_key="storageId",
            description="vSnap count",
            group_tags=["site", "siteName"],
            metric_name="vsnap_count",
            use_count_query=True,
            re_save_historic=True,
            save_total=True,
            repeat_last=True
        )

    def __predict_total_vadp_quantity(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="vadps",
            value_or_count_key=f"count", # unused
            description="total VADP count",
            group_tags=["site", "siteName"],
            metric_name="vadp_count_total",
            re_save_historic=True,
            save_total=True,
            repeat_last=True,

            #

            use_count_query=False,

        )

    def __predict_total_server_memory(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="cpuram",
            value_or_count_key="memorySize",
            description="total server memory",
            metric_name="total_server_memory",
            repeat_last=True,

            #
            group_tags=None,
            use_count_query=False,
            #re_save_historic=False # Changed due to the report-generation accessing only one RP.
            re_save_historic=True,
            save_total=False
        )

    def __predict_used_server_memory(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="cpuram",
            value_or_count_key="memorySize * memoryUtil",
            description="used server memory",
            metric_name="used_server_memory",
            re_save_historic=True,

            #
            group_tags=None,
            use_count_query=False,
            save_total=False
        )

    def __predict_used_server_catalogs(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="sppcatalog",
            value_or_count_key="usedSize",
            description="used server catalogs",
            group_tags=["\"name\""],
            metric_name="used_server_catalogs",
            save_total=False,

            #
            use_count_query=False,
            #re_save_historic=False # Changed due to the report-generation accessing only one RP.
            re_save_historic=True
        )

    def __predict_total_server_catalogs(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="sppcatalog",
            value_or_count_key="totalSize",
            description="total server catalogs",
            group_tags=["\"name\""],
            metric_name="total_server_catalogs",
            save_total=False,
            repeat_last=True,

            #
            use_count_query=False,
            #re_save_historic=False # Changed due to the report-generation accessing only one RP.
            re_save_historic=True
        )
