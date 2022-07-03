"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2022. All Rights Reserved.

 IBM Spectrum Protect Family Software

 Licensed materials provided under the terms of the IBM International Program
 License Agreement. See the Software licensing materials that came with the
 IBM Program for terms and conditions.

 U.S. Government Users Restricted Rights:  Use, duplication or disclosure
 restricted by GSA ADP Schedule Contract with IBM Corp.

 ----------------------------------------------------------------------------------------------
SPDX-License-Identifier: Apache-2.0

Description:
 The code in this branch ("SpMon") is part of an experimental project to
 refactor SppMon services for use in Spectrum Protect environments.

 It is based on the work of Niels Korchinsky, but it is not maintained or
 updated by him.

 This project is under development and is not currently considered ready
 for general use.

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author (SppMon):
 Daniel Wendler
 Niels Korschinsky

Author (SpMon):
 Daniel Wendler
 Niels Korschinsky
 Daniel Boros
 James Damgar
 Rob Elder
 Sean Jones
 Raymond Shum

Changelog (SppMon):
 02/06/2020 version 0.2   tested with SPP 10.1.5
 02/13/2020 version 0.25  improved debug logging & url encoding
 02/20/2020 version 0.31  added function to add / modify REST API url parameters
                          added jobLogDetails function to capture joblogs and store in Influx DB
 03/24/2020 version 0.4   migrated to Influxdb
 04/15/2020 version 0.6   reworked all files with exception handling
 04/16/2020 version 0.6.1 Hotfixing vmStats table
 04/16/2020 version 0.6.2 Split into multiple tables
 04/17/2020 version 0.6.3 New Catalog Statistics and Reduced JobLogs store to only Summary.
 04/18/2020 version 0.6.4 Parsing two new JobLogID's
 04/20/2020 version 0.6.4.1 Minor change to jobLogs
 04/22/2020 version 0.6.5 Improved SSH Commands and added new Stats via ssh
 04/23/2020 version 0.7   New module structure
 04/27/2020 version 0.7.1 Fixes to index errors breaking the execution.
 04/27/2020 version 0.7.2 Reintroduced all joblogs and added --minimumLogs
 04/30/2020 version 0.8   Reworked Exception system, introduces arg grouping
 05/07/2020 version 0.8.1 Part of the documentation and typing system, renamed program args
 05/14/2020 version 0.8.2 Cleanup and full typing
 05/18/2020 version 0.9   Documentation finished and some bugfixes.
 05/19/2020 version 0.9.1 Moved future import into main file.
 06/02/2020 version 0.9.2 Fixed df ssh command, introduced CLOUDPROXY and shortened ssh.py file.
 06/03/2020 version 0.9.3 Introduces --hourly, grafana changes and small bugfixes
 07/16/2020 version 0.9.4 Shift of the --joblogs to --daily as expected
 07/16/2020 version 0.9.5 Dynamically shift of the pagesize for any kind of get-API requests
 08/02/2020 version 0.10.0 Introducing Retention Policies and Continuous Queries, breaking old tables
 08/25/2020 version 0.10.1 Fixes to Transfer Data, Parse Unit and Top-SSH-Command parsing
 09/01/2020 version 0.10.2 Parse_Unit fixes (JobLogs) and adjustments on timeout
 11/10/2020 version 0.10.3 Introduced --loadedSystem argument and moved --minimumLogs to deprecated
 12/07/2020 version 0.10.4 Included SPP 10.1.6 additional job information features and some bugfixes
 12/29/2020 version 0.10.5 Replaced ssh 'top' command by 'ps' command to bugfix truncating data
 01/22/2021 version 0.10.6 Removed `--processStats`, integrated in `--ssh` plus Server/vSnap `df` root recording
 01/22/2021 version 0.10.7 Replaced `transfer_data` by `copy_database` with improvements
 01/28/2021 version 0.11   Copy_database now also creates the database with RP's if missing.
 01/29/2021 version 0.12   Implemented --test function, also disabling regular setup on certain args
 02/09/2021 version 0.12.1 Hotfix job statistic and --test now also checks for all commands individually
 02/07/2021 version 0.13   Implemented additional Office365 Joblog parsing
 02/10/2021 version 0.13.1 Fixes to partial send(influx), including influxdb version into stats
 03/29/2021 version 0.13.2 Fixes to typing, reducing error messages and tracking code for NaN bug
 07/06/2021 version 0.13.3 Hotfixing version endpoint for SPP 10.1.8.1
 07/09/2021 version 0.13.4 Hotfixing storage exception, changing top-level exception handling to reduce the need of further hotfixes
 08/06/2021 version 0.13.5 Fixing PS having unintuitive CPU-recording, reintroducing TOP to collect CPU information only
 07/14/2021 version 0.13.6 Optimizing CQ's, reducing batch size and typo fix within cpuram table
 07/27/2021 version 0.13.7 Streamlining --test arg and checking for GrafanaReader on InfluxSetup
 08/02/2021 version 0.13.8 Enhancement and replacement of the ArgumentParser and clearer config-file error messages
 08/10/2021 version 0.13.9 Rework of the JobLogs and fix of Log-Filter.
 08/18/2021 version 0.14   Added install script and fixed typo in config file, breaking old config files.
 08/22/2021 version 0.15   Added --fullLogs argument and reduced regular/loaded joblog query to SUMMARY-Only
 08/25/2021 version 0.15.1 Replaced SLA-Endpoint by so-far unknown endpoint, bringing it in line with other api-requests.
 08/27/2021 version 1.0.0  Release of SPPMon
 08/27/2021 version 1.0.1  Reverted parts of the SLA-Endpoint change
 08/31/2021 version 1.0.2  Changed VADP table definition to prevent drop of false duplicates
 09/09/2021 version 1.1.0  Increase logging for REST-API errors, add ssh-client skip option for cfg file.
 02/22/2021 version 1.1.1  Only ssh-calls the vSnap-api if it is available
 06/17/2022 version 1.2.0  Change of logfile location, bug and documentation fixes. Removes deprecated functions.

"""
from __future__ import annotations

import functools
import sys

from argparse import ArgumentError, ArgumentParser
from spmon import SpMon

# Version:
SPP_VERSION = "1.2.0  (2022/06/17)"
SP_VERSION = "0.0.0 (2022/06/20)"
# ----------------------------------------------------------------------------
# command line parameter parsing
# ----------------------------------------------------------------------------

# Determine which mode this is running in: SP vs. SPP
mode = sys.argv[1]  # SP vs. SPP

# Parse the remaining arguments
parser = ArgumentParser(
    # exit_on_error=False, TODO: Enable in python version 3.9
    description=
    """Monitoring and long-term reporting for IBM Spectrum Protect and IBM Spectrum Protect Plus.
 Provides a data bridge from SP/SPP to InfluxDB and provides visualization dashboards via Grafana.

 This program provides functions to query IBM Spectrum Protect and IBM Spectrum Protect Plus Servers,
 VSNAP, VADP and other servers via REST API and ssh. This data is stored into a InfluxDB database.""",
    epilog="For feature-requests or bug-reports please visit https://github.com/IBM/spectrum-protect-sppmon")

# Applicable to both SP and SPP
parser.add_argument("--cfg", required=True, dest="configFile", help="REQUIRED: specify the JSON configuration file")
parser.add_argument("--verbose", dest="verbose", action="store_true", help="print to stdout")
parser.add_argument("--debug", dest="debug", action="store_true", help="save debug messages")
parser.add_argument("--test", dest="test", action="store_true", help="tests connection to all components")
parser.add_argument("--ssh", dest="ssh", action="store_true", help="execute monitoring commands via ssh")
parser.add_argument("--cpu", dest="cpu", action="store_true", help="capture SPP server CPU and RAM utilization")
parser.add_argument("--storages", dest="storages", action="store_true", help="store storages (vsnap) statistics")
parser.add_argument("--copy_database", dest="copy_database",
                    help="Copy all data from .cfg database into a new database, specified by `copy_database=newName`. Delete old database with caution.")
parser.add_argument("--constant", dest="constant", action="store_true",
                    help="execute recommended constant functions: (ssh, cpu, sppCatalog)")
parser.add_argument("--hourly", dest="hourly", action="store_true",
                    help="execute recommended hourly functions: (constant + jobs, vadps, storages)")
parser.add_argument("--daily", dest="daily", action="store_true",
                    help="execute recommended daily functions: (hourly +  joblogs, vms, slaStats, vmStats)")
parser.add_argument("--all", dest="all", action="store_true", help="execute all functions: (daily + sites)")

# SPP-specific arguments
if mode == "SPP":
    parser.add_argument("--jobs", dest="jobs", action="store_true", help="store job history")
    parser.add_argument("--jobLogs", dest="jobLogs", action="store_true",
                        help="retrieve detailed information per job (job-sessions)")
    parser.add_argument("--loadedSystem", dest="loadedSystem", action="store_true",
                        help="Special settings for loaded systems, increasing API-request timings.")
    parser.add_argument("--fullLogs", dest="fullLogs", action="store_true",
                        help="Requesting any kind of Joblogs instead of the default SUMMARY-Logs.")
    parser.add_argument("--vms", dest="vms", action="store_true", help="store vm statistics (hyperV, vmWare)")
    parser.add_argument("--vmStats", dest="vmStats", action="store_true",
                        help="calculate vm statistic from catalog data")
    parser.add_argument("--slaStats", dest="slaStats", action="store_true",
                        help="calculate vm's and applications per SLA")
    parser.add_argument("--vadps", dest="vadps", action="store_true", help="store VADPs statistics")
    parser.add_argument("--sites", dest="sites", action="store_true", help="store site settings")
    parser.add_argument("--sppcatalog", dest="sppcatalog", action="store_true",
                        help="capture Spp-Catalog Storage usage")

# SP-specific arguments
if mode == "SP":
    parser.add_argument("-v", '--version', action='version',
                        version="Spectrum Protect Monitoring (SPMon) version " + SP_VERSION)
    parser.add_argument("--queries", required=True, dest="queryFile", help="REQUIRED: SP summary record queries file")
else:
    parser.add_argument("-v", '--version', action='version',
                        version="Spectrum Protect Plus Monitoring (SPPMon) version " + SPP_VERSION)

print = functools.partial(print, flush=True)

# Define error codes
ERROR_CODE_START_ERROR: int = 3
ERROR_CODE_CMD_ARGS: int = 2
ERROR_CODE: int = 1
SUCCESS_CODE: int = 0

# Parse arguments
try:
    ARGS = parser.parse_args(sys.argv[2:])
except SystemExit as exit_code:
    if (exit_code.code != SUCCESS_CODE):
        print("> Error when reading arguments.", file=sys.stderr)
        print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
        print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(exit_code)
except ArgumentError as error:
    print(error.message)
    print("> Error when reading arguments.", file=sys.stderr)
    print("> Please make sure to specify a config file and check the spelling of your arguments.", file=sys.stderr)
    print("> Use --help to display all argument options and requirements", file=sys.stderr)
    exit(ERROR_CODE_CMD_ARGS)

if __name__ == "__main__":
    # Run in one of the supported modes
    if mode == "SPP":
        # SppMon(ARGS).main()
        print("> SPP has been disconnected while developing SPMon", file=sys.stderr)
    elif mode == "SP":
        SpMon(ARGS).main()
