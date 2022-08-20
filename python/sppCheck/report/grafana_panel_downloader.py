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
import shutil
from datetime import datetime
from os.path import isdir, exists
from pathlib import Path
from typing import Any, Dict, Optional

from dateutil.relativedelta import relativedelta
from influx.database_tables import RetentionPolicy
from influx.influx_client import InfluxClient
from requests import ReadTimeout, RequestException, get
from requests.auth import HTTPBasicAuth
from utils.exception_utils import ExceptionUtils
from utils.sppcheck_utils import Themes

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class GrafanaPanelDownloader:

    def __init__(
        self,
        influx_client: InfluxClient,
        select_rp: RetentionPolicy,
        start_date: datetime,
        config_file: Dict[str, Any],
        end_date: datetime,
        prediction_rp: RetentionPolicy,
        excel_rp: RetentionPolicy,
        temp_dir_path: Path,
        theme: Themes) -> None:

        LOGGER.debug("Setting up the PictureDownloader")

        #### Saving class variables ####
        self.__influx_client: InfluxClient = influx_client
        self.__end_date = end_date
        self.__start_date = start_date

        #### Preparing Path where the pictures should be saved ####
        self.__temp_dir_path = temp_dir_path
        if not isdir(self.__temp_dir_path):
            raise ValueError(f"The pdf-temp_files folder does not exist: {self.__temp_dir_path}")
        LOGGER.debug(f"Pictures Path set to {self.__temp_dir_path}")

        #### Reading config for grafana login ####
        try:
            grafana_conf: Dict[str, Any] = config_file["grafana"]

            # required
            username = grafana_conf["username"]
            password = grafana_conf["password"]
            ssl = grafana_conf["ssl"]
            self.__verify_ssl = grafana_conf["verify_ssl"]
            srv_port = grafana_conf["srv_port"]
            srv_address = grafana_conf["srv_address"]

            # optional
            datasource_name = grafana_conf.get("datasource_name", self.__influx_client.database.name)

            orgId = grafana_conf.get("orgId", 1)
        except KeyError as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("No Grafana configuration available in the config file! Aborting")

        #### Preparing URL to server ####
        if ssl:
            self.__srv_url += "https://"
        else:
            self.__srv_url = "http://"
            # disable the verify to avoid bugs
            self.__verify_ssl = False
        self.__srv_url += f"{srv_address}:{srv_port}"
        LOGGER.debug(f"Server url set to {self.__srv_url}")

        self.__http_auth: HTTPBasicAuth = HTTPBasicAuth(username, password)

        #### testing connection ####
        LOGGER.info("> Testing connection to Grafana")

        test_url = f"{self.__srv_url}/api/org"
        try:
            response = get(
                url=test_url,
                auth=self.__http_auth,
                verify=self.__verify_ssl
            )
        except (ReadTimeout, RequestException) as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("Failed to connect to Grafana, please check the configs")
        if response.ok:
            LOGGER.info("> Test successfully")
        else:
            raise ValueError("Failed to connect to Grafana, please check the configs")

        #### Preparing theme ####

        if theme in [Themes.LIGHT, Themes.DARK]:
            theme_str = theme.value
        else:
            theme_str = Themes.LIGHT.value

        #### Preparing panel download URL ####
        # spaces (replaced by "+") in the url dont matter. Works anyway
        self.__panel_prefix_url = f"{self.__srv_url}/render/d-solo/sppcheck/sppcheck-for-ibm-spectrum-protect-plus" + \
                                        f"?orgId={orgId}&var-server={datasource_name}&var-rp={select_rp.name}&theme={theme_str}"

        if prediction_rp:
            self.__panel_prefix_url += f"&var-prediction={prediction_rp.name}"
        if excel_rp:
            self.__panel_prefix_url += f"&var-excel={excel_rp.name}"
        LOGGER.debug(f"Full panel prefix set to {self.__panel_prefix_url}")

    def download_panel(self, panel_id: int, width: int, height: int, file_name: str,
                         relative_from_years: Optional[int] = None,
                         relative_to_years: Optional[int] = None) -> Path:
        """Downloads the panel with the given ID from grafana.

        Uses start_date to now + prediction years range unless relative ranges specified

        Args:
            panelId (int): ID of the grafana panel to download
            width (int): width of the picture in pixel
            height (int): height of the picture in pixel
            file_name (str): name of the panel, used as filename
            relative_from_years (Optional[int], optional): Optional relative time range from now. Defaults to start_date.
            relative_to_years (Optional[int], optional):  Optional relative time range from now. Defaults to now + prediction years.

        Raises:
            ValueError: Either of the relative time ranges is given. Both need to be either omitted or given.
            ValueError: Failed to download the picture from grafana, but receiving an answer with status code
            ValueError: Failed to download the picture from grafana, exiting with a Exception

        Returns:
            Path: relative path to the generated picture, origin from the python folder.
        """

        LOGGER.info(f">>> Downloading Grafana Panel {panel_id}")

        if bool(relative_from_years) != bool(relative_to_years):
            LOGGER.debug(f"relative_from_yeas: {relative_from_years}, relative_to_years: {relative_to_years}")
            raise ValueError("If using either relative_from_yeas or relative_to_years, you must also use the other one.")

        ### create the save path of the downloaded picture ####
        full_file_name = Path(file_name + ".png")
        save_path = Path(self.__temp_dir_path, full_file_name)
        LOGGER.debug(f"save_path: {save_path}")

        # all old files are cleared before
        if exists(save_path):
            raise ValueError(f"Duplicate Path - a file already exists on path: {save_path}")

        # get from and to timestamps, adjust precision from seconds to ms
        # the args year"s" is important, making it relative instead of setting it to the val
        if relative_to_years and relative_from_years:
            from_timestamp = int((datetime.now() - relativedelta(years=relative_to_years)).timestamp()) * 1000
            to_timestamp = int((datetime.now() + relativedelta(years=relative_to_years)).timestamp()) * 1000

        else:
            # use absolute range from start to the very end
            from_timestamp = int(self.__start_date.timestamp()) * 1000
            to_timestamp = int(self.__end_date.timestamp()) * 1000


        ### compute the final URL ###
        request_url = f"{self.__panel_prefix_url}&panelId={panel_id}&width={width}&height={height}" + \
                            f"&from={from_timestamp}&to={to_timestamp}"
        LOGGER.debug(f"request_url: {request_url}")

        try:
            response = get(url=request_url, auth=self.__http_auth, verify=self.__verify_ssl, stream=True)

            if response.ok:
                with open(save_path, 'wb') as file:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, file)
            else:
                raise ValueError(f"Failed to query image from Grafana, code: {response.status_code}, {response.reason}")
        except (ReadTimeout, RequestException) as error:
            ExceptionUtils.exception_info(error)
            raise ValueError("Failed to query image from Grafana due to a Timeout or Server error.")

        LOGGER.debug(f">>> Successfully downloaded Grafana Panel {panel_id}")

        return full_file_name
