#!/bin/bash



# ########### MISC / FUNCTIONS #######################

checkReturn() { # TODO maybe this is Bugged. Other quotations needed?
    eval "${@}"
    if [[ "$?" -ne 0 ]]
        then
            loggerEcho "ERROR when executing command: \"$@\""
            abortInstallScript
    fi
}

sudoCheck() {
    if (( $# != 0 )); then
        >&2 loggerEcho "Illegal number of parameters sudoCheck"
        abortInstallScript
    fi

    loggerEcho "Checking if sudo privileges are available."
    if [[ "$EUID" = 0 ]]; then
        loggerEcho "(1) already root"
    else
        sudo -k # make sure to ask for password on next sudo
        if sudo true; then
            loggerEcho "(2) correct password"
        else
            loggerEcho "(3) wrong password"
            abortInstallScript
        fi
    fi
}

# ########### PRINTING #######################

# print row of # signs to the console
rowLimiter() {
    if (( $# != 0 )); then
        >&2 loggerEcho "Illegal number of parameters rowLimiter"
        abortInstallScript
    fi

    printf '\n'
    printf '#%.0s' $(seq 1 $(tput cols)) && printf '\n'
    printf '\n'
}


initLogger(){
    if (( $# !=1 )); then
        >&2 echo "Illegal number of parameters loggerEcho"
        abortInstallScript
    fi

    set -a # now all variables are exported
    logFile=$1
    set +a # not anymore

    checkReturn touch $logFile
    echo "" >> $logFile
    echo "$(rowLimiter)" >> $logFile
    echo "$(date) |> initialize logger " >> $logFile
    echo "$(rowLimiter)" >> $logFile
    echo "" >> $logFile

}

logger(){
    if [[ ! -w $logFile ]] ; then
        >&2 echo "ERROR: Log-File not writeable - path: ${logFile}"
            abortInstallScript
    fi

    local message=$1

    echo "$(date) |> ${@}" >> $logFile

}

loggerEcho() {
    fi
    if [[ ! -w $logFile ]] ; then
        >&2 echo "ERROR: Log-File not writeable - path: ${logFile}"
            abortInstallScript
    fi

    local message=$1

    echo "$(date) |> ${@}" >> $logFile
    echo "${@}"

}

# ############ USER PROMPTS ###################

# prompt for a confirm with message, returning true or false
confirm() { # param1:message # param2: alwaysconfirm
    if (( $# != 1 && $# != 2)) ; then
        >&2 loggerEcho "Illegal number of parameters confirm"
        abortInstallScript
    fi

    local alwaysConfirm=false
    local message="$1"
    local confirmInput

    logger "$message"

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

    if [ "$autoConfirm" = true ] && ! [ "$alwaysConfirm" = true ] ; then
        printf "$message : autoConfirm -> "
        loggerEcho "Yes"
        return 0
    fi

    read -r -p"$message (Yes/no) [Yes] " confirmInput
    echo ""
    case "$confirmInput" in
        [yY][eE][sS] | [yY] | "" )
            loggerEcho 'Yes'
            return 0
            ;;
        * )
            loggerEcho 'No'
            return 1
            ;;
    esac
}

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
            message="$message [$defaultValue]"
        else # default not given
            defaultValue=""
    fi
    while true ; do
        read -r -p"$message: " promptTextInput
        promptTextInput="${promptTextInput:-$defaultValue}" # substitues if unset or null
        # form: ${parameter:-word}

        logger "$message"

        if confirm "Is \"$promptTextInput\" the correct input?"; then
                break
        fi
    done
    eval $__resultVal="'$promptTextInput'"

}

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
            message="$message [$defaultValue]"
        else # default not given
            defaultValue=""
    fi
    while true ; do
        read -r -s -p"$message: " promptPasswordInput
        promptPasswordInput="${promptPasswordInput:-$defaultValue}" # substitues if unset or null
        # form: ${parameter:-word}

        logger "$message"

        if [[ -z $promptPasswordInput ]]; then
            loggerEcho "No empy value is allowed, please try again."
            continue # start loop again
        else
            local symbCheck=$(echo "$promptPasswordInput" | grep "[$prohibitedSymbols]" >/dev/null; echo $?)
            # 0 means match, which is bad. 1 = all good
            if [[ $symbCheck -ne 1 ]]; then
                loggerEcho "The $description must not contain any of the following symbols: $prohibitedSymbols"
                promptPasswordInput=""
                continue # start loop again
            fi
        fi

        if [ "$autoConfirm" = true ] ; then
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

    eval $__resultVal="'$promptPasswordInput'"
}

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

    while [[ -z $promptLimitedTextInput ]]; do
        if [[ -n ${3+x} ]]; then # evaluates to nothing if not set, form: if [ -z {$var+x} ]; then unset; else set; fi
            promptText "${description}" promptLimitedTextInput $3
        else # default not given
            promptText "${description}" promptLimitedTextInput
        fi

        if [[ -z $promptLimitedTextInput ]]; then
            loggerEcho "No empy value is allowed, please try again."
        else
            local symbCheck=$(echo "$promptLimitedTextInput" | grep "[$prohibitedSymbols]" >/dev/null; echo $?)
            # 0 means match, which is bad. 1 = all good
            if [[ $symbCheck -ne 1 ]]; then
                loggerEcho "The $description must not contain any of the following symbols: $prohibitedSymbols"
                promptLimitedTextInput=""
            fi
        fi
    done

    eval $__resultVal="'$promptLimitedTextInput'"
}

# ######### STARTUP ##############

if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the helper file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    # STARTFUNCTION "${@}" # all arguments passed
fi