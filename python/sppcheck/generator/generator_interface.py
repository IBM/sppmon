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
    DataGenerator
"""

from abc import ABC, abstractmethod
from typing import List



class GeneratorInterface(ABC):

    @classmethod
    @abstractmethod
    def gen_normalized_data(cls, result_count: int, range_days: int, start_value: int, dp_interval_hour: int, year_growth: float,
                          max_growth: float, min_growth: float, dp_change_max: float, dp_change_min: float,
                          dp_change_sigma: float) -> List[List[float]]:
        raise NotImplementedError