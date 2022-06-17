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
    ExcelDictBuilder
"""

import json
from logging import getLogger
from typing import Any, ClassVar, Dict, Optional, Tuple, Union, List

from pathlib import Path

from pandas.core.series import Series

RecDict = Dict[str, Union[str, "RecDict"]]

LOGGER_NAME = 'sppmon'
LOGGER = getLogger(LOGGER_NAME)


class ExcelDictBuilder:

    upper_name: ClassVar[str] = "upper"
    ignore_name: ClassVar[str] = "ignore"
    replace_name: ClassVar[str] = "replace_me"
    prefix_name: ClassVar[str] = "prefix"

    default_dict_keys = [
        upper_name,
        prefix_name
    ]

    @property
    def rec_dict(self) -> RecDict:
        return self.__rec_dict

    @rec_dict.setter
    def rec_dict(self, rec_dict: RecDict) -> None:
        self.__rec_dict = rec_dict
        self.__prefix = self.__calc_prefix(self.rec_dict)

    def __init__(self, excel_struct_path: Path):

        with open(excel_struct_path, "r", encoding="utf8") as json_file:
            self.__rec_dict: RecDict = json.load(json_file, object_pairs_hook=dict)


        self.result: Dict[str, Tuple[Optional[str], Series]] = {}
        """Content: unique_key -> table, value_key, (unit, series)"""
        self.missing_items: List[str] = []
        self.__prefix: str = self.__calc_prefix(self.rec_dict)

    def get_unused_items(self) -> List[str]:
        top_level_dict = self.rec_dict

        # first move to the very top level dict
        while self.upper_name in top_level_dict:
            upper_dict = top_level_dict[self.upper_name]
            if not isinstance(upper_dict, Dict):
                raise ValueError("Inconsistent Dict-structure: upper is not a dict", upper_dict, top_level_dict)
            top_level_dict = upper_dict

        return self.__unused_items_recursive(top_level_dict)

    @classmethod
    def __unused_items_recursive(cls, cur_rec_dict: RecDict) -> List[str]:
        unused_items: List[str] = []
        # use prefix to identify variables without duplicates
        prefix = cls.__calc_prefix(cur_rec_dict)

        # ignore unready or unused keys
        for key, value in cur_rec_dict.items():
            if value in [cls.ignore_name, cls.replace_name]:
                continue
            if key in cls.default_dict_keys:
                continue

            # if it is a unused key, append it
            if isinstance(value, str):
                unused_items.append(f"'{key}': '{prefix + value}'")
            else:
                # if it is a dict, recursive check for its contents
                # extend the list with the found items
                unused_items.extend(cls.__unused_items_recursive(value))

        return unused_items


    @classmethod
    def is_empty_rec_dict(cls, rec_dict: RecDict) -> bool:
        # if it is longer than the default-keys, cant be empty
        if len(rec_dict) > len(cls.default_dict_keys):
            return False

        # Check for values which are not default-values
        # If any non-default values are found, dict is not empty
        return not list(filter(
            lambda key:
                key not in cls.default_dict_keys,
            rec_dict))

    def pop_rec_dict_item(self, item_name: str) -> None:

        if not isinstance(self.rec_dict[item_name], (str, list)):
            raise ValueError("It is only allowed to pop regular items using pop_dict_item method.")
        # remove the last item.
        self.rec_dict.pop(item_name)

        # repeat loop if upper dict is now empty - due to removal of sub-dict
        while self.is_empty_rec_dict(self.rec_dict):

            # current rec_dict is empty
            if self.upper_name not in self.rec_dict:
                # break if you've already reached top level
                break

            # move one level up
            upper_dict = self.rec_dict[self.upper_name]
            if not isinstance(upper_dict, Dict):
                raise ValueError("Inconsistent Dict-structure: upper is not a dict", upper_dict, self.rec_dict)
            self.rec_dict = upper_dict

            # remove all empty dict-items, there must be at least one
            empty_dict_list = list(filter(
                lambda key_value:
                    # make sure it is a dict and empty
                    isinstance(key_value[1], dict)
                    and self.is_empty_rec_dict(key_value[1]),
                self.rec_dict.items()))

            for key, _ in empty_dict_list:
                self.rec_dict.pop(key)
            # if the current rec_dict is now "empty" too, the loop will restart

    def __setitem__(self, excel_line: str, series: Any) -> None:
        self.save(excel_line, series)

    def save(self, excel_line: str, series: Series) -> None:

        var_name = self.rec_dict[excel_line]
        if var_name in [self.ignore_name, self.replace_name]:
            # don't save "ignore" or unfinished items
            return

        if isinstance(var_name, str):
            # split the series into a tuple of unit and the series
            unit_projection_tuple = self.split_unit_series(series)

            self.result[self.__prefix + var_name] = unit_projection_tuple

            # remove the key to detect errors and allow non-unique keys, identified by order
            self.pop_rec_dict_item(excel_line)
        else:
            var_name["upper"] = self.rec_dict
            self.rec_dict = var_name

            if excel_line in self.rec_dict:
                self.save(excel_line, series)

    def adjust_level(self, search_name: str) -> None:
        self.rec_dict = self.__check_higher_level(search_name, self.rec_dict)

    def __check_higher_level(self, search_name: str, base_dict: RecDict) -> RecDict:
        if search_name in base_dict:
            return base_dict
        elif self.upper_name in base_dict:
            upper_dict = base_dict[self.upper_name]
            if not isinstance(upper_dict, Dict):
                raise ValueError("Inconsistent Dict-structure: upper is not a dict", upper_dict, base_dict)
            return self.__check_higher_level(search_name, upper_dict)
        else:
            self.missing_items.append(search_name)
            raise ValueError(f"{search_name} does not exist in the pre-configured json file.")

    @classmethod
    def __calc_prefix(cls, base_dict: RecDict) -> str:

        if cls.prefix_name in base_dict:
            prefix = base_dict[cls.prefix_name]
            if not isinstance(prefix, str):
                raise ValueError("Inconsistent Dict-structure: prefix is not a str", prefix, base_dict)
        else:
            prefix = ""

        if cls.upper_name in base_dict:
            upper_dict = base_dict[cls.upper_name]
            if not isinstance(upper_dict, dict):
                raise ValueError(f"Inconsistent Dict-structure: {cls.upper_name} is not a dict", upper_dict, base_dict)
            upper_prefix = cls.__calc_prefix(upper_dict)
            return upper_prefix + prefix
        else:
            return prefix

    @staticmethod
    def split_unit_series(series: Series) -> Tuple[Optional[str], Series]:
        # format: name, alt_unit, unit, 1...8
        # split into: (unit, 1...8)

        # some rows might not have any unit
        if isinstance(series["unit"], str):
            unit: Optional[str] = series["unit"]
        elif isinstance(series["alt_unit"], str):
            unit = series["alt_unit"]
        else:
            unit = None

        return (unit, series[3:])
