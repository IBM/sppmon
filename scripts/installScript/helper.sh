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
    if [[ ! -w $logFile ]] ; then
        >&2 echo "ERROR: Log-File not writeable - path: ${logFile}"
            abortInstallScript
    fi

    local message=$1

    echo "$(date) |> ${@}" >> $logFile
    echo "${@}"

}

# ############ Generate Certs #################

# generating cert for SSL
generate_cert() {
    # param1: default key location
    # param2: default cert location

    # out-param3: actual key location
    # out-param4: actual cert location

    # returns: unsafe cert (true/false)

    if (( $# != 1 && $# != 2)) ; then
        >&2 loggerEcho "Illegal number of parameters generate_cert"
        abortInstallScript
    fi

    local keyPath="$1"
    local CertPath="$2"
    local __resultKeyPath="$3"
    local __resultCertPath"$4"

    local unsafeSsl

    if confirm "Automatically create a self-signed certificate? "; then

        unsafeSsl=true

        local keyCreateCommand="sudo openssl req -x509 -nodes -newkey rsa:4096 -keyout \"$keyPath\" -out \"$CertPath\""
        local certDuration

        while true; do # repeat until valid symbol
            promptText "How long should it be valid in days? Leave empty for no limit" certDuration ""
            if ! [[ "'$certDuration'" =~ ^\'[0-9]*\'$ ]] ; then
                loggerEcho "You may only enter numbers or leave blank."
            elif [[ -n "$certDuration" ]]; then
                # append duration of cert
                keyCreateCommand="$keyCreateCommand -days $certDuration"
                break
            else
                break
            fi
        done

        # Actually create the cert
        while true; do # repeat until created
            echo $keyCreateCommand
            eval "$keyCreateCommand"
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

        local defaultKeyPath=$keyPath
        KeyPath=""
        local defaultCertPath=$CertPath
        CertPath=""

        # Key
        while [[ -z $keyPath ]]; do
            echo ""
            promptText "Please enter the path to the https cert key" keyPath "$defaultKeyPath"
            if [[ -z $keyPath ]]; then
                loggerEcho "The path of the key must not be empty"
            fi
        done
        # Cert
        while [[ -z $CertPath ]]; do
            echo ""
            promptText "Please enter the path to the https pulic cert" CertPath "$defaultCertPath"
            if [[ -z $CertPath ]]; then
                loggerEcho "The path of the cert must not be empty"
            fi
        done

    fi

    eval $__resultKeyPath="'$keyPath'"
    eval $__resultCertPath="'$CertPath'"

    if [[ $unsafeSsl ]] ; then
        return 0
    else
        return 1
    fi

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