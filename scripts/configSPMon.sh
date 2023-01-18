# TODO:
#
# Prompt the user for the followiing pieces of information:
# **Docker Environment**
#  * Volume -- Directory for shared persistent container storage
#
# **IBM Spectrum Protect Server**
#  * Username -- Server administrator name (should use: "SPMON_ADMIN")
#  * Password -- Server administrator password
#  * Server Address (HLA) -- Hostname or IP of the server
#  * Server Port (LLA) -- TCP/IP port for admin communication
#
# **InfluxDB (v2) Database**
#  * Bucket -- Bucket (named location) to store measurement data
#  * Organization -- Organization (user workspace) to store measurement data
#  * Token -- API token to use for communication
#  * Server Address -- Hostname or IP of the server
#  * Server Port -- TCP/IP port of the server

# This will then generate a ~/.spmonenv file with the following content:
###################################
# User running container infrastructure
# USER=spmon

# Directory path for Docker persistent volumes
# DOCKERVOL=/var/lib/docker/volumes

# InfluxDB related variables
# SPMON_INFLUXDB_USERNAME
# SPMON_INFLUXDB_PASSWORD
# SPMON_INFLUXDB_ORG
# SPMON_INFLUXDB_BUCKET
# SPMON_INFLUXDB_TOKEN
###################################

# And also a ${DOCKERVOL}/spmon/spconnections.json configuration file
# with filled in content