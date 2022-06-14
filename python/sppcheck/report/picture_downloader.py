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
import shutil
from dateutil.relativedelta import relativedelta
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from os.path import isdir

from requests import ReadTimeout, RequestException, get
from requests.auth import HTTPBasicAuth

from influx.database_tables import RetentionPolicy

from influx.influx_client import InfluxClient
from utils.exception_utils import ExceptionUtils

LOGGER_NAME = 'sppmon'
LOGGER = logging.getLogger(LOGGER_NAME)

class PictureDownloader:

    def __init__(
        self,
        influx_client: InfluxClient,
        select_rp: RetentionPolicy,
        start_date: datetime,
        config_file: Dict[str, Any],
        predict_years: int,
        prediction_rp: Optional[RetentionPolicy],
        excel_rp: Optional[RetentionPolicy]) -> None:

        self.__influx_client: InfluxClient = influx_client

        self.__pictures_path = Path("sppcheck", "report", "pictures")
        if not isdir(self.__pictures_path):
            raise ValueError(f"The pdf-picture folder does not exits: {self.__pictures_path}")

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

        if ssl:
            self.__srv_url += "https://"
        else:
            self.__srv_url = "http://"
            # disable the verify to avoid bugs
            self.__verify_ssl = False
        self.__srv_url += f"{srv_address}:{srv_port}"

        # get from and to timestamps, adjust precision
        time_future = int((datetime.now() + relativedelta(years=predict_years)).timestamp()) * 1000
        time_past = int(start_date.timestamp()) * 1000

        self.__panel_prefix_url = f"{self.__srv_url}/render/d-solo/sppcheck/sppcheck-for-ibm-spectrum-protect-plus" + \
                                  f"?orgId={orgId}&from={time_past}&to={time_future}" + \
                                  f"&var-server={datasource_name}&var-rp={select_rp.name}"

        if prediction_rp:
            self.__panel_prefix_url += f"&var-prediction={prediction_rp.name}"
        if excel_rp:
            self.__panel_prefix_url += f"&var-excel={excel_rp.name}"

        self.__http_auth: HTTPBasicAuth = HTTPBasicAuth(username, password)

        # test connection
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

    def download_picture(self, panelId: int, width: int, height: int, name: str) -> Path:
        save_path = Path(self.__pictures_path, name + ".png")
        request_url = f"{self.__panel_prefix_url}&panelId={panelId}&width={width}&height={height}"
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
            raise ValueError("Failed to query image from Grafana")

        return save_path