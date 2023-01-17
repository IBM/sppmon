# Welcome to SPPMon and SPPCheck

[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/5826/badge)](https://bestpractices.coreinfrastructure.org/projects/5826)

SPPMon is an open-source project initiated by the IBM Spectrum Protect Plus development team. The project's goal is to provide a monitoring system for IBM Spectrum Protect Plus that offers multiple options for a day to day monitoring of a data protection environment. The primary focus is the workflows of IBM Spectrum Protect Plus itself, such as job volume and duration or catalog protection, and the consumption of system resources like memory and CPU of all systems related to the data protection environment.
The built-in functionality to monitor the SPP server, vSnap, VADP, and Microsoft 365 proxy systems and can be expanded easily for other systems like application servers.

This introduction focuses on monitoring for IBM Spectrum Protect Plus. For information on monitoring IBM Spectrum Protect, see the documentation for [SPMon](https://github.com/IBM/sppmon/blob/master/spmon/README.md), which is currently in technical preview.

The SPPMon project consists of three major components.
The SPPMon core engine (open-source) is used to query the system data and ingest it into a database.
An Influx time-series database is used to store and prepare the collected data for the graphical interface.
Grafana is utilized as the graphical interface for the project.

SPPMon got extended in September 2022 by SPPCheck in the context of the master thesis of one of the primary developers.
SPPCheck is a system requirement verification and prediction tool aiming to enhance the existing functionality by verifying whether a system was set up correctly according to IBM's recommendations and predicting its future development.
It focuses on the storage consumption of all associated vSnaps and the server's memory and catalog space and is open to future expansion of its capabilities.\
SPPCheck re-uses the existing components and integrates SPPMons core engine while offering a PDF report besides the typical Grafana Dashboard.

The below picture describes the components and the general workflow on a high level.

![SPP / SPPmon Overview](https://github.com/IBM/sppmon/blob/master/pictures/sppmon_architecture.PNG)

## Structure of the Documentation

* The documentation is split into two sections: The user guide and the developer guide. The user guide includes all information needed to set up and configure the SPPMon system and data protection environment. The developer guide includes all information needed to improve the SPPMon system with more functionality and contribute to the open-source projects.

* SPPMon can be set up from [scratch on a Linux operating [system](https://github.com/IBM/spectrum-protect-sppmon/wiki/System-requirements) or deployed in a [containerized environment](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPmon-as-a-Container). See the [install options overview](https://github.com/IBM/spectrum-protect-sppmon/wiki/Install-overview) for more details and a distinction between each option.

* SPPCheck is automatically deployed when using the latest version of SPPMon and can be executed using its distinct [command line arguments](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPCheck-Command-line-Overview)

* Find the full documentation in the project [Wiki](https://github.com/IBM/spectrum-protect-sppmon/wiki)

### Short Links

* [Releases](https://github.com/IBM/spectrum-protect-sppmon/releases)
* [Changelog](https://github.com/IBM/spectrum-protect-sppmon/blob/master/CHANGELOG.md)
* [FAQ](https://github.com/IBM/spectrum-protect-sppmon/wiki/Frequently-asked-Questions)
* [Overview of required and created users](https://github.com/IBM/spectrum-protect-sppmon/wiki/Overview-of-users)
* [Bug Report and Feature Requests](https://github.com/IBM/spectrum-protect-sppmon/issues)
* [Installation of SPPMon](https://github.com/IBM/spectrum-protect-sppmon/wiki/Install-overview)
* [SPPMon Command line arguments](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPMon-Command-line-Overview)
* [SPPCheck Command line arguments](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPCheck-Command-line-Overview)
* [SPPCheck Export PDF Report](https://github.com/IBM/spectrum-protect-sppmon/wiki/SPPCheck-Export-PDF-Report)
* [General Wiki](https://github.com/IBM/spectrum-protect-sppmon/wiki)
