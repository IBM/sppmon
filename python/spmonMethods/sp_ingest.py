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

Author (SppMon):
 Niels Korchinsky

Author (SpMon):
 Daniel Boros
 James Damgar
 Rob Elder
 Sean Jones
 Raymond Shum

Description:
 TODO: Add description

Classes:
 TODO: Add Classes
"""
import logging

from spInflux.sp_influx_client import SpInfluxClient
from spConnection.sp_rest_client import SpRestClient
from spmonMethods.sp_dataclasses import SpRestQuery, SpInfluxTableDefinition, SpRestResponsePage
from utils.sp_connection_utils import SpRestClientUtils
from typing import Any, Dict, List, Optional
from utils.sp_utils import SpUtils

LOGGER = logging.getLogger("spmon")


class SpIngestMethods:
    """TODO:
        - UPDATE DESCRIPTION
        - Further refactor logic
    """

    def __init__(self,
                 influx_client: SpInfluxClient,
                 rest_client: SpRestClient):
        self.__rest_client: SpRestClient = rest_client
        self.__influx_client: SpInfluxClient = influx_client
        self.influx_table_definitions: Optional[Dict[str, SpInfluxTableDefinition]] = None
        self.query_definitions: Optional[List[SpRestQuery]] = None

    def load_definitions(self, queries_file: Dict[str, Any]):
        self.influx_table_definitions = {}
        self.query_definitions = []

        # Table and Query definitions are assigned query_id as key
        for query_id, query_params in queries_file.items():

            # Load query definitions
            query_dataclass: SpRestQuery = SpRestClientUtils.build_query_dataclass(
                query_params=query_params,
                query_id=query_id,
                override_server_list=self.__rest_client.override_server_list
            )
            self.query_definitions.append(query_dataclass)

            # Load table definition
            table_dataclass: SpInfluxTableDefinition = SpUtils.build_dataclass_from_dict(
                dataclass=SpInfluxTableDefinition,
                param_dict=query_params
            )
            self.influx_table_definitions[query_id] = table_dataclass

    def cache_user_queries(self):

        # Get responses for all user defined queries
        for query_definition in self.query_definitions:

            # Get all responses for each target server
            for target_server in query_definition.target_servers:

                response: List[SpRestResponsePage] = self.__rest_client.get_objects(
                    target_server=target_server,
                    query_id=query_definition.query_id,
                    query=query_definition.query
                )

                # Send all pages to influxdb
                for page in response:
                    table_definition = self.influx_table_definitions.get(query_definition.query_id)
                    self.__influx_client.insert_dicts_to_buffer(
                        table_definition=table_definition,
                        paginated_records=page
                    )
