
import logging
from os.path import realpath, join
import re
from os import get_terminal_size
from getpass import getpass
from typing import ClassVar, Optional, Callable, Any

class Utils:

    auto_confirm: bool = False

    @staticmethod
    def signalHandler(signum, frame):
        logging.error("Aborted by user")
        raise ValueError("Aborted by user")


    auth_file_path: ClassVar[str] = ""

    @classmethod
    def setupAuthFile(cls, filepath: Optional[str]):
        if(not filepath):
            if(cls.confirm("Do you want to use an authentification-file? (Optional)", False)):
                filepath = Utils.prompt_string("Please specify file to read authentification from", join(".","delete_me_auth.txt"))
                filepath = realpath(filepath)
                logging.info(f"Authentification read from {filepath}")

        # Test now if it exists
        if(filepath):
            try:
                # dummy open to confirm the path is correct/readable
                with open(filepath, "r"):
                    # confirm it works, now save
                    cls.auth_file_path = filepath
                    logging.info(f"> Authentifications will be read from the file:\n{filepath}")
            except IOError as err:
                logging.error("ERROR: Unable to read authentification file. Continuing with manual input.")
                logging.error(f"Error message: {err}")


    @staticmethod
    def printRow():
        size: int = get_terminal_size().columns
        print()
        print("#"*size)
        print()


    @classmethod
    def read_auth(cls, key: str) -> Optional[str]:
        if(not cls.auth_file_path):
            return None
        result: Optional[str] = None
        try:
            with open(cls.auth_file_path, "r") as pwd_file:
                pattern = re.compile(fr"{key}=\"(.*)\"")
                for line in reversed(pwd_file.readlines()):
                    match = re.match(pattern, line)
                    if(match):
                        result = match.group(1)
        except IOError as error:
            logging.error("Unable to work with authentification file: " + error.args[0])

        if(not result):
            logging.error(f"No Authentification was found for {key} in the auth file.")
        return result


    @classmethod
    def prompt_string(cls, message: str, default: Any = "", allow_empty: bool = False, filter: Callable[[str], bool] = None, is_password=False) -> str:
        validated: bool = False
        result: str = ""

        # Casts default to str
        if(not isinstance(default, str)):
            default = str(default)

        # Only add default brackets if there is a default case
        message = message + f" [{default}]: " if default else message + ": "
        while(not validated):
            logging.debug(message)
            # Request input as either password or string
            if(is_password):
                result = getpass(message).strip() or default
            else:
                result = input(message).strip() or default

            # check for empty
            if(not allow_empty and not result):
                logging.info("> No empty input allowed, please try again")
                continue


            # You may specify via filter (lambda) to have the string match a pattern, type or other
            if(filter and not filter(result)):
                logging.info("> Failed filter rule, please try again.")
                continue


            if(is_password and not cls.auto_confirm):
                # password special confirm
                # if empty it takes default value
                result_confirm = getpass("Please repeat input for confirmation").strip() or default
                if(result_confirm != result):
                    logging.info("These passwords did not match. Please try again.")
                    validated = False
                else:
                    validated = True
            else:
                # regular input confirm
                validated = Utils.confirm(f"Was \"{result}\" the correct input?")
        return result

    @classmethod
    def confirm(cls, message: str, default: bool = True) -> bool:
        if (cls.auto_confirm):
            logging.info(message + ": autoConfirm ->" + str(default))
            return default
        default_msg = "[Y/n]" if default else "[y/N]"
        logging.debug(message + f" {default_msg}: ")
        result: str = input(message + f" {default_msg}: ").strip()
        if not result:
            logging.debug(default)
            return default
        if result in {"y", "Y", "yes", "Yes"}:
            logging.debug(True)
            return True
        else:
            logging.debug(False)
            return False

    @classmethod
    def readAuthOrInput(cls, auth_key: str, message: str, default: str = "", filter: Callable[[str], bool] = None, is_password = False):
        """Used to reduce duplicate code when reading authentification from a authfile, while asking user if not present.
        """
        result: Optional[str] = None
        if(cls.auth_file_path):
            result = Utils.read_auth(auth_key)
        if(not result):
            result = Utils.prompt_string(message, default=default, filter=filter, is_password=is_password)
        return result