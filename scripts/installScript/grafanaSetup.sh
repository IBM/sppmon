#!/bin/bash
#
# (C) IBM Corporation 2021
#
# Description:
# Installation and configuration of Grafana, including optional HTTPS-Setup.
# Activates Grafana on startup and checks for active state.
#
#
# Repository:
#   https://github.com/IBM/spectrum-protect-sppmon
#
# Author:
#  Niels Korschinsky

grafanaSetup() {

    clear
    rowLimiter
    loggerEcho "Setup and installation of Grafana"
    echo ""
    echo "> configuring yum repository"
    sudo tee /etc/yum.repos.d/grafana.repo<<EOF
[grafana]
name=grafana
baseurl=https://packages.grafana.com/oss/rpm
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://packages.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF

    loggerEcho "> Installing Grafana"
    checkReturn sudo yum install grafana

    loggerEcho "> Firewall configuration"
    checkReturn sudo firewall-cmd --add-port=3000/tcp --permanent
    checkReturn sudo firewall-cmd --reload

    local config_path=/etc/grafana
    local config_file="${config_path}/grafana.ini"
    local config_file_backup="${config_file}.orig"
    if [[ -f "${config_file_backup}" ]]; then
        loggerEcho "> Found previous grafana config file backup."
        loggerEcho "> Restoring original config file from backup."
        checkReturn sudo cp "${config_file_backup}" "${config_file}"
    else
        loggerEcho "> Backuping default configuration into ${config_file_backup}"
        checkReturn sudo cp -n "${config_file}" "${config_file_backup}"
    fi

    # Access rights
    checkReturn sudo chown -R grafana:grafana "${config_path}"

    loggerEcho "> Editing config file - part 1 -"

    if confirm "Disable reporting usage data to usage.influxdata.com?"
        then
            # [analytics] reporting_enabled
            checkReturn sudo sed -ri '"/[analytics]/,/\;?reporting_enabled\s*=.*/ s|\;*\s*reporting_enabled\s*=.*| reporting_enabled = false|"' "${config_file}"
        else
            checkReturn sudo sed -ri '"/[analytics]/,/\;?reporting_enabled\s*=.*/ s|\;*\s*reporting_enabled\s*=.*| reporting_enabled = true|"' "${config_file}"
    fi

    if ! confirm "Do you want to use default storage locations for all grafana data?" ; then
        local data_path
        local logs_path
        local plugins_path
        local provisioning_path

        promptText "Specify a Path to where grafana can store temp files, sessions, and the sqlite3 db (if that is used):" data_path "/var/lib/grafana"

        # [paths] data
        checkReturn sudo sed -ri "\"/\[paths\]/,/data\s*=.*/ s|\;*\s*data\s*=.*| data = ${data_path}|\"" "${config_file}"

        checkReturn sudo mkdir -p "${data_path}"
        checkReturn sudo chown -R grafana:grafana "${data_path}"

        promptText "Specify a directory where grafana can store logs:" logs_path "/var/log/grafana"

        # logs
        checkReturn sudo sed -ri "\"/\[paths\]/,/logs\s*=.*/ s|\;*\s*logs\s*=.*| logs = ${logs_path}|\"" "${config_file}"

        checkReturn sudo mkdir -p "${logs_path}"
        checkReturn sudo chown -R grafana:grafana "${logs_path}"

        promptText "Specify a directory where grafana will automatically scan and look for plugins:" plugins_path "/var/lib/grafana/plugins"

        # plugins
        checkReturn sudo sed -ri "\"/\[paths\]/,/plugins\s*=.*/ s|\;*\s*plugins\s*=.*| plugins = ${plugins_path}|\"" "${config_file}"

        checkReturn sudo mkdir -p "${plugins_path}"
        checkReturn sudo chown -R grafana:grafana "${plugins_path}"

        promptText "Specify a folder that contains provisioning config files that grafana will apply on startup and while running:" provisioning_path "conf/provisioning"

        # provisioning
        checkReturn sudo sed -ri "\"/\[paths\]/,/provisioning\s*=.*/ s|\;*\s*provisioning\s*=.*| provisioning = ${provisioning_path}|\"" "${config_file}"

        checkReturn sudo mkdir -p "${provisioning_path}"
        checkReturn sudo chown -R grafana:grafana "${provisioning_path}"
    fi

    echo ""
    echo "The following steps are optional and will setup Grafana to use SSL for"
    echo "secure communications.  This is highly recommended!"
    echo ""
    if confirm "Do you want to enable HTTPS-communication for Grafana? "; then

        # [server] protocol = https
        checkReturn sudo sed -ri '"/\[server\]/,/\;?protocol\s*=.*/ s|\;*\s*protocol\s*=.*| protocol = https|"' "${config_file}"

        # influx certs
        local httpsKeyPath="/etc/ssl/grafana-selfsigned.key"
        local httpsCertPath="/etc/ssl/grafana-selfsigned.crt"
        # generate
        if ! generate_cert "${httpsKeyPath}" "${httpsCertPath}" httpsKeyPath httpsCertPath ; then
            unsafeSsl=true
        fi

        checkReturn sudo chown -R grafana:grafana "${httpsKeyPath}"
        checkReturn sudo chown -R grafana:grafana "${httpsCertPath}"
        # Edit config file again
        # [server] cert_file
        checkReturn sudo sed -ri "\"/\[server\]/,/\;*\s*cert_file\s*=.*/ s|\;*\s*cert_file\s*=.*| cert_file = \\\"${httpsCertPath}\\\"|\"" "${config_file}"
        # [server] cert_key
        checkReturn sudo sed -ri "\"/\[server\]/,/\;*\s*cert_key\s*=.*/ s|\;*\s*cert_key\s*=.*| cert_key = \\\"${httpsKeyPath}\\\"|\"" "${config_file}"

    else
        # [server] protocol = http (disable HTTPS)
        checkReturn sudo sed -ri '"/\[server\]/,/\;*\s*protocol\s*=.*/ s|\;*\s*protocol\s*=.*| protocol = http|"' "${config_file}"

    fi


    ## email



    loggerEcho "> Starting Grafana service"
    checkReturn sudo systemctl enable --now grafana-server

    echo "> Waiting 10 seconds for startup"
    sleep 10

    loggerEcho "> Verify Grafana service is active"
    checkReturn sudo systemctl is-active grafana-server

    loggerEcho "Finished Grafana Setup"

}

# Start if not used as source
if [ "$1" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the grafanaSetup file"
        abortInstallScript
    fi

    # prelude
    mainPath="$1"
    # shellcheck source=./installer.sh
    source "${mainPath}" "--source-only"

    grafanaSetup "$@" # all arguments passed
fi