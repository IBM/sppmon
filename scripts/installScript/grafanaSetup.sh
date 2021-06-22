#!/bin/bash

grafanaSetup() {

    clear
    rowLimiter
    echo "Setup and installation of Grafana"
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

    echo "> Installing Grafana"
    checkReturn sudo yum install grafana

    echo "> Starting Grafana service"
    checkReturn sudo systemctl enable --now grafana-server

    echo "> Waiting 10 seconds for startup"
    sleep 10

    echo "> Verify Grafana service is active"
    checkReturn sudo systemctl is-active grafana-server

    echo "> Firewall configuration"
    checkReturn sudo firewall-cmd --add-port=3000/tcp --permanent
    checkReturn sudo firewall-cmd --reload

    echo "Finished Grafana Setup"

}

# Start if not used as source
if [ "${1}" != "--source-only" ]; then
    if (( $# != 1 )); then
        >&2 echo "Illegal number of parameters for the grafanaSetup file"
        abortInstallScript
    fi

    # prelude
    local mainPath="$1"
    source "$mainPath" "--source-only"

    grafanaSetup "${@}" # all arguments passed
fi