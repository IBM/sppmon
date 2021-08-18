"""
(C) IBM Corporation 2021

Description:
    Groups helper functions for python scripts.
    Includes logger-setup, auth-file reading, user inputs and more.

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Niels Korschinsky
"""


import logging
from os.path import realpath, join
import re
from os import get_terminal_size
from getpass import getpass
from typing import ClassVar, Optional, Callable, Any


class Utils:
    """Groups helper functions for python scripts.
    Includes logger-setup, auth-file reading, user inputs and more.

    Functions:
        setupLogger - Initializes a logger with given name to given gile and returns it.

    """

    LOGGER: logging.Logger
    """Logger used within this script to log into the calling functions logger.
    Initialized within the script using the utils functions.
    """
    auth_file_path: ClassVar[str] = ""
    """Path to the auth file with login informations.
    Initialized within setupAuthFile.
    """
    auto_confirm: bool = False
    """Skip any confirm messages.
    Initialized within the script using the utils functions.
    """

    @classmethod
    def setupLogger(cls, loggerName: str, filePath) -> logging.Logger:
        """Initializes a logger with given name to given gile and returns it.
        Logger writes debug informations into file and info onto console.

        Args:
            loggerName (str): name of the logger for reference
            filePath ([type]): path to file which should be used as log.

        Raises:
            ValueError: Unable to open file.

        Returns:
            logging.Logger: Logger ready to use, also accessable via loggerName.
        """
        try:
            fileHandler = logging.FileHandler(filePath)
        except Exception as error:
            print("unable to open logger")
            raise ValueError("Unable to open Logger") from error

        fileHandlerFmt = logging.Formatter(
            '%(asctime)s:[PID %(process)d]:%(levelname)s:%(module)s.%(funcName)s> %(message)s')
        fileHandler.setFormatter(fileHandlerFmt)
        fileHandler.setLevel(logging.DEBUG)

        streamHandler = logging.StreamHandler()
        streamHandler.setLevel(logging.INFO)

        logger = logging.getLogger(loggerName)
        logger.setLevel(logging.DEBUG)

        logger.addHandler(fileHandler)
        logger.addHandler(streamHandler)

        return logger

    @classmethod
    def signalHandler(cls, signum, frame):
        """Used as signal handler if the user aborts the script.
        Logs the abort.

        Args:
            signum ([type]): Not used, required as signalhandler.
            frame ([type]): Not used, required as signalhandler.

        Raises:
            ValueError: Aborted by user
        """
        cls.LOGGER.error("Aborted by user.")
        raise ValueError("Aborted by user.")

    @classmethod
    def setupAuthFile(cls, filepath: Optional[str]):
        """Reads the Authfile and ask for path if missing.

        Args:
            filepath (Optional[str]): Path to the auth-file.
        """
        if(not filepath):
            if(cls.confirm("Do you want to use an authentification-file? (Optional)", False)):
                filepath = Utils.prompt_string(
                    "Please specify file to read authentification from", join(".", "delete_me_auth.txt"))
                filepath = realpath(filepath)
                cls.LOGGER.info(f"Authentification read from {filepath}")

        # Test now if it exists
        if(filepath):
            try:
                # dummy open to confirm the path is correct/readable
                with open(filepath, "r"):
                    # confirm it works, now save
                    cls.auth_file_path = filepath
                    cls.LOGGER.info(
                        f"> Authentifications will be read from the file:\n{filepath}")
            except IOError as err:
                cls.LOGGER.error(
                    "ERROR: Unable to read authentification file. Continuing with manual input.")
                cls.LOGGER.error(f"Error message: {err}")

    @classmethod
    def printRow(cls):
        """Function to print a row of `#` onto the console.
        """
        size: int = get_terminal_size().columns
        print()
        print("#"*size)
        print()

    @classmethod
    def read_auth(cls, key: str) -> Optional[str]:
        """Reads auth data from the auth file.

        Args:
            key (str): name of the attributed wanted.

        Returns:
            Optional[str]: Value of the key if found.
        """
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
            cls.LOGGER.error(
                "Unable to work with authentification file: " + error.args[0])

        if(not result):
            cls.LOGGER.error(
                f"No Authentification was found for {key} in the auth file.")
        return result

    @classmethod
    def prompt_string(cls, message: str, default: Any = "", allow_empty: bool = False, filter: Callable[[str], bool] = None, is_password=False) -> str:
        """Promts the user for a string or password, applying optional filter for allowed content.
        Loops if invalid content is provided until aborted or valid result available.

        Args:
            message (str): Message to display before asking
            default (Any, optional): Default value of the prompt. Defaults to "".
            allow_empty (bool, optional): Whether an empty answer is allowed. Defaults to False.
            filter (Callable[[str], bool], optional): Function (or lambda) used to check for disallowed content. Defaults to None.
            is_password (bool, optional): Hides sensitive input if flagged as password. Defaults to False.

        Returns:
            str: Result of the prompt.
        """
        validated: bool = False
        result: str = ""

        # Casts default to str
        if(not isinstance(default, str)):
            default = str(default)

        # Only add default brackets if there is a default case
        message = message + f" [{default}]: " if default else message + ": "
        while(not validated):
            cls.LOGGER.debug(message)
            # Request input as either password or string
            if(is_password):
                result = getpass(message).strip() or default
            else:
                result = input(message).strip() or default

            # check for empty
            if(not allow_empty and not result):
                cls.LOGGER.info("> No empty input allowed, please try again")
                continue

            # You may specify via filter (lambda) to have the string match a pattern, type or other
            if(filter and not filter(result)):
                cls.LOGGER.info("> Failed filter rule, please try again.")
                continue

            if(is_password and not cls.auto_confirm):
                # password special confirm
                # if empty it takes default value
                result_confirm = getpass(
                    "Please repeat input for confirmation").strip() or default
                if(result_confirm != result):
                    cls.LOGGER.info(
                        "These passwords did not match. Please try again.")
                    print()
                    validated = False
                else:
                    validated = True
            else:
                # regular input confirm
                validated = Utils.confirm(
                    f"Was \"{result}\" the correct input?")
        return result

    @classmethod
    def confirm(cls, message: str, default: bool = True) -> bool:
        """True/False user input confirm with a message.

        Args:
            message (str): Message to display when asking
            default (bool, optional): Default value if just enter is pressed. Defaults to True.

        Returns:
            bool: Answer of user to prompt.
        """
        if (cls.auto_confirm):
            cls.LOGGER.info(message + ": autoConfirm ->" + str(default))
            return default
        default_msg = "[Y/n]" if default else "[y/N]"
        cls.LOGGER.debug(message + f" {default_msg}: ")
        result: str = input(message + f" {default_msg}: ").strip()
        if not result:
            cls.LOGGER.debug(default)
            return default
        if result in {"y", "Y", "yes", "Yes"}:
            cls.LOGGER.debug(True)
            return True
        else:
            cls.LOGGER.debug(False)
            return False

    @classmethod
    def readAuthOrInput(cls, auth_key: str, message: str, default: str = "", filter: Callable[[str], bool] = None, is_password=False):
        """Reads key from authfile if present, otherwise ask user for password/text.

        Args:
            auth_key (str): Key to be searched within auth file.
            message (str): Message to be displayed if key is missing.
            default (str, optional): Default value of the password/text. Defaults to "".
            filter (Callable[[str], bool], optional): Filterfunction to allow only certain values. Defaults to None.
            is_password (bool, optional): Hides sensitive data if flagged as password. Defaults to False.

        Returns:
            [type]: [description]
        """
        result: Optional[str] = None
        if(cls.auth_file_path):
            result = Utils.read_auth(auth_key)
        if(not result):
            result = Utils.prompt_string(
                message, default=default, filter=filter, is_password=is_password)
        return result
