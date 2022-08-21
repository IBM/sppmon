"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2020, 2021. All Rights Reserved.

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
    This Module provides other themed features.
    You may implement new methods here if they do not fit anywhere else

Classes:
    OtherMethods
"""

from sppmonMethods.ssh import SshMethods
from sppConnection.ssh_client import SshClient, SshTypes
from sppConnection.rest_client import RestClient
from typing import Any, Dict, List, Optional
from influx.influx_client import InfluxClient
from utils.methods_utils import MethodUtils
import logging


from utils.exception_utils import ExceptionUtils

LOGGER = logging.getLogger("sppmon")


class OtherMethods:

    @staticmethod
    def test_connection(influx_client: InfluxClient, rest_client: Optional[RestClient], config_file: Dict[str, Any]):
        if(not config_file):
            raise ValueError("SPPmon does not work without a config file")

        LOGGER.info("Testing all connections required for SPPMon to work")
        working: bool = True # SPPMon itself will finish successful (no critical errors)
        no_warnings: bool = True # SPPMon will finish without any warnings (no errors at all)

        # ## InfluxDB ##

        LOGGER.info("> Testing and configuring InfluxDB")
        try:
            influx_client.connect()
            influx_client.disconnect()
            if(not influx_client.use_ssl):
                ExceptionUtils.error_message("> WARNING: Mandatory SSL is disabled. We highly recommend to enable it!")
                no_warnings = False

            LOGGER.info("InfluxDB is ready for use")
        except ValueError as error:
            ExceptionUtils.exception_info(error, extra_message="> Testing of the InfluxDB failed. This is a critical component of SPPMon.")
            working = False

        # ## REST-API ##

        LOGGER.info("> Testing REST-API of SPP.")
        try:
            if(not rest_client):
                raise ValueError("Rest-client is setup. Unavailable to test it.")
            rest_client.login()
            (version_nr, build_nr) = rest_client.get_spp_version_build()
            LOGGER.info(f">> Successfully connected to SPP V{version_nr}, build {build_nr}.")
            rest_client.logout()
            LOGGER.info("> REST-API is ready for use")
        except ValueError as error:
            ExceptionUtils.exception_info(error, extra_message="> Testing of the REST-API failed. This is a critical component of SPPMon.")
            working = False

        # ## SSH-CLIENTS ##

        LOGGER.info("> Testing all types of SSH-Clients: Server, VAPDs, vSnaps, Cloudproxy and others")
        ssh_working = True # The arg --ssh will finish without any error at all

        # Count of clients checks
        ssh_clients: List[SshClient] = SshMethods.setup_ssh_clients(config_file)
        if(not ssh_clients):
            ExceptionUtils.error_message(">> No SSH-clients detected at all. At least the server itself should be added for process-statistics.")
            ssh_working = False
        else:
            for type in SshTypes:
                if(not list(filter(lambda client: client.client_type == type , ssh_clients))):
                    LOGGER.info(f">> No {type.name} client detected.")

                    if(type == SshTypes.SERVER):
                        ExceptionUtils.error_message(">> Critical: Without Server as ssh client you wont have any process statistics available. These are a key part of SPPMon.")
                        ssh_working = False # No error, but still critical

                    if(type == SshTypes.VSNAP):
                        LOGGER.info(">> WARNING: Without vSnap as ssh client you have no access to storage information. You may add vSnap's for additional monitoring and alerts.")
                        no_warnings = False # ssh will still work, but thats definitely a warning

            ssh_methods: SshMethods = SshMethods(influx_client, config_file, False)
            # Connection check
            LOGGER.info(f">> Testing now connection and commands of {len(ssh_clients)} registered ssh-clients.")
            for client in ssh_clients:
                try:
                    client.connect()
                    client.disconnect()

                    error_count: int = len(ExceptionUtils.stored_errors)
                    MethodUtils.ssh_execute_commands(
                        ssh_clients=[client],
                        ssh_type=client.client_type,
                        command_list=ssh_methods.client_commands[client.client_type] + ssh_methods.all_command_list)
                    if(len(ExceptionUtils.stored_errors) != error_count):
                        ssh_working = False
                        ExceptionUtils.error_message(
                            f"Not all commands available for client {client.host_name} with type: {client.client_type}.\n" +
                            "Please check manually if the commands are installed and their output.")

                except ValueError as error:
                    ExceptionUtils.exception_info(error, extra_message=f"Connection failed for client {client.host_name} with type: {client.client_type}.")
                    ssh_working = False

        if(ssh_working):
            LOGGER.info("> Testing of SSH-clients successfully.")
        else:
            LOGGER.info("> Testing of SSH-clients failed! SPPMon will still work, not all information are available.")
            no_warnings = False

        # #### Conclusion ####

        if(working and no_warnings):
            LOGGER.info("> All components tested successfully. SPPMon is ready to be used!")
        elif(working):
            LOGGER.info("> Testing partially successful. SPPMon will run, but please check the warnings.")
        else:
            LOGGER.info("> Testing failed. SPPMon is not ready to be used. Please fix the connection issues.")
