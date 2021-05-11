
import re
from os.path import realpath, join
import sys
from os import DirEntry, scandir, popen
from typing import List
from utils import Utils

class CrontabConfig:

    def main(self):
        ############# ARGS ##################
        # Arg 1: Config file DIR
        # Arg 2: Python executable (Python3)
        # Arg 3: SPPMON executable
        #####################################

        Utils.printRow()

        print("> Generating new Config files")

        # ### Config dir setup
        config_dir: str
        if(not len(sys.argv) >= 2):
            print("> No config-dir specifed by first arg.")
            config_dir = Utils.prompt_string("Please specify the dir where config files are placed", join(".", "..", "config_files"))
        else:
            config_dir = sys.argv[1]
        config_dir = realpath(config_dir)
        print(f"> All configurations files will be read from {config_dir}")

        # ### python setup
        python_path: str
        if(not len(sys.argv) >= 3):
            print("> No python instance specifed by second arg.")
            python_path = Utils.prompt_string("Please specify the path to python", "python3")
        else:
            python_path = sys.argv[2]
        python_path = realpath(python_path)
        print(f"> Following python instance will be used: {python_path}")

        # ### sppmon setup
        sppmon_path: str
        if(not len(sys.argv) >= 4):
            print("> No sppmon instance specifed by third arg.")
            sppmon_path = Utils.prompt_string("Please specify the path to sppmon.py executable", join(".", "..", "python", "sppmon.py"))
        else:
            sppmon_path = sys.argv[3]
        sppmon_path = realpath(sppmon_path)
        print(f"> Following sppmon instance will be used: {sppmon_path}")



        #  get a list of all config files
        config_files: List[DirEntry[str]] = list(filter(
            lambda entry:
                entry.is_file(follow_symlinks=True) and
                entry.name.endswith(".conf") and
                entry.name != "sppconnections_default.conf",
            scandir(config_dir)))

        print("> NOTE: Example config \"sppconnections_default.conf\" is ignored")

        if(len(config_files) == 0):
            print("No config files found.")
            return
            ############## EXIT ###################
        else:
            print(f"> Found {len(config_files)} config files")

        print("> You may add a crontab configuration for all or only indiviual SPP-Servers")
        print("> If you choose individual ones you may get promped for each server.")

        Utils.printRow()

        selected_configs: List[DirEntry[str]] = []
        if(Utils.confirm("Do you want add a crontab config for all servers at once?")):
            selected_configs = config_files
        else:
            # Repeat until one config is selected
            while(not selected_configs):

                for n, entry in enumerate(config_files):
                    print(f"[{n:2d}]:\t\t{entry.name}")
                selected_indices: str = Utils.prompt_string(
                    "Please select indices of servers to be added: (comma-seperated list)",
                    filter=(lambda x: bool(re.match(r"^(?:\s*(\d+)\s*,?)+$", x))))

                try:
                    selected_configs = list(map(
                        lambda str_index: config_files[int(str_index.strip())],
                        selected_indices.split(",")))
                except IndexError:
                    print("One of the indices was out of bound. Please try again")
                    continue

        Utils.printRow()

        # now selected_configs contains all required config files
        print("> Please select now the wanted monitoring intervall/offset for *all* selected spp-servers")

        minute_interval: int = int(Utils.prompt_string(
            "In which *intervall* do you want to monitor constant data like CPU/RAM on all clients? (in minutes: 1-15)",
            "3",
            filter=lambda x: x.isdigit() and int(x) <= 15 and int(x) >= 1))

        hourly_interval: int = int(Utils.prompt_string(
            "In which *intervall* do you want to \"hourly\" monitoring actions? (in minutes: 15-120)",
            "30",
            filter=lambda x: x.isdigit() and int(x) <= 120 and int(x) >= 15))

        daily_interval: int = int(Utils.prompt_string(
            "In which *intervall* do you want to request new joblogs? (in hours: 1-48)",
            "12",
            filter=lambda x: x.isdigit() and int(x) < 48 and int(x) >= 1))
        print("> Offset-Hint: Concurrent calls are no problem for SPPMon, it is used to distribute the load on the spp-server")
        daily_minute_offset: int = int(Utils.prompt_string(
            f"At which minute every {daily_interval} hours should SPPMON run joblogs requesting actions? (in minutes: 0-59)",
            "22",
            filter=lambda x: x.isdigit() and int(x) < 60))

        all_interval: int = int(Utils.prompt_string(
            "In which *intervall* do you want perform a full scan? (in days: 1-90)",
            "15",
            filter=lambda x: x.isdigit() and int(x) <= 90 and int(x) >= 1))
        all_hour_offset: int = int(Utils.prompt_string(
            f"At which hour every {daily_interval} days should SPPMON perform a full scan? (in hours: 0-23)",
            "2",
            filter=lambda x: x.isdigit() and int(x) < 23))
        all_minute_offset: int = int(Utils.prompt_string(
            f"At which minute every {daily_interval} days at {all_hour_offset}:xx should SPPMON perform a full scan? (in minutes: 0-59)",
            "35",
            filter=lambda x: x.isdigit() and int(x) < 60))

        constant_cron_post: str = " --constant >/dev/null 2>&1"
        constant_cron_pre: str = f"*/{minute_interval} * * * * "

        hourly_cron_post: str = " --hourly >/dev/null 2>&1"
        hourly_cron_pre: str = f"*/{hourly_interval} * * * * "

        daily_cron_post: str = " --daily >/dev/null 2>&1"
        daily_cron_pre: str = f"{daily_minute_offset} */{daily_interval} * * * "

        all_cron_post: str = " --all >/dev/null 2>&1"
        all_cron_pre: str = f"{all_minute_offset} {all_hour_offset} */{all_interval} * * "

        Utils.printRow()

        print("> Saving crontab configuration as SUDO")
        print("> No old configurations have been edited, if wanted please remove them manually by using `sudo crontab -e`")
        old_crontab: str = popen("sudo crontab -l").read()

        print("> Writing crontab config into temporary file")
        temp_file_path = "temp_crontab_sppmon.txt"
        with open(temp_file_path, "w") as temp_file:
            lines: List[str] = []

            for entry in selected_configs:
                lines.append(f"\n# {entry.name}:")
                lines.append(constant_cron_pre + python_path + " " + sppmon_path + " --cfg=" + entry.path + constant_cron_post)
                lines.append(hourly_cron_pre + python_path + " " + sppmon_path + " --cfg=" + entry.path + hourly_cron_post)
                lines.append(daily_cron_pre + python_path + " " + sppmon_path + " --cfg=" + entry.path + daily_cron_post)
                lines.append(all_cron_pre + python_path + " " + sppmon_path + " --cfg=" + entry.path + all_cron_post)
            # also add newline when writing lines
            temp_file.writelines(line + "\n" for line in lines)

        print("> Loading crontab configuration")
        print(popen("sudo crontab " + temp_file_path).read())
        new_crontab: str = popen("sudo crontab -l").read()
        if(new_crontab == old_crontab):
            print("> WARNING: Crontab unmodified, failed to write")
            print(f"> Generated crontab-file:{temp_file_path}")
        else:
            print("> Successfully enabled new crontab configuration")
            print("> Deleting temporary config file")
            print(popen(f"sudo rm {temp_file_path}").read())

        print("> Finished setting up crontab configuration")



if __name__ == "__main__":
    CrontabConfig().main()