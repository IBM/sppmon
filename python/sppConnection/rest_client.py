"""This module provides the rest client which allows a connection to the REST-API of the SPP-Server.

Classes:
    RestClient
"""
from __future__ import annotations

import json
import logging
import time
from enum import Enum, unique
from typing import Any, Dict, List, Optional, Tuple

from requests import get, post, delete
from requests.auth import HTTPBasicAuth
from requests.exceptions import ReadTimeout, RequestException
from requests.models import Response
from requests.packages.urllib3 import disable_warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from utils.connection_utils import ConnectionUtils
from utils.execption_utils import ExceptionUtils
from utils.spp_utils import SppUtils

LOGGER = logging.getLogger("sppmon")
# TODO: Remove this once in production!
disable_warnings(InsecureRequestWarning)

@unique
class RequestType(Enum):
    GET = "GET"
    POST = "POST"

class RestClient():
    """Provides access to the REST-API. You need to login before using it.

    Methods:
        login - Logs in into the REST-API. Call this before using any methods.
        logout - Logs out of the REST-API.
        get_spp_version_build - queries the spp version and build number.
        get_objects - Querys a response(-list) from a REST-API endpoint or URI.
        post_data - Queries endpoint by a POST-Request.

    """


    __headers = {
        'Accept':       'application/json',
        'Content-type': 'application/json'}
    """Headers send to the REST-API. SessionId added after login."""

    def __init__(self, config_file: Dict[str, Any],
                 initial_connection_timeout: float,
                 pref_send_time: int,
                 request_timeout: int | None,
                 max_send_retries: int,
                 starting_page_size: int,
                 min_page_size: int,
                 verbose: bool):

        if(not config_file):
            raise ValueError("A config file is required to setup the InfluxDB client.")

        auth_rest = SppUtils.get_cfg_params(
            param_dict=config_file,
            param_name="sppServer")
        if(not isinstance(auth_rest, dict)):
            raise ValueError("The REST-API config is corrupted within the file: Needs to be a dictionary.")

        self.__timeout = request_timeout
        self.__initial_connection_timeout = initial_connection_timeout

        self.__preferred_time = pref_send_time
        self.__page_size = starting_page_size
        self.__min_page_size = min_page_size
        self.__max_send_retries = max_send_retries

        self.__verbose = verbose
        try:
            self.__username: str = auth_rest["username"]
            self.__password: str = auth_rest["password"]
            self.__srv_address: str = auth_rest["srv_address"]
            self.__srv_port: int = auth_rest["srv_port"]
        except KeyError as error:
            raise ValueError("Not all REST-API Parameters are given", auth_rest) from error

        self.__sessionid: str = ""
        self.__srv_url: str = ""

    def login(self) -> None:
        """Logs in into the REST-API. Call this before using any methods.

        Sets up the sessionId and the server URL.

        Raises:
            ValueError: Login was not sucessfull.
        """
        http_auth: HTTPBasicAuth = HTTPBasicAuth(self.__username, self.__password)
        self.__srv_url = f"https://{self.__srv_address}:{self.__srv_port}"
        login_url = self.get_url("/api/endeavour/session")

        LOGGER.debug(f"login to SPP REST API server: {self.__srv_url}")
        if(self.__verbose):
            LOGGER.info(f"login to SPP REST API server: {self.__srv_url}")
        try:
            (response_json, _) = self.query_url(url=login_url, auth=http_auth, request_type=RequestType.POST)
        except ValueError as error:
            ExceptionUtils.exception_info(error=error)
            ExceptionUtils.error_message(
                "Please make sure your Hostadress, port, username and password for REST-API (not SSH) login is correct."
                + "\nYou may test this by logging in into the SPP-Website with the used credentials.")
            raise ValueError(f"REST API login request not successfull.")
        try:
            self.__sessionid: str = response_json["sessionid"]
        except KeyError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("Login into SPP failed: No Session-ID received")

        (version, build) = self.get_spp_version_build()

        LOGGER.debug(f"SPP-Version: {version}, build {build}")
        LOGGER.debug(f"REST API Session ID: {self.__sessionid}")
        if(self.__verbose):
            LOGGER.info(f"REST API Session ID: {self.__sessionid}")
            LOGGER.info(f"SPP-Version: {version}, build {build}")

        self.__headers['X-Endeavour-Sessionid'] = self.__sessionid


    def logout(self) -> None:
        """Logs out of the REST-API.

        Raises:
            ValueError: Error when logging out.
            ValueError: Wrong status code when logging out.
        """
        url = self.get_url("/api/endeavour/session")
        try:
            response_logout: Response = delete(url, headers=self.__headers, verify=False)
        except RequestException as error:
            ExceptionUtils.exception_info(error=error)
            raise ValueError("error when logging out")

        if response_logout.status_code != 204:
            raise ValueError("Wrong Status code when logging out", response_logout.status_code)

        if(self.__verbose):
            LOGGER.info("Rest-API logout successfull")
        LOGGER.debug("Rest-API logout successfull")

    def get_url(self, endpoint: str) -> str:
        """Creates URL out of internal serverURL and given endpoint

        Args:
            endpoint (str): Endpoint to create URL to

        Raises:
            ValueError: No endpoint is given

        Returns:
            str: complete URL to SPP-Server
        """
        if(not endpoint):
            raise ValueError("endpoint is required to create URL")
        return self.__srv_url + endpoint

    def get_spp_version_build(self) -> Tuple[str, str]:
        """queries the spp version and build number.

        Returns:
            Tuple[str, str] -- Tuple of (version_nr, build_nr)
        """
        try:
            # VERSION SPP 10.1.8.1+
            # New endpoint for version
            results = self.get_objects(
                endpoint="/api/lifecycle/ping",
                allow_list=["version", "build"],
                add_time_stamp=False
            )
        except ValueError as error:
            # FALLBACK OPTION: Pre SPP 10.1.8.1
            # old endpoint for version
            try:
                results = self.get_objects(
                    endpoint="/ngp/version",
                    allow_list=["version", "build"],
                    add_time_stamp=False
                )
            except ValueError as outer_error:
                # move both errors to outer scope
                raise ValueError("Failed to obtain SPP version through REST", error, outer_error)

        return (results[0]["version"], results[0]["build"])

    def get_objects(self,
                    endpoint: str = None, uri: str = None,
                    params: Dict[str, Any] = None,
                    post_data: Dict[str, Any] = None,
                    request_type: RequestType = RequestType.GET,
                    array_name: str = None,
                    allow_list: List[str] = None, ignore_list: List[str] = None,
                    add_time_stamp: bool = False) -> List[Dict[str, Any]]:
        """Querys a response(-list) from a REST-API endpoint or URI from multiple pages

        Specify `array_name` if there are multiple results / list.
        Use allow_list to pick only the values specified.
        Use ignore_list to pick everything but the values specified.
        Both: allow_list items overwrite ignore_list items, still getting all not filtered.
        Param pageSize is only guranteed to be valid for the first page if included within params.

        Note:
        Do not specify both endpoint and uri, only uri will be used

        Keyword Arguments:
            endpoint {str} -- endpoint to be queried. Either use this or uri (default: {None})
            uri {str} -- uri to be queried. Either use this or endpoint (default: {None})
            params {Dict[str, Any]} -- Dictionary with all URL-Parameters. pageSize only guranteed to be valid for first page (default: {None})
            post_data {Dict[str, Any]} -- Dictionary with Body-Data. Only use on POST-Requests
            request_type: {RequestType} -- Either GET or POST
            array_name {str} -- name of array if there are multiple results wanted (default: {None})
            allow_list {list} -- list of item to query (default: {None})
            ignore_list {list} -- query all but these items(-groups). (default: {None})
            add_time_stamp {bool} -- whether to add the capture timestamp  (default: {False})

        Raises:
            ValueError: Neither a endpoint nor uri is specfied
            ValueError: Negative or 0 pagesize
            ValueError: array_name is specified but it is only a single object

        Returns:
            {List[Dict[str, Any]]} -- List of dictonarys as the results
        """
        if(not endpoint and not uri):
            raise ValueError("neiter endpoint nor uri specified")
        if(endpoint and uri):
            LOGGER.debug("added both endpoint and uri. This is unneccessary, uri is ignored")
        # if neither specifed, get everything
        if(not allow_list and not ignore_list):
            ignore_list = []
        if(params is None):
            params = {}

        # create uri out of endpoint
        if(endpoint):
            next_page =  self.get_url(endpoint)
        else:
            next_page = uri

        result_list: List[Dict[str, Any]] = []

        # Aborts if no nextPage is found
        while(next_page):
            LOGGER.debug(f"Collected {len(result_list)} items until now. Next page: {next_page}")
            if(self.__verbose):
                LOGGER.info(f"Collected {len(result_list)} items until now. Next page: {next_page}")

            # Request response
            (response, send_time) = self.query_url(next_page, params, request_type, post_data)

            # find follow page if available and set it
            (_, next_page_link) = SppUtils.get_nested_kv(key_name="links.nextPage.href", nested_dict=response)
            next_page: Optional[str] = next_page_link
            if(next_page):
                # Overwrite params with params from next link
                params = ConnectionUtils.get_url_params(next_page)
                # remove params from page
                next_page = ConnectionUtils.url_set_params(next_page, None)



            # Check if single object or not
            if(array_name):
                # get results for this page, if empty nothing happens
                page_result_list: Optional[List[Dict[str, Any]]] = response.get(array_name, None)
                if(page_result_list is None):
                    raise ValueError("array_name does not exist, this is probably a single object")
            else:
                page_result_list = [response]

            filtered_results = ConnectionUtils.filter_values_dict(
                result_list=page_result_list,
                allow_list=allow_list,
                ignore_list=ignore_list)

            if(add_time_stamp): # direct time add to make the timestamps represent the real capture time
                for mydict in filtered_results:
                    time_key, time_val = SppUtils.get_capture_timestamp_sec()
                    mydict[time_key] = time_val
            result_list.extend(filtered_results)

            # adjust pagesize if either the send time is too high
            # or regulary adjust on max-page sizes requests
            # dont adjust if page isnt full and therefore too quick
            if(send_time > self.__preferred_time or len(page_result_list) == self.__page_size):
                LOGGER.debug(f"send_time: {send_time}, len: {len(page_result_list)}, pageSize = {self.__page_size} ")
                self.__page_size = ConnectionUtils.adjust_page_size(
                    page_size=len(page_result_list),
                    min_page_size=self.__min_page_size,
                    preferred_time=self.__preferred_time,
                    send_time=send_time)
                LOGGER.debug(f"Changed pageSize from {len(page_result_list)} to {self.__page_size} ")
                params["pageSize"] = self.__page_size





        LOGGER.debug("objectList size %d", len(result_list))
        return result_list

    def query_url(
        self,
        url: str,
        params: Dict[str, Any] = None,
        request_type: RequestType = RequestType.GET,
        post_data: Dict[str, str] = None,
        auth: HTTPBasicAuth = None) -> Tuple[Dict[str, Any], float]:
        """Sends a request to this endpoint. Repeats if timeout error occured. Adust the pagesize on timeout.

        Arguments:
            url {str} -- URL to be queried. Must contain the server-uri and Endpoint. Does not allow encoded parameters
            post_data {str} -- additional data with filters/parameters. Only to be send with a POST-Request (default: {None})
            auth {HTTPBasicAuth} -- Basic auth to be used to login into SPP via POST-Request(default: {None})
            type {RequestType} -- What kind of Request should be made, defaults to GET

        Raises:
            ValueError: No URL specified
            ValueError: Error when requesting endpoint
            ValueError: Wrong status code
            ValueError: failed to parse result
            ValueError: Timeout when sending result
            ValueError: No post-data/auth is allowed in a GET-Request

        Returns:
            Tuple[Dict[str, Any], float] -- Result of the request with the required send time
        """
        if(not url):
            raise ValueError("no url specified")
        if((post_data or auth) and type == RequestType.GET):
            raise ValueError("No post-data/auth is allowed in a GET-Request")
        LOGGER.debug(f"query url: {url}, type: {type}, post_data: {post_data} auth: {True if auth else False}")
        if(not params):
            params = {}

        failed_tries: int = 0
        response_query: Optional[Response] = None
        send_time: float = -1 # prevent unbound var

        # avoid unset pageSize to not get into SPP defaults
        if(not params.get("pageSize", None)):
            LOGGER.debug(f"setting pageSize to {self.__page_size} from unset value")
            params["pageSize"] = self.__page_size

        while(response_query is None):

            # send the query
            try:
                start_time = time.perf_counter()
                if(request_type == RequestType.GET):
                    response_query = get(
                        url=url, headers=self.__headers, verify=False,
                        params=params,
                        timeout=(self.__initial_connection_timeout, self.__timeout))
                elif(request_type == RequestType.POST):
                    response_query = post(
                        url=url, headers=self.__headers, verify=False,
                        params=params, json=post_data, auth=auth,
                        timeout=(self.__initial_connection_timeout, self.__timeout))
                end_time = time.perf_counter()
                send_time = (end_time - start_time)

            except ReadTimeout as timeout_error:

                # timeout occured, increasing failed trys
                failed_tries += 1

                url_params = ConnectionUtils.get_url_params(url)


                # #### Aborting cases ######
                if(failed_tries > self.__max_send_retries):
                    ExceptionUtils.exception_info(error=timeout_error)
                    # read start index for debugging
                    start_index = url_params.get("pageStartIndex", None)
                    page_size = url_params.get("pageSize", None)
                    # report timeout with full information
                    raise ValueError("timeout after repeating a maximum ammount of times.",
                                     timeout_error, failed_tries, page_size, start_index)

                if(self.__page_size == self.__min_page_size):
                    ExceptionUtils.exception_info(error=timeout_error)
                    # read start index for debugging
                    start_index = url_params.get("pageStartIndex", None)
                    page_size = url_params.get("pageSize", None)
                    # report timeout with full information
                    raise ValueError("timeout after using minumum pagesize. repeating the request is of no use.",
                                     timeout_error, failed_tries, page_size, start_index)

                # #### continuing cases ######
                if(failed_tries == self.__max_send_retries): # last try
                    LOGGER.debug(f"Timeout error when requesting, now last try of total {self.__max_send_retries}. Reducing pagesize to minimum for url: {url}")
                    if(self.__verbose):
                        LOGGER.info(f"Timeout error when requesting, now last try of total {self.__max_send_retries}. Reducing pagesize to minimum for url: {url}")

                    # persist reduced size for further requests
                    self.__page_size = self.__min_page_size
                    # repeat with minimal possible size
                    LOGGER.debug(f"setting pageSize from {params.get('pageSize', None)} to {self.__page_size}")
                    params["pageSize"] = self.__page_size

                else: # (failed_tries < self.__max_send_retries): # more then 1 try left
                    LOGGER.debug(f"Timeout error when requesting, now on try {failed_tries} of {self.__max_send_retries}. Reducing pagesizefor url: {url}")
                    if(self.__verbose):
                        LOGGER.info(f"Timeout error when requesting, now on try {failed_tries} of {self.__max_send_retries}. Reducing pagesize for url: {url}")

                    # persist reduced size for further requests
                    self.__page_size = ConnectionUtils.adjust_page_size(
                        page_size=params["pageSize"],
                        min_page_size=self.__min_page_size,
                        timeout=True)
                    # repeat with reduced page size
                    LOGGER.debug(f"setting pageSize from {params.get('pageSize', None)} to {self.__page_size}")
                    params["pageSize"] = self.__page_size

            except RequestException as error:
                ExceptionUtils.exception_info(error=error)
                raise ValueError("error when requesting endpoint", error)

        if( not response_query.ok):
            raise ValueError("Wrong Status code when requesting endpoint data",
                             response_query.status_code, url, response_query)

        try:
            response_json: Dict[str, Any] = response_query.json()
        except (json.decoder.JSONDecodeError, ValueError) as error:
            raise ValueError("failed to parse query in restAPI request", response_query)

        return (response_json, send_time)
