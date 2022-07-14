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
 SpRestIterator
 SpRestClient
"""
import _io
import logging
import json

from enum import Enum, unique
from io import StringIO

import requests.exceptions
from requests import post
from spmonMethods.sp_dataclasses import SpServerParams, SpRestResponsePage
from typing import Dict, Any, Tuple, List, Optional
from utils.connection_utils import ConnectionUtils
from utils.sp_connection_utils import SpRestClientUtils, SpIteratorUtils
from utils.sp_utils import SpUtils

import urllib3
# NOTE: This should be removed once in production. Added to suppress warnings during testing.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOGGER = logging.getLogger("spmon")


@unique
class RestResponseArray(Enum):
    """
    Represents a subset of the expected response from the OC. Results can be returned in
    a dictionary containing headers (columns), items (key, pair values) or messages (not
    used in the tool).
    """
    HEADERS: str = 'hdr'
    ITEMS: str = 'items'


class SpRestClient:
    """Queries the OC hub server defined in spconnections_default.conf. Each query
    is routed to connected spoke servers defined in the "target_servers" list of
    spqueries.json.

    Methods:
        discover_spoke_servers - Get list which includes hub server and all attached spoke servers
        get_url - Builds endpoint to communicate with hub or spoke servers.
        query_url - Sends provided query to a specified OC server as POST data and retrieves the response.
        get_objects - Gets all possible pages of records from a specified server for a specified query.

    TODO:
        - Implement feature to discover spoke servers rather than explicitly
          listing them as target servers.
        - Implement further configuration options.
        - Delineate verbose & non-verbose logging.
    """
    DB2_IN_PROGRESS: str = "timestamp('1956-09-05-00.00.00.000000')"
    """Timestamp value of active processes, also returned as -1"""

    ENDPOINT: str = "/oc/api/cli/issueConfirmedCommand"
    """Endpoint appended to the address:port value of the hub server"""

    POST_HEADERS: Dict[str, str] = {
        'OC-API-Version': '1.0',
        'Accept': 'application/json, application/xml',
        'Content-Type': 'text/plain'
    }
    """Headers necessary for communication with the OC"""

    def __init__(self,
                 server_params: SpServerParams,
                 starting_page_size: int,
                 discover_target_servers: bool):
        """Initializes SpRestClient. Login/disconnect not necessary.
        
        Args:
            server_params {SpServerParams}: Dataclass containing connection parameters for OC hub server.
            starting_page_size {int}: Number of records per page of response.
        """
        LOGGER.info("Initializing SpRestClient")

        self.server_params: SpServerParams = server_params
        self.page_size: int = starting_page_size
        self.discover_target_servers: bool = discover_target_servers
        self.override_server_list: Optional[List[str]] = None

        if discover_target_servers:
            self.override_server_list = self.discover_spoke_servers()


    def discover_spoke_servers(self) -> List[str]:
        """Queries hub server for all attached spoke servers. Appends results to a list, which
        includes the hub servers, which is returned.

        Returns:
            {List[str]} - List containing names of spoke servers and "None", representing hub server

        """
        LOGGER.info("Querying hub server for spoke servers.")
        query: str = "SELECT SERVER_NAME FROM SERVERS"
        query_results: SpRestResponsePage

        query_results, _ = self.query_url(
            query_id="DISCOVERY",
            target_server=None,
            query=query
        )

        target_servers = []
        for record in query_results.items:
            for _, server_name in record.items():
                target_servers.append(server_name)
        target_servers.append(None)
        LOGGER.info(f"Discovered servers: {target_servers}")
        return target_servers

    def get_url(self,
                target_server: str = None) -> str:
        """Builds URL to connect with either specified target server or hub server.

        Args:
            target_server {str}: Spoke server (if any) to connect to.

        Returns:
            str: URL pointing to either hub server or connected spoke server.
        """
        server = f"/{target_server}" if target_server else ""
        return f"https://{self.server_params.srv_address}:{self.server_params.srv_port}{self.ENDPOINT}{server}"

    def query_url(self,
                  query: str,
                  query_id: str,
                  target_server: str = None) -> Tuple[SpRestResponsePage, float]:
        """Sends query as POST data to the target server. Builds and returns a dataclass
        (SpRestResponsePage) from the response. The dataclass contains one page (defined in
        self.page_size) of records.

        Args:
            query {str}: Query to send to target server.
            query_id {str}: Query identifier. Key in the spqueries.json file.
            target_server {str}: Server that query is routed to. If none, then hub is queried. (default: {False})

        Raises:
            ValueError: Response from OC is not 200 (OK)
            ValueError: Unable to parse response from OC
            ValueError: Response from OC contains no records or data other than records

        Returns:
            Tuple[SpResponsePage, float] -- Dataclass of response and the measured send time.

        TODO:
            - Add validation for parameters
            - Implement retries for failed queries.
            - Implement logic for handling for timeouts
            - Implement exception handling for failed connections
        """
        url: str = self.get_url(target_server)

        LOGGER.info(f"[{query_id}] Retrieving records from: {url}")

        # TODO: Set timeout as user defined value
        try:
            response_query = post(
                url=url,
                data=query,
                headers=self.POST_HEADERS,
                auth=(self.server_params.username, self.server_params.password),
                verify=False,
                timeout=120
            )
            send_time = response_query.elapsed.total_seconds()
            LOGGER.info(f"[{query_id}] Received response in {send_time} seconds.")
        except requests.exceptions.Timeout as error:
            raise ConnectionUtils.rest_response_error(
                response_query,
                "Timeout has occurred.",
                url
            )

        if not response_query.ok:
            raise ConnectionUtils.rest_response_error(
                response_query,
                "Wrong status code when requesting endpoint data",
                url
            )

        try:
            response_json: List[List[Dict[str, Any]]] = response_query.json()
        except (json.decoder.JSONDecodeError, ValueError) as error:
            raise ValueError(f"[{query_id}] Failed to parse response from {target_server}", response_query)

        try:
            response_json: Dict[str, Any] = SpUtils.get_top_level_dict(response_json)
        except ValueError as empty_response_error:
            raise ValueError("Rest response json contains no records")

        if not response_json.get("items"):
            raise ValueError("Rest response json contains no records")

        # Server address is added to as host name if we are only querying hub server (no target servers)
        response_page: SpRestResponsePage = SpRestClientUtils.build_response_dataclass(
            query_id=query_id,
            target_server=target_server if target_server else self.server_params.srv_address,
            response_json=response_json
        )

        return response_page, send_time

    def get_objects(self,
                    query: str,
                    query_id: str,
                    target_server: str = None,
                    add_time_stamp: bool = False) -> List[SpRestResponsePage]:
        """Issues provided query against specified target server and receives a paginated
        response. The response contains all records applicable to the defined query.

        Args:
            query {str}: Query to send to the target server
            query_id {str}: Query identifier. Key in the spqueries.json file.
            target_server {str}: Server that query is routed to. If none, then hub is queried. (default: {None})
            add_time_stamp {bool}: Whether to add capture timestamp (default: {False})

        Returns:
            {List[SpResponsePage]}: List of all pages of records for the query from the target server.

        TODO:
            - Add validation for parameters
            - Extract logic for appending tool defined timestamp to records
            - Implement logic for adjusting page size dynamically
        """

        responding_server = target_server if target_server else self.server_params.srv_address
        result_list: List[SpRestResponsePage] = []
        query_iterator = SpRestIterator(
            query=query,
            query_id=query_id,
            rest_client=self,
            target_server=target_server
        )

        LOGGER.info(f"[{query_id}] Getting all objects from server: {responding_server}.")

        for page, send_time in query_iterator:
            if add_time_stamp:
                for record in page.items:
                    time_key, time_val = SpUtils.get_capture_timestamp_sec()
                    record[time_key] = time_val

            result_list.append(page)

        LOGGER.info(f"[{query_id}] Retrieved {len(result_list)} total page(s) server: {responding_server}")

        return result_list


class SpRestIterator:
    """Used to paginate the response received from the REST API endpoint. Currently, pagination
    is a function of a template used to wrap the user defined query.

    Methods:
        - update_base_statement - Update query with current page of record request & read only clause

    TODO:
        - Add validation for parameters passed to all methods
    """

    def __init__(self,
                 query: str,
                 query_id: str,
                 rest_client: SpRestClient,
                 target_server: str = None):
        """Initializes SpRestIterator. Wraps user defined query within a template header and
        footer that allows for pagination. Template is inserted into a StringIO object, which
        is updated with next page values.

        Args:
            query {str}: Query to send to the target server
            query_id {str}: Query identifier. Key in the spqueries.json file.
            rest_client {SpRestClient}: SpRestClient initialized by SpMon
            target_server {str}: Server that query is routed to. If none, then hub is queried. (default: {None})
        """
        self.base_statement_eol: int = 0
        """Index position of the last element of the string containing: (template header) + (query) """
        self.current_record: int = 1
        """Row number of the first record of the current page"""
        self.statement: StringIO
        """Object holding the user defined query wrapped in template components"""

        self.query: str = query
        self.query_id: str = query_id
        self.rest_client: SpRestClient = rest_client
        self.target_server: str = target_server

        # Wrap user defined query in template header and footer. Cap with read only clause.
        self.statement, self.base_statement_eol = SpIteratorUtils.init_paginated_query(query=self.query)
        self._update_base_statement()

    def _update_base_statement(self) -> None:
        """Drops previous page values and read only clause from the statement. Then, appends updated page
        values and read only clause.
        """
        SpIteratorUtils.set_query_page_value(
            statement=self.statement,
            insertion_index=self.base_statement_eol,
            starting_record=self.current_record,
            page_size=self.rest_client.page_size
        )
        SpIteratorUtils.set_query_read_only_clause(statement=self.statement)

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[SpRestResponsePage, float]:
        """Queries target server, requesting records for an incrementing page value
        until no responses are received. This can occur on the first response. Iteration
        will stop if any error is encountered.

        Returns:
            {Tuple[SpRestResponsePage, float]} - Returns a page of records from the target server and response time.
        """
        responding_server = self.target_server if self.target_server else self.rest_client.server_params.srv_address

        # Do not continue if last page was not full
        if self.current_record != 1 and (self.current_record - 1) % self.rest_client.page_size != 0:
            LOGGER.info(f"[{self.query_id}] Exiting iterator. Received all available records from {responding_server}.")
            raise StopIteration

        LOGGER.info(f"[{self.query_id}] Attempting to retrieve records from {responding_server}. "
                    + f"Current Record: {self.current_record}. "
                    + f"Page Size: {self.rest_client.page_size}")

        try:
            response_dataclass, send_time = self.rest_client.query_url(
                query=self.statement.getvalue(),
                query_id=self.query_id,
                target_server=self.target_server
            )
        except ValueError as empty_response_error:
            LOGGER.info(f"[{self.query_id}] Exiting iterator. Received response from "
                        + f"{responding_server}: {empty_response_error}")
            raise StopIteration

        # self.current_record += self.rest_client.page_size
        self.current_record += len(response_dataclass.items)
        self._update_base_statement()

        LOGGER.info(f"[{self.query_id}] Retrieved {len(response_dataclass.items)} record(s) from {responding_server}")
        return response_dataclass, send_time
