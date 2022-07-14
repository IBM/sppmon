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
 SpIteratorUtils
 SpRestClientUtils
"""
import logging

from io import StringIO
from typing import Tuple, Dict, Any, List, Optional

from spmonMethods.sp_dataclasses import SpRestResponsePage, SpRestQuery
from utils.sp_utils import SpUtils

LOGGER = logging.getLogger("spmon")


class SpRestClientUtils:
    """Wrapper for methods used by SpRestClient.

    Methods:
        - build_response_dataclass - Builds and returns SpRestResponsePage object using provided parameters
    """
    @classmethod
    def build_response_dataclass(cls,
                                 response_json: Dict[str, Any],
                                 query_id: str,
                                 target_server: str) -> SpRestResponsePage:
        """Takes json formatted response from REST API endpoint and returns dataclass holding its values.

        Args:
            response_json {Dict[str, Any]: JSON formatted response received from the OC
            query_id {str}:  Query identifier. Key in the spqueries.json file.
            target_server: Server that query is routed to.

        Returns:
            {SpRestResponsePage} - Dataclass object representing response from target server
        """
        response_dataclass: SpRestResponsePage = SpUtils.build_dataclass_from_dict(
            dataclass=SpRestResponsePage,
            param_dict=response_json
        )
        response_dataclass.query_id = query_id
        response_dataclass.host = target_server
        return response_dataclass

    @classmethod
    def build_query_dataclass(cls,
                              query_params: Dict[str, Any],
                              query_id: str,
                              override_server_list: Optional[List[str]] = None) -> SpRestQuery:
        query_dataclass: SpRestQuery = SpUtils.build_dataclass_from_dict(
            dataclass=SpRestQuery,
            param_dict=query_params
        )
        query_dataclass.query_id = query_id

        # Replace target servers with discovered servers if setting is enabled
        if override_server_list:
            query_dataclass.target_servers = override_server_list
        else: # Append none to empty lists (with no override). Hub server is queried.
            if len(query_dataclass.target_servers) == 0:
                query_dataclass.target_servers.append(None)

        return query_dataclass


class SpIteratorUtils:
    """Wrapper for methods used by SpRestIterator.

    The templated used for pagination adds a row number to records associated with a user-defined
    query. It then selects a window from the set of those results.

    Methods:
        init_paginated_query - Builds statement StringIO object containing query, template header and footer
        set_query_page_value - Update statement StringIO object with new page values and read only clause
    """
    PAGINATED_QUERY_TEMPLATE_HEADER: str = "SELECT * FROM (SELECT *, Row_number() OVER() AS rowid FROM("
    PAGINATED_QUERY_TEMPLATE_FOOTER: str = ")) WHERE rowid "
    PAGINATED_QUERY_READ_ONLY_CLAUSE: str = " FOR READ ONLY WITH UR"

    @classmethod
    def init_paginated_query(cls,
                             query: str) -> Tuple[StringIO, int]:
        """Writes template header, user-defined query and footer to a StringIO object. Returns it and the
        index of the last character in the StringIO object.

        Args:
            query {str}: User-defined query. SpMon loads it from spqueries.json.

        Returns:
            {Tuple[StringIO, int]} - Tuple containing StringIO object of formatted query and index of last character.
        """
        base_statement = StringIO()
        base_statement.write(
            cls.PAGINATED_QUERY_TEMPLATE_HEADER
            + query
            + cls.PAGINATED_QUERY_TEMPLATE_FOOTER
        )
        end_index = base_statement.tell()
        return base_statement, end_index

    @classmethod
    def set_query_page_value(cls,
                             statement: StringIO,
                             insertion_index: int,
                             starting_record: int,
                             page_size: int) -> None:
        """Appends a clause specifying page value (BETWEEN STARTING_RECORD AND ENDING_RECORD) to a
        provided StringIO object.

        Args:
            statement {str}: Previously formatted StringIO object containing template footer/header and query.
            insertion_index: Index at which to insert BETWEEN clause
            starting_record: Row number of the first record of the current page
            page_size: Maximum number of records query should retrieve
        """
        pagination_clause = f"BETWEEN {starting_record} AND {(ending_record := starting_record + page_size - 1)}"
        statement.truncate(insertion_index)
        statement.seek(insertion_index)
        statement.write(pagination_clause)

    @classmethod
    def set_query_read_only_clause(cls,
                                   statement: StringIO) -> None:
        """Appends read only clause to previously formatted StringIO statement.

        Args:
            statement: Previously formatted StringIO object containing template footer/header, query and page values.
        """
        statement.write(cls.PAGINATED_QUERY_READ_ONLY_CLAUSE)

