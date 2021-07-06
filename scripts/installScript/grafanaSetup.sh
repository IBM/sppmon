#!/bin/bash

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

    local config_path=/etc/influxdb
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

    loggerEcho "> Editing config file - part 1 -"

    if confirm "Disable reporting usage data to usage.influxdata.com?"
        then
            checkReturn sudo sed -i '"s/\;*\s*reporting_disabled\s*=.*/ reporting_disabled = true/"' "${config_file}"
        else
            checkReturn sudo sed -i '"s/\;*\s*reporting_disabled\s*=.*/ reporting_disabled = false/"' "${config_file}"
    fi

    if ! confirm "Do you want to use default storage locations for all grafana data?" ; then
        local data_path
        local logs_path
        local plugins_path
        local provisioning_path

        promptText "Specify a Path to where grafana can store temp files, sessions, and the sqlite3 db (if that is used):" data_path "/var/lib/grafana"

        # [paths] data
        checkReturn sudo sed -ri "\"/\[paths\]/,/data\s*=.+/ s|\;*\s*data\s*=.+| data = ${data_path}|\"" "${config_file}"

        promptText "Specify a directory where grafana can store logs:" logs_path "/var/log/grafana"

        # logs
        checkReturn sudo sed -ri "\"/\[paths\]/,/logs\s*=.+/ s|\;*\s*logs\s*=.+| logs = ${logs_path}|\"" "${config_file}"

        promptText "Specify a directory where grafana will automatically scan and look for plugins:" plugins_path "/var/lib/grafana/plugins"

        # plugins
        checkReturn sudo sed -ri "\"/\[paths\]/,/plugins\s*=.+/ s|\;*\s*plugins\s*=.+| plugins = ${plugins_path}|\"" "${config_file}"

        promptText "Specify a folder that contains provisioning config files that grafana will apply on startup and while running:" provisioning_path "conf/provisioning"

        # provisioning
        checkReturn sudo sed -ri "\"/\[paths\]/,/provisioning\s*=.+/ s|\;*\s*provisioning\s*=.+| provisioning = ${provisioning_path}|\"" "${config_file}"

    fi

    # Access rights
    checkReturn sudo chown -R influxdb:influxdb "${config_path}"
    checkReturn sudo mkdir -p "${influx_db_path}"
    checkReturn sudo chown -R influxdb:influxdb "${influx_db_path}"

    ## email

    ## https


    loggerEcho "> Starting Grafana service"
    checkReturn sudo systemctl enable --now grafana-server

    echo "> Waiting 10 seconds for startup"
    sleep 10

    loggerEcho "> Verify Grafana service is active"
    checkReturn sudo systemctl is-active grafana-server

    loggerEcho "Finished Grafana Setup"

}

# Start if not used as source
if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the grafanaSetup file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    grafanaSetup "${@}" # all arguments passed
fi