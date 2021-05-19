#!/bin/bash

# aborting the script with a restart message
abortInstallScript() {
    if (( $# != 0 )); then
        >&2 echo "Illegal number of parameters abortInstallScript"
    fi

    rowLimiter

    echo "Aborting the SPPMon install script."
    echo "You may continue the script from the last saved point by restarting it."
    echo "Last saved point is: $continue_point."

    echo "Please remember you may have sensitive data saved within ${authFile}."
    echo "Make sure to delete if once you're done!"

    rowLimiter

    # exit with error code
    exit -1
}

saveState() { # param1: new continue_point #param2: name of next step
    if (( $# != 2 )); then
        >&2 echo "Illegal number of parameters saveState"
        abortInstallScript
    fi
    # global on purpose
    continue_point="$1"
    echo "$continue_point" > "$saveFile"

    local next_step="$2"

    rowLimiter
    echo "## Safepoint: You may abort the script now ##"
    if ! (confirm "Continue with $next_step?");
        then
            abortInstallScript
        else
            echo "continuing with $next_step"
    fi
}

# get path of current script
getPath() {
    if (( $# != 0 )); then
        >&2 echo "Illegal number of parameters getPath"
        abortInstallScript
    fi
    #DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    #echo $DIR
    #local DIR=$(dirname "$(readlink -f "$0")")
    #echo $DIR

    echo $(dirname "$(readlink -f "$0")")
}

saveAuth() { # topic is the describer
    if (( $# != 2 )); then
        >&2 echo "Illegal number of parameters saveAuth"
        abortInstallScript
    fi
    local topic=$1 # param1: topic
    local value=$2 # param2: value

    # save into global variable
    set -a # now all variables are exported
    eval "$topic=\"${value}\""
    set +a # Not anymore

    echo "$topic=\"${value}\"" >> "$authFile"
}

readAuth() {
    if (( $# != 0 )); then
        >&2 echo "Illegal number of parameters readAuth"
        abortInstallScript
    fi
    if [[ -r "$authFile" ]]; then
        set -a # now all variables are exported
        source "${authFile}"
        set +a # Not anymore
    fi
}

restoreState() {
    if (( $# != 0 )); then
        >&2 echo "Illegal number of parameters restoreState"
        abortInstallScript
    fi

    if [[ -f "$saveFile" ]]; then # already executed

        rowLimiter

        continue_point=$(<"$saveFile")
        echo "Welcome to the SPPMon install guide. You last saved point was $continue_point."
        echo "WARNING: Restarting has unpredictable effects. No warranty for any functionality."
        echo ""
        if confirm "Do you want to continue without restarting? Abort by CTRL + C."
            then # no restart
                echo "Continuing from last saved point"
            else # restart
                echo "restarting install process"
                continue_point='WELCOME'
            echo "$continue_point" > "$saveFile"
        fi
    else # First execution
        continue_point='WELCOME'
        echo "$continue_point" > "$saveFile"
    fi
}

removeGeneratedFiles() {
    if (( $# != 0 )); then
        >&2 echo "Illegal number of parameters removeGeneratedFiles"
        abortInstallScript
    fi

    if [[ -f "$saveFile" ]]
        then
            rm "$saveFile"
    fi

    if [[ -f "$authFile" ]]
        then
            rm "$authFile"
    fi
}

main(){

    if [[ "${1}" == "--debug" ]]
        then
            removeGeneratedFiles
    fi

    restoreState
    # Sudo Check
    sudoCheck

    # Part zero: Welcome
    if [[ $continue_point == "WELCOME" ]]
        then
            source "${subScripts}/welcome.sh" "$mainPath"
            # Savepoint and explanation inside of `welcome`
    fi

    # Part 1: System Setup (incomplete?)
    if [[ $continue_point == "SYS_SETUP" ]]
        then
            source "${subScripts}/setupRequirements.sh" "$mainPath"
            saveState 'PYTHON_SETUP' 'Python3 installation and packages'
    fi

    # Part 4: Python installation and packages
    if [[ $continue_point == "PYTHON_SETUP" ]]
        then
            source "${subScripts}/pythonSetup.sh" "$mainPath"

            saveState 'INFLUX_SETUP' 'InfluxDB installation and setup'
    fi

    # Part 2: InfluxDB installation and setup
    if [[ $continue_point == "INFLUX_SETUP" ]]
        then
            source "${subScripts}/influxSetup.sh" "$mainPath"
            saveState 'GRAFANA_SETUP' 'Grafana installation'
    fi

    # Part 3: Grafana installation
    if [[ $continue_point == "GRAFANA_SETUP" ]]
        then
            source "${subScripts}/grafanaSetup.sh" "$mainPath"
            saveState 'USER_MANGEMENT' 'User creation for SPP, vSnap and others'
    fi

    # Part 5: User management for SPP server and components
    if [[ $continue_point == "USER_MANGEMENT" ]]
        then
            rowLimiter
            echo "Please follow user creation instructions"
            echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/Create-user-accounts-in-SPP-server-and-vsnaps"
            #source "${subScripts}/userManagement.sh" "$mainPath"
            saveState 'CONFIG_FILE' 'creation of the monitoring file for each SPP-Server'
    fi

    # Part 6: User management for SPP server and components
    if [[ $continue_point == "CONFIG_FILE" ]]; then
        local python_exe=$(which python3)
        checkReturn "$python_exe" "${path}/addConfigFile.py" "${configDir}" "${authFile}"
        echo "> IMPORTANT: if you have existing config files at a different location than: ${configDir}"
        echo "> please abort now!"
        echo "> Copy all existing config files into the dir ${configDir}"
        saveState 'CRONTAB' 'Crontab configuration for automatic execution.'
    fi

    # Part 7: Crontab setup for config files
    if [[ $continue_point == "CRONTAB" ]]; then
        local python_exe=$(which python3)
        local sppmon_exe=$(realpath ${path}/../python/sppmon.py)
        checkReturn "$python_exe" "${path}/addCrontabConfig.py" "${configDir}" "${python_exe}" "${sppmon_exe}"
        saveState 'GRAFANA_DASHBOARDS' 'Creation and configuration of the grafana dashboards'
    fi

    # Part 9: Grafana dashboards
    if [[ $continue_point == "GRAFANA_DASHBOARDS" ]]; then
        rowLimiter
        echo "> Please follow grafana import instructions"
        echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/Configure-Grafana"
        saveState 'FINISHED' 'displaying finishing notes about the install of SPPMon'
    fi

    # Part 10: Finishing notes
    if [[ $continue_point == "FINISHED" ]]
        then
            source "${subScripts}/finishingScript.sh" "$mainPath"
    fi

}

# Start main if not used as source
if [ "${1}" != "--source-only" ]; then

    # prelude
    path=$(getPath)
    subScripts="${path}/installScript"
    mainPath="${path}/installer.sh"
    saveFile="${subScripts}/.savefile.txt"
    configDir=$(realpath ${path}/../config_files)
    authFile="${path}/delete_me_auth.txt"

    # Sources
    source "$subScripts/helper.sh" "--source-only"

    # handling of signals
    trap " abortInstallScript " INT QUIT HUP

    main "${@}" # all arguments passed
fi
