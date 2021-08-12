#!/bin/bash

restartInflux() {
    if (( $# != 0 )); then
        >&2 loggerEcho "Illegal number of parameters restartInflux"
        abortInstallScript
    fi
    local check_influx='systemctl is-active influxdb &>/dev/null; echo $?'

    if (( $(eval "${check_influx}") == 0 )); then
        loggerEcho "> Restarting influxDB service"
        checkReturn sudo systemctl restart influxdb
    else
        loggerEcho "> Starting influxDB service"
        checkReturn sudo systemctl start influxdb
    fi

    loggerEcho "> Waiting 10 seconds for startup of influxDB"
    sleep 10
    #for (( i = 0; i < 10; i++)); do
    #    sleep 1
    #    if (( $(eval "${check_influx}") == 0 )); then
    #        echo "Restart sucessfull"
    #        return 0
    #    fi
    #done
    if (( $(eval "${check_influx}") == 0 )); then
        loggerEcho "> Restart sucessfull"
        return 0
    else
        loggerEcho "> Restart failed"
        abortInstallScript
    fi

}

executeInfluxCommand() {
    if (( $# > 3 || $# < 1 )); then
        >&2 loggerEcho "Illegal number of parameters executeInfluxCommand"
        abortInstallScript
    fi

    local command=$1 # param1: command to be executed
    local userName=$2 # param2: user to be logged in
    local password=$3 # param3: password to be used

    local connectionTestString="influx -host $influxAddress -port $influxPort"
    if [[ -n $userName ]] ; then
        connectionTestString="$connectionTestString -username $userName"
    fi
    if [[ -n $password ]] ; then
        connectionTestString="$connectionTestString -password $password"
    fi
    if [[ $sslEnabled != "false" ]] ; then # globalVar
        connectionTestString="$connectionTestString -ssl"
        if [[ $unsafeSsl != "false" ]] ; then # globalVar
            connectionTestString="$connectionTestString -unsafeSsl"
        fi
    fi
    logger $connectionTestString -execute "${command}"
    loggerEcho "> Waiting 10 seconds to avoid connection error"
    sleep 10
    local connectionOutput=$($connectionTestString -execute "${command}")
    local connectionCode=$?
    logger "$connectionOutput"
    logger "$connectionCode"
    return $connectionCode

}

verifyConnection() {
    if (( $# != 2 )); then
        >&2 loggerEcho "Illegal number of parameters verifyConnection"
        abortInstallScript
    fi
    local userName=$1 # param1: user to be logged in
    local password=$2 # param2: password to be used

    loggerEcho "> verifying connection to InfluxDB"

    executeInfluxCommand "SHOW DATABASES" "$userName" "$password"
    local influxVerifyCode=$?

    if [[ $influxVerifyCode -ne 0 ]]; then

        loggerEcho "> ERROR: The connection could not be established."
        if ! confirm "Do you want to continue anyway?" ; then
            abortInstallScript
        fi
    else
        loggerEcho "> connection sucessfull established."
    fi
}

influxSetup() {

    clear
    rowLimiter
    loggerEcho "Setup and installation of InfluxDB"
    echo ""

    loggerEcho "> configuring yum repository"
    sudo tee  /etc/yum.repos.d/influxdb.repo 1> /dev/null <<EOF
[influxdb]
name = InfluxDB Repository
baseurl = https://repos.influxdata.com/rhel/7/x86_64/stable/
enabled = 1
gpgcheck = 1
gpgkey = https://repos.influxdata.com/influxdb.key
EOF

    loggerEcho "> Installing database"
    checkReturn sudo yum install influxdb-1.8.1-1

    local influxAddress=$(ip route get 1 | sed -n 's/^.*src \([0-9.]*\) .*$/\1/p')
    local influxPort=8086

    loggerEcho "> Firewall configuration"
    checkReturn sudo firewall-cmd --add-port=${influxPort}/tcp --permanent
    checkReturn sudo firewall-cmd --reload

    local config_path=/etc/influxdb
    local config_file="${config_path}/influxdb.conf"
    local config_file_backup="${config_file}.orig"
    if [[ -f "${config_file_backup}" ]]; then
        loggerEcho "> Found previous influx config file backup."
        loggerEcho "> Restoring original config file from backup."
        checkReturn sudo cp "${config_file_backup}" "${config_file}"
    else
        loggerEcho "> Backuping default configuration into ${config_file_backup}"
        checkReturn sudo cp -n "${config_file}" "${config_file_backup}"
    fi

    local influx_db_path
    echo ""
    echo "Specify the directory location where you want to store InfluxDb data files"
    echo "including data, meta, and wal.  The directory will be created automatically,"
    echo "and should be located under a file system with space dedicated to SPPmon."
    echo ""
    promptText "Specify a directory for InfluxDB storage:" influx_db_path "$(realpath /influxDB)"

    # Access rights
    checkReturn sudo chown -R influxdb:influxdb "${config_path}"
    checkReturn sudo mkdir -p "${influx_db_path}"
    checkReturn sudo chown -R influxdb:influxdb "${influx_db_path}"

    loggerEcho "> Editing config file - part 1 -"
    if confirm "Disable reporting usage data to usage.influxdata.com?"
        then
            checkReturn sudo sed -i '"s/\#*\s*reporting-disabled\s*=.*/ reporting-disabled = true/"' "${config_file}"
        else
            checkReturn sudo sed -i '"s/\#*\s*reporting-disabled\s*=.*/ reporting-disabled = false/"' "${config_file}"
    fi

    # sed -i 's/search_string/replace_string/' filename
    # sed -i -r '/header3/,/pattern/ s|pattern|replacement|' filename

    # Changing dirs cause on default path /var/lib permissions will fail
    # [meta] dir
    checkReturn sudo sed -ri "\"/\[meta\]/,/dir\s*=.+/ s|\#*\s*dir\s*=.+| dir = \\\"${influx_db_path}/meta\\\"|\"" "${config_file}"


    # [data] dir
    checkReturn sudo sed -ri "\"/\[data\]/,/dir\s*=.+/ s|\#*\s*dir\s*=.+| dir = \\\"${influx_db_path}/data\\\"|\"" "${config_file}"
    # [data] wal-dir
    checkReturn sudo sed -ri "\"/\[data\]/,/wal-dir\s*=.+/ s|\#*\s*wal-dir\s*=.+| wal-dir = \\\"${influx_db_path}/wal\\\"|\"" "${config_file}"

    # [http] enabled = true
    #checkReturn sudo sed -ri '"/\[http\]/,/enabled\s*=.+/ s|\#*\s*enabled\s*=.+| enabled = true|"' "${config_file}"
    # [http] log-enabled = true
    #checkReturn sudo sed -ri '"/\[http\]/,/log-enabled\s*=.+/ s|\#*\s*log-enabled\s*=.+| log-enabled = true|"' "${config_file}"

    # [http] flux-enabled = true
    checkReturn sudo sed -ri '"/\[http\]/,/flux-enabled\s*=.+/ s|\#*\s*flux-enabled\s*=.+| flux-enabled = true |"' "${config_file}"
    # [http] flux-log-enabled = true
    #checkReturn sudo sed -ri '"/\[http\]/,/flux-log-enabled\s*=.+/ s|\#*\s*flux-log-enabled\s*=.+| flux-log-enabled = true |"' "${config_file}"

    # [http] bind-address
    checkReturn sudo sed -ri "\"/\[http\]/,/bind-address\s*=.+/ s|\#*\s*bind-address\s*=.+| bind-address = \\\":${influxPort}\\\"|\"" "${config_file}"

    # DISABLE to allow user creation
    # [http] auth-enabled = false
    checkReturn sudo sed -ri '"/\[http\]/,/auth-enabled\s*=.+/ s|\#*\s*auth-enabled\s*=.+| auth-enabled = false|"' "${config_file}"
    # [http] https-enabled = false
    checkReturn sudo sed -ri '"/\[http\]/,/https-enabled\s*=.+/ s|\#*\s*https-enabled\s*=.+| https-enabled = false|"' "${config_file}"

    checkReturn sudo systemctl enable influxdb
    restartInflux

    loggerEcho "Creating InfluxDB super user"

    #################### INFLUXADMIN USER ################
    local adminCreated=false
    # Create user
    while [ "$adminCreated" = false ] ; do # repeat until break, when it works

        readAuth # read all existing auths
        # At this point SSL has not been configured, so avoid verifyConnnection() failures
        sslEnabled="false"
        unsafeSsl="false"

        # Sets default to either pre-saved value or influxadmin
        if [[ -z $influxAdminName ]]; then
            local influxAdminName="influxAdmin"
        fi
        echo ""
        promptLimitedText "Please enter the desired InfluxDB admin name" influxAdminName "$influxAdminName"

        # sets default to presaved value if empty
        if [[ -z $influxAdminPassword ]]; then
            local influxAdminPassword
        fi
        promptPasswords "Please enter the desired InfluxDB admin password" influxAdminPassword "$influxAdminPassword"

        executeInfluxCommand "CREATE USER \"$influxAdminName\" WITH PASSWORD '$influxAdminPassword' WITH ALL PRIVILEGES"
        local userCreateReturnCode=$?

        if (( $userCreateReturnCode != 0 ));then
            loggerEcho "Creation failed due an error. Please read the output above."
            if ! confirm "Do you want to try again (y) or continue (n)? Abort by ctrl + c" "--alwaysConfirm"; then
                # user wants to exit
                adminCreated=true
            fi
            # else
            # Start again
            loggerEcho "Trying again"
        else
            loggerEcho "> admin creation sucessfully"
            adminCreated=true
        fi

    done

    saveAuth "influxAdminName" "${influxAdminName}"
    saveAuth "influxAdminPassword" "${influxAdminPassword}"
    saveAuth "influxPort" "${influxPort}"
    saveAuth "influxAddress" "${influxAddress}"

    verifyConnection "$influxAdminName" "$influxAdminPassword"

    #################### GRAFANA READER USER ################

    # this should always be grafana reader
    local influxGrafanaReaderName="GrafanaReader"

    echo ""
    loggerEcho "Creating InfluxDB '$influxGrafanaReaderName' user"

    # Create user
    local grafanaReaderCreated=false
    while [ "$grafanaReaderCreated" = false ]  ; do # repeat until break, when it works

        readAuth # read all existing auths
        # At this point SSL has not been configured, so avoid verifyConnnection() failures
        sslEnabled="false"
        unsafeSsl="false"

        # sets default to presaved value if empty
        if [[ -z $influxGrafanaReaderPassword ]]; then
            local influxGrafanaReaderPassword
        fi
        promptPasswords "Please enter the desired GrafanaReader password" influxGrafanaReaderPassword "$influxGrafanaReaderPassword"

        executeInfluxCommand "CREATE USER \"$influxGrafanaReaderName\" WITH PASSWORD '$influxGrafanaReaderPassword'"
        local userCreateReturnCode=$?

        if (( $userCreateReturnCode != 0 )) ;then
            loggerEcho "Creation failed due an error. Please read the output above."
            if ! confirm "Do you want to try again (y) or continue (n)? Abort by ctrl + c" "--alwaysConfirm"; then
                # user wants to exit
                grafanaReaderCreated=true
            fi
            loggerEcho "Trying again"
            # else
            # Start again
        else
            loggerEcho "> GrafanaReader creation sucessfully"
            grafanaReaderCreated=true
        fi

    done

    saveAuth "influxGrafanaReaderName" "${influxGrafanaReaderName}"
    saveAuth "influxGrafanaReaderPassword" "${influxGrafanaReaderPassword}"

    verifyConnection "$influxGrafanaReaderName" "$influxGrafanaReaderPassword"

    ############# ENABLE AUTH ##################

    loggerEcho " > Editing influxdb config file - part 2 -"
    # [http] auth-enabled = true
    checkReturn sudo sed -ri '"/\[http\]/,/auth-enabled\s*=.+/ s|\#*\s*auth-enabled\s*=.+| auth-enabled = true|"' "${config_file}"
    # [http] pprof-auth-enabled = true
    #checkReturn sudo sed -ri '"/\[http\]/,/pprof-enabled\s*=.+/ s|\#*\s*pprof-enabled\s*=.+| pprof-enabled = true|"' "${config_file}"
    # [http] ping-auth-enabled = true
    #checkReturn sudo sed -ri '"/\[http\]/,/ping-auth-enabled\s*=.+/ s|\#*\s*ping-auth-enabled\s*=.+| ping-auth-enabled = true|"' "${config_file}"

    # ################# START OF HTTPS ##########################

    rowLimiter

    echo ""
    echo "The following steps are optional and will setup InfluxDB to use SSL for"
    echo "secure communications.  This is highly recommended!"
    echo ""
    if confirm "Do you want to enable HTTPS-communication for the influxdb? "; then
        # [http] https-enabled = true
        checkReturn sudo sed -ri '"/\[http\]/,/https-enabled\s*=.+/ s|\#*\s*https-enabled\s*=.+| https-enabled = true|"' "${config_file}"

        echo ""
        echo "The following step will assist with the creation of a self-signed"
        echo "certificate for InfluxDB.  If you intend to use a self-signed"
        echo "certificate that you have created already, or a certificate"
        echo "signed by a certificate authority that you have already obtained,"
        echo "answer no to skip this step."
        echo ""
        sslEnabled=true
        local httpsKeyPath="/etc/ssl/influxdb-selfsigned.key"
        local httpsCertPath="/etc/ssl/influxdb-selfsigned.crt"

        if generate_cert "$httpsKeyPath" "$httpsCertPath" httpsKeyPath httpsCertPath ; then
            unsafeSsl=true
        fi

        checkReturn sudo chown -R influxdb:influxdb "${httpsKeyPath}"
        checkReturn sudo chown -R influxdb:influxdb "${httpsCertPath}"

        # Edit config file again
        # [http] https-certificate
        checkReturn sudo sed -ri "\"/\[http\]/,/https-certificate\s*=.+/ s|\#*\s*https-certificate\s*=.+| https-certificate = \\\"$httpsCertPath\\\"|\"" "${config_file}"
        # [http] https-private-key
        checkReturn sudo sed -ri "\"/\[http\]/,/https-private-key\s*=.+/ s|\#*\s*https-private-key\s*=.+| https-private-key = \\\"$httpsKeyPath\\\"|\"" "${config_file}"


    fi

    ###################### END OF HTTPS ######################

    saveAuth "sslEnabled" "$sslEnabled"
    saveAuth "unsafeSsl" "$unsafeSsl"

    restartInflux

    # Checking connection
    verifyConnection $influxAdminName $influxAdminPassword

    loggerEcho "Finished InfluxDB Setup"
    sleep 2

}


# Start if not used as source
if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 loggerEcho "Illegal number of parameters for the influxSetup file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    influxSetup "${@}" # all arguments passed
fi