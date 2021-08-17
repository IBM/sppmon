#!/bin/bash
#
# (C) IBM Corporation 2021
#
# Description:
# Groups helping function for logger, user interactions, prints and more
#
#
# Repository:
#   https://github.com/IBM/spectrum-protect-sppmon
#
# Author:
#  Niels Korschinsky
#
# Functions:
#   checkReturn - Checks if the argument statement was executed correctly, aborts otherwise.
#   sudoCheck - Checks for sudo permissions, aquires them if not root.
#   rowLimiter - Prints a delimiting row of # onto the console.
#   initLogger - Initializes logger, required to call before use of logger-functions.
#   logger - Prints text into logfile only.
#   loggerEcho - Prints text into logfile and on stdout.
#   generate_cert - Generating key + cert file for SSL-connections.
#   confirm - True/False-prompt with a message.
#   promptText - message-promt for a text.
#   promptPasswords - message-promt for a passwords, hiding input and prohibiting symbols.
#   promptLimitedText - message-promt for a text, prohibiting symbols.

# ########### MISC / FUNCTIONS #######################

#######################################
# Checks if the argument statement was executed correctly, aborts otherwise.
# Globals:
#   None
# Arguments:
#   @: Any command with args to be executed. Just prepend this function
# Outputs:
#   stdout: Information on error with executed command
#   log: Information on error with executed command
# Returns:
#   None, aborts script on failure
#######################################
checkReturn() { # TODO(Niels Korschinsky) maybe this is Bugged. Other quotations needed?
    eval "$@"
    if [[ "$?" -ne 0 ]]
        then
            loggerEcho "ERROR when executing command: \"$@\""
            abortInstallScript
    fi
}

#######################################
# Checks for sudo permissions, aquires them if not root.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   stdout: execution information
#   log: execution information
# Returns:
#   None, aborts script on wrong password
#######################################
sudoCheck() {
    if (( $# != 0 )); then
        >&2 loggerEcho "Illegal number of parameters sudoCheck"
        abortInstallScript
    fi

    loggerEcho "Checking if sudo privileges are available."
    if [[ "${EUID}" = 0 ]]; then
        loggerEcho "(1) already root"
    else
        # use validate option to refresh the sudo timer, or authenticate.
        if sudo -v; then
            loggerEcho "(2) correct password"
        else
            loggerEcho "(3) wrong password"
            abortInstallScript
        fi
    fi
}

# ########### PRINTING #######################

#######################################
# Prints a delimiting row of # onto the console.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   stdout: row of #
# Returns:
#   None
#######################################
rowLimiter() {
    if (( $# != 0 )); then
        >&2 loggerEcho "Illegal number of parameters rowLimiter"
        abortInstallScript
    fi

    printf '\n'
    printf '#%.0s' $(seq 1 $(tput cols)) && printf '\n'
    printf '\n'
}

#######################################
# Initializes logger, required to call before use of logger-functions.
# Globals:
#   logFile - set
# Arguments:
#   1: path to logfile
# Outputs:
#   log: script init information.
# Returns:
#   None
#######################################
initLogger(){
    if (( $# !=1 )); then
        >&2 echo "Illegal number of parameters loggerEcho"
        abortInstallScript
    fi

    set -a # now all variables are exported
    logFile=$1
    set +a # not anymore

    checkReturn touch ${logFile}
    echo "" >> ${logFile}
    echo "$(rowLimiter)" >> ${logFile}
    echo "$(date) |> initialize logger " >> ${logFile}
    echo "$(rowLimiter)" >> ${logFile}
    echo "" >> ${logFile}

}

#######################################
# Prints text into logfile only.
# Globals:
#   logFile - read
# Arguments:
#   @: Message(s) to write
# Outputs:
#   stderr: Unable to write log file
#   log: Date + Logging information
# Returns:
#   None
#######################################
logger(){
    if [[ ! -w "${logFile}" ]] ; then
        >&2 echo "ERROR: Log-File not writeable - path: ${logFile}"
            abortInstallScript
    fi

    echo "$(date) |> $@" >> "${logFile}"

}

#######################################
# Prints text into logfile and on stdout.
# Globals:
#   logFile - read
# Arguments:
#   @: Message(s) to write
# Outputs:
#   stderr: Unable to write log file
#   stdout: Logging information
#   log: Date + Logging information
# Returns:
#   None
#######################################
loggerEcho() {
    if [[ ! -w "${logFile}" ]] ; then
        >&2 echo "ERROR: Log-File not writeable - path: ${logFile}"
            abortInstallScript
    fi

    echo "$(date) |> $@" >> "${logFile}"
    echo "$@"

}

# ############ Generate Certs #################

#######################################
# Generating key + cert file for SSL-connections.
# Globals:
#   None
# Arguments:
#   1: Default path to key-file
#   2: Default path to cert-file
#   3: Out-Param - path to key file
#   4: Out-Param - path to cert file
# Outputs:
#   stdout: execution information, confirms
#   log: execution information, illegal duration.
# Returns:
#   0 if CA-signed cert, 1 if selfsigned cert
#######################################
generate_cert() {
    if (( $# != 4 )) ; then
        >&2 loggerEcho "Illegal number of parameters generate_cert"
        abortInstallScript
    fi

    local keyPath="$1"
    local certPath="$2"
    local __resultKeyPath="$3"
    local __resultCertPath="$4"

    local unsafeSsl

    if confirm "Do you want to create a self-signed certificate now? Choose no for existing certificate."; then

        unsafeSsl=true

        local keyCreateCommand="sudo openssl req -x509 -nodes -newkey rsa:4096 -keyout \"${keyPath}\" -out \"${certPath}\""
        local certDuration

        while true; do # repeat until valid symbol
            promptText "How long should it be valid in days? Leave empty for no limit" certDuration ""
            if ! [[ "'${certDuration}'" =~ ^\'[0-9]*\'$ ]] ; then
                loggerEcho "You may only enter numbers or leave blank."
            elif [[ -n "${certDuration}" ]]; then
                # append duration of cert
                keyCreateCommand="${keyCreateCommand} -days ${certDuration}"
                break
            else
                break
            fi
        done

        # Actually create the cert
        while true; do # repeat until created
            echo ${keyCreateCommand}
            eval "${keyCreateCommand}"
            if [[ $? -ne 0 ]]; then
                if ! confirm "cert creation failed. Do you want to try again?"; then
                    abortInstallScript
                fi
            else
                loggerEcho "> cert created sucessfully"
                break
            fi
        done
    else # Provide own cert

        echo ""
        echo "If the certificate you are providing is self-signed, sppmon will"
        echo "need to use the --unsafeSsl option."
        echo ""
        if confirm "Is your cert self-signed requiring the unsafe ssl flag?"; then
            unsafeSsl=true
        fi

        local defaultKeyPath=${keyPath}
        keyPath=""
        local defaultCertPath=${certPath}
        certPath=""

        # Key
        while [[ -z ${keyPath} ]] ; do
            echo ""
            promptText "Please enter the path to the https cert key" keyPath "${defaultKeyPath}"
            if [[ -z ${keyPath} ]]; then
                loggerEcho "The path of the key must not be empty"
            fi
        done
        # Cert
        while [[ -z ${certPath} ]] ; do
            echo ""
            promptText "Please enter the path to the https public cert" certPath "${defaultCertPath}"
            if [[ -z ${certPath} ]]; then
                loggerEcho "The path of the cert must not be empty"
            fi
        done

    fi

    eval ${__resultKeyPath}="'${keyPath}'"
    eval ${__resultCertPath}="'${certPath}'"

    if [[ ! ${unsafeSsl} ]] ; then
        return 0
    else
        return 1
    fi

}


# ############ USER PROMPTS ###################

#######################################
# True/False-prompt with a message.
# Globals:
#   None
# Arguments:
#   1: message to display
#   2: Optional - alwaysConfirm flag
# Outputs:
#   stdout: message and chosen answer
#   log: message and chosen answer, autoconfirm flag
# Returns:
#   0 if chosen yes or autoconfirm, 1 if no
#######################################
confirm() { # param1:message # param2: alwaysconfirm
    if (( $# != 1 && $# != 2)) ; then
        >&2 loggerEcho "Illegal number of parameters confirm"
        abortInstallScript
    fi

    local alwaysConfirm=false
    local message="$1"
    local confirmInput

    logger "${message}"

    # if two arguments exists, the second has to be alwaysConfirm
    if (( $# == 2 )) ; then
        if [[ "$2" == "--alwaysConfirm" ]] ; then
            alwaysConfirm=true
            logger "alwaysConfirm"
        else
            >&2 loggerEcho "Illegal second parameter; is not alwaysConfirm for confirm"
            abortInstallScript
        fi
    fi

    if [ "${autoConfirm}" = true ] && ! [ "${alwaysConfirm}" = true ] ; then
        printf "${message} : autoConfirm -> "
        loggerEcho "Yes"
        return 0
    fi

    read -r -p"${message} (Yes/no) [Yes] " confirmInput
    echo ""
    case "${confirmInput}" in
        [yY][eE][sS] | [yY] | "")
            loggerEcho 'Yes'
            return 0
            ;;
        *)
            loggerEcho 'No'
            return 1
            ;;
    esac
}

#######################################
# message-promt for a text.
# Globals:
#   None
# Arguments:
#   1: message to display
#   2: Out-param - text result
#   3: Optional - default value
# Outputs:
#   stdout: message and answer
#   log: message and answer
# Returns:
#   None
#######################################
promptText() {
    if (( $# != 2 && $# != 3 )); then
        >&2 loggerEcho "Illegal number of parameters promptText"
        abortInstallScript
    fi

    local message="$1" # param1:message
    local __resultVal=$2 # param2: result
    local defaultValue # OPTIONAL param3: default val

    local promptTextInput

    if [[ -n ${3+x} ]] # evaluates to nothing if not set, form: if [ -z {$var+x} ]; then unset; else set; fi
        then    # default set
            defaultValue="$3"
            message="${message} [${defaultValue}]"
        else # default not given
            defaultValue=""
    fi
    while true ; do
        read -r -p"${message}: " promptTextInput
        promptTextInput="${promptTextInput:-$defaultValue}" # substitues if unset or null
        # form: ${parameter:-word}

        logger "${message}"

        if confirm "Is \"${promptTextInput}\" the correct input?"; then
                break
        fi
    done
    eval ${__resultVal}="'${promptTextInput}'"

}

#######################################
# message-promt for a passwords, hiding input and prohibiting symbols.
# Globals:
#   autoConfirm - read
# Arguments:
#   1: message to display
#   2: Out-param - text result
#   3: Optional - default value
# Outputs:
#   stdout: message and answer
#   log: message and answer
# Returns:
#   None
#######################################
promptPasswords() {
    if (( $# != 2 && $# != 3 )); then
        >&2 loggerEcho "Illegal number of parameters promptText"
        abortInstallScript
    fi

    local message="$1" # param1:message
    local __resultVal=$2 # param2: result
    local defaultValue # OPTIONAL param3: default val

    local prohibitedSymbols="\" '\\/"
    local promptPasswordInput
    local promptPasswordInputConfirm

    if [[ -n ${3+x} ]] # evaluates to nothing if not set, form: if [ -z {$var+x} ]; then unset; else set; fi
        then    # default set
            defaultValue="$3"
            message="${message} [${defaultValue}]"
        else # default not given
            defaultValue=""
    fi
    while true ; do
        read -r -s -p"${message}: " promptPasswordInput
        promptPasswordInput="${promptPasswordInput:-${defaultValue}}" # substitues if unset or null
        # form: ${parameter:-word}

        logger "${message}"

        if [[ -z ${promptPasswordInput} ]]; then
            loggerEcho "No empy value is allowed, please try again."
            continue # start loop again
        else
            local symbCheck=$(echo "${promptPasswordInput}" | grep "[${prohibitedSymbols}]" >/dev/null; echo $?)
            # 0 means match, which is bad. 1 = all good
            if [[ ${symbCheck} -ne 1 ]]; then
                loggerEcho "The ${description} must not contain any of the following symbols: ${prohibitedSymbols}"
                promptPasswordInput=""
                continue # start loop again
            fi
        fi

        if [ "${autoConfirm}" = true ] ; then
            break
        fi

        # Confirmation by repeating
        echo ""
        promptPasswordInputConfirm=""
        read -r -s -p"Please repeat to confirm: " promptPasswordInputConfirm
        logger "Password repeat confirm"
        promptPasswordInputConfirm="${promptPasswordInputConfirm:-$defaultValue}"

        echo "" # newline

        # Everything is correct -> return value
        if [[ "${promptPasswordInput}" == "${promptPasswordInputConfirm}" ]]; then
                break # exit
        else
            loggerEcho "Input did not match, please try again"
            # continue / start loop again
        fi
    done

    eval ${__resultVal}="'${promptPasswordInput}'"
}

#######################################
# message-promt for a text, prohibiting symbols.
# Globals:
#   autoConfirm - read
# Arguments:
#   1: message to display
#   2: Out-param - text result
#   3: Optional - default value
# Outputs:
#   stdout: message and answer
#   log: message and answer
# Returns:
#   None
#######################################
promptLimitedText() {
    if (( $# != 2 && $# != 3 )); then
        >&2 loggerEcho "Illegal number of parameters promptLimitedText"
        abortInstallScript
    fi

    local description="$1" # param1: description in text
    local __resultVal=$2 # param2: result
    # OPTIONAL param3: default val

    local prohibitedSymbols="\" '\\/"
    local promptLimitedTextInput

    while [[ -z ${promptLimitedTextInput} ]]; do
        if [[ -n ${3+x} ]]; then # evaluates to nothing if not set, form: if [ -z {$var+x} ]; then unset; else set; fi
            promptText "${description}" promptLimitedTextInput $3
        else # default not given
            promptText "${description}" promptLimitedTextInput
        fi

        if [[ -z ${promptLimitedTextInput} ]]; then
            loggerEcho "No empy value is allowed, please try again."
        else
            local symbCheck=$(echo "${promptLimitedTextInput}" | grep "[${prohibitedSymbols}]" >/dev/null; echo $?)
            # 0 means match, which is bad. 1 = all good
            if [[ ${symbCheck} -ne 1 ]]; then
                loggerEcho "The ${description} must not contain any of the following symbols: ${prohibitedSymbols}"
                promptLimitedTextInput=""
            fi
        fi
    done

    eval ${__resultVal}="'${promptLimitedTextInput}'"
}

# ######### STARTUP ##############

if [ "$1" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the helper file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "${mainPath}" "--source-only"

    # STARTFUNCTION "$@" # all arguments passed
fi