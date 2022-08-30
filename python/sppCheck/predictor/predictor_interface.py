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

from abc import ABC, abstractmethod
from typing import Dict, Union

from pandas import Series


class PredictorInterface(ABC):

    @abstractmethod
    def data_preparation(self,
                         predict_data: Dict[int, Union[int, float]],
                         dp_freq_hour: int) -> Series:
        raise NotImplementedError

    @abstractmethod
    def predict_data(self,
                     data_series: Series,
                     forecast_years: float) -> Series:
        raise NotImplementedError