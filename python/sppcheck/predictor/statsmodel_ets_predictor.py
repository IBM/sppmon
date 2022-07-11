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

from typing import Dict, Union

from pandas import Series
from sppCheck.predictor.predictor_interface import PredictorInterface
from statsmodels.tsa.exponential_smoothing.ets import ETSModel, ETSResults

from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class StatsmodelEtsPredictor(PredictorInterface):

    def data_preparation(self, predict_data: Dict[int, Union[int, float]], dp_freq_hour: int) -> Series:

        LOGGER.debug(f"Received {len(predict_data)} datapoints for forecasting")
        # filter over values, only positive allowed, change epoch time to utc time
        positive_data = {datetime.utcfromtimestamp(k): v for k, v in predict_data.items() if v is not None and v > 0}

        if len(predict_data) > len(positive_data):
            LOGGER.info(f"Removed {len(predict_data) - len(positive_data)} negative / none values from dataset")

        LOGGER.debug(f"Resampling into {dp_freq_hour}H frequency")

        data_series: Series = Series(positive_data,
            ).resample(f"{dp_freq_hour}H"    # make sure the frequency is correct
            ).mean()                         # overlapping points are changed via mean

        LOGGER.debug(f"{len(data_series)} Datapoints after resampling.")

        nan_count = len(data_series) - data_series.count()
        if nan_count:
            LOGGER.info(f"{nan_count} values are nan after resampling, interpolating them")
            data_series = data_series.interpolate(limit=1)  # fill missing values

            remaining_nan_count = len(data_series) - data_series.count()
            if remaining_nan_count:
                LOGGER.info(f"Could not interpolate {remaining_nan_count} values.")

        return data_series


    def predict_data(self,
                    data_series: Series,
                    forecast_years: float) -> Series:

        # convert to hour
        try:
            dp_freq_hour: float = data_series.index.freq.nanos / 3600000000000 # type: ignore
        except AttributeError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("The data series is corrupted, no frequency at the index available", data_series.index)

         # discard prediction data without new data
        hours_last_data = (datetime.now() - data_series.index.max()).total_seconds() / (60 * 60)

        # discard if the data is older than 7 days and 3 times the frequency
        # May some datapoints fail, therefore this grace period
        if hours_last_data > 24 * 7 and hours_last_data > dp_freq_hour * 3:
            raise ValueError("This set of data is too old to be used")

        forecast_dp_count = round((forecast_years * 365 * 24) / dp_freq_hour)

        LOGGER.debug(f"forecasting using {len(data_series)} datapoints")

        if len(data_series) < 15:
            raise ValueError(f"At least 15 values are required for a prediction, only {len(data_series)} given", data_series)

        # interpolate nan values
        nan_count = len(data_series) - data_series.count()
        if nan_count:
            LOGGER.info(f"{nan_count} values are nan when predicting, forcing an interpolation")
            data_series = data_series.interpolate()  # fill missing values

        ets_fit: ETSResults = ETSModel(
            data_series,
            error="mul",
            trend="mul",
            initialization_method="estimated", # no real documentation here
            missing="skip" # drop missing values, like nan -> doesnt work due to freq not being detected even if set
            ).fit(optimized=True, disp=False) # type: ignore
        prediction: Series = ets_fit.forecast(forecast_dp_count)

        # if it is not monotonic, the values are swapping between positive and negative, highly increasing
        # e.g. +1000, -1000, +10.000, -10.000 ...
        if not prediction.is_monotonic:
            ExceptionUtils.error_message("The result is highly likely corrupted, it is not monotonic.")

        # definition in Series: a series of same values (eg 2,2,2,2) is all monotonic, increasing and decreasing
        # a decreasing prediction does not align with the purpose of SPPCheck, which assumes only exponential increasing values
        if prediction.is_monotonic_decreasing and not prediction.is_monotonic_increasing:
            ExceptionUtils.error_message("The result is highly likely corrupted, it is monotonic decreasing")

        return prediction
