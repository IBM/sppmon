# Change log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

Here we write upgrading notes for brands. It's a team effort to make them as
straightforward as possible.

### Added

### Changed

### Fixed

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

* Install Script for automatically installing SPPMon, Python, InfluxDB, and Grafana on a blank CentOs system.
  * Features a `--alwaysConfirm` argument for less confirmations
* Two stand-alone python scripts for automatically creating Config files and adding them to crontab
  > These scripts are used within the install script
* Created script `scripts/generifyDashboard.py`, which is now on developer side. This makes sure a dashboard exported for external use is truly generic.
  > See Grafana changes for reasoning

### Python / Execution

#### Fixes

* `--test`:  Fixes Abort without summary on SSH-Errors
* Fixes empty error message without explanation if sites are an empty array
  * Also adds debug output for easier remote tracing
* Corrupted config-file path no longer breaks SPPMon but prints a error message
* Partly fixes #40, but some ID's still remain missing due other issues. Descriped within issue itself.
* JobLogs: The type-filter is no longer ignored on regular/loaded execution - requesting way less logs.
* Fixed an error when importing individual job log statistics and `ressourceType` was missing

#### Changes

* Replaces OptionParser with Argumentparser
* Improves `--test` argument: Outsources code, improves display and messages.
  * Enhanced Description and help message
  * Catches typos and missing arguments within the parser
* Removed disallowed terms from SPPMon code, using `allow_list` instead
* Reworks REST-API POST-Requests to be merged with GET-Requests
  * This includes the repeated tries if a request fails
  * Deprecates `url_set_param`, using functionality of `requests`-package instead
  * Using Python-Structs for url-params instead of cryptical encoded params
* Reworks REST-API requests even more to use parameters more efficient and consistent, making the code hopefully more readable.
  * Changes get_url_params to gain all parameters from URL-Encoding
  * Introduces set_url_params to set all params into URL encoding
  * Reads params of next page and allows injecting whole dictionary of params
* Changes vms per SLA-request to not query all vms anymore, ~~but using pageSize to 1 and reading the `total` aggregated field and not repeat for other pages~~.
  * Changed to query so-far unknown endpoint, using count and group aggregate to query all data with a single API-request
  > This brings the sla-request in line with the other api-requests.
* Reworked/Commented the job-log request and prepared a filter via individual joblog-ID's
* Labeled python argument ` -create_dashboard` and associated args as depricated, to be removed in v1.1 (See Grafana-Changes)

### Influx

#### Changes

* Checks user (GrafanaReader) for permissions (READ) on current Database, warns if user not exists and grands permissions if missing (Feature of V1.0)
* Reworks Influx-write Queries to repeat once if failed with fallback options
  * This includes enhanced error messages
  * Influx-Statistic send is reworked to be per table
* Split Influx-Stats: Query duration per item also groups via table and show average

#### Fixes

* Optimized Continious-Queries setup
  * No longer all CQ are re-build on start of **all** sppmon exections, works now as intended
  * Changed definition to match influxDB return values (7d -> 1 w)
  * Changed quotations to match influxDB return values

#### Breaking Changes

* Typo fix in stddev, breaking old data.
  * These numbers are used nowhere, therefore this will likley not break anything
  * Old Data is still available by the old name `sttdev`

### Grafana-Dashboards

#### Added

* Added Hyper-V Job Duration Panel similar to VMWare-Panel into 14 and 90/INF Dashboard
* Added versioning tags to each dashboard. Starting with v1.0
* Added unique data source tags to the 14-day dashboard
  * They have no use yet, but might be used for directly referencing onto a certain dashboard from 90-days/mult dashboard
* Added unique tags for identifying 14-day, 90-day and mult dashboards
* Created links from each dashboards to the others, grouped by type
  * The 14-days dashboards are created as dropdown

#### Changes

* Changed dashboard to be exported for `external use`:
  * You may change the datasource on importing
  * Both UID and Dashboard name will be variable generated based on datasource chosen
  * Labeled python argument ` -create_dashboard` and associated args as depricated, to be removed in v1.1
    > Note: Listed here only for completeness, see python changes
  * Created pyhton stand-alone script for generifying dashboard
    > Note: Listed here only for completeness, see script changes

## [0.5.4-beta] - 2021-08-11

### Fixes

* Bugfixes flat CPU-statistics due `ps` unexpected behavior.
  * `ps` no longer tracks CPU-Data, Track of RAM and some other system informations remains.
  * Re-introduced `top`-ssh command, but only collecting CPU-Statistics (see top-memory-truncation issue #14 & #32)
  > **The process-stats panel is accurate again after applying this fix.**

## [0.5.3-beta] - 2021-07-11

### Changes

* Changed top-level exception catching: Catches any exceptions instead of only our self-defined ValueErrors
  -> Prevents a complete abort of SPPMon if something unexpected happens.
  -> **This will reduce the need of urgent hotfixes like this one.**
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

* Reminder: `--minimumLogs` depricated, to be removed in V1.0. Use `--loadedSystem` instead
* `--processStats` depricated, integrated into `--ssh`
* `transfer_data` removed. Use `copy_datase` instead.
  * removed `--old_database`, integraded into `copy_database` CFG file.
* `--test` implemented

InfluxDB tables:

* `jobs`: Added new fields `numTasks`, `percent` and tag `indexStatus`.
* `jobs_statistics`: New
* `jobLogs`: Renaming of arguments, adding `jobExecutionTime`.
* `sppmon_metrics`: Added `influxdb_version` and new arguments
* `vmReplicateSummary` and `vmReplicateStats`: `removed tag `messageId`
* `vadps`: Moved 3 tags to fields, adjusted CQ to run on distinct ID's
* `ProcessStats`: Removed 2 fields and 3 tags due change `top` to `ps` command.
* `office365stats` and `office365transfBytes` new
* `df_ssh`: Renamed `avail` to `available`, bugfixing a tag