** **UNDER CONSTRUCTION** **

# Welcome to SPMon

SPMon is an open-source project initiated by the IBM Spectrum Protect development team. The project's goal is to provide an observability and monitoring system for IBM Spectrum Protect that offers multiple options for a day to day monitoring of a data protection environment. The primary focus of the project is to provide support for detailed monitoring of one or more IBM Spectrum Protect systems over time to enable visibility for key performance indicators, daily ingest trends, storage pool occupancy and capacity trends, success / failure counts, and other metrics. SPMon can be used in addition to the IBM Spectrum Protect Operations Center to provide a holistic view of an environment.

The initial set of pre-created monitoring statements and dashboard widgets can be easily expanded upon to suit your monitoring needs and preferences. Guidance is provided for how to structure queries and create widgets and dashboards to help achieve your monitoring requirements.

The SPMon project consists of three major components. The SPMon core engine (open-source, shared with SPPMon), is used to query the system data and ingest it into a database. An InfluxDB (v2) time-series database is used to store and prepare the collected data for a graphical interface. Grafana is utilized as the graphical interface for the project.

The below picture describes the components and the general workflow at a high level.

**TODO: Add image**

## Structure of the Documentation

* The documentation is split into two sections: The user guide and the query guide. The user guide includes all information needed to set up and configure the SPMon system for monitoring of a data protection environment. The query guide includes all information needed to create new IBM Spectrum Protect queries and map those to new Grafana widgets (with persistent storage in InfluxDB (v2)). A developer guide will be provided in the future for those wanting to help improve the SPMon system with more functionality and contribute to the open-source project.

# SPMon User Guide

## Installation Overview

A complete SPMon environment consists of the SPMon application and appropriately configured InfluxDB (v2) and Grafana instances. Currently, the SPMon application can be deployed within a Docker containerized environment. The InfluxDB (v2) and Grafana instances can be deployed in separate containers along with SPMon or they may be distinct, pre-existing instances that SPMon is configured to use.

The project includes a *Dockerfile* which can be used to build the SPMon container from a Python 3.10 base and automatically pull in dependent Python modules and SPMon code. Instructions are provided below for how to build this container.

The project also includes a *docker-compose.yml* file which can be used to orchestrate the creation and deployment of a complete SPMon environment within a Docker environment, including a SPMon container, an InfluxDB (v2) container, and a Grafana container. Instructions are provided below for following this approach.

## Overview of Users and User Requirements

The following users are required by or created by SPMon as a part of the configuration. Some users may be created as a part of the installation steps, while others need to be manually added. Any usernames displayed are default usernames. They might differ on your system.

### InfluxDB (v2)

If you are provisioning a new InfluxDB (v2) container, the following user is created automatically by the configuration script. If you are using an existing InfluxDB (v2) instance, the following user must be created manually.

|Username|Used for|Permissions|Install Script?|Notes|
|--------|--------|-----------|---------------|-----|
|GrafanaReader|Grafana Display|Read|Yes|Notes|

### Grafana

The following "admin" Grafana user is created after the first start of the application. Its password must be changed on first login. This applies both when provisioning a new Grafana container and when using an existing instance.

|Username|Used for|Role|Required?|Notes|
|--------|--------|-----------|---------------|-----|
|admin|Administration, Dashboard imports|Admin|Yes|Default Password: "admin" - **change on first login**|
|viewer|View Dashboards as guest|Viewer|No|Optional role for view-only access|

### IBM Spectrum Protect Server

The following administrative user must be created manually within each monitored IBM Spectrum Protect server prior to deploying and using SPMon. The password must be the same for each monitored server.

|Admin|Used for|Authority|Required?|Notes|
|--------|--------|-----------|---------------|-----|
|SPMON_ADMIN|Execution of IBM Spectrum Protect administrative SQL|None required|Yes|Register this admin with a secure password. Used for read-only queries for data gathering|

## System Requirements

Testing of the containerized SPMon solution was performed using a CentOS 7.9 host system. Other Linux operating systems have not been tested but should work similarly with similar steps.

### 1. Install CentOS 7.9 on a VM or physical host

- Create a virtual machine or provision a physical host with a minimum of 4 vCPU, 8 GB RAM, 1 x 50 GB disk for the operating system and 1 x 100 GB disk for persistent data (if deploying InfluxDB (v2) and Grafana containers)
- Install the operating system on the 50 GB disk
- Setup the network configuration in the installer so that the system can be accessed via SSH
- Set the root password and create a non-root user **spmon** with a secure password
```
# As root
useradd spmon
passwd spmon
```

### 2. Update the operating system and required software

- Login as the **spmon** operating system user and then change to **root**
```
su - root
```
- Give the user root permissions. Create a `/etc/sudoers.d/spmon` containing the following one line:
```
echo "spmon ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/spmon
exit             # back to spmon
```
- Uninstall any "old" versions of Docker (following steps [here](https://docs.docker.com/engine/install/centos/))
```
sudo yum remove docker \
                docker-client \
                docker-client-latest \
                docker-common \
                docker-latest \
                docker-latest-logrotate \
                docker-logrotate \
                docker-engine
```
- Install the latest version of Docker Engine and configure it to start on boot
```
sudo yum update -y
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
```

### 3. As the spmon user, continue creating a file system for persistent container storage

**Note** that the following assumes that **/dev/sdb** is the 100 GB "data" disk to be used for container storage. Replace this with the applicable disk name for your environment. The `lsblk` command can be used to help identify disks on Linux.

**The use of persistent container storage is only required when deploying InfluxDB (v2) and Grafana containers alongside the SPMon container in the same containerized environment.**

1. `sudo pvcreate /dev/sdb`
2. `sudo vgcreate spmonvg /dev/sdb`
3. `sudo lvcreate -a y -n spmon -l 100%FREE spmonvg`
4. `sudo mkfs -t xfs /dev/mapper/spmonvg-spmon`
5. `sudo mkdir /var/lib/docker/volumes`
6. `mount /dev/mapper/spmonvg-spmon /var/lib/docker/volumes`
7. `echo "/dev/mapper/spmonvg-spmon /var/lib/docker/volumes   xfs     defaults  0 0" | sudo tee -a /etc/fstab`

Create sub-directories for each component. These sub-directories will be used to interact with the application components before, during, and after deployment.

1. `sudo mkdir /var/lib/docker/volumes/spmon`
2. `sudo mkdir /var/lib/docker/volumes/influx`
3. `sudo mkdir /var/lib/docker/volumes/influx/data`
4. `sudo mkdir /var/lib/docker/volumes/influx/config`
5. `sudo mkdir /var/lib/docker/volumes/influx/scripts`
6. `sudo mkdir /var/lib/docker/volumes/grafana`

### 4. Finish the docker setup and allow the spmon user to manage containers

1. `sudo groupadd docker`
2. `sudo usermod -aG docker spmon`
3. `su - spmon # Log back in so the new group assignments take effect.`
4. `sudo systemctl start docker`
5. `docker run hello-world           # this should work as non-root`
6. `sudo yum install git -y          # For downloading project code`
7. `sudo reboot`

### 5. Open firewall ports 8086 and 3000 for the InfluxDB (v2) and Grafana containers

After the system reboots, proceed with the following:

1. `sudo yum install -y firewalld`
2. `sudo systemctl start firewalld`
3. `sudo systemctl enable firewalld`
4. `sudo firewall-cmd --add-port=8086/tcp --permanent`
5. `sudo firewall-cmd --add-port=3000/tcp --permanent`
6. `sudo firewall-cmd --reload`
7. `sudo systemctl restart docker`


## Prerequisite Steps

The following prerequisite steps are needed regardless of whether automated Docker and/or Docker Compose steps are pursued or existing InfluxDB (v2) and Grafana instances are used.

### IBM Spectrum Protect Server

#### Administrative user

In order for SPMon to be able to collect data, the IBM Spectrum Protect server being monitored needs to have a read-only, local (non-LDAP/AD) administrator user defined. It is recommended that this user be given the name `SPMON_ADMIN` to uniquely identify it. This administrator needs to be defined with the same password on each IBM Spectrum Protect server being monitored by a given instance of SPMon. It is not necessary to grant this user any elevated "authority".
```
# From the dsmadmc command line interface or server console
register admin SPMON_ADMIN SOMESECUREPASSWORD
```

#### Operations Center

The IBM Spectrum Protect Operations Center component needs to be installed and configured for the IBM Spectrum Protect server being monitored. In addition, the REST API endpoint within the Operations Center needs to be enabled. This can be done with the following steps:
- Navigate to the Operations Center home page for the IBM Spectrum Protect server to monitor
- Mouse over the "gear icon" in the top right of the top horizontal banner and click on "Settings"
- Under "Integration Services", check the "Enable administrative REST API" box
- Click the "Save" button

### Configuration Script

The provided configuration script `<location of project>/spectrum-protect-sppmon/scripts/configSPMon.sh` should be run prior to building and/or starting the SPMon container and before provisioning InfluxDB (v2)/Grafana containers or before interacting with existing instances.

A unique API token is needed by SPMon to authenticate and store data to InfluxDB (v2). For the initial setup, generate a unique token ahead of time to use with InfluxDB (v2) and SPMon. Run the following command and record the UUID it returns:
- `uuidgen`

For example:
```
[spmon@ip-172-31-4-221 ~]$ uuidgen
9cfdc251-13a2-408b-8478-8285c9554e9f
```

Next, run the `configSPMon.sh` configuration script and fill in the following data for each category:
* **IBM Spectrum Protect Server**
  * Username -- Server administrator name (should use: "SPMON_ADMIN")
  * Password -- Server administrator password
  * Server Address (HLA) -- Hostname or IP of the server
  * Server Port (LLA) -- TCP/IP port for admin communication
* **InfluxDB (v2) Database**
  * Bucket -- Bucket (named location) to store measurement data
  * Organization -- Organization (user workspace) to store measurement data
  * Token -- API token to use for communication
  * Server Address -- Hostname or IP of the server
  * Server Port -- TCP/IP port of the server

The content for the "IBM Spectrum Protect Server" should match what is configured for a running IBM Spectrum Protect server, including a read-only administrator user.

The content for the "InfluxDB (v2) Database" should match what is configured for an existing/running InfluxDB (v2) instance or, if the instance will be provisioned using Docker or Docker Compose, it should be the intended configuration. Use the unique API token generated earlier with the `uuidgen` command as the value for "Token".

Running the configuration script will result in data in the `/var/lib/docker/volumes/spmon/spconnections.conf` SPMon configuration file being initially populated or changed. It will also modify values in a `.env` Docker environment variable file for use during container provisioning.

### SPMon

#### IBM Spectrum Protect server and InfluxDB (v2) communication

SPMon needs to be configured to understand how to communicate with the IBM Spectrum Protect server using the administrative API in order to issue data queries and the InfluxDB (v2) instance in order to store data for its data model. This behavior is dictated by the configuration file named `/var/lib/docker/volumes/spmon/spconnections.conf` in the "spmon" persistent volume location.

Running the provided `configSPMon.sh` configuration script will take care of populating the content of this file based on user prompts and must be run first prior to building/starting the SPMon container. The configuration file contains the following content:
```
{
    "spServer":{
              "username" :    "USER_NAME",
              "password" :    "USER_PASSWORD",
              "srv_address" : "SERVER_ADDRESS",
              "srv_port" :    "SERVER_ADMIN_PORT"
    },
    "spInfluxDB":{
              "bucket" :      "BUCKET_NAME",
              "org" :         "ORG_NAME",
              "token" :       "API_TOKEN",
              "srv_address" : "INFLUX_ADDRESS",
              "srv_port" :    "INFLUX_PORT"
    }
}
```
**NOTE**: The provided configuration script should be used to initially populate or change the values of this JSON file. While the content can be changed manually, to avoid any potential parsing errors, use the configuration script to alter configuration file content. This will also ensure that the Docker `.env` file used for container provisioning will be kept in sync.

For the `spServer` section, `username` and `password` should match the read-only, local administrative user created for the IBM Spectrum Protect server. The server's high-level address (HLA -- hostname or IP) should be provided for `srv_address` and the administrative port (TCP) being listened on for `srv_port`.

For the `spInfluxDB` section, `bucket` should match the InfluxDB (v2) bucket name created to house the monitored data for SPMon with `org` being the owning organization. The `srv_address` and `srv_port` fields should match the hostname/IP and (TCP) port of the listening InfluxDB (v2) instance, respectively. The `token` field should contain the API access token generated that provides access to the bucket and organization.

#### IBM Spectrum Protect queries

SPMon issues a series of administrative API queries against the IBM Spectrum Protect server to gather data during each collection. These queries are defined in a `spqueries.json` file. A default set of queries is provided within the project at the following path:

`spectrum-protect-sppmon/python/spConnection/spqueries.json`

To get started, copy this file to the persistent volume location for SPMon:

- `sudo cp <location of project>/spectrum-protect-sppmon/python/spConnection/spqueries.json /var/lib/docker/volumes/spmon/spqueries.json`

See the **SPMon Query Guide** for information on how to create your own queries.

### Grafana

The persistent volume location used for Grafana can be pre-populated with a Dashboard and Widgets which match the default set of queries collected with SPMon.

**TODO: Finish**

## Docker Compose Container Setup

The following instructions can be used to deploy a SPMon container, an InfluxDB (v2) container, and a Grafana container within a Docker environment using the provided *docker-compose.yml* Docker Compose file.

First, clone the Github project
```
git clone https://github.com/IBM/spectrum-protect-sppmon.git
```

Next, run the provided `configSPMon.sh` configuration script to initially populate the needed configuration and environment files
```
cd <location of project>/spectrum-protect-sppmon/scripts
./configSPMon.sh
```

Navigate to the directory with the *docker-compose.yml* file for SPMon and use Docker Compose to bring the containers up in the background
```
cd <location of project>/spectrum-protect-sppmon/python/docker/spmon
docker-compose up -d
```

The Docker Compose orchestration should provision an InfluxDB (v2) container first, using the provided configuration parameters generated by the configuration script to create an organization, bucket, API token, and a read-only "GrafanaReader" user. Then SPMon and Grafana containers will be provisioned with configurations that point to this instance. All three containers will use the persistent storage volume locations created earlier and be connected using a Docker network.

Verify that the images were created:
```
docker image ls
```

The output should appear similar to the following:
```
docker image ls
REPOSITORY              TAG                 IMAGE ID            CREATED             SIZE
spmon                   latest              f40cb1362714        24 seconds ago      912 MB
```

Verify that the containers are running:
```
docker ps
```

The output should appear similar to the following:
```
TODO: Provide example output
```

## Manual Setup

The following instructions describe how to setup the SPMon and, optionally, an InfluxDB (v2) and Grafana container manually. Use these instructions if you want to deploy these containers separately or if you already have separate, distinct InfluxDB (v2) and Grafana instances. To deploy all containers automatically into a Docker environment, follow the **"Docker Compose Container Setup"** instructions instead.

### Docker Network

If InfluxDB (v2) and Grafana containers are being provisioned, create a Docker "bridge" style network so that they can communicate with each other and the SPMon container. If pre-existing instances already exist, then changes may be needed to networking configurations so that instances can communicate.
```
docker network create -d bridge influx-network
```

### Configuration Script

As with the **"Docker Compose Container Setup"** instructions, the provided `configSPMon.sh` configuration script should be run first to initially populate the needed configuration and environment files. First, clone the Github project and run this configuration script to record this data
```
git clone https://github.com/IBM/spectrum-protect-sppmon.git
cd <location of project>/spectrum-protect-sppmon/scripts
./configSPMon.sh
```

### Setup the InfluxDB (v2) Container

Setup a new InfluxDB (v2) container using the persistent storage created earlier.

First, pull down the appropriate InfluxDB (v2) image:
```
docker pull influxdb:2.0
```

Run the container briefly to generate a configuration file that we can edit. Store this configuration file to the persistent volume directory path. It can be customized later, as necessary, for your deployment:
```
docker run --rm influxdb:2.0 influxd print-config > config.yml
sudo cp config.yml /var/lib/docker/volumes/influx/config/config.yml
```

Source the SPMon environment file so that neede variables are used from the configuration script.
```
. <location of project>/spectrum-protect-sppmon/python/docker/spmon/.env
```

Run the influx DB container in detached mode, passing the needed persistent data, configuration, and scripting paths as volume mount points to the container. Each of the configuration parameters are pulled from an `.env` environment file that was generated/modified by the `configSPMon.sh` configuration script run earlier.
```
docker run -d -p 8086:8086 \
    -v ${DOCKERVOL}/influx/data:/var/lib/influxdb2 \
    -v ${DOCKERVOL}/influx/config:/etc/influxdb2 \
    -v ${DOCKERVOL}/influx/scripts:/docker-entrypoint-initdb.d \
    -e DOCKER_INFLUXDB_INIT_MODE=setup \
    -e DOCKER_INFLUXDB_INIT_USERNAME=${SPMON_INFLUXDB_USERNAME} \
    -e DOCKER_INFLUXDB_INIT_PASSWORD=${SPMON_INFLUXDB_PASSWORD} \
    -e DOCKER_INFLUXDB_INIT_ORG=${SPMON_INFLUXDB_ORG} \
    -e DOCKER_INFLUXDB_INIT_BUCKET=${SPMON_INFLUXDB_BUCKET} \
    -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=${SPMON_INFLUXDB_TOKEN}
    --net=influx-network
    --name=influxdb influxdb:2.0
```

For this initial run, the container is created in "setup" mode (`DOCKER_INFLUXDB_INIT_MODE`) to generate the configuration within the application.

The InfluxDB container will take a few moments to initialize. To verify InfluxDB is ready to connect to, connect to the container with a bash shell and attempt to run the `influx` command:
```
docker exec -it influxdb /bin/bash
influx bucket list
exit
```

For example:
```
[spmon@ip-172-31-4-221 ~]$ docker exec -it influxdb /bin/bash
root@7696740a9a0b:/# influx bucket list
ID                      Name            Retention       Shard group duration    Organization ID
ed6b2fbb939edda1        _monitoring     168h0m0s        24h0m0s                 8d107c1f57cb2a62
26aa9b11329363f3        _tasks          72h0m0s         24h0m0s                 8d107c1f57cb2a62
0a063b7f1be664ce        spmon           infinite        168h0m0s                8d107c1f57cb2a62

root@7696740a9a0b:/# exit
```

### Setup the SPMon Container

After cloning the Github project and running the `configSPMon.sh` configuration script (see earlier steps in this section), a `/var/lib/docker/volumes/spmon/spconnections.conf` configuration file will be created. It can later be modified, if needed, by running the configuration script again. After this is done for the first time, use the provided *Dockerfile* to build the SPMon container
```
# Change into the top-level directory of the project
cd <location of project>/spectrum-protect-sppmon
docker build . -t spmon -f python/docker/spmon/Dockerfile
```

Verify that the image was created
```
docker image ls
```

The output should appear similar to the following:
```
docker image ls
REPOSITORY              TAG                 IMAGE ID            CREATED             SIZE
spmon                   latest              feac9237dfaa        5 seconds ago       1.28 GB
```

Source the SPMon environment file so that neede variables are used from the configuration script.
```
. <location of project>/spectrum-protect-sppmon/python/docker/spmon/.env
```

Run the SPMon container in detached mode, passing the needed persistent volume sub-directory with the configuration and queries files contained inside. If InfluxDB (v2) and Grafana containers are being provisioned as well, add the `--net` parameter to include the Docker network.
```
docker run -d -t -v ${DOCKERVOL}/spmon:/spmon --net=influx-network --name=spmon spmon
```

### Setup the Grafana Container

The Grafana container is set up using a persistent volume for Grafana metadata.

First, pull the appropriate container image:
```
docker pull grafana/grafana-oss:8.2.0
```

Source the SPMon environment file so that neede variables are used from the configuration script.
```
. <location of project>/spectrum-protect-sppmon/python/docker/spmon/.env
```

Run the Grafana container in detached mode, passing the needed persistent volume sub-directory. If an InfluxDB (v2) container was provisioned, include the `--net` parameter to include the Docker network.
```
docker run -d -t -v ${DOCKERVOL}/grafana:/var/lib/grafana --net=influx-network --name=grafana grafana/grafana-oss:8.2.0
```

The following command can be used to verify that Grafana can be connected to:
```
docker exec -ti grafana /bin/bash
```

### Starting and Stopping Containers

Each of the provisioned containers can be stopped and started using the following commands:
```
# Stop a container
docker stop CONTAINERNAME

# Start a container
docker start CONTAINERNAME
```

where `CONTAINERNAME` can be one of: `spmon`, `influxdb`, or `grafana`

This applies both in the case of this manual container deployment as well as with Docker Compose.

## SPMon Query Guide

SPMon collects data from IBM Spectrum Protect servers via the administrative API using a configured administrative user. The `spqueries.json` file defines the set of queries that are run during each interval to collect data that is then stored within the InfluxDB (v2) instance.

The SPMon project comes included with a set of IBM Spectrum Protect administrative API queries pre-created for use with the provided matching Grafana dashboard and widget set to help get started and provide for a "default" configuration. The following guidance can be used to add / remove / modify queries as needed to suit your environment.

### Query Language

SPMon administrative API queries are defined within a `spqueries.json` file with a particular JSON structure:
```
{
    "QUERY_LABEL" : {
        "query" : "QUERY_SQL",
        "measurement" : "QUERY_INFLUXDB_MEASUREMENT",
        "datetime" : "COLUMN_FOR_DATETIME",
        "tags" : [
            "TAG_COLUMN_01",
            "TAG_COLUMN_02",
            ...
            "TAG_COLUMN_N",
        ],
        "fields" : [
            "FIELD_COLUMN_01",
            "FIELD_COLUMN_02",
            ...
            "FIELD_COLUMN_N",
        ],
        "target_servers": [ "OPTIONAL_TARGET_SERVER_01", ... ]
    },

    ... other queries ...
}
```

The `QUERY_LABEL` uniquely identifies a "label" for this query (within SPMon). Each defined query must have a unique label. The `query` field specifies the administrative SQL to run on the IBM Spectrum Protect server. The `measurement` field specifies the "measurement" name within InfluxDB (v2) where the data is stored. The `datetime` field identifies the column name from the query output to use as the InfluxDB "date/time" field for time-series purposes.

The `tags` array field specifies 1 or more column names from the query output to use as InfluxDB "tags" for the "measurement". InfluxDB "tags" are indexed by the database and should be highly variable (have high cardinality), such as hashes, string names, UUIDs, etc. At least 1 column name must be identified.

The `fields` array field specifies 1 or more column names from the query output to use as InfluxDB "fields" for the "measurement". InfluxDB "fields" are not indexed by the database and generally represent data you want to chart or graph with a function, such as data quantities or counts. At least 1 column name must be identified.

There can be no overlap between "tags" and "fields" (i.e. a column may only be included in one but not both arrays).

Finally, the `target_servers` field is an optional array of IBM Spectrum Protect server names to run this query against. If no server is chosen, then this query is run against all servers in the configuration for this instance of SPMon. In this way you can selectively run certain queries against certain servers only.

The JSON body of `spqueries.json` can include 1 or more query objects (each with unique labels).

As a concrete example, the provided `DAILY_INGEST` query is defined as follows:
```
    "DAILY_INGEST" : {
        "query" : "SELECT TIMESTAMP(DATE(s.START_TIME)) AS DATE, (CAST(FLOAT(SUM(s.bytes_protected))/1024/1024 AS DECIMAL(12,2))) AS PROTECTED_MB, (CAST(FLOAT(SUM(s.bytes_written))/1024/1024 AS DECIMAL(12,2))) AS WRITTEN_MB, (CAST(FLOAT(SUM(s.dedup_savings))/1024/1024 AS DECIMAL(12,2))) AS DEDUPSAVINGS_MB, (CAST(FLOAT(SUM(s.comp_savings))/1024/1024 AS DECIMAL(12,2))) AS COMPSAVINGS_MB, (CAST(FLOAT(SUM(s.dedup_savings))/FLOAT(SUM(s.bytes_protected))*100 AS DECIMAL(5,2))) AS DEDUP_PCT, (CAST(FLOAT(SUM(s.bytes_protected) - SUM(s.bytes_written))/FLOAT(SUM(s.bytes_protected))*100 AS DECIMAL(5,2))) AS SAVINGS_PCT, SUM(BIGINT(timestampdiff(2, char(s.end_time - s.start_time)))) as TOTAL_TIME_SEC, CAST((FLOAT(SUM(s.bytes_protected))/1024/1024)/(SUM(BIGINT(timestampdiff(2, char(s.end_time - s.start_time))))) AS DECIMAL(12,2)) as AVG_FE_MBPS, CAST((FLOAT(SUM(s.bytes_written))/1024/1024)/(SUM(BIGINT(timestampdiff(2, char(s.end_time - s.start_time))))) AS DECIMAL(12,2)) as AVG_BE_MBPS from summary s WHERE activity in ('BACKUP','ARCHIVE', 'OBJECT CLIENT BACKUP') GROUP BY DATE(S.START_TIME)",
        "measurement" : "DAILY_INGEST",
        "datetime" : "DATE",
        "tags" : [
            "HOST"
        ],
        "fields" : [
            "PROTECTED_MB",
            "WRITTEN_MB",
            "DEDUPSAVINGS_MB",
            "COMPSAVINGS_MB",
            "DEDUP_PCT",
            "SAVINGS_PCT",
            "TOTAL_TIME_SEC",
            "AVG_FE_MBPS",
            "AVG_BE_MBPS"
        ],
        "target_servers": []
    }
```

Both the (unique) SPMon label for the query and the InfluxDB measurement are given the value `DAILY_INGEST`. From the query SQL output, the `DATE` column is identified as a date/time column to use for time-series tracking within InfluxDB. Just the `HOST` column name is chosen as a tag for the query while each of the other columns are specified as fields. No `target_servers` are specified, so this query will run against all servers in the configuration.

Note that the `HOST` column is not included within the query itself. SPMon will automatically insert this as a column for the measurement for all queries.

### Data Collection and Storage Flow

First, an appropriate `crontab` entry within the SPMon container must be chosen to specify a collection time and frequency for the application.

Each time the `spmon.py` program is executed, it will execute the set of queries defined in the queries JSON file against all or a subset of the IBM Spectrum Protect servers in its configuration. SPMon will first authenticate with the configured InfluxDB instance. Then, for each query and each server, SPMon will authenticate with the configured IBM Spectrum Protect administrative user to that server and execute the administrative SQL with a REST call to the server. The response content for the query is then batched and inserted into the InfluxDB database bucket as a measurement with the appropriate columns marked as the date/time, tags, and fields.

### Data Visualization

An instance of Grafana is configured to communicate with the InfluxDB (v2) database as a data source which is used to populate a Dashboard and a set of Widgets within its graphical interface.

Grafana Widgets are visualizations that support different use cases and graph, chart, or present data from a source in different ways. In the case of SPMon, the "data source" is an InfluxDB (v2) instance and each Widget derives its data from one or more measurements within the InfluxDB database.

As a best practice, the set of queries defined for SPMon and the associated IBM Spectrum Protect servers they are run against should match and be kept in sync with an instance of a Grafana Dashboard and its Widgets. As queries are then added or removed from the query set they can then be added or removed from Grafana dashboard configuration.

### Grafana Configuration Examples

TODO: Describe Grafana Dashboard/Widget creation/editing within the GUI as well as with JSON.