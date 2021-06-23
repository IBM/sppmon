
from enum import auto
import re
from os.path import realpath, join
from os import DirEntry, scandir, popen
from typing import List
from utils import Utils
import argparse

class CrontabConfig:

    def main(self, config_path: str, python_path: str, sppmon_path: str, auto_confirm: bool):
        ############# ARGS ##################
        # Arg 1: Config file DIR
        # Arg 2: Python executable (Python3)
        # Arg 3: SPPMON executable
        #####################################

        Utils.printRow()
        Utils.auto_confirm = auto_confirm

        print("> Generating new Config files")

        # ### Config dir setup
        config_dir: str
        if(not config_path):
            print("> No config-dir specifed")
            config_path = Utils.prompt_string("Please specify the dir where config files are placed", join(".", "..", "config_files"))
        config_path = realpath(config_path)
        print(f"> All configurations files will be read from {config_path}")

        # ### python setup
        if(not python_path):
            print("> No python instance specifed")
            python_path = Utils.prompt_string("Please specify the path to python", "python3")
        python_path = realpath(python_path)
        print(f"> Following python instance will be used: {python_path}")

        # ### sppmon setup
        if(not sppmon_path):
            print("> No sppmon instance specifed")
            sppmon_path = Utils.prompt_string("Please specify the path to sppmon.py executable", join(".", "..", "python", "sppmon.py"))
        sppmon_path = realpath(sppmon_path)
        print(f"> Following sppmon instance will be used: {sppmon_path}")

        Utils.printRow()


        #  get a list of all config files
        config_files: List[DirEntry[str]] = list(filter(
            lambda entry:
                entry.is_file(follow_symlinks=True) and
                entry.name.endswith(".conf") and
                entry.name != "sppconnections_default.conf",
            scandir(config_path)))

        print("> NOTE: Example config \"sppconnections_default.conf\" is ignored")

        if(len(config_files) == 0):
            print("No config files found.")
            exit(0)
            ############## EXIT ###################
        else:
            print(f"> Found {len(config_files)} config files")

        print("> You may add a crontab configuration for all or only indiviual SPP-Servers")
        print("> If you choose individual ones you may get promped for each server.")

        Utils.printRow()

        selected_configs: List[DirEntry[str]] = []
        # If there is only one, always select it.
        if(len(config_files) == 1 or Utils.confirm("Do you want add a crontab config for all servers at once?")):
            print("> Selected all available config files for crontab setup")
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
                    print(f"> Selected {len(selected_configs)} config files for crontab setup")
                except IndexError:
                    print("One of the indices was out of bound. Please try again")
                    continue

        Utils.printRow()

        minute_interval: int = 3
        hourly_interval: int = 60
        daily_interval: int = 12
        daily_minute_offset: int = 22
        all_interval: int = 15
        all_hour_offset: int = 2
        all_minute_offset: int = 35

        if(not Utils.confirm("Do you want to use default settings or specify your own timings?", True)):

            # now selected_configs contains all required config files
            print("SPPmon collections are broken into different groupings that are executed")
            print("at different frequencies. Keeping the default frequencies is")
            print("recommended.")
            print("> These frequencing will be applied the same for all SPP servers")
            print("> being configured.\n")

            minute_interval: int = int(Utils.prompt_string(
                "Specify the interval for constant data like CPU/RAM (in minutes: 1-15)",
                minute_interval,
                filter=lambda x: x.isdigit() and int(x) <= 15 and int(x) >= 1))

            hourly_interval: int = int(Utils.prompt_string(
                "Specify the interval for \"hourly\" monitoring actions (in minutes: 15-120)",
                hourly_interval,
                filter=lambda x: x.isdigit() and int(x) <= 120 and int(x) >= 15))

            daily_interval: int = int(Utils.prompt_string(
                "Specify the interval to request new joblogs (in hours: 1-48)",
                daily_interval,
                filter=lambda x: x.isdigit() and int(x) < 48 and int(x) >= 1))
            print("> Offset-Hint: Concurrent calls are no problem for SPPMon, it is used to distribute the load on the spp-server")
            daily_minute_offset: int = int(Utils.prompt_string(
                f"At which minute every {daily_interval} hours should SPPMON run joblogs requesting actions? (in minutes: 0-59)",
                daily_minute_offset,
                filter=lambda x: x.isdigit() and int(x) < 60))

            all_interval: int = int(Utils.prompt_string(
                "Specify the interval to perform a full scan? (in days: 1-90)",
                all_interval,
                filter=lambda x: x.isdigit() and int(x) <= 90 and int(x) >= 1))
            all_hour_offset: int = int(Utils.prompt_string(
                f"At which hour every {daily_interval} days should SPPMON perform a full scan? (in hours: 0-23)",
                all_hour_offset,
                filter=lambda x: x.isdigit() and int(x) < 23))
            all_minute_offset: int = int(Utils.prompt_string(
                f"At which minute every {daily_interval} days at {all_hour_offset}:xx should SPPMON perform a full scan? (in minutes: 0-59)",
                all_minute_offset,
                filter=lambda x: x.isdigit() and int(x) < 60))

        else:
            print("Using default timings")

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
        # save old crontab config to append and compare if changes were made
        old_crontab: str = popen("sudo crontab -l").read()

        print("> Writing crontab config into temporary file")
        # writing into a file has the advantage of a crontab internal syntax check on loading
        temp_file_path = "temp_crontab_sppmon.txt"
        with open(temp_file_path, "w") as temp_file:
            lines: List[str] = []
            # if an crontab config exists, prepend it
            if("no crontab for" not in old_crontab):
                print("> WARNING: No old configurations have been edited/removed. Please remove/edit them manually by using `sudo crontab -e`")
                print("> Old configuration are prepended to new configurations")
                lines.append(old_crontab + "\n")

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
            exit(1)
        else:
            print("> Successfully enabled new crontab configuration")
            print("> Deleting temporary config file")
            print(popen(f"sudo rm {temp_file_path}").read())


        print("> Finished setting up crontab configuration")
        print("> HINT: You may add additional servers by calling the script `/scripts/addCrontabConfig.py`")




if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        "Find offensive terms to replace within the SPP-BA-Client-Agent.")
    parser.add_argument("--configPath", dest="config_path",
                        default=join(".", "..", "config_files"),
                        help="Path to folder containing the config files (default: `./../config_files`)")
    parser.add_argument("--pythonPath", dest="python_path",
                        default="python3",
                        help="Path to python 3.7.2+ (default: `python3`)")
    parser.add_argument("--sppmonPath", dest="sppmon_path",
                        default=join(".", "..", "python", "sppmon.py"),
                        help="Path to sppmon.py executable (default: `./../python/sppmon.py`)")
    parser.add_argument("--autoConfirm", dest="auto_confirm",
                        action="store_true",
                        help="Autoconfirm most confirm prompts")
    args = parser.parse_args()
    CrontabConfig().main(args.config_path, args.python_path, args.sppmon_path, args.auto_confirm)