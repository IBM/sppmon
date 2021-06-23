
import re
import json
import signal
from os import get_terminal_size
from os.path import isfile, realpath, join
from sys import path
from typing import Any, Dict, List
from utils import Utils
import argparse

class ConfigFileSetup:


    @staticmethod
    def createServerDict() -> Dict[str, Any]:
        spp_server: Dict[str, Any] = {}
        spp_server["username"] = Utils.prompt_string("Please enter the SPP REST-API Username (equal to login via website)")
        spp_server["password"] = Utils.prompt_string("Please enter the REST-API Users Password (equal to login via website)", is_password=True)
        spp_server["srv_address"] = Utils.prompt_string("Please enter the SPP server address")

        spp_server["srv_port"] = int(
            Utils.prompt_string(
                "Please enter the SPP server port",
                "443",
                filter=(lambda x: x.isdigit())))

        spp_server["jobLog_rentation"] = Utils.prompt_string(
            "How long are the JobLogs saved within the Server? (Format: 48h, 60d, 2w)",
            "60d",
            filter=(lambda x: bool(re.match(r"^[0-9]+[hdw]$", x))))
        return spp_server

    @staticmethod
    def createInfluxDict(server_name: str) -> Dict[str, Any]:
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
        print(f"> Your influxDB database name for this server is \"{dbName}\"")
        influxDB["dbName"] = dbName

        return influxDB




    def main(self, config_path: str, auth_file: str, auto_confirm: bool):

        ############# ARGS ##################
        # Arg 1: Config file DIR
        # Arg 2: password file
        #####################################

        Utils.printRow()
        Utils.auto_confirm=auto_confirm
        signal.signal(signal.SIGINT, Utils.signalHandler)

        print("> Generating new Config files")

        # ### Config dir setup
        config_path = realpath(config_path)
        print(f"> All new configurations files will be written into the directory:\n {config_path}")

        # ### authFile setup
        if(not auth_file):
            print("> No authentification file specifed")
            Utils.setupAuthFile(None)
        else: # take none if not exists, otherwise take auth path
            Utils.setupAuthFile(auth_file)


        # ########## EXECUTION ################
        Utils.printRow()
        print("> You may add multiple SPP-Server now.")
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
                    config_file_path = join(realpath(config_path), server_name + ".conf")

                    if(isfile(config_file_path)):
                        print(f"> There is already a file at {config_file_path}.")
                        if(not Utils.confirm("Do you want to replace it?")):
                            print("> Please re-enter a different server name")
                            # remove content to allow loop to continue
                            config_file_path = ""
                            server_name = ""
                        else:
                            print("> Overwriting old config file")

                # Overwrite existing file
                with open(config_file_path, "w") as config_file:
                    print(f"> Created config file under {config_file_path}")


                    # Structure of the config file
                    configs: Dict[str, Any] = {}

                    # #################### SERVER ###############################
                    Utils.printRow()
                    print("> collecting server information")

                    # Saving config
                    configs["sppServer"] = ConfigFileSetup.createServerDict()

                    print("> finished collecting server information")
                    # #################### influxDB ###############################
                    Utils.printRow()
                    print("> collecting influxDB information")

                    # Saving config
                    configs["influxDB"] = ConfigFileSetup.createInfluxDict(server_name)

                    print("> finished collecting influxdb information")
                    # #################### ssh clients ###############################
                    Utils.printRow()
                    print("> collecting ssh client information")

                    ssh_clients: List[Dict[str, Any]] = []

                    print("")
                    print("> NOTE: You will now be asked for multiple ssh logins")
                    print("> You may test all these logins yourself by logging in via ssh")
                    print("> Following categories will be asked:")
                    ssh_types: List[str] = ["vsnap", "vadp", "cloudproxy", "other"] # server excluded here
                    print("> server, "+ ", ".join(ssh_types))
                    print("> Please add all clients accordingly.")
                    print()
                    print("> If you misstyped anything you may edit the config file manually afterwards")
                    print("> NOTE: It is highly recommended to add at least one vSnap client")

                    if(not Utils.confirm("Do you want to continue now?")):
                        json.dump(configs, config_file, indent=4)
                        print(f"> saved all information into file {config_file_path}")
                        print("> finished setup for this server.")
                        continue # Contiuing to the next server config file loop


                    # #################### ssh clients: SERVER ###############################
                    Utils.printRow()
                    print("> Collecting SPP-Server ssh information")

                    ssh_server: Dict[str, Any] = {}

                    print("> Test the requested logins by logging into the SPP-Server via ssh yourself.")
                    ssh_server["name"] = server_name
                    spp_server_dict: Dict[str, Any] = configs["sppServer"]
                    ssh_server["srv_address"] = spp_server_dict["srv_address"]
                    ssh_server["srv_port"] = int(
                                        Utils.prompt_string(
                                        f"Please enter the SSH port of the SPP server",
                                        "22",
                                        filter=(lambda x: x.isdigit())))
                    ssh_server["username"] = Utils.prompt_string("Please enter the SPP-Server SSH username (equal to login via ssh)")
                    ssh_server["password"] = Utils.prompt_string("Please enter the SPP-Server SSH user password (equal to login via ssh)", is_password=True)
                    ssh_server["type"] = "server"

                    # Saving config
                    ssh_clients.append(ssh_server)

                    # #################### ssh clients all other ###############################
                    for ssh_type in ssh_types:
                        try:
                            Utils.printRow()
                            print(f"> Collecting {ssh_type} ssh information")

                            # counter for naming like: vsnap-1 / vsnap-2
                            counter: int = 1

                            while(Utils.confirm(f"Do you want to add (another) {ssh_type}-client?")):
                                try:
                                    ssh_client: Dict[str, Any] = {}

                                    print(f"> Test the requested logins by logging into the {ssh_type}-client via ssh yourself.")
                                    ssh_client["name"] = Utils.prompt_string(
                                        f"Please enter the name of the {ssh_type}-client (display only)",
                                        f"{ssh_type}-{counter}")
                                    counter += 1 # resetted on next ssh_type

                                    ssh_client["srv_address"] = Utils.prompt_string(f"Please enter the server address of the {ssh_type}-client")
                                    ssh_client["srv_port"] = int(
                                        Utils.prompt_string(
                                        f"Please enter the port of the {ssh_type}-client",
                                        "22",
                                        filter=(lambda x: x.isdigit())))
                                    ssh_client["username"] = Utils.prompt_string(f"Please enter the {ssh_type}-client username (equal to login via ssh)")
                                    ssh_client["password"] = Utils.prompt_string(f"Please enter the {ssh_type}-client user password (equal to login via ssh)", is_password=True)
                                    ssh_client["type"] = ssh_type

                                    # Saving config
                                    ssh_clients.append(ssh_client)

                                    Utils.printRow()
                                except ValueError as err:
                                    print(err)
                                    print("Aborted adding this ssh client. Continuing with next client")
                        except ValueError as err:
                            print(err)
                            print("Skipped this type of SSH-Client. Continuing with next type.")


                    # save all ssh-clients
                    configs["sshclients"] = ssh_clients
                    print("> Finished setting up SSH Clients")

                    # #################### SAVE & EXIT ###############################
                    print("> Writing into config file")
                    json.dump(configs, config_file, indent=4)
                    print(f"> Configuraton saved into the file:\n{config_file_path}")
                    Utils.printRow()
                    continue # Contiuing to the next server config file loop
        except ValueError as err:
            print(err)

        print("> Finished config file creation")




if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        "Find offensive terms to replace within the SPP-BA-Client-Agent.")
    parser.add_argument("--configPath", dest="config_path",
                        default=join(".", "..", "config_files"),
                        help="Path to folder containing the config files (default: `./../config_files`)")
    parser.add_argument("--authFile", dest="auth_file",
                        required=False,
                        default=join(".", "delete_me_auth.txt"),
                        help="Path to authentification file (default: `./delete_me_auth.txt`)")
    parser.add_argument("--autoConfirm", dest="auto_confirm",
                        action="store_true",
                        help="Autoconfirm most confirm prompts")
    args = parser.parse_args()
    ConfigFileSetup().main(args.config_path, args.auth_file, args.auto_confirm)