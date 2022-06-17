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

from datetime import datetime
from random import randint
from time import mktime
from typing import Dict, List, Union

from influx.influx_client import InfluxClient
from sppCheck.generator.fakedata_generator import FakeDataGenerator
from sppCheck.generator.generator_interface import GeneratorInterface
from utils.sppcheck_utils import SizingUtils
from utils.exception_utils import ExceptionUtils


class FakeDataController:

    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                datagen_range_days: int, fakedata_rp_name: str) -> None:
        if not influx_client:
            raise ValueError("FakeData Controller is not available, missing the influx_client")
        self.__influx_client: InfluxClient = influx_client

        self.__generatorI: GeneratorInterface = FakeDataGenerator()

        self.__dp_interval_hour = dp_interval_hour
        self.__datagen_range_days = datagen_range_days

        self.__influx_client.drop_rp(fakedata_rp_name)
        self.__fakedata_rp = SizingUtils.create_unique_rp(self.__influx_client, fakedata_rp_name)

    def gen_fake_data(self):
        try:
            self.__gen_storage_data()
        except ValueError as error:
            ExceptionUtils.exception_info(error, "Failed to generate Storage data, skipping")
        pass

    def __gen_storage_data(self) -> None:

        total_start_value = pow(2,40)*4050
        vsnap_count = 30

        individual_start_value = total_start_value / vsnap_count

        # generate Storage data
        gen_data = self.__generatorI.gen_normalized_data(
            result_count=vsnap_count,
            range_days=self.__datagen_range_days,
            start_value=individual_start_value,
            dp_interval_hour=self.__dp_interval_hour,
            year_growth=10,
            max_growth=15,
            min_growth=5,
            dp_change_max=7,
            dp_change_min=-15,
            dp_change_sigma=0.4)


        insert_data: List[Dict[str, Union[str, int, float]]] = []


        for i, set_of_data in enumerate(gen_data):

            storage_id = f"{i}_{randint(1000,2000)}"
            name = f"generated_vSnap_{storage_id}"
            type = "generated"
            host_address = name

            default_dict: Dict[str, Union[str, int, float]] = {
                    "name": name,
                    "hostAddress": host_address,
                    "type": type,
                    "storageId": storage_id
                }


            time = mktime(datetime.now().timetuple())
            # hour * minutes * seconds
            time_reduce = self.__dp_interval_hour * 60 * 60


            gen_series: List[Dict[str, Union[str, int, float]]] = []
            # reverse to start from now, add datapoints reduced by the offset between each dp.
            for gen_value in reversed(set_of_data):

                # shallow copy is enough
                insert_dict = default_dict.copy()

                insert_dict["used"] = round(gen_value)
                insert_dict["updateTime"] = time


                time -= time_reduce

                gen_series.append(insert_dict)

            insert_data.extend(gen_series)

        self.__influx_client.insert_dicts_to_buffer("storages", insert_data, self.__fakedata_rp)
        self.__influx_client.flush_insert_buffer()
