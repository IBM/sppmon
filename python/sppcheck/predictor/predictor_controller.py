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

from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from sppcheck.predictor.predictor_influx_connector import \
    PredictorInfluxConnector
from utils.exception_utils import ExceptionUtils


class PredictorController:

    @property
    def report_rp(self):
        return self.__report_rp

    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                 select_rp: RetentionPolicy, rp_timestamp: str,
                 forecast_years: float) -> None:
        if not influx_client:
            raise ValueError("PredictorController is not available, missing the influx_client")

        self.__predictor_influx_connector = PredictorInfluxConnector(
            influx_client,
            dp_interval_hour,
            select_rp,
            rp_timestamp,
            forecast_years
        )
        self.__report_rp = self.__predictor_influx_connector.report_rp

    def predict_all_data(self):

        function_list = [
            self.__predict_physical_capacity_wr,
            self.__predict_vsnap_quantity,
            self.__predict_total_vadp_quantity,
            self.__predict_total_server_memory,
            self.__predict_used_server_memory,
            self.__predict_server_catalogs,
        ]

        for function in function_list:
            try:
                function()
            except ValueError as error:
                ExceptionUtils.exception_info(error, f"Error when predicting {function.__name__}, skipping it.")

    def __predict_physical_capacity_wr(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="storages",
            value_or_count_key="used",
            description="Storage data",
            group_tag="storageId",

            ##
            data_type=None,
            use_count_query=False,
            no_grouped_total=False
        )

    def __predict_vsnap_quantity(self):
        self.__predictor_influx_connector.predict_data(
            table_name="storages",
            value_or_count_key="storageId",
            description="vSnap count",
            group_tag="site, siteName",
            data_type="vsnap_count",
            use_count_query=True,

            ##
            no_grouped_total=False
        )

    def __predict_total_vadp_quantity(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="vadps",
            value_or_count_key=f"count AS {PredictorInfluxConnector.sppcheck_value_name}", # unused
            description="total VADP count",
            group_tag="site, siteName",
            data_type="vadp_total_count",
            use_count_query=False,

            #
            no_grouped_total=False
        )

    def __predict_total_server_memory(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="cpuram",
            value_or_count_key="memorySize",
            description="total server memory",

            #
            group_tag=None,
            data_type=None,
            use_count_query=False,
            no_grouped_total=False
        )

    def __predict_used_server_memory(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="cpuram",
            value_or_count_key=f"memorySize * memoryUtil as {PredictorInfluxConnector.sppcheck_value_name}",
            description="used server memory",
            data_type="server_used_memory",

            #
            group_tag=None,
            use_count_query=False,
            no_grouped_total=False
        )

    def __predict_server_catalogs(self) -> None:
        self.__predictor_influx_connector.predict_data(
            table_name="sppcatalog",
            value_or_count_key="usedSize",
            description="server catalogs",
            group_tag="\"name\"",
            no_grouped_total=True,

            #
            data_type=None,
            use_count_query=False,
        )
