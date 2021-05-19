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
    echo "!! This file does contain sensible informations like passwords and usernames in clear text !!"
    echo "This file contains most login informations set or created while running the script"
    echo "You may use it manually write down login informations."
    echo "!! Please make sure to delete this file after the script is finished !!"
    if ! confirm "Do you understand and continue?"; then
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