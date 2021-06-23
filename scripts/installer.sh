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

    echo "Please remember you may have sensitive data saved within"
    echo "${authFile}."
    echo "Make sure to delete the file once you are finished!"

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
    echo "## Safepoint: If needed, the installation can be exited for later restart ##"
    echo ""
    if ! (confirm "Continue with $next_step?" "--alwaysConfirm");
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

        clear
        rowLimiter

        continue_point=$(<"$saveFile")
        echo "Welcome to the SPPMon guided installation."
        echo ""
        echo "Detected save point: $continue_point."
        echo "WARNING: Restarting the installation will not work in all cases."
        echo "You can restart the installation from the beginning by answering no to the"
        echo "prompt, or exit by pressing CTRL+C"
        echo ""
        if confirm "Do you want to continue from the save point?"
            then # no restart
                echo "Continuing from last saved point"
            else # restart
                echo "Restarting the install process"
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
    local argument
    for argument in "$@"; do
        if [[ "$argument" == "--debug" ]]; then
            removeGeneratedFiles
        fi

        if [[ "$argument" == "--autoConfirm" ]]; then
            autoConfirm=true
        else
            autoConfirm=false
        fi
        export autoConfirm
    done

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
            saveState 'PYTHON_SETUP' 'Python3 installation and package requirements'
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
            clear
            rowLimiter
            echo "User creation on SPP server, vSnap servers, and VADP proxies"
            echo ""
            echo "User accounts are needed on the systems that will be monitored by SPPmon."
            echo "This step is currently manual."
            echo "Please follow the user creation instructions:"
            echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/Create-user-accounts-in-SPP-server-and-vsnaps"
            #source "${subScripts}/userManagement.sh" "$mainPath"
            saveState 'CONFIG_FILE' 'creation of a monitoring file for each SPP server'
    fi

    # Part 6: Create SPPmon .conf files required for SPPmon execution
    if [[ $continue_point == "CONFIG_FILE" ]]; then
        clear
        rowLimiter
        echo "Create one or more .conf files for SPPmon"
        local python_exe=$(which python3)
        if [[ $autoConfirm == true ]] ; then
            checkReturn "$python_exe" "${path}/addConfigFile.py" "--configPath=${configDir}" "--authFile=${authFile}" "--autoConfirm"
        else
            checkReturn "$python_exe" "${path}/addConfigFile.py" "--configPath=${configDir}" "--authFile=${authFile}"
        fi
        echo "> IMPORTANT: if you have existing config files at a different location than: ${configDir}"
        echo "> please abort now!"
        echo "> Copy all existing config files into the dir ${configDir}"
        saveState 'CRONTAB' 'Crontab configuration for automatic execution.'
    fi

    # Part 7: Crontab setup for config files
    if [[ $continue_point == "CRONTAB" ]]; then
        clear
        rowLimiter
        echo "Create cron jobs for automated SPPmon execution"
        echo ""
        local python_exe=$(which python3)
        local sppmon_exe=$(realpath ${path}/../python/sppmon.py)
        if [[ $autoConfirm == true ]] ; then
            checkReturn "$python_exe" "${path}/addCrontabConfig.py" "--configPath=${configDir}" "--pythonPath=${python_exe}" "--sppmonPath=${sppmon_exe}" "--autoConfirm"
        else
            checkReturn "$python_exe" "${path}/addCrontabConfig.py" "--configPath=${configDir}" "--pythonPath=${python_exe}" "--sppmonPath=${sppmon_exe}"
        fi
        saveState 'GRAFANA_DASHBOARDS' 'Creation and configuration of the grafana dashboards'
    fi

    # Part 9: Grafana dashboards
    if [[ $continue_point == "GRAFANA_DASHBOARDS" ]]; then
        clear
        rowLimiter
        echo "Import SPPmon dashboards into Grafana"
        echo ""
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
