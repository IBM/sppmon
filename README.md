# Welcome to SPPMon

SPPMon is an open-source project initiated by the IBM Spectrum Protect Plus development team. The goal of the project is to provide a monitoring system for IBM Spectrum Protect Plus that offers multiple options for a day to day monitoring of a data protection environment. The major focus is the workflows of IBM Spectrum Protect Plus itself, such as job volume and duration or catalog protection, and the consumption of system resources like memory and CPU of all systems related to the data protection environment.
The built-in functionality to monitor the SPP server, vSnap, VADP, and Microsoft 365 proxy systems and can be expanded easily for other systems like application servers.

THE SPPMon project consists of three major components. The SPPMon core engine (the open-source) is used to query the system data and ingest it into a database. An Influx time-series database is used to store and prepare the collected data for the graphical interface. Grafana is utilized as the graphical interface for the project. The below picture describes the components and the general workflow on a high level.

![SPP / SPPmon Overview](https://github.com/IBM/sppmon/blob/master/pictures/sppmon_architecture.PNG)

## Structure of the Documentation

* The documentation is split into two sections: The user guide and the developer guide. The user guide includes all information needed to set up and configure the SPPMon system and data protection environment. The developer guide includes all information needed to improve the SPPMon system with more functionality, contribute to the open-source projects.

* SPPMon can be setup from [scratch on a Linux operating system](https://github.com/IBM/spectrum-protect-sppmon/wiki/System-requirements) or can be deployed in a [containerized environment](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPmon-as-a-Container). See the [install options overview](https://github.com/IBM/spectrum-protect-sppmon/wiki/Install-overview) for more details and a distinction between each option.

* Please refer to the [FAQ](https://github.com/IBM/spectrum-protect-sppmon/wiki/Frequently-asked-Questions) for frequently asked questions.
* An overview of all required and created users can be found [here](https://github.com/IBM/spectrum-protect-sppmon/wiki/Overview-of-users).
* The complete changelog can be found [here](https://github.com/IBM/spectrum-protect-sppmon/blob/master/CHANGELOG.md)


## Find the documentation in the project [Wiki](https://github.com/IBM/spectrum-protect-sppmon/wiki)
