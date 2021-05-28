#!/bin/bash

welcome() {
    # Welcome Message
    rowLimiter

    echo "Welcome to the Spectrum-Protect-Plus Monitoring install wizard!"
    echo "This script will guide you through the install process of SPPMon."
    echo ""
    echo "If you have any feature requests or want to report bugs, please refer to our github page."
    echo "https://github.com/IBM/spectrum-protect-sppmon"
    echo "If you require any assistance with installing, please refer to our wiki page or open an issue to allow us to improve this process."
    echo "https://github.com/IBM/spectrum-protect-sppmon/wiki"

    rowLimiter

    echo "IMPORTANT: This install script will create a configuration-file."
    echo "!! This file contains sensitive information such as passwords and usernames in plain text. !!"
    echo "This file is where most of the log-in data is written, which will be generated when the script is run"
    echo "You may use this file to obtain your authentication credentials after running the script."
    echo "!! Please make sure to delete this file after you have executed the script !!"
    if ! confirm "Did you understand the instructions and want to continue?"; then
        echo "Aborting install script. Nothing has been changed yet."
        exit -1
    fi

    rowLimiter

    echo "There are multiple breakpoints when running the installer"
    echo "You may stop at each breakpoint and continue the installer later."
    echo "IMPORTANT: Do not abort inbetween breakpoint! This might have unexpected consequences."
    echo "Note: You may use the [default] case by just hitting enter in any following prompts"
    if ! (confirm "Start install script?"); then
        echo "Aborting install script. Nothing has been changed yet."
        exit -1
    else
        echo ""
        echo "Starting install script for sppmon."
        echo ""
        continue_point='SYS_SETUP'
        echo "$continue_point" > $saveFile
    fi
}

# Start if not used as source
if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 echo "Illegal number of parameters for the welcome file"
        abortInstallScript
    fi
    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    welcome "${@}" # all arguments passed
fi