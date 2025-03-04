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
import logging
from random import randint
from time import mktime
from typing import Any, Dict, List, Union

from influx.influx_client import InfluxClient
from sppCheck.generator.fakedata_generator import FakeDataGenerator
from sppCheck.generator.generator_interface import GeneratorInterface
from utils.influx_utils import InfluxUtils
from utils.sppcheck_utils import SppcheckUtils
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class FakeDataController:

    def __init__(self, influx_client: InfluxClient, dp_interval_hour: int,
                datagen_range_days: int, fakedata_rp_name: str) -> None:
        if not influx_client:
            raise ValueError("FakeData Controller is not available, missing the influx_client")
        self.__influx_client: InfluxClient = influx_client

        self.__generatorI: GeneratorInterface = FakeDataGenerator()

        self.__dp_interval_hour = dp_interval_hour
        self.__datagen_range_days = datagen_range_days

        LOGGER.debug(f"> dp_interval_hour: {dp_interval_hour}, datagen_range_days: {datagen_range_days}, fakedata_rp_name: {fakedata_rp_name}")

        self.__influx_client.drop_rp(fakedata_rp_name)
        self.__fakedata_rp = SppcheckUtils.create_unique_rp(self.__influx_client, fakedata_rp_name)

        LOGGER.debug(f"> Fakedata RP: {self.__fakedata_rp}")

    def gen_fake_data(self):

        LOGGER.info("Starting the generation of all metrics.")

        try:
            self.__gen_storage_data(
                total_start_storage=pow(2,40)*4050,
                vsnap_count=10
            )
            self.__influx_client.flush_insert_buffer()
        except ValueError as error:
            ExceptionUtils.exception_info(error, "Failed to generate Storage data, skipping it.")

        # other generations may follow here
        pass

        LOGGER.info("Completed the generation of all metrics.")

    def __gen_storage_data(self, total_start_storage: int, vsnap_count: int) -> None:

        LOGGER.info("> Starting generation of storage data")
        LOGGER.debug(f"> total start storage: {total_start_storage}")
        LOGGER.debug(f"> vsnap_count: {vsnap_count}")

        individual_start_value = total_start_storage // vsnap_count

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

        LOGGER.info("> Generated required amount of vSnaps.")
        LOGGER.info("> Adding Metadata (Tags) to each one.")

        insert_data: List[Dict[str, Union[str, int, float]]] = []

        # iterate over each vsnap to add its metadata
        for i, data_series in enumerate(gen_data):

            # storage ID should be for example 5_234567
            # high random so this is practically unique, see uuid in a small format
            storage_id = f"{i}_{randint(100000,200000)}"
            name = f"generated_vSnap_{storage_id}"
            host_address = name

            LOGGER.debug(f">> vSnap storageId: {storage_id}")

            type = "generated"

            # this is basically the metadata
            metadata_dict: Dict[str, Union[str, int, float]] = {
                    "name": name,
                    "hostAddress": host_address,
                    "type": type,
                    "storageId": storage_id,
                }

            # add time stamps and the data values for each point within the series
            # storage table uses the "updateTime" as timestamp value
            gen_series = self.__add_time_to_series(
                data_series,
                "used",
                metadata_dict,
                "updateTime")

            insert_data.extend(gen_series)

        LOGGER.info(f"> Finished generation of {vsnap_count} vSnaps, inserting storage data into the InfluxDB.")

        self.__influx_client.insert_dicts_to_buffer("storages", insert_data, self.__fakedata_rp)


    def __add_time_to_series(self, data_series: List[float], data_key: str, metadata_dict: Dict[str, Any], time_key: str = InfluxUtils.time_key_names[0]):


        time = mktime(datetime.now().timetuple())

        # hour * minutes * seconds
        time_reduce = self.__dp_interval_hour * 60 * 60

        LOGGER.debug(f">> current_time: {time}, time_reduce: {time_reduce}")
        LOGGER.debug(f">> data_key: {data_key}, time_key: {time_key}")

        gen_series: List[Dict[str, Union[str, int, float]]] = []
        # reverse to start from now, add datapoints reduced by the offset between each dp.
        for gen_value in reversed(data_series):

            # shallow copy is enough
            insert_dict = metadata_dict.copy()

            insert_dict[data_key] = round(gen_value)
            insert_dict[time_key] = time

            time -= time_reduce

            gen_series.append(insert_dict)

        return gen_series