"""This Module provides helper methods for the connection module.
You may implement new static/class helper methods in here.

Classes:
    ConnectionUtils
"""
import logging
from typing import Dict, Any, List, Optional
import urllib.parse as parse

from utils.spp_utils import SppUtils
from utils.execption_utils import ExceptionUtils


LOGGER = logging.getLogger("sppmon")

class ConnectionUtils:
    """Wrapper for static /class connection themed helper methods. You may implement new methods in here.

    Methods:
        get_with_sub_values - Extends a dict by possible sub-dicts in its values, recursive.
        url_set_params - Sets params within a URL to a given mapping
        get_url_params - reads all param values from a url
        filter_values_dict - removed unwanted items from a list of dicts.
        adjust_page_size - Adjust dynamically the pagesize for requests.

    """

    allowed_send_delta: float
    """How much % difference is allowed in both directions before adjustments are made"""
    timeout_reduction: float
    """How much % the pagesize is reduced after a timeout"""
    max_scaling_factor: float
    """maximum factor for the pagesize to be increased in one go"""
    verbose = False

    @classmethod
    def get_with_sub_values(cls, mydict: Dict[str, Any], ignore_list: List[str]) -> Dict[str, Any]:
        """Extends a dict by possible sub-dicts in its values, recursive.

        Key names get extended by dot and sub-keyname.

        Arguments:
            mydict {Dict[str, Any]} -- original dict with possible sub-dicts
            ignore_list {List[str]} -- which paths should be deleted/ignored.

        Raises:
            ValueError: no original dict given.

        Returns:
            Dict[str, Any] -- a new dict with extended values.
        """
        if(mydict is None):
            raise ValueError("need dictionary to gather sub-values")
        if(ignore_list is None):
            ignore_list = []

        # all results should be in here
        full_dict: Dict[str, Any] = {}

        for (key, value) in mydict.items():
            # ignore if this value / path should be ignored
            # effective deleting it.
            if(key in ignore_list):
                continue

            # if a subdict, dig deeper
            if(isinstance(value, dict)):

                # first qualify names to allow filtering in recursive calls
                # otherwise only simply names below
                sub_dict: Dict[str, Any] = {}
                value: Dict[str, Any]
                for (sub_key, sub_value) in value.items():
                    qualified_key = "%s.%s" % (key, sub_key)
                    sub_dict[qualified_key] = sub_value

                sub_dict = cls.get_with_sub_values(sub_dict, ignore_list)

                # Like a extend in this case
                full_dict.update(sub_dict)
            else:
                full_dict[key] = value

        return full_dict

    @staticmethod
    def url_set_params(url: str, new_params: Optional[Dict[str, List[str]]]) -> str:
        """Sets params within a URL to a given mapping

        Arguments:
            url {str} -- URL which is parsed and changed
            new_params {Dict[str, List[str]]} -- new params to set for the URL

        Raises:
            ValueError: No URL specified

        Returns:
            {str} -- new modified URL
        """
        if(not url):
            raise ValueError("need url to set params")
        if(new_params is None):
            new_params = {}

        parse_result = parse.urlparse(url)
        query_params_encoded = parse.urlencode(new_params, True)

        parse_result =  parse.ParseResult(
            parse_result.scheme,
            parse_result.netloc,
            parse_result.path,
            parse_result.params,
            query_params_encoded, # change query params
            parse_result.fragment)

        new_url: str = parse.urlunparse(parse_result)

        return new_url

    @staticmethod
    def get_url_params(url: str) -> Dict[str, List[str]]:
        """reads all param values from a url

        Args:
            url (str): url to be parsed

        Raises:
            ValueError: no url given

        Returns:
            Dict[str, List[str]]: Dict of paramName to param-values
        """

        if(not url):
            raise ValueError("need url to read param")
        _, _, _, _, query, _ = parse.urlparse(url)
        query_params = parse.parse_qs(query)
        return query_params


    @classmethod
    def adjust_page_size(cls,
                         page_size: int,
                         min_page_size: int,
                         preferred_time: float = None,
                         send_time: float = None,
                         timeout: bool = False) -> int:
        """Adjust dynamically the pagesize for requests.

        This method uses class attributes for finetuning.
        It tries to adjust the pagesize to reach the preferred time of the sending process.

        Args:
            page_size (int): actually used pagesize
            min_page_size (int): minimum allowed pagesize
            preferred_time (float, optional): the perfect send time. Defaults to None.
            send_time (float, optional): the actual send time. Defaults to None.
            timeout (bool, optional): if the requests timed out. Defaults to False.

        Raises:
            ValueError: no pagesize given
            ValueError: no minpagesize given
            ValueError: not both preferred and sendtime given on timeout

        Returns:
            int: the new pagesize
        """

        if(page_size is None):
            raise ValueError("need a old pagesize to adjust to a new one")
        if(min_page_size is None):
            raise ValueError("need min_page_size")
        if(not timeout and (preferred_time is None or send_time is None)):
            raise ValueError("need both preferred and send time if not timeout")

        if(timeout):
            size_over_limit = page_size-min_page_size
            # reduce pagesize
            new_page_size = int(page_size - (size_over_limit * cls.timeout_reduction))

            LOGGER.debug(f"reducing pagesize due timeout, from {page_size} to {new_page_size}.")
            if(cls.verbose):
                LOGGER.info(f"reducing pagesize due timeout, from {page_size} to {new_page_size}.")
            return new_page_size

        time_difference_quota = send_time / preferred_time

        if(abs(time_difference_quota-1) <= cls.allowed_send_delta):
            # Difference is OK, too small to change
            # nothing to do
            return page_size

        LOGGER.debug(f"adjusting page size due too high time difference, actual: {send_time}, preferred: {preferred_time}")
        if(cls.verbose):
            LOGGER.info(f"adjusting page size due too high time difference, actual: {send_time}, preferred: {preferred_time}")

        # reset to the preferred value
        new_page_size = page_size / time_difference_quota
        new_page_size = int(new_page_size)

        # limit the maximum grow, with bonus for very low areas
        if(new_page_size > cls.max_scaling_factor * (page_size + 5)):
            new_page_size = int(cls.max_scaling_factor * (page_size + 5))

        # avoid getting stuck on 1
        if(new_page_size < min_page_size + 5):
            new_page_size = min_page_size + 5

        LOGGER.debug(f"changed page size from {page_size} to {new_page_size}")
        if(cls.verbose):
            LOGGER.info(f"changed page size from {page_size} to {new_page_size}")

        return new_page_size



    @classmethod
    def filter_values_dict(cls,
                           result_list: List[Dict[str, Any]],
                           allow_list: List[str] = None,
                           ignore_list: List[str] = None) -> List[Dict[str, Any]]:
        """Removes unwanted values from a list of dicts.

        Use allow_list to only pick the values specified. Gather all values if empty/none
        Use ignore_list to pick everything but the values specified.
        Both: allow_list itmes overwrite ignore_list times, still getting all items not filtered.

        Args:
            result_list (List[Dict[str, Any]]): source items to be filtered
            allow_list (List[str], optional): items to be kept. Retains all values if empty. Defaults to None.
            ignore_list (List[str], optional): items to be removed. Defaults to None.

        Raises:
            ValueError: no result list specified

        Returns:
            List[Dict[str, Any]]: list of filtered dicts
        """

        if(result_list is None):
            raise ValueError("need valuelist to filter values")


        new_result_list: List[Dict[str, Any]] = []

        # if single object this is a 1 elem list
        for result in result_list:

            new_result: Dict[str, Any] = {}

            # Only aquire items wanted
            if(allow_list):

                for allow_key in allow_list:
                    (key, value) = SppUtils.get_nested_kv(key_name=allow_key, nested_dict=result)
                    if(key in new_result):
                        key = allow_key
                    new_result[key] = value

                # warn if something is missing
                if(len(new_result) != len(allow_list)):
                    ExceptionUtils.error_message(
                        f"Result has not same lenght as allowlist, probably typing error: {result_list}")

            # aquire all but few unwanted
            if(ignore_list is not None):
                # add sub-dicts to dictonary itself, filtering inclusive
                full_result = cls.get_with_sub_values(mydict=result, ignore_list=ignore_list)
                new_result.update(full_result)

            new_result_list.append(new_result)

        return new_result_list
