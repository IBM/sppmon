#!/bin/bash

welcome() {
    # Welcome Message
    clear
    rowLimiter

    echo "exported autoconfirm: $autoConfirm"

    echo "Welcome to the Spectrum-Protect-Plus Monitoring install wizard!"
    echo ""
    echo "This script will guide you through the install process of SPPMon. Feature"
    echo " requests or bug reports can be submitted on the SPPmon github page:"
    echo "https://github.com/IBM/spectrum-protect-sppmon"
    echo "For additional assistance with installing SPPmon, please refer to the SPPmon"
    echo "wiki page:"
    echo "https://github.com/IBM/spectrum-protect-sppmon/wiki"

    rowLimiter

    echo "IMPORTANT: This install script will create a configuration-file for maintaining"
    echo "configuration information while the installation is in progress."
    echo "!! This file contains sensitive information such as passwords and usernames in"
    echo "plain text. !! You may use this file to obtain your authentication credentials"
    echo "after running the script."
    echo "!! Please make sure to delete after completing the SPPmon installation !!"
    echo ""
    if ! confirm "Do you understand the instructions and want to continue?"; then
        echo "Aborting install script. Nothing has been changed yet."
        exit -1
    fi

    clear
    rowLimiter

    echo "There are multiple points during the installation at which you may stop"
    echo "and continue the installation later."
    echo "IMPORTANT: Do not abort in between breakpoints! This might have unexpected"
    echo "consequences. Note: You may use the [default] case by just hitting enter"
    echo "in any following prompts."
    echo ""
    if ! (confirm "Start the install script?"); then
        echo "Aborting install script. Nothing has been changed yet."
        exit -1
    else
        echo ""
        echo "Starting the install script for sppmon."
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