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
 SpInfluxClient
"""
import logging
import sys

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
from spmonMethods.sp_dataclasses import SpInfluxParams, SpInfluxTableDefinition, SpRestResponsePage
from typing import List, Dict, Any
from utils.sp_influx_utils import SpInfluxUtils
from utils.exception_utils import ExceptionUtils

LOGGER = logging.getLogger("spmon")


class SpInfluxClient:
    """Class used to manage connection and data ingest to InfluxDB.

    Methods:
        connect: Initializes InfluxDBClient and connects to InfluxDB server
        disconnect: Ends connection to InfluxDB server and flushes buffer
        insert_dicts_to_buffer: Inserts records (collected from OC) into intermediate buffer
        flush_insert_buffer: Sends contents of intermediate buffer to InfluxDB

    TODO:
        - Identify functionality from SppMon's InfluxClient that should be implemented in SpInfluxClient
        - Implement fallback_max_batch_size
        - Implement metrics tracking for insert operations
    """

    @property
    def version(self):
        return self.__version

    __insert_buffer: Dict[SpInfluxTableDefinition, List[Point]] = {}
    """Holds records formatted for insert to InfluxDB. Each key is associated with a list of all records
    to be inserted using the associated table definition."""

    __query_max_batch_size = 5000
    """Max number of records to be sent to InfluxDB at a time."""

    def __init__(self,
                 sp_influx_server_params: SpInfluxParams,
                 verbose: bool = False):
        """Initializes SpInfluxClient. Connect should be used to initialize InfluxDBClient
        before any other methods are called.

        Args:
            sp_influx_server_params {SpInfluxParams}: Influx server connection parameters.
            verbose {bool}: Whether log output should be detailed.
        """
        self.sp_influx_server_params: SpInfluxParams = sp_influx_server_params
        self.verbose: bool = verbose

        self.__client: InfluxDBClient | None = None
        self.__current_buffer_size: int = 0
        self.__version: str | None = None

    def get_url(self) -> str:
        """Builds InfluxDB URL.

        Returns:
            {str} - URL endpoint of InfluxDB Server
        """
        return f"http://{self.sp_influx_server_params.srv_address}:{self.sp_influx_server_params.srv_port}"

    def connect(self) -> None:
        """Initializes InfluxDBClient and tests connection to InfluxDB server. Configures logger.

        TODO:
            - Consider initializing WRITE API and setting write options.
        """
        self.__client = InfluxDBClient(
            url=self.get_url(),
            token=self.sp_influx_server_params.token,
            org=self.sp_influx_server_params.org,
            debug=self.verbose
        )

        connected: bool = self.__client.ping()
        if not connected:
            raise ValueError("Login to influxdb failed")

        self.__version: str = self.__client.version()
        LOGGER.info(f"Connected to influxdb, version: {self.__version}")

        for _, logger in self.__client.conf.loggers.items():
            logger.setLevel(logging.DEBUG)
            logger.addHandler(logging.StreamHandler(sys.stdout))

    def disconnect(self) -> None:
        """Disconnects from InfluxDB server. Attempts to flush buffer before doing so.

        Raises:
            ValueError: Could not flush buffer.
        """
        try:
            self.flush_insert_buffer()
        except ValueError as error:
            ExceptionUtils.exception_info(
                error=error,
                extra_message="Failed to flush buffer on logout, possible data loss")

        self.__client.close()
        self.__client = None
        LOGGER.info("Disconnected from influxdb")

    def insert_dicts_to_buffer(self,
                               table_definition: SpInfluxTableDefinition,
                               paginated_records: SpRestResponsePage) -> None:
        """Inserts paginated list of records into the insert_buffer. Each page is inserted as a Point.
        Length of the insert_buffer is checked after each insert and flushed if safe limit is exceeded.

        Args:
            table_definition {SpInfluxTableDefinition}: Parameters used to insert Points into InfluxDB
            paginated_records {SpResponsePage}: Record pages associated with the table_definition

        TODO:
            - Consider extracting logic for processing records to points into a SpInfluxUtils
            - Add validation for parameters
        """

        record_buffer = []
        # Format records as Points and append to record_buffer
        for record in paginated_records.items:
            # Flatten dictionary containing time_key
            SpInfluxUtils.format_db2_time_key(
                record=record,
                time_key=table_definition.datetime
            )
            record["HOST"] = paginated_records.host
            record_as_point = Point.from_dict(
                dictionary=record,
                write_precision=WritePrecision.S,
                record_measurement_name=table_definition.measurement,
                record_time_key=table_definition.datetime,
                record_tag_keys=table_definition.tags,
                record_field_keys=table_definition.fields
            )
            record_buffer.append(record_as_point)

        # Extend table_buffer with contents of record_buffer
        table_buffer = self.__insert_buffer.get(table_definition, list())
        table_buffer.extend(record_buffer)
        self.__insert_buffer[table_definition] = table_buffer
        self.__current_buffer_size += len(record_buffer)
        LOGGER.info(f"Appended {len(record_buffer)} items to the insert buffer")

        # Flush insert buffer if length exceeds safe limit
        if self.__current_buffer_size >= (safe_limit := 2 * self.__query_max_batch_size):
            LOGGER.info(f"Record buffer ({self.__current_buffer_size}) has exceeded or met the safe limit of "
                        f"{safe_limit} entries. Flushing buffer.")
            self.flush_insert_buffer()

    def flush_insert_buffer(self) -> None:
        """Sends contents of insert_buffer to InfluxDB. Uses default write options settings for retry,
        batch size, etc.

        Raises:
            ValueError: Insert buffer is None (not initialized).

        TODO:
            - Implement fallback
            - Implement user configuration of write options

        """
        if self.__insert_buffer is None:
            raise ValueError("Insert buffer has not been initialized.")

        if not self.__insert_buffer:
            LOGGER.info("Attempted to flush buffer but it was empty.")
            return

        table_definitions = list(self.__insert_buffer.keys())

        for table_definition in table_definitions:
            record_list = self.__insert_buffer.get(table_definition)

            try:
                # Note: Seems like all points get sent as a single new line delimited string in body
                # of POST request. Not sure if batch size matters for write.
                with self.__client.write_api(
                    write_options=SYNCHRONOUS
                ) as write_api:
                    write_api.write(
                        bucket=self.sp_influx_server_params.bucket,
                        record=record_list,
                    )
                inserted_points: List[Point] = self.__insert_buffer.pop(table_definition, None)
                self.__current_buffer_size -= len(inserted_points)
            except InfluxDBError as error:
                ExceptionUtils.exception_info(
                    error=error,
                    extra_message=f"An error occurred when sending insert buffer "
                                  + "for table {table_definition.measurement}"
                )

            LOGGER.info(f"Sent {len(record_list)} records for '{table_definition.measurement}' as a point to influx.")