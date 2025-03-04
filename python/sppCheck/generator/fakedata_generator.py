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

from math import floor

from scipy.stats import truncnorm
from typing import List

from sppCheck.generator.generator_interface import GeneratorInterface

class FakeDataGenerator(GeneratorInterface):

    @classmethod
    def __gen_data(cls, range_days: int, dp_interval_hour: int, start_value: int, year_growth: float,
                dp_change_max: float, dp_change_min: float, dp_change_sigma: float) -> List[float]:
        """Generates a list of random data using standard deviation, exponentially affecting each next data point.

        Args:
            range_days (int): the range over how many days data should be generated
            dp_interval_hour (int): frequency of each data point
            start (int): start value of the data
            year_growth (float): growth estimate per year in percent
            dp_change_max (float): positive maximum of change per data point in percent
            dp_change_min (float): negative maximum of change per data point in percent
            dp_change_sigma (float): sigma of change per data point in percent

        Returns:
            List[float]: exponentially affected data points, including the star value.
        """

        # the yearly change rate needs to be calculated into a change rate per data point
        # Also the data points per day are variable, since the latestData argument could be used.
        dp_per_day = 24 / dp_interval_hour
        dp_growth_rate = year_growth / (365 * dp_per_day)

        # distribution calculated according to https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.truncnorm.html
        dist = truncnorm(
            (dp_change_min - dp_growth_rate) / dp_change_sigma,
            (dp_change_max - dp_growth_rate) / dp_change_sigma,
            loc=dp_growth_rate,
            scale=dp_change_sigma
            )

        # the generation must be executed on a per-data point basis
        # generate as many data points as required for the period, data points per day multiplied with total days.
        # rvs requires a int as value, therefore the floor call
        values: List[float] = dist.rvs(floor(dp_per_day * range_days)) # type: ignore

        # initialize the result list with the scaling value
        results: List[float] = [start_value]

    	# increase and decrease the next value multiplicative based on the one before.
        # this is a exponential growth.
        for iteration in values:
            results.append(results[-1] * (100 + iteration) / 100)

        return results

    @classmethod
    def gen_normalized_data(cls, result_count: int, range_days: int, start_value: int, dp_interval_hour: int, year_growth: float,
                          max_growth: float, min_growth: float, dp_change_max: float, dp_change_min: float,
                          dp_change_sigma: float) -> List[List[float]]:
        results: List[List[float]] = list()

        # generate as many valid results as requested.
        # if a result is invalid, continue. This might lead to an endless loop if every result is invalid.
        while(len(results) < result_count):
            instance_result = cls.__gen_data(
                range_days,
                dp_interval_hour,
                start_value,
                year_growth,
                dp_change_max,
                dp_change_min,
                dp_change_sigma)


            # following code limits the trend over the whole duration of the generation
            # how many years are generated, like 0.5 <-> 3.2
            range_years = range_days / 365
            # results in Values like 1.4000
            deviance = instance_result[-1] / instance_result[0]

            # adjust growth exponentially over generation range
            # results in values like 0.5 <-> 1.5
            min_growth_normalized = pow( 1 + (min_growth / 100), range_years)
            max_growth_normalized = pow( 1 + (max_growth / 100), range_years)

            # only append the result if it is valid -> within the accepted deviance of total growth
            if min_growth_normalized <= deviance <= max_growth_normalized:
                results.append(instance_result)

        return results
