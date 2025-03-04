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
    This Module provides SPPMon testing methods.
    You may implement new methods to test the functionality of SPPMon

Classes:
    TestingMethods
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from influx.influx_client import InfluxClient
from sppConnection.rest_client import RestClient
from sppConnection.ssh_client import SshClient, SshTypes
from utils.exception_utils import ExceptionUtils
from utils.methods_utils import MethodUtils
from utils.spp_utils import SppUtils

from sppmonMethods.ssh import SshMethods

LOGGER = logging.getLogger("sppmon")


class TestingMethods():
    """This Class groups all methods used for testing the aspects of SPPMon, both connectivity and functionality
    """

    @classmethod
    def __test_influx(cls, influx_client: Optional[InfluxClient]) -> Tuple[List[str], List[str]]:
        """Extracted code for testing the connectivity of the influxDB.

        A Influxclient is used due to the requirement of setting up a influxClient anyway.
        No connection should be established until done so by this method

        Args:
            influx_client (Optional[InfluxClient]): influxdb to be tested

        Returns:
            Tuple[List[str], List[str]]: Two lists: Errors and Warnings
        """

        # Note: Use influx_client due the necessarily to set it up anyway beforehand
        # First connect is inside of this testing

        LOGGER.info("> Testing and configuring InfluxDB")

        warnings: List[str] = []
        errors: List[str] = []

        if(not influx_client):
            ExceptionUtils.error_message(
                "Setup of the InfluxDB failed. Probably an error within the config file.")
            errors.append(
                "Setup of the InfluxDB failed. Probably an error within the config file.")
            return (errors, warnings)

        if(not influx_client.use_ssl):
            warnings.append(
                "The influxDB does not use a HTTPS connection. Please consider enabling it.")

        try:
            influx_client.connect()
            # illegal access onto user list, but better than exposing everywhere. This is a limited test case.
            user_list: List[Dict[str, Union[str, bool]]
                            ] = influx_client._InfluxClient__client.get_list_users()
            for user in user_list:
                # impossible to read their passwords here
                if(user.get("user", None) == "sppmonInfluxUser"):
                    warnings.append(
                        "The user sppmonInfluxUser still exists within the influxDB. " +
                        "Please delete it, use influxAdmin instead.")

            influx_client.disconnect()
            if(not influx_client.use_ssl):
                ExceptionUtils.error_message(
                    "> WARNING: Mandatory SSL is disabled. We highly recommend to enable it!")
                warnings.append(
                    "Mandatory SSL for the connection with the InfluxDB is disabled. " +
                    "We highly recommend to enable it!")

        except ValueError as error:
            ExceptionUtils.exception_info(
                error, "Connection to the InfluxDB failed.")
            errors.append(
                "Connecting and Disconnecting to the InfluxDB failed. Probably either a URL or Auth error.")
            return (errors, warnings)

        LOGGER.info("Tested InfluxDB successfully. Ready for use")
        return (errors, warnings)

    @classmethod
    def __test_REST_API(cls, rest_client: Optional[RestClient]) -> Tuple[List[str], List[str]]:
        """Extracted code for testing the connectivity of the REST-API.

        A rest_client is used due mass of variables used to setup the client.
        No connection should be established until done so by this method

        Args:
            rest_client (Optional[RestClient]): rest_client to be tested

        Returns:
            Tuple[List[str], List[str]]: Two lists: Errors and Warnings
        """

        LOGGER.info("> Testing REST-API of SPP.")

        warnings: List[str] = []
        errors: List[str] = []
        if(not rest_client):
            errors.append(
                "Setting up of the Rest-Client failed. The Config file may be corrupted.")
            return (errors, warnings)

        try:
            rest_client.login()
            (version_nr, build_nr) = rest_client.get_spp_version_build()
            LOGGER.info(
                f">> Successfully connected to SPP V{version_nr}, build {build_nr}.")
            rest_client.logout()
        except ValueError:
            errors.append(
                "The connection to the REST-API failed. Probably either a URL or Auth error.")
            return (errors, warnings)

        LOGGER.info("> REST-API is ready for use")

        return (errors, warnings)

    @classmethod
    def __test_ssh(cls, config_file: Dict[str, Any], influx_client: Optional[InfluxClient]) -> Tuple[List[str], List[str]]:
        """Extracted code for testing the connection and execution of ssh-clients.

        Any errors might not stop SPPMon, but will cause a serious data loss due missing collection.
        Adding a SPP-Server as client is required, not doing so is counted as error.
        Having no vSnap-Sever added will cause a warning.

        Args:
            config_file (Dict[str, Any]): config file with ssh-client definitions
            influx_client (Optional[InfluxClient]): influxDB client, none if setup failed

        Returns:
            Tuple[List[str], List[str]]: Two lists: Errors and Warnings
        """

        LOGGER.info(
            "> Testing all types of SSH-Clients: Server, VADPs, vSnaps, Cloudproxy and others")

        warnings: List[str] = []
        errors: List[str] = []

        # ### Check count of clients available ###
        ssh_clients: List[SshClient] = []
        try:
            ssh_clients = SshMethods.setup_ssh_clients(config_file)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, "Error when reading config file for ssh-clients. The auth file might be inconsistent")
            errors.append(
                "Error when reading config file for ssh-clients. The auth file might be inconsistent")
            return (errors, warnings)

        # Check any available
        if(not ssh_clients):
            ExceptionUtils.error_message(
                ">> No SSH-clients detected within the config file. " +
                "At least the REST-Server should be added. SPPMon will still complete but this will greatly reduce the data to be displayed.")
            errors.append("No SSH-clients detected within the config file. " +
            "At least the REST-Server should be added. SPPMon will still complete but this will greatly reduce the data to be displayed.")
            return (errors, warnings)

        # Check server added
        if(not list(filter(lambda client: client.client_type == SshTypes.SERVER, ssh_clients))):
            ExceptionUtils.error_message(
                ">> The REST-Server is not registered as SHH-Client. " +
                "SPPMon will still complete but this will greatly reduce the data to be displayed.")
            errors.append(
                "The REST-Server is not registered as SHH-Client. " +
                "SPPMon will still complete but this will greatly reduce the data to be displayed.")

        # Check vSnap added
        if(not list(filter(lambda client: client.client_type == SshTypes.VSNAP, ssh_clients))):
            LOGGER.info(
                ">> WARNING: No vSnap is registered as SHH-Client. " +
                "SPPMon will still complete but no storage information will be displayed.")
            warnings.append(
                "No vSnap is registered as SHH-Client. " +
                "SPPMon will still complete but no storage information will be displayed.")

        # Check total missing clients
        missing_types: Set[SshTypes] = set(SshTypes)
        for client in ssh_clients:
            if(client.client_type in missing_types):
                missing_types.remove(client.client_type)
        if(missing_types):
            warnings.append(
                f"""This is only a reminder: No ssh-clients of following types are registered: {", ".join(map(str, missing_types))}""")


        if(not influx_client):
            ExceptionUtils.error_message(
                "Further testing is dependent on the InfluxDB. Impossible to test due errors.")
            errors.append(
                "Further testing is dependent on the InfluxDB. Impossible to test due errors.")
            return (errors, warnings)

        try:
            ssh_methods: SshMethods = SshMethods(
                influx_client, config_file, False)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, "Error when setting up SSH-Clients. Probably a inconsistency within the config file.")
            errors.append(
                "Error when setting up SSH-Clients. Probably a inconsistency within the config file.")
            return (errors, warnings)

        # Connection check
        LOGGER.info(
            f">> Testing connection and commands of each of the {len(ssh_clients)} registered ssh-clients.")
        for client in ssh_clients:
            try:
                LOGGER.info(f"Testing connection to client {client.host_name}")

                client.connect()
                client.disconnect()

                LOGGER.info("Successfully connected.")

            except ValueError as error:
                ExceptionUtils.exception_info(
                    error, f"Connecting to client {client.host_name} with type {client.client_type} failed.")
                errors.append(
                    f"Connecting to client {client.host_name} with type {client.client_type} failed.")
                continue

            LOGGER.info(
                f"Testing individual commands for client {client.host_name}")

            # it is not easy possible / much work needed to execute all commands one by one
            # Therefore I check the errors before executing and afterwards
            # If there is an increase, some commands failed
            error_count: int = len(ExceptionUtils.stored_errors)

            command_list = ssh_methods.client_commands[client.client_type] + \
                ssh_methods.all_command_list
            try:
                MethodUtils.ssh_execute_commands(
                    ssh_clients=[client],
                    ssh_type=client.client_type,
                    command_list=command_list)
            except ValueError as error:
                ExceptionUtils.exception_info(
                    error, extra_message=
                    f"Critical error when executing ssh commands for client {client}. Please review.")
                errors.append(
                    f"Critical error when executing ssh commands for client {client}. Please review.")

            # Check if errors increased
            if(len(ExceptionUtils.stored_errors) != error_count):
                ExceptionUtils.error_message(
                    f"Not all commands available for client {client.host_name} with type: {client.client_type}.\n" +
                    "Please check manually if the commands are available.")

                errors.append(
                    f"A SSH-Command failed for client {client.host_name} with type {client.client_type}.\n" +
                    "\tPlease check manually if all following commands are available:\n" +
                    "\n".join(map(lambda command: "\t" + command.cmd, command_list)))

            else:
                LOGGER.info("Successfully executed commands.")

        return (errors, warnings)

    @staticmethod
    def __password_similarity_check(info_dict: Dict[str, Any], logger_name: str) -> Tuple[List[str], List[str]]:

        warnings: List[str] = []
        errors: List[str] = []

        compromised_passwords: List[str] = [
            "Test_1234a", "sppM0n_Au1h", "gr8fana_Au1h", "sppmon", "NOT_A_SAFE_PASSWORD"]

        password: str = info_dict.get("password", None)
        if(not password):
            errors.append(
                f"No password found in the {logger_name}-config file part.")

        similarity: float = 0
        for password_check in compromised_passwords:
            similarity = max(SequenceMatcher(
                None, password, password_check).quick_ratio(), similarity)
        if(similarity >= 0.7):
            errors.append(
                f"The {logger_name} password is too similar to the old wiki-password and MUST be changed.")

        return (errors, warnings)

    @classmethod
    def __test_config_file(cls, config_file: Dict[str, Any]) -> Tuple[List[str], List[str]]:

        warnings: List[str] = []
        errors: List[str] = []
        try:
            rest_info: Dict[str, Any] = SppUtils.get_cfg_params(
                config_file, "sppServer")

            # see Merge #60, fixes typo. Deprecated since 0.14, remove compatibility in v1.1
            if("jobLog_rentation" in rest_info):
                warnings.append(
                    "Config file has typo in sppServer-topic: Replace `jobLog_rentation` by `jobLog_retention`")

            pwd_error, pwd_warning = cls.__password_similarity_check(
                rest_info, "REST-API")
            errors.extend(pwd_error)
            warnings.extend(pwd_warning)

        except (ValueError, Exception) as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Extracting REST-Client out of the config file failed.")
            errors.append(
                "Extracting REST-Client out of the config file failed.")

        try:
            influx_info: Dict[str, Any] = SppUtils.get_cfg_params(
                config_file, "influxDB")

            pwd_error, pwd_warning = cls.__password_similarity_check(
                influx_info, "InfluxDB")
            errors.extend(pwd_error)
            warnings.extend(pwd_warning)

        except (ValueError, Exception) as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Extracting influxDB out of the config file failed.")
            errors.append("Extracting influxDB out of the config file failed.")

        try:
            ssh_client_info: List[Dict[str, Any]] = SppUtils.get_cfg_params(
                config_file, "sshclients")

            for client in ssh_client_info:
                client_name = client.get("name", "UNKNOWN-SSH-CLIENT")
                pwd_error, pwd_warning = cls.__password_similarity_check(
                    client, "ssh-client-" + client_name)
                errors.extend(pwd_error)
                warnings.extend(pwd_warning)

        except (ValueError, Exception) as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Extracting influxDB out of the config file failed.")
            errors.append("Extracting influxDB out of the config file failed.")

        return (errors, warnings)

    @classmethod
    def test_connection(cls, config_file: Dict[str, Any], influx_client: Optional[InfluxClient], rest_client: Optional[RestClient]):
        """Tests the connectivity and functionality of all aspects of SPPMon.

        Errors within the influxDB and REST-Client count as critical error, ssh only as non-critical error.
        Creates a error summary at the very end. Warnings will be recorded too and listed.
        Both REST-Client and InfluxDB should not be connected beforehand, only created.

        Args:
            config_file (Dict[str, Any]): sppmon config file
            influx_client (Optional[InfluxClient]): created, but not connected influxClient
            rest_client (Optional[RestClient]): created, but not connected RestClient
        """

        # Note: Use influx_client and rest_client due the variable-heavy setup (rest)
        # and necessarily to set it up anyway beforehand (influx)
        # First connect is inside of this testing
        if(not config_file):
            raise ValueError("SPPmon does not work without a config file")

        general_warnings: List[str] = []
        general_errors: List[str] = []

        # ## Config file ##

        try:
            config_errors, config_warnings = cls.__test_config_file(
                config_file)
            general_warnings.extend(config_warnings)
            general_errors.extend(config_errors)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Checking the config file failed due an unknown error.")
            general_errors.append(
                "Checking the config file failed due an unknown error.")

        # ######## Connection start ########

        LOGGER.info("Testing all connections required for SPPMon to work")

        # ## InfluxDB ##
        try:
            influx_errors, influx_warnings = cls.__test_influx(influx_client)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Testing of the InfluxDB failed due an unknown error")
            influx_errors: List[str] = [
                "Testing of the InfluxDB failed due an unknown error."]
            influx_warnings: List[str] = []

        if(influx_errors):
            influx_client = None

        print("\n", flush=True)
        # ## REST-API ##

        try:
            rest_errors, rest_warnings = cls.__test_REST_API(rest_client)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Testing of the REST-API failed due an unknown error")
            rest_errors: List[str] = [
                "Testing of the REST-API failed due an unknown error."]
            rest_warnings: List[str] = []

        print("\n", flush=True)
        # ## SSH-CLIENTS ##

        try:
            ssh_errors, ssh_warnings = cls.__test_ssh(
                config_file, influx_client)
        except ValueError as error:
            ExceptionUtils.exception_info(
                error, extra_message="> Testing of the SSH-Clients failed due an unknown error")
            ssh_errors: List[str] = [
                "Testing of the SSH-Clients failed due an unknown error."]
            ssh_warnings: List[str] = []

        print("\n", flush=True)
        # #### Conclusion ####

        LOGGER.info("#### Testing Summary ###")
        print("\n", flush=True)
        summary_message: str = ""

        if(influx_errors or rest_errors or general_errors):
            # only amplify message: change if empty
            if(not summary_message):
                summary_message = "Testing failed. SPPMon is NOT ready to be used."

            # print messages
            LOGGER.info("### Critical errors, required to fix ###")
            for i, error in enumerate(influx_errors + rest_errors + general_errors, 1):
                LOGGER.info(f"Nr {i}: {error}")
            print("\n", flush=True)

        if(ssh_errors):
            # only amplify message: change if empty
            if(not summary_message):
                summary_message = "Testing completed with non-critical errors. " + \
                "SPPMon will run, but data will be missing. Please review the errors listed above."

            # print messages
            LOGGER.info("### Non-Critical errors which cause a data loss ###")
            for i, error in enumerate(ssh_errors, 1):
                LOGGER.info(f"Nr {i}: {error}")
            print("\n", flush=True)

        if(ssh_warnings or influx_warnings or rest_warnings or general_warnings):
            # only amplify message: change if empty
            if(not summary_message):
                summary_message = "Testing successful. Please review the warnings listed above."

            # print messages
            LOGGER.info("### Warnings to check before executing ###")
            for i, warning in enumerate(ssh_warnings + influx_warnings + rest_warnings + general_warnings, 1):
                LOGGER.info(f"Nr {i}: {warning}")
            print("\n", flush=True)

        # no case above hit
        if(not summary_message):
            summary_message = "Testing successful. SPPMon is ready to go."
        LOGGER.info("RESULT: " + summary_message)
