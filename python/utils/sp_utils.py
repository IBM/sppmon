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
 SpUtils
"""
from utils.spp_utils import SppUtils
from dataclasses import fields
from typing import List, Any, Dict, TypeVar, Generic, Tuple
from spmonMethods.sp_dataclasses import SpInfluxParams, SpRestQuery, SpServerParams, SpInfluxTableDefinition


class SpUtils:
    """Wrapper for general purpose helper methods for broad use across SpMon.

    Methods:
        build_dataclass_from_dict: Initialize dataclass from a dict containing config parameters
        get_top_level_dict: Retrieves the top level dictionary (if exists) from a REST api response
        get_capture_timestamp_sec: Wrapper around an SppUtil that gets the actual timestamp in seconds
    """

    Dataclass = TypeVar(
        "Dataclass",
        SpInfluxParams,
        SpRestQuery,
        SpServerParams,
        SpInfluxTableDefinition
    )

    @classmethod
    def build_dataclass_from_dict(cls,
                                  dataclass: Generic[Dataclass],
                                  param_dict: Dict[str, Any]) -> Generic[Dataclass]:
        """Generic initialization of dataclass by unpacking a dictionary comprehension. Dataclass
        attributes and corresponding dictionary keys have the same name.

        Args:
            dataclass: Type of dataclass to initialize. Defined in sp_dataclasses.py.
            param_dict: Dictionary containing parameters for that dataclass.

        Returns:
            {Generic[Dataclass]} - Initialized dataclass object specified as a parameter.
        """
        return dataclass(**{field.name: param_dict.get(field.name) for field in fields(dataclass)})

    @classmethod
    def get_top_level_dict(cls, rest_response: List[Any]) -> Dict[str, Any]:
        """Retrieves top level dictionary from the JSON formatted response of the OC's REST
        API endpoint. Descends nested lists until either the dictionary is found or no lists
        remain.

        Args:
            rest_response: JSON formatted REST API response.

        Raises:
            ValueError: Rest response does not contain a dictionary (empty response).

        Returns:
            {Dict[str, Any]} - Top level dictionary embedded within the REST response.
        """
        while not isinstance(rest_response, dict):
            if not rest_response[0]:
                raise ValueError("rest_response does not contain a dictionary")
            rest_response = rest_response[0]
        return rest_response

    @classmethod
    def get_capture_timestamp_sec(cls) -> Tuple[str, int]:
        """Wrapper method around an SppUtils.get_capture_timestamp_sec. Returns time
        key formatted to as "Sp" rather than "Spp" and a timestamp in seconds.

        Returns:
            {Tuple[str, int]} - Time key as str and the time in seconds as int
        """
        time_key: str
        actual_time_sec: int
        time_key, actual_time_sec = SppUtils.get_capture_timestamp_sec()
        time_key = time_key.replace("spp", "sp")
        return time_key, actual_time_sec



