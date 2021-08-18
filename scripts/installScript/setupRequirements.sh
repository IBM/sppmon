#!/bin/bash
#
# (C) IBM Corporation 2021
#
# Description:
# Logs system informations and checks for yum install.
# Asks for updating yum installs.
#
#
# Repository:
#   https://github.com/IBM/spectrum-protect-sppmon
#
# Author:
#  Niels Korschinsky

setupRequirements() {
    # Part One: Setup and Requirements

    clear
    rowLimiter
    loggerEcho "Checking system setup and requirements"
    echo ""
    echo "To make sure this script can run sucessfully, please make sure the system"
    echo "requirements are fullfied."
    echo "https://github.com/IBM/spectrum-protect-sppmon/wiki/System-requirements"

    echo ""
    loggerEcho "> Checking yum install"
    if ! [ -x "$(command -v yum)" ]
        then
            loggerEcho "ERROR: yum is not available. Please make sure it is installed!"
            abortInstallScript
        else
            loggerEcho "> Yum installed."
    fi

    loggerEcho "> Logging System information"
    loggerEcho -e "-------------------------------System Information----------------------------"
    loggerEcho -e "Hostname:\t\t"`hostname`
    loggerEcho -e "uptime:\t\t\t"`uptime | awk '{print $3,$4}' | sed 's/,//'`
    loggerEcho -e "Manufacturer:\t\t"`cat /sys/class/dmi/id/chassis_vendor`
    loggerEcho -e "Product Name:\t\t"`cat /sys/class/dmi/id/product_name`
    loggerEcho -e "Version:\t\t"`sudo cat /sys/class/dmi/id/product_version`
    loggerEcho -e "Serial Number:\t\t"`sudo cat /sys/class/dmi/id/product_serial`
    loggerEcho -e "Machine Type:\t\t"`vserver=$(lscpu | grep Hypervisor | wc -l); if [ ${vserver} -gt 0 ]; then echo "VM"; else echo "Physical"; fi `
    loggerEcho -e "Operating System:\t"`hostnamectl | grep "Operating System" | cut -d ' ' -f5-`
    loggerEcho -e "Kernel:\t\t\t"`uname -r`
    loggerEcho -e "Architecture:\t\t"`arch`
    loggerEcho -e "Processor Name:\t\t"`awk -F':' '/^model name/ {print $2}' /proc/cpuinfo | uniq | sed -e 's/^[ \t]*//'`
    loggerEcho -e "Active User:\t\t"`w | cut -d ' ' -f1 | grep -v USER | xargs -n1`
    loggerEcho -e "System Main IP:\t\t"`hostname -I`
    loggerEcho -e "----------------------------------Disk--------------------------------------"
    df -PhT
    logger $(df -PhT)
    loggerEcho -e "-------------------------------Package Updates-------------------------------"
    yum updateinfo summary | grep 'Security|Bugfix|Enhancement'
    logger $(yum updateinfo summary | grep 'Security|Bugfix|Enhancement')
    echo ""
    loggerEcho "> finished logging."

    echo "This install script can now optionally check and install general operating"
    echo "system updates ('yum upgrade').  This is recommended."
    echo ""
    if confirm "Do you want to upgrade operating system components?" ; then
        if [ "${autoConfirm}" = true ]  ; then
            yes y | sudo yum upgrade
        else
            sudo yum upgrade
        fi
    fi

}

# Start if not used as source
if [ "$1" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the SetupRequirements file"
        abortInstallScript
    fi
    # prelude
    local mainPath="$1"
    # shellcheck source=./installer.sh
    source "${mainPath}" "--source-only"


    setupRequirements "$@" # all arguments passed
fi