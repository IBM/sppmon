"""
(C) IBM Corporation 2021

Description:
    Creates new config files within the default config file dir.
    Uses both user input and authentification file for auth informations.


Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Niels Korschinsky
"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
from os.path import dirname, isfile, join, realpath
from typing import Any, Dict, List

from utils import Utils

LOGGER: logging.Logger


class ConfigFileSetup:
    """
    Creates new config files within the default config file dir.
    Uses both user input and authentification file for auth informations.

    Functions:
        addSshClient - Asks for ssh-login information for a certain ssh-client type.
        createServerDict - Asks SPP-REST-Server information from user and returns them.
        createInfluxDict - Reads InfluxDB config from authfile or asks user.
        main - See description above.

    """

    @staticmethod
    def addSshClient(ssh_type: str) -> List[Dict[str, Any]]:
        """Asks for ssh-login information for a certain ssh-client type.

        Args:
            ssh_type (str): Type of ssh-client.

        Returns:
            List[Dict[str, Any]]: List of added ssh-clients.
        """

        ssh_clients: List[Dict[str, Any]] = []

        Utils.printRow()
        LOGGER.info(
            f"> Collecting {ssh_type} ssh information")

        # counter for naming like: vsnap-1 / vsnap-2
        counter: int = 1

        while(Utils.confirm(f"Do you want to add (another) {ssh_type}-client?")):
            try:
                ssh_client: Dict[str, Any] = {}

                print(
                    "> Test the requested logins by logging into" +
                    f"the {ssh_type}-client via ssh yourself.")
                ssh_client["name"] = Utils.prompt_string(
                    f"Please enter the name of the {ssh_type}-client (display only)",
                    f"{ssh_type}-{counter}")
                counter += 1  # resetted on next ssh_type

                ssh_client["srv_address"] = Utils.prompt_string(
                    f"Please enter the server address of the {ssh_type}-client")
                ssh_client["srv_port"] = int(
                    Utils.prompt_string(
                        f"Please enter the port of the {ssh_type}-client",
                        "22",
                        filter=(lambda x: x.isdigit())))
                ssh_client["username"] = Utils.prompt_string(
                    f"Please enter the {ssh_type}-client username (equal to login via ssh)")
                ssh_client["password"] = Utils.prompt_string(
                    f"Please enter the {ssh_type}-client user password (equal to login via ssh)",
                    is_password=True)
                ssh_client["type"] = ssh_type

                # Saving config
                ssh_clients.append(ssh_client)

                Utils.printRow()
            except ValueError as err:
                LOGGER.error(err)
                LOGGER.info(
                    "Aborted adding this ssh client. Continuing with next client")
        return ssh_clients

    @staticmethod
    def createServerDict() -> Dict[str, Any]:
        """
        Asks SPP-REST-Server information from user and returns them.

        Returns:
            Dict[str, Any]: All Informations for SPP-REST-Access
        """
        spp_server: Dict[str, Any] = {}
        spp_server["username"] = Utils.prompt_string(
            "Please enter the SPP REST-API Username (equal to login via website)")
        spp_server["password"] = Utils.prompt_string(
            "Please enter the REST-API Users Password (equal to login via website)", is_password=True)
        spp_server["srv_address"] = Utils.prompt_string(
            "Please enter the SPP server address")

        spp_server["srv_port"] = int(
            Utils.prompt_string(
                "Please enter the SPP server port",
                "443",
                filter=(lambda x: x.isdigit())))

        spp_server["jobLog_retention"] = Utils.prompt_string(
            "How long are the JobLogs saved within the Server? (Format: 48h, 60d, 2w)",
            "60d",
            filter=(lambda x: bool(re.match(r"^[0-9]+[hdw]$", x))))
        return spp_server

    @staticmethod
    def createInfluxDict(server_name: str) -> Dict[str, Any]:
        """
        Reads InfluxDB config from authfile or asks user.

        Args:
            server_name (str): Name of SPP server to set influxDB-name

        Returns:
            Dict[str, Any]: All Informations for Influx-Access
        """

        influxDB: Dict[str, Any] = {}

        influxDB["username"] = Utils.readAuthOrInput(
            "influxAdminName",
            "Please enter the influxAdmin username",
            "influxAdmin"
        )

        influxDB["password"] = Utils.readAuthOrInput(
            "influxAdminPassword",
            "Please enter the influxAdmin user password",
            is_password=True
        )

        influxDB["ssl"] = bool(Utils.readAuthOrInput(
            "sslEnabled",
            "Please enter whether ssl is enabled (True/False)",
            "True",
            filter=(lambda x: bool(re.match(r"^(True)|(False)$", x)))
        ))

        # Only check this if ssl is enabled
        # Note: verify_ssl is the logical opposite of unsafeSsl
        influxDB["verify_ssl"] = False if (not influxDB["ssl"]) else not bool(Utils.readAuthOrInput(
            "unsafeSsl",
            "Please enter whether the ssl certificate is selfsigned (True/False)",
            filter=(lambda x: bool(re.match(r"^(True)|(False)$", x)))
        ))

        influxDB["srv_address"] = Utils.readAuthOrInput(
            "influxAddress",
            "Please enter the influx server address"
        )

        influxDB["srv_port"] = int(Utils.readAuthOrInput(
            "influxPort",
            "Please enter the influx server port",
            "8086",
            filter=(lambda x: x.isdigit())
        ))

        # Need to remove any illegal characters from the db name.  For now, we will limit the characters
        # to letters and numbers
        dbName = ''.join(filter(str.isalnum, server_name))
        LOGGER.info(
            f"> Your influxDB database name for this server is \"{dbName}\"")
        influxDB["dbName"] = dbName

        return influxDB

    def main(self, config_path: str, auth_file: str, auto_confirm: bool):
        """
        Creates new config files within the default config file dir.
        Uses both user input and authentification file for auth informations.

        Args:
            config_path (str): Config file DIR
            auth_file (str): File with pairs of authentification data
            auto_confirm (bool): Skip any confirm messages
        """

        fileDirPath = dirname(sys.argv[0])
        logPath = join(fileDirPath, "logs", "installLog.txt")

        global LOGGER_NAME
        LOGGER_NAME = 'configFileLogger'
        global LOGGER
        LOGGER = Utils.setupLogger(LOGGER_NAME, logPath)

        Utils.printRow()
        Utils.auto_confirm = auto_confirm
        Utils.LOGGER = LOGGER
        signal.signal(signal.SIGINT, Utils.signalHandler)

        LOGGER.info("> Checking for sudo rights")
        # Only works on Linux, therefore error here.
        if os.name == 'posix':
            if os.geteuid() == 0:
                print("Already root")
            else:
                print("Root rights required to run script.")
                subprocess.call(['sudo', 'python3', *sys.argv])
                sys.exit()

        LOGGER.info("> Generating new Config files")

        # ### Config dir setup
        config_path = realpath(config_path)
        LOGGER.info(
            f"> All new configurations files will be written into the directory:\n {config_path}")

        # ### authFile setup
        try:
            if(not auth_file):
                LOGGER.info("> No authentification file specifed")
                Utils.setupAuthFile(None)
            else:  # take none if not exists, otherwise take auth path
                Utils.setupAuthFile(auth_file)
        except Exception as error:
            LOGGER.info(f"> Setup of auth-file failed due error: {error}")

        # ########## EXECUTION ################
        Utils.printRow()
        LOGGER.info("> You may add multiple SPP-Server now.")
        print("> Each server requires it's own config file")

        try:
            while(Utils.confirm("\nDo you want to to add a new SPP-Server now?")):

                config_file_path: str = ""
                server_name: str = ""
                while(not config_file_path or not server_name):
                    # Servername for filename and config
                    server_name = Utils.prompt_string(
                        "What is the name of the SPP-Server? (Human Readable, no Spaces)",
                        filter=(lambda x: not " " in x))
                    # Replace spaces
                    config_file_path = join(
                        realpath(config_path), server_name + ".conf")

                    if(isfile(config_file_path)):
                        LOGGER.info(
                            f"> There is already a file at {config_file_path}.")
                        if(not Utils.confirm("Do you want to replace it?")):
                            LOGGER.info(
                                "> Please re-enter a different server name")
                            # remove content to allow loop to continue
                            config_file_path = ""
                            server_name = ""
                        else:
                            LOGGER.info("> Overwriting old config file")

                os.system("touch " + config_file_path)
                os.system("sudo chmod 600 " + config_file_path)
                LOGGER.info(f"> Created config file under {config_file_path}")

                # Overwrite existing file
                with open(config_file_path, "w") as config_file:
                    LOGGER.info(
                        f"> Accessed config file under {config_file_path}")

                    # Structure of the config file
                    configs: Dict[str, Any] = {}

                    # #################### SERVER ###############################
                    Utils.printRow()
                    LOGGER.info("> collecting server information")

                    # Saving config
                    configs["sppServer"] = ConfigFileSetup.createServerDict()

                    LOGGER.info("> finished collecting server information")
                    # #################### influxDB ###############################
                    Utils.printRow()
                    LOGGER.info("> collecting influxDB information")

                    # Saving config
                    configs["influxDB"] = ConfigFileSetup.createInfluxDict(
                        server_name)

                    LOGGER.info("> finished collecting influxdb information")
                    # #################### ssh clients ###############################
                    Utils.printRow()
                    LOGGER.info("> collecting ssh client information")

                    ssh_clients: List[Dict[str, Any]] = []

                    print("")
                    print("> NOTE: You will now be asked for multiple ssh logins")
                    print(
                        "> You may test all these logins yourself by logging in via ssh")
                    print("> Following categories will be asked:")
                    # server excluded here
                    ssh_types: List[str] = [
                        "vsnap", "vadp", "cloudproxy", "other"]
                    LOGGER.info("> server, " + ", ".join(ssh_types))
                    print("> Please add all clients accordingly.")
                    print()
                    print(
                        "> If you misstyped anything you may edit the config file manually afterwards")
                    print(
                        "> NOTE: It is highly recommended to add at least one vSnap client")

                    if(not Utils.confirm("Do you want to continue now?")):
                        json.dump(configs, config_file, indent=4)
                        LOGGER.info(
                            f"> saved all information into file {config_file_path}")
                        LOGGER.info("> finished setup for this server.")
                        continue  # Contiuing to the next server config file loop

                    # #################### ssh clients: SERVER ###############################
                    Utils.printRow()
                    LOGGER.info("> Collecting SPP-Server ssh information")

                    ssh_server: Dict[str, Any] = {}

                    print(
                        "> Test the requested logins by logging into the SPP-Server via ssh yourself.")
                    ssh_server["name"] = server_name
                    spp_server_dict: Dict[str, Any] = configs["sppServer"]
                    ssh_server["srv_address"] = spp_server_dict["srv_address"]
                    ssh_server["srv_port"] = int(
                        Utils.prompt_string(
                            f"Please enter the SSH port of the SPP server",
                            "22",
                            filter=(lambda x: x.isdigit())))
                    ssh_server["username"] = Utils.prompt_string(
                        "Please enter the SPP-Server SSH username (equal to login via ssh)")
                    ssh_server["password"] = Utils.prompt_string(
                        "Please enter the SPP-Server SSH user password (equal to login via ssh)",
                        is_password=True)
                    ssh_server["type"] = "server"

                    # Saving config
                    ssh_clients.append(ssh_server)

                    # #################### ssh clients all other ###############################
                    for ssh_type in ssh_types:
                        try:
                            ssh_clients.extend(ConfigFileSetup.addSshClient(ssh_type))
                        except ValueError as err:
                            LOGGER.error(err)
                            LOGGER.info(
                                "Skipped this type of SSH-Client. Continuing with next type.")

                    # save all ssh-clients
                    configs["sshclients"] = ssh_clients
                    print("> Finished setting up SSH Clients")

                    # #################### SAVE & EXIT ###############################
                    LOGGER.info("> Writing into config file")
                    json.dump(configs, config_file, indent=4)
                    LOGGER.info(
                        f"> Configuraton saved into the file:\n{config_file_path}")
                    Utils.printRow()
                    continue  # Contiuing to the next server config file loop
        except ValueError as err:
            LOGGER.error(err)

        LOGGER.info("> Finished config file creation")


if __name__ == "__main__":

    fileDirPath = dirname(sys.argv[0])
    configPathDefault = realpath(join(fileDirPath, "..", "config_files"))
    authPathDefault = realpath(join(fileDirPath, "delete_me_auth.txt"))

    parser = argparse.ArgumentParser(
        "Support agent to create new server configuration files for SPPMon")
    parser.add_argument("--configPath", dest="config_path",
                        default=configPathDefault,
                        help=f"Path to folder containing the config files (default: `{configPathDefault}`)")
    parser.add_argument("--authFile", dest="auth_file",
                        required=False,
                        default=authPathDefault,
                        help=f"Path to authentification file (default: `{authPathDefault}`)")
    parser.add_argument("--autoConfirm", dest="auto_confirm",
                        action="store_true",
                        help="Autoconfirm most confirm prompts")
    args = parser.parse_args()
    ConfigFileSetup().main(args.config_path, args.auth_file, args.auto_confirm)
