#!/bin/bash
#
# (C) IBM Corporation 2021
#
# Description:
# Installs SPPMon with all its required components on the system.
# This script manages the control flow of the installer between its components.
# It initializes the logger and traps abort signals.
#
# Repository:
#   https://github.com/IBM/spectrum-protect-sppmon
#
# Author:
#  Niels Korschinsky
#
# Version: 1.0 (2021/08/13)
#
# Functions:
#   abortInstallScript - Aborts the install script and prints last saved state.
#   saveState - Saves last savepoint into file and asks to continue with next one.
#   getPath - Get absolute path of current script.
#   saveAuth - Saves an authentification pair into file and publishs it script-wide.
#   readAuth - Reads all authentification pairs from file and publishs them script-wide.
#   restoreState - Restores the last script savepoint or restarts script.
#   removeGeneratedFiles - Removes script automated generated files, excludes logging files.
#   main - see description above

#######################################
# Aborts the install script and prints last saved state.
# Globals:
#   continue_point - read
#   authFile - read
#   logFile - read
# Arguments:
#   None
# Outputs:
#   stdout: exit information and auth file warning
#   log: latest continue_point
# Returns:
#   exit -1
#######################################
abortInstallScript() {
    if [[ -w "${logFile}" ]] ; then
        logger "Aborting the SPPMon install script."
        logger "Last saved point is: ${continue_point}."
    fi

    rowLimiter

    echo "Aborting the SPPMon install script."
    echo "You may continue the script from the last saved point by restarting it."
    echo "Last saved point is: ${continue_point}."
    echo ""
    echo "Please remember you may have sensitive data saved within"
    echo "${authFile}."
    echo "Make sure to delete the file once you are finished!"

    rowLimiter

    # exit with error code
    exit 1
}

#######################################
# Saves last savepoint into file and asks to continue with next one.
# Globals:
#   continue_point - set
#   saveFile - read
# Arguments:
#   1: next step identifier within installer
#   2: texual description of the next step
# Outputs:
#   stdout: information of savepoint, question whether to continue.
#   log: next step identifier if program resumes
# Returns:
#   None, aborts script on choice
#######################################
saveState() {
    if (( $# != 2 )); then
        >&2 loggerEcho "Illegal number of parameters saveState"
        abortInstallScript
    fi
    # global on purpose
    continue_point="$1"
    echo "${continue_point}" > "${saveFile}"

    local next_step="$2"

    rowLimiter
    echo "## Safepoint: If needed, the installation can be exited for later restart ##"
    echo ""
    if ! (confirm "Continue with ${next_step}?" "--alwaysConfirm");
        then
            abortInstallScript
        else
            loggerEcho "continuing with ${next_step}"
    fi
}

#######################################
# Get absolute path of current script.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   stdout: absolute path of script
# Returns:
#   None
#######################################
getPath() {
    # WARNING: Use of logger impossible due call before setup.
    dirname "$(readlink -f "$0")"
}

#######################################
# Saves an authentification pair into file and publishs it script-wide.
# Globals:
#   authFile - read
#   name of the variable - set
# Arguments:
#   1: name of the variable
#   2: value of the variable
# Outputs:
#   auth_file: appends pair of name=value
# Returns:
#   None
#######################################
saveAuth() {
    if (( $# != 2 )); then
        >&2 loggerEcho "Illegal number of parameters saveAuth"
        abortInstallScript
    fi
    local name=$1
    local value=$2

    # save into global variable
    set -a # now all variables are exported
    eval "${name}=\"${value}\""
    set +a # Not anymore

    # create file if it does not exists and add permissions
    if [[ ! -e "${authFile}" ]] ; then
        sudo touch "${authFile}"
        sudo chmod 600 "${authFile}"
    fi

    echo "${name}=\"${value}\"" | sudo tee -a "${authFile}" >/dev/null
}

#######################################
# Reads all authentification pairs from file and publishs them script-wide.
# Globals:
#   authFile - read
#   name of the variable - set
#   +++
# Arguments:
#   None
# Outputs:
#   None
# Returns:
#   None
#######################################
readAuth() {
    if [[ -r "${authFile}" ]]; then
        set -a # now all variables are exported

        # shellcheck source=./delete_me_auth.txt
        # shellcheck disable=SC1091
        source <(sudo cat "${authFile}")
        set +a # Not anymore
    fi
}

#######################################
# Restores the last script savepoint or restarts script.
# Globals:
#   saveFile - read
#   continue_point - set
# Arguments:
#   None
# Outputs:
#   Only on restart:
#       stdout: Restart-Message and asks for continue
#   saveFile: reads old continue_point and writes new point
# Returns:
#   None
#######################################
restoreState() {

    if [[ -f "${saveFile}" ]]; then # already executed

        clear
        rowLimiter

        continue_point=$(<"${saveFile}")
        loggerEcho "Welcome to the SPPMon guided installation."
        echo ""
        loggerEcho "Detected save point: ${continue_point}."
        echo "WARNING: Restarting the installation will not work in all cases."
        echo "You can restart the installation from the beginning by answering no to the"
        echo "prompt, or exit by pressing CTRL+C"
        echo ""
        if confirm "Do you want to continue from the save point?"
            then # no restart
                loggerEcho "Continuing from last saved point"
            else # restart
                loggerEcho "Restarting the install process"
                continue_point='WELCOME'
            echo "${continue_point}" > "${saveFile}"
        fi
    else # First execution
        continue_point='WELCOME'
        echo "${continue_point}" > "${saveFile}"
    fi
}

#######################################
# Removes script automated generated files, excludes logging files.
# Globals:
#   saveFile - read
#   authFile - read
# Arguments:
#   None
# Outputs:
#   authFile: Deletes file if exits
#   saveFile: Deletes file if exits
# Returns:
#   None
#######################################
removeGeneratedFiles() {

    if [[ -f "${saveFile}" ]]
        then
            rm "${saveFile}"
    fi

    if [[ -f "${authFile}" ]]
        then
            rm "${authFile}"
    fi
}

main(){
    local argument
    for argument in "$@"; do
        if [[ "${argument}" == "--debug" ]]; then
            removeGeneratedFiles
        fi

        if [[ "${argument}" == "--autoConfirm" ]]; then
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
    if [[ ${continue_point} == "WELCOME" ]]
        then
            # shellcheck source=./installScript/welcome.sh
            source "${subScripts}/welcome.sh" "${mainPath}"
            # Savepoint and explanation inside of `welcome`
    fi

    # Part 1: System Setup (incomplete?)
    if [[ ${continue_point} == "SYS_SETUP" ]]
        then
            # shellcheck source=./installScript/setupRequirements.sh
            source "${subScripts}/setupRequirements.sh" "${mainPath}"
            saveState 'PYTHON_SETUP' 'Python3 installation and package requirements'
    fi

    # Part 4: Python installation and packages
    if [[ ${continue_point} == "PYTHON_SETUP" ]]
        then
            # shellcheck source=./installScript/pythonSetup.sh
            source "${subScripts}/pythonSetup.sh" "${mainPath}"

            saveState 'INFLUX_SETUP' 'InfluxDB installation and setup'
    fi

    # Part 2: InfluxDB installation and setup
    if [[ ${continue_point} == "INFLUX_SETUP" ]]
        then
            # shellcheck source=./installScript/influxSetup.sh
            source "${subScripts}/influxSetup.sh" "${mainPath}"
            saveState 'GRAFANA_SETUP' 'Grafana installation'
    fi

    # Part 3: Grafana installation
    if [[ ${continue_point} == "GRAFANA_SETUP" ]]
        then
            # shellcheck source=./installScript/grafanaSetup.sh
            source "${subScripts}/grafanaSetup.sh" "${mainPath}"
            saveState 'USER_MANGEMENT' 'User creation for SPP, vSnap and others'
    fi

    # Part 5: User management for SPP server and components
    if [[ ${continue_point} == "USER_MANGEMENT" ]]
        then
            clear
            rowLimiter
            loggerEcho "User creation on SPP server, vSnap servers, and VADP proxies"
            echo ""
            echo "User accounts are needed on the systems that will be monitored by SPPmon."
            echo "This step is currently manual."
            echo "Please follow the user creation instructions:"
            echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/Create-user-accounts-in-SPP-server-and-vsnaps"
            #source "${subScripts}/userManagement.sh" "${mainPath}"
            saveState 'CONFIG_FILE' 'creation of a monitoring file for each SPP server'
    fi

    # Part 6: Create SPPmon .conf files required for SPPmon execution
    if [[ ${continue_point} == "CONFIG_FILE" ]]; then
        clear
        rowLimiter
        loggerEcho "Create one or more .conf files for SPPmon"
        local python_exe
        python_exe=$(which python3)
        if [ "${autoConfirm}" == true ]  ; then
            checkReturn sudo "${python_exe}" "${path}/addConfigFile.py" "--configPath=${configDir}" "--authFile=${authFile}" "--autoConfirm"
        else
            checkReturn sudo "${python_exe}" "${path}/addConfigFile.py" "--configPath=${configDir}" "--authFile=${authFile}"
        fi
        echo "> IMPORTANT: if you have existing config files at a different location than: ${configDir}"
        echo "> please abort now!"
        loggerEcho "> Copy all existing config files into the dir ${configDir}"
        saveState 'CRONTAB' 'Crontab configuration for automatic execution.'
    fi

    # Part 7: Crontab setup for config files
    if [[ ${continue_point} == "CRONTAB" ]]; then
        clear
        rowLimiter
        loggerEcho "Create cron jobs for automated SPPmon execution"
        echo ""
        local python_exe
        python_exe=$(which python3)
        local sppmon_exe
        sppmon_exe=$(realpath "${path}/../python/sppmon.py")
        if [ "${autoConfirm}" == true ]  ; then
            checkReturn sudo "${python_exe}" "${path}/addCrontabConfig.py" "--configPath=${configDir}" "--pythonPath=${python_exe}" "--sppmonPath=${sppmon_exe}" "--autoConfirm"
        else
            checkReturn sudo "${python_exe}" "${path}/addCrontabConfig.py" "--configPath=${configDir}" "--pythonPath=${python_exe}" "--sppmonPath=${sppmon_exe}"
        fi
        saveState 'GRAFANA_DASHBOARDS' 'Creation and configuration of the grafana dashboards'
    fi

    # Part 9: Grafana dashboards
    if [[ ${continue_point} == "GRAFANA_DASHBOARDS" ]]; then
        clear
        rowLimiter
        loggerEcho "Import SPPmon dashboards into Grafana"
        echo ""
        echo "> Please follow grafana import instructions"
        echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/Import-Grafana-Dashboards"
        saveState 'FINISHED' 'displaying finishing notes about the install of SPPMon'
    fi

    # Part 10: Finishing notes
    if [[ ${continue_point} == "FINISHED" ]]
        then
            # shellcheck source=./installScript/finishingScript.sh
            source "${subScripts}/finishingScript.sh" "${mainPath}"
    fi

}

# Start main if not used as source
if [ "$1" != "--source-only" ]; then

    # prelude
    path=$(getPath)
    subScripts="${path}/installScript"
    mainPath="${path}/installer.sh"
    saveFile="${subScripts}/.savefile.txt"
    configDir=$(realpath "${path}/../config_files")
    authFile="${path}/delete_me_auth.txt"

    # Sources
    # shellcheck source=./installScript/helper.sh
    source "${subScripts}/helper.sh" "--source-only"

    # Logger
    mkdir -p "${path}/logs"
    initLogger "${path}/logs/installLog.txt"
    logger "$@"

    # handling of signals
    trap " abortInstallScript " INT QUIT HUP


    main "$@"  # all arguments passed
fi
