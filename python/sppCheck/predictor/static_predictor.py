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

import logging

from datetime import datetime

from pandas import Series, Timestamp, date_range
from sppCheck.predictor.statsmodel_ets_predictor import StatsmodelEtsPredictor

from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class StaticPredictor(StatsmodelEtsPredictor):

    def predict_data(self,
                    data_series: Series,
                    forecast_years: float) -> Series:

        LOGGER.debug("Using a static prediction")

        # read the frequency to calculate how many data points needs to be forecasted
        try:
            # convert to hour
            dp_freq_hour: float = data_series.index.freq.nanos / 3600000000000 # type: ignore
        except AttributeError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("The data series is corrupted, no frequency at the index available", data_series.index)

        hours_last_data = (datetime.now() - data_series.index.max()).total_seconds() / (60 * 60)
        # discard if the data is older than 7 days and 3 times the frequency
        # May some data points fail, therefore this grace period
        if hours_last_data > 24 * 7 and hours_last_data > dp_freq_hour * 3:
            raise ValueError("This set of data is too old to be used")

        LOGGER.debug(f"forecasting using {len(data_series)} data points")

        last_timestamp = data_series.last_valid_index()
        last_value = data_series.get(last_timestamp)

        # this issues a warning if not ignored when importing
        # prediction should start +1x freq from the last one.
        start_timestamp: Timestamp = last_timestamp + last_timestamp.freq.delta

        # get count of data points required
        forecast_dp_count = round((forecast_years * 365 * 24) / dp_freq_hour)

        # get a time range with all required indices
        forecast_indices = date_range(start=start_timestamp, periods=forecast_dp_count, freq=f"{dp_freq_hour}H")

        # create a series with all the same value
        prediction_series = Series([last_value]*forecast_dp_count, forecast_indices)

        return prediction_series