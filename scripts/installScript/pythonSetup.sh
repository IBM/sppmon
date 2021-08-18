#!/bin/bash
#
# (C) IBM Corporation 2021
#
# Description:
# Installation of python3 and sppmon-requirements-file.
# Installs as alternative version due yum requirement of python2.7.
# Also installs gcc and development tools if not available.
#
#
# Repository:
#   https://github.com/IBM/spectrum-protect-sppmon
#
# Author:
#  Niels Korschinsky
#
# Functions:
#   currentInstallCheck - Checks if the current python install is sufficent.
#   pythonSetup - see description above.

#######################################
# Checks if the current python install is sufficent.
# Globals:
#   None
# Arguments:
#   None
# Outputs:
#   stdout: extended execution information and current python version
#   log: execution information and current python version
# Returns:
#   0 if version is sufficent, 1 if not.
#######################################
currentInstallCheck() {
    loggerEcho "> Verifying the installed python version"
    local python_old_path=$(which python)

    local current_ver=$(python -V 2>&1 | grep -oP "^Python \K.*")
    #  code does work with 3.8, but latest version is better.
    local required_ver="3.9.6"

    if [ "$(printf '%s\n' "${required_ver}" "${current_ver}" | sort -V | head -n1)" = "${required_ver}" ]; then
        loggerEcho "> Compatible Python version installed (${current_ver} > ${required_ver})."

        loggerEcho "> Creating systemlink to /usr/bin/python3"
        checkReturn ln -sf "${python_old_path}" /usr/bin/python3
        return 0
    elif command -v python3 &> /dev/null ; then
        local python_old_path=$(which python3)
        local current_ver=$(python3 -V 2>&1 | grep -oP "^Python \K.*")

        if [ "$(printf '%s\n' "${required_ver}" "${current_ver}" | sort -V | head -n1)" = "${required_ver}" ]; then
            loggerEcho "> Compatible Python version installed (${current_ver} > ${required_ver})."
            return 0
        fi
    fi

    # This uses the latest python 3 install if available -> this version does matter the most.
    loggerEcho "> Current version does not match the requirements (${current_ver} < ${required_ver})"
    return 1
}

pythonSetup() {

    # if not python 3, but 4 - changes have to be made below and in many parts of the installer.
    local python_version="396"
    local python_version_main="3.9"
    local python_version_dots="3.9.6"


    clear
    rowLimiter
    loggerEcho "Installation of Python and packages"
    echo ""

    loggerEcho "> Checking gcc install"
    gcc --version &>/dev/null
    if (( $? != 0 ))
        then
            loggerEcho "> Installing gcc"
            checkReturn sudo yum install gcc
        else
            loggerEcho "> gcc installed."
    fi

    loggerEcho "> Installing development libaries and packages"
    checkReturn sudo yum -y groupinstall '"Development Tools"'
    checkReturn sudo yum -y install openssl-devel bzip2-devel libffi-devel
    checkReturn sudo yum -y install wget

    # check for current python install
    if ! currentInstallCheck ; then

        loggerEcho "> Installing Python ${python_version_dots}"

        checkReturn mkdir -p "/tmp/python${python_version}"
        checkReturn cd "/tmp/python${python_version}/"
        checkReturn wget "https://www.python.org/ftp/python/${python_version_dots}/Python-${python_version_dots}.tgz"
        # TODO get without internet

        checkReturn cd "/tmp/python${python_version}/"
        checkReturn tar -xf "Python-${python_version_dots}.tgz"
        checkReturn cd "/tmp/python${python_version}/Python-${python_version_dots}"
        checkReturn ./configure --enable-optimizations --prefix=/usr --quiet

        # Only set alternatives if python 2.7 is installed
        if command -v python2.7 &> /dev/null ; then

            loggerEcho "> Python may take a few minutes to install. Please wait."
            echo "> You do not need to press anything."
            checkReturn sudo make altinstall -s

            loggerEcho "> Configuring alternatives between python2.7 (yum) and python ${python_version_dots} (sppmon)."
            checkReturn sudo update-alternatives --install /usr/bin/python python "/usr/bin/python${python_version_main}" 2
            checkReturn sudo update-alternatives --install /usr/bin/python python /usr/bin/python2.7 1
            checkReturn sudo update-alternatives --set python /usr/bin/python2.7
        else
            checkReturn sudo make install
        fi

        loggerEcho "> Creating systemlink to /usr/bin/python3"
        checkReturn sudo ln -sf "/usr/bin/python${python_version_main}" "/usr/bin/python3"

        # Confirming install

        current_ver=$(python3 -V 2>&1)
        if [ "$(printf '%s\n' "${required_ver}" "${current_ver}" | sort -V | head -n1)" = "${required_ver}" ]; then
            loggerEcho "> Python install sucessfull."
        else
            loggerEcho "> Python install unsucessfull."
            abortInstallScript
        fi
    fi

    loggerEcho "> Checking and upgrading pip version"
    checkReturn sudo -H python3 -m pip install --upgrade pip

    loggerEcho "> Installing required packages"
    #echo $(realpath $(dirname "${mainPath}")/../python/requirements.txt)

    checkReturn sudo -H python3 -m pip install -U -r $(realpath $(dirname "${mainPath}")/../python/requirements.txt)

    loggerEcho "Finished Python installation Setup"

}

# Start if not used as source
if [ "$1" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the pythonSetup file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "${mainPath}" "--source-only"

    pythonSetup "$@" # all arguments passed
fi