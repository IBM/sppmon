#!/bin/bash

finishingScript() {

    rowLimiter

    echo "You've completed the install of SPPMon!"
    echo "You may find saved config files under ${config_dir}"
    if [[ -e ${passwordFile} ]]; then
        echo "It seems like there are some configuration saved. These contain sensible data."
        if confirm "Do you want to show all saved configurations now?"; then
            rowLimiter
            checkReturn cat "${passwordFile}"
            rowLimiter
        fi
        if confirm "Do you want to delete this file now?"; then
            checkReturn sudo rm -f "${passwordFile}"
            echo "> Deleted all sensitive data"
        fi
    fi
    echo "> If you have any questions, feedback or feature requests, feel free to open an issue: https://github.com/IBM/spectrum-protect-sppmon/issues"
    echo "> You may call all scripts within the dir ${path} for adding new config files, adding servers to crontab and more"
    echo "> All these informations are also documented within the wiki: https://github.com/IBM/spectrum-protect-sppmon/wiki"
    echo "> Please make sure to regulary pull from git for the latest SPPMon release via `git pull`"
    echo "Goodbye"


}

# Start if not used as source
if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 echo "Illegal number of parameters for the finishingScript file"
        abortInstallScript
    fi
    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    finishingScript "${@}" # all arguments passed
fi