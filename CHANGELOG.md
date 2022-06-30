# Change log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

### Added

* SPPCheck function and internal structure
  * Unfinished yet, though first results are available.
* Added Grafana Dashboard for SPPCheck

### Changed

* Upgraded CodeQL to v2

### Fixed

* Code scanning alert #2 and #3: Printing passwords into logger due to an faulty if-expression.

### Known Issues

## [1.2.0] - 2022-06-17

### Added

* Adds FullLogs and LoadedSystem information to the Grafana SPPMon Runtime Duration panel.
* Adds clarification that all timestamps are changed into second precision on insert.
* Adds support for batch insert to insert into a different retention policy
* Selection queries now also support an alternative retention policy to query from
* CreateRP-Method in the influxClient to allow creating non-lasting retention policies
* Adds pandas-stubs, openpyxl and pyxlsb to requirements file
* Prints total count of errors during the execution if there are any - instead of "script finished" output
* Added type spelling dictionary to the settings file
* Added linting settings to the settings file

### Changed

* Moved pid files-functions and other functions from SPPMon to helper functions.
  * Adjusted log messages to make their message generic if required.
  * Added arguments to replace self-access.
* Changed default log and pid-file locations from `home/sppmonLogs/FILE` to `spectrum-protect-sppmon/sppmonLogs/FILE`
* Added init declarations in the SPPMon `__init__` function to allow overview of all self-vars
* Changed SelectionQueries to only take a single table instead of an List of such, as it isn't required and complicates the code
* Predefined retention policies are no longer protected in the definitions module.
* Sending a select query now raises a error when it fails.
* Allows SelectionQueries from table to be another inner-selection query
  * Changed all calls of the constructor
  * Made sure to only allow inner queries when using the selection-keyword.
* Changed the severity of unknown type-annotation due to submodules not being typed from error to warning.
* Minor printing edits when generifing Dashboard
* Removes deprecated functions

### Fixed

* Fixed typo in exception_utils.py file, renaming it and all references on it.
* Lots of typos in the inline documentation
* SelectionQuery and associated methods: Introduces Optional annotation to fix linter error

### Known Issues

* In newer Grafana versions the dashboard import might corrupt the datasource name. A fix is unavailable yet, though the error is only visual.
* Some typos in the table definitions (commited / uncommited) cannot be fixed. This would not be backward-compatible and break the database.

## [1.1.1] - 2022-02-22

### Added

* Adds FullLogs and LoadedSystem information to the Grafana SPPMon Runtime Duration panel.
* Adds license information into each SPPMon code file.
* Specifies the encoding and reading permission when opening config files.

### Changed

* Avoids the wget-certificate check when installing and downloading the python tgz in the installer.
* Updates the requirements.txt to include sub-dependencies and updates to lates version.

### Fixed

* Fixes Issue #86 vSnap hanging up on start due to pool call by checking first if the `vsnap` command is available.

## [1.1.0] - 2021-09-09

### Added

* Added ConnectionUtils function `rest_response_error`. This function helps to extract the response-error message and includes all important pieces of information into a ValueError. This error should be raised afterward.
* Config-file option for ssh-clients `skip_cmds`. List of strings like `["mpstat", "ps"]` to skip commands on certain clients.

### Changed

* REST-API Login and Statuscheck for get_objects use the new function `rest_response_error` to raise their error.
* Adds the `skip_cmd` option to the default-config file.

### Fixed

* `--test`-execution: Fixes unusual KeyError when using a config file with more than one vSnap (or other) ssh-client.

## [1.0.2] - 2021-08-31

### Changed

* Marked the default group time when using the template CQ more clearly as `[*]`
* Grafana Dashboards:
  * 14-Day dashboard:
    * Changed VADP Proxy state table to support the VADPName grouping and status
      * Used Grafana organizing mechanics to leave query intact, hiding old data with status=null and vadpName="".
    * Changed VADP Proxy state per site to only use new data since 14-day is not too long
      * Changed to use field count and group over status instead of two separate queries
  * 90-Day dashboard:
    * Changed %-Enabled VADP dashboard to total count dashboard
    * Added for both VADP Proxy state and total count dashboard a new query, grouping over status and grouping on `count`. Old queries left intact for backward compatibility.
    * Hides series with null/none, adding average to legend.

* InfluxDB-Table `VADPs`:
  * Moved fields `state` and `vadpName` to tags
    * Renamed `state` to `status` to avoid issues due to double-named tags/fields
  * Changed CQ to group only over 'old' Tags
  * Changed aggregation from a split over enabled/disable to grouping over the state itself.
    This removes now-duplicate CQ definitions and all `WHERE`-grouping clauses.

### Fixed

* VADPs are no longer dropped due to being marked as duplicates by the InfluxDB.

## [1.0.1] - 2021-08-27

### Fixed

* Reverts SLA-Endpoint changes to stop counting removed VM's.
  * Pagesize code inside of the rest-request remains unchanged.

### Changed

* Changes SLA-Request count-field name and group name to a better matching candidate.
  * Removes the need to cut of prefix via regex
  * Removes associated regex code
* Changes REST-Client query time measurement from using a timer to using the result-internal timer.

## [1.0.0] - 2021-08-26

### Major changes summary

* SPPMon now features an install script!
  * Check out the [documentation](Installation\install-overview.md) how to easily and quickly install SPPMon
  * Don't forget to also check the new stand-alone scripts for creating config files and adding them to crontab!
* SPPMon now features a `--test` argument to test your config file before execution
* Reworked Grafana-Dashboard import process for easy monitoring and alerting of multiple servers
* Reduces the load on the SPP-Server to a minimum while also minimizing executing timings
* Fixed many bugs and increased stability

### Scripts

#### Added

* Install script for automatically installing SPPMon, Python, InfluxDB, and Grafana on a blank CentOs system.
  * Features a `--alwaysConfirm` argument for fewer confirmations
* Two stand-alone python scripts for automatically creating Config files and adding them to crontab
  > These scripts are used within the install script
* Created script `scripts/generifyDashboard.py`, which is now on the developer side. This makes sure a dashboard exported for external use is truly generic.
  > See Grafana changes for reasoning

### Python / Execution

#### Fixes

* `--test`:  Fixes Abort without summary on SSH-Errors
* Fixes empty error message without explanation if sites are an empty array
  * Adds debug output for easier remote tracing
* Corrupted config-file path no longer breaks SPPMon but prints an error message
* Partly fixes #40, but some IDs still remain missing due to other issues. The fix is described within the issue.
* JobLogs: The type-filter is no longer ignored on regular/loaded execution - requesting way fewer logs.
* Fixed an error when importing individual job log statistics, and `resourceType` was missing

#### Changes

* Replaces OptionParser with Argumentparser
* Improves `--test` argument: Outsources code, improve display and messages.
  * Enhanced Description and help message
  * Catches typos and missing arguments within the parser
* Removed disallowed terms from SPPMon code, using `allow_list` instead
* Reworks REST-API POST-Requests to be merged with GET-Requests
  * This includes the repeated tries if a request fails
  * Deprecates `url_set_param`, using functionality of `requests`-package instead
  * Using Python-Structs for URL-params instead of cryptic encoded params
* Reworks REST-API requests to use parameters more efficiently and consistently, making the code hopefully more readable.
  * Changes get_url_params to gain all parameters from URL-Encoding
  * Introduces set_url_params to set all params into URL encoding
  * Reads params of next page and allows injecting the whole dictionary of params
* Changes VMs per SLA-request to not query all VMs anymore, ~~but using pageSize to 1 and reading the `total` aggregated field and not repeat for other pages~~.
  * Changed to query so-far unknown endpoint, using count and group aggregate to query all data with a single API-request
  > This brings the SLA request in line with the other API requests.
* Reworked/Commented the job-log request and prepared a filter via individual JobLog-ID's
* Labeled python argument `-create_dashboard` and associated args as deprecated, to be removed in v1.1 (See Grafana-Changes)

### Influx

#### Changes

* Checks user (GrafanaReader) for permissions (READ) on current Database, warns if user not exists, and grants permissions if missing (Feature of V1.0)
* Reworks Influx-write Queries to repeat once if failed with fallback options
  * This includes enhanced error messages
  * Influx-Statistic send is reworked to be per table
* Split Influx-Stats: Query duration per item also groups via table and show average

#### Fixes

* Optimized Continuous-Queries setup
  * No longer all CQ is re-build on the start of **all** SPPMon executions, works now as intended
  * Changed definition to match InfluxDB return values (7d -> 1 w)
  * Changed quotations to match InfluxDB return values

#### Breaking Changes

* Typo fix in stddev, breaking old data.
  * These numbers are used nowhere, this will likely not break anything
  * Old Data is still available by the old name `sttdev`

### Grafana-Dashboards

#### Added

* Added Hyper-V Job Duration Panel similar to VMWare-Panel into 14 and 90/INF Dashboard
* Added versioning tags to each dashboard. Starting with v1.0
* Added unique data source tags to the 14-day dashboard
  * They have no use yet but might be used for directly referencing onto a certain dashboard from 90-days/multiple dashboards
* Added unique tags for identifying 14-day, 90-day, and multiple dashboards
* Created links from each dashboard to the others, grouped by type
  * The 14-days dashboards are created as dropdown

#### Changes

* Changed dashboard to be exported for `external use`:
  * You may change the data source on importing
  * Both UID and Dashboard names will be variable generated based on the data source chosen
  * Labeled Python argument `-create_dashboard` and associated args as deprecated, to be removed in v1.1
    > Note: Listed here only for completeness, see Python changes
  * Created a Python stand-alone script for generifying dashboard
    > Note: Listed here only for completeness, see script changes

## [0.5.4-beta] - 2021-08-11

### Fixes

* Bugfixes flat CPU statistics due to `ps` unexpected behavior.
  * `ps` no longer tracks CPU-Data, Track of RAM, and some other system information remains.
  * Re-introduced `top`-ssh command, but only collecting CPU-Statistics (see top-memory-truncation issue #14 & #32)
  > **The process-stats panel is accurate again after applying this fix.**

## [0.5.3-beta] - 2021-07-11

### Changes

* Changed top-level exception catching: Catches any exceptions instead of only our self-defined ValueErrors
  -> Prevents a complete abort of SPPMon if something unexpected happens.
  -> **This will reduce the need for urgent hotfixes like this one.**
* Changes empty result severity of REST-Requests from error to info
* Changed typings from critical components to support better linting

### Fixes

* Hotfixes SPPMon storages request to fail due `free` or `total` being none, crashing whole SPPMon execution

## [0.5.2-beta] - 2021-07-07

### Fixes

* Hotfixing version endpoint for SPP 10.1.8.1 breaking SPP REST-Endpoint
* Reduces Spam of empty error messages due to site requests being empty
* NaN error in CPU-Stats
* ssh `pools`-measurement now contains the correct timestamp
* allows `mpstat` to include a YYYY-system date format (21 vs. 2021)

### Changes

* Typing and printing changes when successfully finishing SPPMon.py
* General Dashboard changes:
  * Alert Notification bodies now contain meaningful messages
  * Changes Office365 type from none to percent

## [0.5.1-beta] - 2021-02-16

### Changed

* Removed the filter `messageId` from any query to the `vmReplicateStats` and `vmReplicateSummary` table:
  * `Additional Statistics`-Grafana panel in 14-Days and Multiple Server Dashboard
  * `daily total data protected`-Grafana panel in 14-Days Dashboard
    > Note: This does not affect the `vmBackupSummary`-Table (or queries against this one). This table does require a `messageId` as a filter.

## [0.5.0-beta] - 2021-02-12

### Major changes and features summary

* Includes now SPP 10.1.6 additional job information
  * Success ratio of VM's backup (Example: 54/70 VM's backup)
* Tracks root storage space of Server and vSnap clients
* Check if all components are configured correctly and working with `--test`
* Office365 Backup analysis (Items backup, data transferred)
* Allows copying a database with a new name in case of a naming error/backup.
* Adds and reorganized panels within Grafana
* Improvement of logging messages, code structure for late implementations, and a lot of bugfixes

### Fixed

* Replaced `top` command by `ps` command to bugfix the truncation of memory sizes of ssh-clients
* Reduces the `partial send` error message of the InfluxDB to a minimum.
* Influx Version is now displayable even when not using an admin user
* The default table now also has a retention policy, fixing the use of the default split if no table is declared
* Added a missing comma in `df_ssh` table declaration
* Fixes a bug with negative ssh-`FREE` ram values
* Now uses `realpath` for path-creation

### Changed

* Reminder: `--minimumLogs` deprecated, to be removed in V1.0. Use `--loadedSystem` instead
* `--processStats` deprecated, integrated into `--ssh`
* `transfer_data` removed. Use `copy_database` instead.
  * removed `--old_database`, integrated into `copy_database` CFG file.
* `--test` implemented

InfluxDB tables:

* `jobs`: Added new fields `numTasks`, `percent` and tag `indexStatus`.
* `jobs_statistics`: New
* `jobLogs`: Renaming of arguments, adding `jobExecutionTime`.
* `sppmon_metrics`: Added `influxdb_version` and new arguments
* `vmReplicateSummary` and `vmReplicateStats`: `removed tag` messageId
* `vadps`: Moved 3 tags to fields, adjusted CQ to run on distinct ID's
* `ProcessStats`: Removed 2 fields and 3 tags due change `top` to `ps` command.
* `office365stats` and `office365transfBytes` new
* `df_ssh`: Renamed `avail` to `available`, bugfixing a tag
