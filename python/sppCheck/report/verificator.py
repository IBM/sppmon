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
from pathlib import Path
from os.path import exists, isfile
from typing import Dict, Any, Optional

from influx.database_tables import RetentionPolicy

from influx.influx_client import InfluxClient
from sppCheck.report.picture_downloader import PictureDownloader

class Verificator:

    def __init__(
        self,
        influx_client: InfluxClient,
        dp_interval_hour: int,
        select_rp: RetentionPolicy,
        rp_timestamp: str,
        start_date: datetime,
        config_file: Dict[str, Any],
        predict_years: int,
        prediction_rp: Optional[RetentionPolicy],
        excel_rp: Optional[RetentionPolicy]) -> None:
        if not influx_client:
            raise ValueError("Logic Tool is not available, missing the influx_client")

        self.__influx_client: InfluxClient = influx_client

        self.__picture_generator = PictureDownloader(
            influx_client,
            select_rp, start_date,
            config_file, predict_years,
            prediction_rp, excel_rp)

        self.__template_pdf = Path("sppcheck", "report", "SPPCheck Template.pdf")
        if not exists(self.__template_pdf) and isfile(self.__template_pdf):
            raise ValueError("Template PDF does not exists or is not a file.")
