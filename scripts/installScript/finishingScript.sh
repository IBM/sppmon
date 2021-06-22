#!/bin/bash

finishingScript() {

    clear
    rowLimiter

    echo "You've completed the install of SPPMon!"
    echo ""
    echo "> You may find saved config files under:"
    echo ${configDir}
    if [[ -e ${authFile} ]]; then
        echo "> The configuration state file still exists.  This file may include"
        echo "sensitive information such as passwords. You can optionally view"
        echo "the contents of this file now. WARNING: authentification in plain text"
        echo ""
        if confirm "> Do you want view the configuration file contents?"; then
            rowLimiter
            checkReturn cat "${authFile}"
            rowLimiter
        fi
        echo ""
        if confirm "> Do you want to delete this file now?"; then
            checkReturn sudo rm -f "${authFile}"
            echo "> Deleted all sensitive data"
        fi
    fi
    echo ""
    echo "> If you have questions, feedback or feature requests, you can submit them"
    echo "via an issue opened at:"
    echo "https://github.com/IBM/spectrum-protect-sppmon/issues"
    echo ""
    echo "> In the future if you want to configure SPPmon for additional"
    echo "SPP servers, you can run individual installations scripts".
    echo "The scripts are located within the directory:"
    echo "${path}."
    echo ""
    echo "> Documentation for SPPmon is available within the wiki:"
    echo "https://github.com/IBM/spectrum-protect-sppmon/wiki"
    echo ""
    echo "> Please make sure to regulary pull SPPmon updates from git"
    echo "using the command:"
    echo "  git pull"
    echo ""
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