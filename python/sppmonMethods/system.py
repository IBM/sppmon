"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2020, 2021. All Rights Reserved.

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
    This Module provides all functionality around the spp-system itself.
    You may implement new system methods in here.

Classes:
    SystemMethods
"""
import logging

import re
from typing import Union, Optional, Dict, Any

from utils.exception_utils import ExceptionUtils
from utils.methods_utils import MethodUtils
from sppConnection.api_queries import ApiQueries
from influx.influx_client import InfluxClient
from influx.influx_queries import SelectionQuery, Keyword

LOGGER = logging.getLogger("sppmon")

class SystemMethods:
    """Wrapper for all spp-system related functionality. You may implement new methods in here.

    Methods:
        sppcatalog - Saves the spp filesystem catalog information in the influxdb.
        cpuram - Saves the cpu and ram usage of the spp system.
        site_name_by_id - Returns a site_name by a associated site_id.
        sites - Collects all site information including throttle rate.

    """

    def __init__(self, influx_client: Optional[InfluxClient], api_queries: Optional[ApiQueries], verbose: bool = False):
        if(not influx_client):
            raise ValueError("System Methods are not available, missing influx_client.")
        if(not api_queries):
            raise ValueError("System Methods are not available, missing api_queries.")
        self.__influx_client = influx_client
        self.__api_queries = api_queries
        self.__verbose = verbose

        # filled by `sites` or `site_name_by_id`
        self.__site_name_dict: Dict[int, str] = {}

    def sppcatalog(self) -> None:
        """Saves the spp filesystem catalog information."""
        result = MethodUtils.query_something(
            name="sppcatalog stats",
            source_func=self.__api_queries.get_file_system,
            deactivate_verbose=True
        )

        # This is not a key value, but a value rename
        # Therefore the regular rename-tuples do not work.
        value_renames = {
            'Configuration':            "Configuration",
            'Search':                   "File",
            'System':                   "System",
            'Catalog':                  "Recovery"
        }
        for row in result:
            row['name'] = value_renames[row['name']]

        if(self.__verbose):
            MethodUtils.my_print(result)
        self.__influx_client.insert_dicts_to_buffer("sppcatalog", result)

    def cpuram(self) -> None:
        """Saves the cpu and ram usage of the spp system."""
        table_name = 'cpuram'

        result = MethodUtils.query_something(
            name=table_name,
            rename_tuples=[
                ('data.size', 'dataSize'),
                ('data.util', 'dataUtil'),
                ('data2.size', 'data2Size'),
                ('data2.util', 'data2Util'),
                ('data3.size', 'data3Size'),
                ('data3.util', 'data3Util'),
                ('memory.size', 'memorySize'),
                ('memory.util', 'memoryUtil'),
            ],
            source_func=self.__api_queries.get_server_metrics
        )
        self.__influx_client.insert_dicts_to_buffer(table_name=table_name, list_with_dicts=result)

    def site_name_by_id(self, site_id: Union[int, str]) -> Optional[str]:
        """Returns a site_name by a associated site_id.

        Uses a already buffered result if possible, otherwise queries the influxdb for the name.

        Arguments:
            site_id {Union[int, str]} -- id of the site

        Returns:
            Optional[str] -- name of the site, None if not found.
        """
        if(site_id is None):
            ExceptionUtils.error_message("siteId is none, returning None")
            return None
        # if string, parse to int
        if(isinstance(site_id, str)):
            site_id = site_id.strip(" ")
            if(re.match(r"\d+", site_id)):
                site_id = int(site_id)
            else:
                ExceptionUtils.error_message("siteId is of unsupported string format")
                return None
        # if still not int, error
        if(not isinstance(site_id, int)):
            ExceptionUtils.error_message("site id is of unsupported type")
            return None

        # return if already saved -> previous call or `sites`-call
        result = self.__site_name_dict.get(site_id, None)
        if(result is not None): # empty str allowed
            return result

        table_name = 'sites'
        table = self.__influx_client.database[table_name]
        query = SelectionQuery(
            keyword=Keyword.SELECT,
            table_or_query=table,
            # description, throttleRates cause we need a field to query
            fields=["siteId", "siteName", "description", "throttleRates"],
            where_str=f"siteId = \'{site_id}\'",
            order_direction="DESC",
            limit=1
        )
        result_set = self.__influx_client.send_selection_query(query) # type: ignore
        result_dict: Dict[str, Any] = next(result_set.get_points(), None) # type: ignore
        if(not result_dict):
            ExceptionUtils.error_message(f"no site with the id {site_id} exists")
            return None

        # save result and return it
        result = result_dict['siteName']
        self.__site_name_dict[site_id] = result
        return result

    def sites(self) -> None:
        """Collects all site information including throttle rate.

        This information does not contain much statistic information.
        It should only be called if new sites were added or changed.
        """
        table_name = 'sites'

        result = MethodUtils.query_something(
            name=table_name,
            source_func=self.__api_queries.get_sites,
            rename_tuples=[
                ('id', 'siteId'),
                ('name', 'siteName'),
                ('throttles', 'throttleRates')
            ]
            )
        LOGGER.debug(f"sites: {result}")
        # save results into internal storage to avoid additional request for ID's
        # used instead of `site_name_by_id`
        for row in result:
            self.__site_name_dict[row['siteId']] = row['siteName']
            # explicit none check since [] also needs to be converted into str
            if(row['throttleRates'] != None):
                row['throttleRates'] = str(row['throttleRates'])

        self.__influx_client.insert_dicts_to_buffer(table_name=table_name, list_with_dicts=result)
