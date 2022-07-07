"""
 ----------------------------------------------------------------------------------------------
 (c) Copyright IBM Corporation 2020, 2021. All Rights Reserved.

 IBM Spectrum Protect Family Software

 Licensed materials provided under the terms of the IBM International Program
 License Agreement. See the Software licensing materials that came with the
 IBM Program for terms and conditions.

 U.S. Government Users Restricted Rights:  Use, duplication or disclosure
 restricted by GSA ADP Schedule Contract with IBM Corp.

 ----------------------------------------------------------------------------------------------
SPDX-License-Identifier: Apache-2.0

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Niels Korschinsky

Description:
    All kinds of tables, retention policies and continuous queries definitions are implemented here

Classes:
    Definitions
"""
from __future__ import annotations


import __main__
from os.path import basename

from typing import Callable, ClassVar, Dict, List, Optional, Union

from utils.exception_utils import ExceptionUtils

from influx.database_tables import Database, Datatype, RetentionPolicy, Table
from influx.influx_queries import ContinuousQuery, Keyword, SelectionQuery


class Definitions:
    """Within this class, all tables, retention policies, and continuous queries are defined.

    Use each area to declare each type.
    Retention Policies are *always* declared at the top as classmethod.
    You may use individual CQ below with the table declaration or define a template below the RP's.
    See existent definitions to declare your own.

    The start of all execution is the single method `add_table_definitions`.
    Do NOT use anything before executing this, the ClassVar `database` is set in there.

    Attributes:
        __database

    Classmethod for internal use:
        RP_AUTOGEN
        RP_INF
        RP_YEAR
        RP_HALF_YEAR
        RP_DAYS_90
        RP_DAYS_14
        _CQ_DWSMPL
        __add_predef_table

    Methods:
        add_table_definitions - Set ups all table, CQ and RP definitions.
    """

    __database: ClassVar[Database]

    # ################ Retention Policies ##################
    # ################       README       ##################
    # Be aware data is stored by either its duration or the longest CQ-GROUP BY clause duration.
    # Grouped into grafana-dashboards of either 14, 90, or INF Days. Select duration accordingly.
    # High Data count is stored in 14d, downsampled to 90d (1d), then to INF (1w).
    # Low Data count is stored in 90d, downsampled to INF (1w).
    # Data that cannot be downsampled is preserved for either half or full year.

    @classmethod
    def RP_AUTOGEN(cls):
        """"Default auto-generated RP, leave at inf to not loose data in case of non-definition"""
        return RetentionPolicy(name="autogen", database=cls.__database, duration="INF")

    @classmethod
    def RP_INF(cls):  # notice: just inf is a influx error -> counted AS numberlit
        """Infinite duration for long time preservation of heavy downsampled data"""
        return RetentionPolicy(name="rp_inf", database=cls.__database, duration="INF")

    @classmethod
    def RP_YEAR(cls):
        """Year duration for long time preservation of non-downsampled data"""
        return RetentionPolicy(name="rp_year", database=cls.__database, duration="56w")

    @classmethod
    def RP_HALF_YEAR(cls):
        """Half-year duration for long time preservation of non-downsampled data"""
        return RetentionPolicy(name="rp_half_year", database=cls.__database, duration="28w")

    @classmethod
    def RP_DAYS_90(cls):
        """3 Month duration for either non-downsampled data of low count/day or medium-downsampled of high count/day."""
        return RetentionPolicy(name="rp_days_90", database=cls.__database, duration="90d")

    @classmethod
    def RP_DAYS_14(cls):
        """2w duration for non-downsampled data of high count/day"""
        return RetentionPolicy(name="rp_days_14", database=cls.__database, duration="14d", default=True)

    @classmethod
    def RP_DAYS_7(cls):
        """1w duration for special non-downsampled data of high count/day, to allow an aggregate before downsampling"""
        return RetentionPolicy(name="rp_days_7", database=cls.__database, duration="7d")

    # ########## NOTICE #############
    # Any reduce below 7 days does not work if inserting by a group by (1w) clause:
    # Data duration is ignored if the group clause is higher, using it instead.
    # also be aware that any aggregate is split over any GROUPING, therefore it may not be of a good use!

    # ################ Continuous Queries ###################

    @classmethod
    def _CQ_DWSMPL(
            cls, fields: List[str], new_retention_policy: RetentionPolicy,
            group_time: str, group_args: List[str] = ["*"]) -> Callable[[Table, str], ContinuousQuery]:
        """Creates a template CQ which groups by time, * . Always uses the base table it was created from.

            Downsamples the data into another retention policy, using given aggregations within the list of fields.
            It is required to return a callable since at the time of declaration no table instance is available.
            The tables are inserted at runtime within the setup of the influx-client.

        Args:
            fields (List[str]): Fields to be selected and aggregated, influx-keywords need to be escaped.
            new_retention_policy (RetentionPolicy): new retention policy to be inserted into
            group_time (str): time-literal on which the data should be grouped
            group_args (List[str], optional): Optional other grouping clause. Defaults to ["*"].

        Returns:
            Callable[[Table, str], ContinuousQuery]: Lambda which is transformed into a CQ later on.
        """
        if(group_args is None):
            group_args = ["*"]
        return lambda table, name: ContinuousQuery(
            name=name, database=cls.__database,
            select_query=SelectionQuery(
                Keyword.SELECT,
                table_or_query=table,
                into_table=Table(cls.__database, table.name, retention_policy=new_retention_policy),
                fields=fields,
                group_list=[f"time({group_time})"] + group_args),
            for_interval="1w"
        )

    @classmethod
    def _CQ_TMPL(
            cls, fields: List[str], new_retention_policy: RetentionPolicy,
            group_time: str, group_args: List[str] = ["*"], where_str: Optional[str] = None) -> Callable[[Table, str], ContinuousQuery]:
        """Creates a CQ to do whatever you want with it.

        It is required to return a callable since at the time of declaration no table instance is available.
        The tables are inserted at runtime within the setup of the influx-client.

        Args:
            fields (List[str]): Fields to be selected and aggregated, influx-keywords need to be escaped.
            new_retention_policy (RetentionPolicy): new retention policy to be inserted into
            group_time (str): time-literal on which the data should be grouped
            group_args (List[str], optional): Optional other grouping clause. Defaults to ["*"].
            where_str (str): a where clause in case you want to define it. Defaults to None.

        Returns:
            Callable[[Table, str], ContinuousQuery]: Lambda which is transformed into a CQ later on.
        """
        if(group_args is None):
            group_args = ["*"]
        return lambda table, name: ContinuousQuery(
            name=name, database=cls.__database,
            select_query=SelectionQuery(
                Keyword.SELECT,
                table_or_query=table,
                into_table=Table(cls.__database, table.name, retention_policy=new_retention_policy),
                fields=fields,
                where_str=where_str,
                group_list=[f"time({group_time})"] + group_args),
            for_interval="1w"
        )

    @classmethod
    def add_predef_table(cls, name: str, fields: Dict[str, Datatype], tags: List[str],
                         time_key: Optional[str] = None,
                         retention_policy: Optional[RetentionPolicy] = None,
                         continuous_queries: Optional[
                             List[Union[
                                 ContinuousQuery,
                                 Callable[[Table, str], ContinuousQuery]]]] = None
                        ) -> None:
        """Declares a new predefined table. Recommended to to with every table you may want to insert into the influxdb.


        It is recommended to declare each param by name.
        If you do not declare the time_key, it will use sppmon capture time.
        Declare Retention Policy by ClassMethods declared above. Blank for `autogen`-RP (not recommended).
        Declare Continuous queries by using either the cq_template or creating your own.
        Be aware it is impossible to use `database["tablename"] to gain a instance of a table, this table is not defined yet.

        Arguments:
            name {str} -- Name of the table/measurement
            fields {Dict[str, Datatype]} -- fields of the table. At least one entry, name AS key, datatype AS value.
            tags {List[str]} -- tags of the table. Always of datatype string

        Keyword Arguments:
            time_key {Optional[str]} -- Name of key used AS timestamp. Blank if capturetime (default: {None})
            retention_policy {RetentionPolicy} -- Retention policy to be associated (default: {None})
            continuous_queries {List[Union[ContinuousQuery, Callable[[Table, str], ContinuousQuery]]]}
                -- List of either a CQ or a template which is transformed within this method (default: {None})
        """

        # create a retention instance out of the constructor methods
        if(not retention_policy):
            retention_policy = cls.RP_AUTOGEN()

        # add to save used policies
        cls.__database.retention_policies.add(retention_policy)

        # switch needed to allow table default value to be used.
        # avoids redundant default declaration
        if(time_key):
            table = Table(
                database=cls.__database,
                name=name,
                fields=fields,
                tags=tags,
                time_key=time_key,
                retention_policy=retention_policy
            )
        else:
            table = Table(
                database=cls.__database,
                name=name,
                fields=fields,
                tags=tags,
                retention_policy=retention_policy
            )
        cls.__database.tables[name] = table

        # save CQ
        if(continuous_queries):
            i = 0
            for continuous_query in continuous_queries:
                if(not isinstance(continuous_query, ContinuousQuery)):
                    continuous_query = continuous_query(table, f"cq_{table.name}_{i}")
                    i += 1
                cls.__database.continuous_queries.add(continuous_query)

                # make sure the args exist
                if(continuous_query.select_query and continuous_query.select_query.into_table):
                    cls.__database.retention_policies.add(continuous_query.select_query.into_table.retention_policy)
                else:
                    # regex parsing?
                    ExceptionUtils.error_message(
                        "Probably a programming error, report to DEV's. " +
                        f"Missing retention policy for CQ {continuous_query.name}.")

    @classmethod
    def add_table_definitions(cls, database: Database):
        """Set ups all table, CQ and RP definitions. Those are undeclared before.

        Always call this method before using any Definition-CLS methods.
        ClassVar database is set within.

        Args:
            database (Database): database instance to be defined.
        """
        cls.__database = database

        # ################################################################################
        # ################# Add Table Definitions here ###################################
        # ################################################################################
        # #################            READ ME         ###################################
        # ################################################################################
        # Structure:
        # cls.__add_predef_table(
        #   name="tablename",
        #   fields={
        #       "field_1": Datatype.INT|FLOAT|BOOL|STRING|TIMESTAMP,
        #        [...]
        #   },
        #   tags=[ # OPTIONAL, = [] if unused
        #       "tag_1",
        #        [...]
        #   ],
        #   time_key="time", # OPTIONAL, remove for capture time. Declare it AS field too if you want to save it beside AS `time`.
        #   retention_policy=cls._RP_DURATION_N(), # OPTIONAL, `autogen` used if empty. Recommended to set.
        #   continuous_queries=[                                    # OPTIONAL, recommended based on RP-Duration
        #       cls._CQ_TMPL(["mean(*)"], cls.RP_DAYS_90(), "6h"), # REMOVE this line if RP_DAYS_90 used
        #       cls._CQ_TMPL(["mean(*)"], cls.RP_INF(), "1w")      # Edit both mean(*)-cases if a special aggregation is required. You may also use mean(field_name) AS field_name to keep the old name.
        #       ]
        #   )
        # ################################################################################
        # DISCLAIMER: This annoying repetition of fields is caused due issue #97
        # see https://github.com/influxdata/influxdb/issues/7332
        # This is a tradeoff, worse readable code for easier Grafana-Support
        # ################################################################################

        # ################## Job Tables ##############################

        cls.add_predef_table(
            name='jobs',
            fields={  # FIELDS
                'duration':         Datatype.INT,
                'start':            Datatype.TIMESTAMP,
                'end':              Datatype.TIMESTAMP,
                'jobLogsCount':     Datatype.INT,
                # due high numbers id is saved AS field
                'id':               Datatype.INT,
                'numTasks':         Datatype.INT,
                'percent':          Datatype.FLOAT
                # count(id) -> "count": Int -> RP INF
            },
            tags=[  # TAGS
                'jobId',
                'status',
                'indexStatus',
                'jobName',
                'subPolicyType',
                'type',
                'jobsLogsStored'
            ],
            time_key='start',
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"duration\") AS \"duration\"", "sum(jobLogsCount) AS jobLogsCount",
                    "mean(numTasks) AS numTasks", "mean(percent) AS percent",
                    "count(id) AS count"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='jobs_statistics',
            fields={
                'total':            Datatype.INT,
                'success':          Datatype.INT,
                'failed':           Datatype.INT,
                'skipped':          Datatype.INT,
                'id':               Datatype.INT,
                # count(id) -> "count": Int -> RP INF
            },
            tags=[
                'resourceType',
                'jobId',
                'status',
                'indexStatus',
                'jobName',
                'type',
                'subPolicyType',
            ],
            time_key='start',
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(total) AS total", "mean(success) AS success",
                    "mean(failed) AS failed", "mean(skipped) AS skipped",
                    "count(id) AS count"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='jobLogs',
            fields={  # FIELDS
                # Due high numbers these ID's are saved AS fields. Maybe remove ID's?
                'jobLogId':         Datatype.STRING,
                'jobSessionId':     Datatype.INT,

                # default fields
                'messageParams':    Datatype.STRING,
                "message":          Datatype.STRING,
                'jobExecutionTime': Datatype.TIMESTAMP
            },
            tags=[  # TAGS
                'type',
                'messageId',
                'jobName',
                'jobId'
            ],
            time_key='logTime',
            retention_policy=cls.RP_HALF_YEAR(),
            continuous_queries=[
                # cls._CQ_TRNSF(cls.RP_DAYS_14())
            ]
        )

        # ############# SPPMon Execution Tables ########################


        cls.add_predef_table(
            name='influx_metrics',
            fields={  # FIELDS
                'duration_ms':      Datatype.FLOAT,
                'item_count':       Datatype.INT
            },
            tags=[  # TAGS
                'keyword',
                'tableName'
            ],
            time_key='time',
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(duration_ms) AS duration_ms",
                    "mean(item_count) AS item_count",
                    "stddev(*)"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(duration_ms) AS duration_ms",
                    "mean(item_count) AS item_count",
                    "stddev(*)"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='sshCmdResponse',
            fields={
                'output':           Datatype.STRING
            },
            tags=[
                'command',
                'host',
                'ssh_type'
            ],
            retention_policy=cls.RP_HALF_YEAR()
            # time_key unset
        )

        cls.add_predef_table(
            name='sppmon_metrics',
            fields={
                'duration':         Datatype.INT,
                'errorCount':       Datatype.INT,
                'errorMessages':    Datatype.STRING
            },
            tags=[
                "configFile",
                "fullLogs",
                "copy_database",
                "cpu",
                "create_dashboard",
                "dashboard_folder_path",
                "hourly",
                "loadedSystem",
                "old_database",
                "processStats",
                "sites",
                "sppcatalog",
                "storages",
                "test",
                "transfer_data",
                'all',
                'constant',
                'daily',
                'debug',
                'influxdb_version',
                'jobLogs',
                'jobs',
                'minimumLogs',
                'siteStats',
                'slaStats',
                'spp_build',
                'spp_version',
                'ssh',
                'type',
                'vadps',
                'verbose',
                'vmStats',
                'vms',
                'vsnapInfo',
                'sppmon_version',
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"duration\") AS \"duration\"",
                    "sum(errorCount) AS sum_errorCount"
                    ], cls.RP_DAYS_90(), "6h"), # errorMessages is dropped due being str
                cls._CQ_DWSMPL([
                    "mean(\"duration\") AS \"duration\"",
                    "sum(errorCount) AS sum_errorCount"
                    ], cls.RP_INF(), "1w")
            ]
        )

        # ############### VM SLA Tables ##########################

        cls.add_predef_table(
            name='slaStats',
            fields={
                'vmCountBySLA':     Datatype.INT
            },
            tags=[
                'slaId',
                'slaName'
            ],
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(vmCountBySLA) AS vmCountBySLA"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name="vms",
            fields={
                'uptime':           Datatype.TIMESTAMP,
                'powerState':       Datatype.STRING,
                # cannot fix these typos without breaking existing tables
                'commited':         Datatype.INT,
                'uncommited':       Datatype.INT,
                'shared':           Datatype.INT,
                'cpu':              Datatype.INT,
                'coresPerCpu':      Datatype.INT,
                'memory':           Datatype.INT,
                'name':             Datatype.STRING
            },
            tags=[
                'host',
                'vmVersion',
                'osName',
                'isProtected',
                'inHLO',
                'isEncrypted',
                'datacenterName',
                'id',                   # For issue #6, moved id to tags from fields to ensure uniqueness in tag set
                'hypervisorType'
            ],
            time_key='catalogTime',
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL(
                    fields=[ # strings are not calculated, uptime AS timestamp removed
                        # cannot fix these typos without breaking existing tables
                        "mean(commited) AS commited",
                        "mean(uncommited) AS uncommited",
                        "mean(shared) AS shared",
                        "mean(cpu) AS cpu",
                        "mean(coresPerCpu) AS coresPerCpu",
                        "mean(memory) AS memory"
                    ],
                    new_retention_policy=cls.RP_DAYS_90(),
                    group_time="6h",
                    group_args=[
                        'host',
                        'vmVersion',
                        'osName',
                        'isProtected',
                        'inHLO',
                        'isEncrypted',
                        'datacenterName',
                        #'id',  ## Not ID to allow a meaningful grouping
                        'hypervisorType'
                    ]),
                cls._CQ_DWSMPL(
                    fields=[
                        # cannot fix these typos without breaking existing tables
                        "mean(commited) AS commited",
                        "mean(uncommited) AS uncommited",
                        "mean(shared) AS shared",
                        "mean(cpu) AS cpu",
                        "mean(coresPerCpu) AS coresPerCpu",
                        "mean(memory) AS memory"
                    ],
                    new_retention_policy=cls.RP_INF(),
                    group_time="1w",
                    group_args=[
                        'host',
                        'vmVersion',
                        'osName',
                        'isProtected',
                        'inHLO',
                        'isEncrypted',
                        'datacenterName',
                        #'id',  ## Not ID to allow a meaningful grouping
                        'hypervisorType'
                    ]),


                # VM STATS TABLE
                # ContinuousQuery(
                #     name="cq_vms_to_stats",
                #     database=cls.database,
                #     regex_query=f"SELECT count(name) AS vmCount, max(commited) AS vmMaxSize, min(commited) AS vmMinSize\
                #         sum(commited) AS vmSizeTotal, mean(commited) AS vmAvgSize, count(distinct(datacenterName)) AS nrDataCenters\
                #         count(distinct(host)) AS nrHosts\
                #         INTO {cls.RP_DAYS_90()}.vmStats FROM {cls.RP_DAYS_14()}.vms GROUP BY \
                #         time(1d)"
                #         # TODO: Issue with vmCount per x, no solution found yet.
                #         # see Issue #93
                # )
            ]
        )

        cls.add_predef_table(
            name='vmStats',
            fields={
                'vmCount':              Datatype.INT,

                'vmMaxSize':            Datatype.INT,
                'vmMinSize':            Datatype.INT,
                'vmSizeTotal':          Datatype.INT,
                'vmAvgSize':            Datatype.FLOAT,

                'vmMaxUptime':          Datatype.INT,
                'vmMinUptime':          Datatype.INT,
                'vmUptimeTotal':        Datatype.INT,
                'vmAvgUptime':          Datatype.FLOAT,

                'vmCountProtected':     Datatype.INT,
                'vmCountUnprotected':   Datatype.INT,

                'vmCountEncrypted':     Datatype.INT,
                'vmCountPlain':         Datatype.INT,

                'vmCountHLO':           Datatype.INT,
                'vmCountNotHLO':        Datatype.INT,

                'vmCountHyperV':        Datatype.INT,
                'vmCountVMware':        Datatype.INT,

                'nrDataCenters':        Datatype.INT,
                'nrHosts':              Datatype.INT,
            },
            tags=[],
            time_key='time',
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                # cls._CQ_TRNSF(cls.RP_DAYS_14()), # removed due bug.
                cls._CQ_DWSMPL([ # see issue #97 why this long list is required..
                    "mean(vmCount) AS vmCount",
                    "mean(vmMaxSize) AS vmMaxSize",
                    "mean(vmMinSize) AS vmMinSize",
                    "mean(vmSizeTotal) AS vmSizeTotal",
                    "mean(vmAvgSize) AS vmAvgSize",
                    "mean(vmMaxUptime) AS vmMaxUptime",
                    "mean(vmMinUptime) AS vmMinUptime",
                    "mean(vmUptimeTotal) AS vmUptimeTotal",
                    "mean(vmAvgUptime) AS vmAvgUptime",
                    "mean(vmCountProtected) AS vmCountProtected",
                    "mean(vmCountUnprotected) AS vmCountUnprotected",
                    "mean(vmCountEncrypted) AS vmCountEncrypted",
                    "mean(vmCountPlain) AS vmCountPlain",
                    "mean(vmCountHLO) AS vmCountHLO",
                    "mean(vmCountNotHLO) AS vmCountNotHLO",
                    "mean(vmCountHyperV) AS vmCountHyperV",
                    "mean(vmCountVMware) AS vmCountVMware",
                    "mean(nrDataCenters) AS nrDataCenters",
                    "mean(nrHosts) AS nrHosts",
                    ], cls.RP_INF(), "1w")
            ]

        )

        cls.add_predef_table(
            name='vmBackupSummary',
            fields={
                'transferredBytes':         Datatype.INT,
                'throughputBytes/s':        Datatype.INT,
                'queueTimeSec':             Datatype.INT,
                'protectedVMDKs':           Datatype.INT,
                'TotalVMDKs':               Datatype.INT,
                'name':                     Datatype.STRING
            },
            tags=[
                'proxy',
                'vsnaps',
                'type',
                'transportType',
                'status',
                'messageId'
            ],
            time_key='time',
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"throughputBytes/s\") AS \"throughputBytes/s\"",
                    "mean(queueTimeSec) AS queueTimeSec",
                    "sum(transferredBytes) AS sum_transferredBytes",
                    "sum(protectedVMDKs) AS sum_protectedVMDKs",
                    "sum(TotalVMDKs) AS sum_TotalVMDKs"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(\"throughputBytes/s\") AS \"throughputBytes/s\"",
                    "mean(queueTimeSec) AS queueTimeSec",
                    "sum(transferredBytes) AS sum_transferredBytes",
                    "sum(protectedVMDKs) AS sum_protectedVMDKs",
                    "sum(TotalVMDKs) AS sum_TotalVMDKs"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='vmReplicateSummary',
            fields={
                'total':                      Datatype.INT,
                'failed':                     Datatype.INT,
                'duration':                   Datatype.INT
            },
            tags=[], # None
            time_key='time',
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                # cls._CQ_TRNSF(cls.RP_DAYS_14()),
                cls._CQ_DWSMPL([
                    "mean(\"duration\") AS \"duration\"",
                    "sum(total) AS sum_total",
                    "sum(failed) AS sum_failed"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='vmReplicateStats',
            fields={
                'replicatedBytes':          Datatype.INT,
                'throughputBytes/sec':      Datatype.INT,
                'duration':                 Datatype.INT
            },
            tags=[],# None
            time_key='time',
            retention_policy=cls.RP_DAYS_90(),
            continuous_queries=[
                # cls._CQ_TRNSF(cls.RP_DAYS_14()),
                cls._CQ_DWSMPL([
                    "mean(\"throughputBytes/sec\") AS \"throughputBytes/sec\"",
                    "sum(replicatedBytes) AS replicatedBytes",
                    "mean(\"duration\") AS \"duration\""
                    ], cls.RP_INF(), "1w")
            ]
        )

        # ############### VADP VSNAP Tables ##########################

        cls.add_predef_table(
            name='vadps',
            fields={
                # Dummy fields, since they are not required at tag but good to have.
                # Having them as tags would require a dummy field and unnecessarily increase series cardinality
                'vadpId':                       Datatype.INT,
                'ipAddr':                       Datatype.STRING
            },
            tags=[
                'status', # Useful to group over state later on, as well as now. Renamed because of duplicate name.
                'siteId', # Required for later grouping
                'siteName', # Just addon to the siteID
                'version', # Useful to group on at any stage
                'vadpName', # Required to make each vadp unique -> not dropped.
            ],
            retention_policy=cls.RP_HALF_YEAR(),
            continuous_queries=[
                cls._CQ_TMPL(
                    fields=["count(distinct(vadpId)) AS count"],
                    new_retention_policy=cls.RP_DAYS_14(),
                    group_time="1h",
                    group_args=[
                        'siteId',
                        'siteName',
                        'version',
                        'status'
                    ]
                ),
                cls._CQ_TMPL(
                    fields=["count(distinct(vadpId)) AS count"],
                    new_retention_policy=cls.RP_DAYS_90(),
                    group_time="6h",
                    group_args=[
                        'siteId',
                        'siteName',
                        'version',
                        'status'
                    ]
                ),
                cls._CQ_TMPL(
                    fields=["count(distinct(vadpId)) AS count"],
                    new_retention_policy=cls.RP_INF(),
                    group_time="1w",
                    group_args=[
                        'siteId',
                        'siteName',
                        'version',
                        'status'
                    ]
                )
            ]
        )

        cls.add_predef_table(
            name='storages',
            fields={
                'free':             Datatype.INT,
                'pct_free':         Datatype.FLOAT,
                'pct_used':         Datatype.FLOAT,
                'total':            Datatype.INT,
                'used':             Datatype.INT,
                'name':             Datatype.STRING
            },
            tags=[
                'isReady',
                'site',
                'siteName',
                'storageId',
                'type',
                'version',
                'hostAddress'
            ],
            time_key='updateTime',
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(free) AS free",
                    "mean(pct_free) AS pct_free",
                    "mean(pct_used) AS pct_used",
                    "mean(total) AS total",
                    "mean(used) AS used",
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(free) AS free",
                    "mean(pct_free) AS pct_free",
                    "mean(pct_used) AS pct_used",
                    "mean(total) AS total",
                    "mean(used) AS used",
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='vsnap_pools',
            fields={
                'compression_ratio':        Datatype.FLOAT,
                'deduplication_ratio':      Datatype.FLOAT,
                'diskgroup_size':           Datatype.INT,
                'health':                   Datatype.INT,
                'size_before_compression':  Datatype.INT,
                'size_before_deduplication':Datatype.INT,
                'size_free':                Datatype.INT,
                'size_total':               Datatype.INT,
                'size_used':                Datatype.INT
            },
            tags=[
                'encryption_enabled',
                'compression',
                'deduplication',
                'id',
                'name',
                'pool_type',
                'status',
                'hostName',
                'ssh_type'
            ], # time key unset, updateTime is not what we want -> it is not updated
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(compression_ratio) AS compression_ratio",
                    "mean(deduplication_ratio) AS deduplication_ratio",
                    "mean(diskgroup_size) AS diskgroup_size",
                    "mean(health) AS health",
                    "mean(size_before_compression) AS size_before_compression",
                    "mean(size_before_deduplication) AS size_before_deduplication",
                    "mean(size_free) AS size_free",
                    "mean(size_total) AS size_total",
                    "mean(size_used) AS size_used"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(compression_ratio) AS compression_ratio",
                    "mean(deduplication_ratio) AS deduplication_ratio",
                    "mean(diskgroup_size) AS diskgroup_size",
                    "mean(health) AS health",
                    "mean(size_before_compression) AS size_before_compression",
                    "mean(size_before_deduplication) AS size_before_deduplication",
                    "mean(size_free) AS size_free",
                    "mean(size_total) AS size_total",
                    "mean(size_used) AS size_used"
                    ], cls.RP_INF(), "1w")
            ]

        )

        cls.add_predef_table(
            name='vsnap_system_stats',
            fields={
                'size_arc_max':             Datatype.INT,
                'size_arc_used':            Datatype.INT,
                'size_ddt_core':            Datatype.INT,
                'size_ddt_disk':            Datatype.INT,
                'size_zfs_arc_meta_max':    Datatype.INT,
                'size_zfs_arc_meta_used':   Datatype.INT,
            },
            tags=[
                'hostName',
                'ssh_type'
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(size_arc_max) AS size_arc_max",
                    "mean(size_arc_used) AS size_arc_used",
                    "mean(size_ddt_core) AS size_ddt_core",
                    "mean(size_ddt_disk) AS size_ddt_disk",
                    "mean(size_zfs_arc_meta_max) AS size_zfs_arc_meta_max",
                    "mean(size_zfs_arc_meta_used) AS size_zfs_arc_meta_used"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(size_arc_max) AS size_arc_max",
                    "mean(size_arc_used) AS size_arc_used",
                    "mean(size_ddt_core) AS size_ddt_core",
                    "mean(size_ddt_disk) AS size_ddt_disk",
                    "mean(size_zfs_arc_meta_max) AS size_zfs_arc_meta_max",
                    "mean(size_zfs_arc_meta_used) AS size_zfs_arc_meta_used"
                    ], cls.RP_INF(), "1w")
            ]
        )

        # ############# SPP System Stats #####################

        cls.add_predef_table(
            name='cpuram',
            fields={
                'cpuUtil':          Datatype.FLOAT,
                'memorySize':       Datatype.INT,
                'memoryUtil':       Datatype.FLOAT,
                'dataSize':         Datatype.INT,
                'dataUtil':         Datatype.FLOAT,
                'data2Size':         Datatype.INT,
                'data2Util':         Datatype.FLOAT,
                'data3Size':         Datatype.INT,
                'data3Util':         Datatype.FLOAT
            },
            tags=[],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(cpuUtil) AS cpuUtil",
                    "mean(memorySize) AS memorySize",
                    "mean(memoryUtil) AS memoryUtil",
                    "mean(dataSize) AS dataSize",
                    "mean(dataUtil) AS dataUtil",
                    "mean(data2Size) AS data2Size",
                    "mean(data2Util) AS data2Util",
                    "mean(data3Size) AS data3Size",
                    "mean(data3Util) AS data3Util",
                    "stddev(*)"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(cpuUtil) AS cpuUtil",
                    "mean(memorySize) AS memorySize",
                    "mean(memoryUtil) AS memoryUtil",
                    "mean(dataSize) AS dataSize",
                    "mean(dataUtil) AS dataUtil",
                    "mean(data2Size) AS data2Size",
                    "mean(data2Util) AS data2Util",
                    "mean(data3Size) AS data3Size",
                    "mean(data3Util) AS data3Util",
                    "stddev(*)"
                    ], cls.RP_INF(), "1w")
            ]
        )

        cls.add_predef_table(
            name='sites',
            fields={
                'throttleRates':   Datatype.STRING,
                'description':     Datatype.STRING
            },
            tags=[
                'siteId',
                'siteName'
            ],
            retention_policy=cls.RP_HALF_YEAR(),
            continuous_queries=[
                # cls._CQ_TRNSF(cls.RP_DAYS_14())
            ]
            # time_key unset
        )

        cls.add_predef_table(
            name="sppcatalog",
            fields={
                'totalSize':                Datatype.INT,
                'usedSize':                 Datatype.INT,
                'availableSize':            Datatype.INT,
                'percentUsed':              Datatype.FLOAT,
                'status':                   Datatype.STRING
            },
            tags=[
                'name',
                'type'
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(totalSize) AS totalSize",
                    "mean(usedSize) AS usedSize",
                    "mean(availableSize) AS availableSize",
                    "mean(percentUsed) AS percentUsed"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(totalSize) AS totalSize",
                    "mean(usedSize) AS usedSize",
                    "mean(availableSize) AS availableSize",
                    "mean(percentUsed) AS percentUsed"
                    ], cls.RP_INF(), "1w")
            ]
            # capture time
        )

        cls.add_predef_table(
            name="processStats",
            fields={
                '%CPU':                     Datatype.FLOAT,
                '%MEM':                     Datatype.FLOAT,
                'TIME+':                    Datatype.INT,
                'VIRT':                     Datatype.INT,
                'MEM_ABS':                  Datatype.INT
            },
            tags=[
                'COMMAND',
                'PID',
                'USER',
                'hostName',
                'collectionType',
                'ssh_type'
            ],# time key is capture time
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                # ~Different pattern here due the removal of the PID grouping.~
                # Best would be a RP of 2 hours but due the group by (6h) and (1w) the duration would be increased to 1w
                # Otherwise you could create a new CQ by constructor / copy-paste lambda of CQ_TMPL and edit the source table.

                # EDIT does not work: by the group by more than command the sum gets reduced, a multiple-from-query is still to be made in grafana
                # this does not help, therefore removed. Also grouping by PID re-enabled, AS it would corrupt the mean due some 0%-pid-processes.
                # cls._CQ_TMPL(
                #     [
                #         "sum(\"%CPU\") AS \"%CPU\"",
                #         "sum(\"%MEM\") AS \"%MEM\"",
                #         "sum(\"RES\") AS \"RES\"",
                #         "sum(\"SHR\") AS \"SHR\"",
                #         "sum(\"TIME+\") AS \"TIME+\"",
                #         "sum(\"VIRT\") AS \"VIRT\"",
                #         "sum(\"MEM_ABS\") AS \"MEM_ABS\"",
                #         ],
                #     cls.RP_DAYS_14(), "1s",
                #     [
                #         'COMMAND',
                #         'NI',
                #         #'PID', # ALL BUT PID
                #         'PR',
                #         'S',
                #         '\"USER\"',
                #         'hostName',
                #         'ssh_type',
                #         'fill(previous)'
                #         ]),
                cls._CQ_DWSMPL([
                    "mean(\"%CPU\") AS \"%CPU\"",
                    "mean(\"%MEM\") AS \"%MEM\"",
                    "mean(RES) AS RES",
                    "mean(SHR) AS SHR",
                    "mean(\"TIME+\") AS \"TIME+\"",
                    "mean(VIRT) AS VIRT",
                    "mean(MEM_ABS) AS MEM_ABS",
                    "stddev(\"%CPU\") AS \"stddev_%CPU\"",
                    "stddev(\"%MEM\") AS \"stddev_%MEM\""
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(\"%CPU\") AS \"%CPU\"",
                    "mean(\"%MEM\") AS \"%MEM\"",
                    "mean(RES) AS RES",
                    "mean(SHR) AS SHR",
                    "mean(\"TIME+\") AS \"TIME+\"",
                    "mean(VIRT) AS VIRT",
                    "mean(MEM_ABS) AS MEM_ABS",
                    "stddev(\"%CPU\") AS \"sttdev_%CPU\"",
                    "stddev(\"%MEM\") AS \"sttdev_%MEM\""
                    ], cls.RP_INF(), "1w"),
            ]
        )

        cls.add_predef_table(
            name='ssh_mpstat_cmd',
            fields={
                "%usr":                 Datatype.FLOAT,
                "%nice":                Datatype.FLOAT,
                "%sys":                 Datatype.FLOAT,
                "%iowait":              Datatype.FLOAT,
                "%irq":                 Datatype.FLOAT,
                "%soft":                Datatype.FLOAT,
                "%steal":               Datatype.FLOAT,
                "%guest":               Datatype.FLOAT,
                "%gnice":               Datatype.FLOAT,
                "%idle":                Datatype.FLOAT,
                "cpu_count":            Datatype.INT,
            },
            tags=[
                "CPU",
                "name",
                "host",
                "system_type",
                'hostName',
                'ssh_type'
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"%usr\") AS \"%usr\"",
                    "mean(\"%nice\") AS \"%nice\"",
                    "mean(\"%sys\") AS \"%sys\"",
                    "mean(\"%iowait\") AS \"%iowait\"",
                    "mean(\"%irq\") AS \"%irq\"",
                    "mean(\"%soft\") AS \"%soft\"",
                    "mean(\"%steal\") AS \"%steal\"",
                    "mean(\"%guest\") AS \"%guest\"",
                    "mean(\"%gnice\") AS \"%gnice\"",
                    "mean(\"%idle\") AS \"%idle\"",
                    "mean(cpu_count) AS cpu_count"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(\"%usr\") AS \"%usr\"",
                    "mean(\"%nice\") AS \"%nice\"",
                    "mean(\"%sys\") AS \"%sys\"",
                    "mean(\"%iowait\") AS \"%iowait\"",
                    "mean(\"%irq\") AS \"%irq\"",
                    "mean(\"%soft\") AS \"%soft\"",
                    "mean(\"%steal\") AS \"%steal\"",
                    "mean(\"%guest\") AS \"%guest\"",
                    "mean(\"%gnice\") AS \"%gnice\"",
                    "mean(\"%idle\") AS \"%idle\"",
                    "mean(cpu_count) AS cpu_count"
                    ], cls.RP_INF(), "1w")
            ]
            # capture time
        )

        cls.add_predef_table(
            name="ssh_free_cmd",
            fields={
                #"available":                Datatype.INT, removed, integrated into "free"
                "buff/cache":               Datatype.INT,
                "free":                     Datatype.INT,
                "shared":                   Datatype.INT,
                "total":                    Datatype.INT,
                "used":                     Datatype.INT,

            },
            tags=[
                "name",
                'hostName',
                'ssh_type'
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"buff/cache\") AS \"buff/cache\"",
                    "mean(free) AS free",
                    "mean(shared) AS shared",
                    "mean(total) AS total",
                    "mean(used) AS used"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(\"buff/cache\") AS \"buff/cache\"",
                    "mean(free) AS free",
                    "mean(shared) AS shared",
                    "mean(total) AS total",
                    "mean(used) AS used"
                    ], cls.RP_INF(), "1w")
            ]
            # capture time
        )

        cls.add_predef_table(
            name="df_ssh",
            fields={
                "Size":                     Datatype.INT,
                "Used":                     Datatype.INT,
                "Available":                Datatype.INT,
                "Use%":                     Datatype.INT,
            },
            tags=[
                "Filesystem",
                "Mounted",
                "hostName",
                "ssh_type"
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "mean(\"Use%\") AS \"Use%\"",
                    "mean(Available) AS Available",
                    "mean(Used) AS Used",
                    "mean(Size) AS Size"
                    ], cls.RP_DAYS_90(), "6h"),
                cls._CQ_DWSMPL([
                    "mean(\"Use%\") AS \"Use%\"",
                    "mean(Available) AS Available",
                    "mean(Used) AS Used",
                    "mean(Size) AS Size"
                    ], cls.RP_INF(), "1w")
            ]
            # capture time
        ),

        # ################# Other Tables ############################

        cls.add_predef_table(
            name="office365Stats",
            fields={
                "protectedItems":           Datatype.INT,
                "selectedItems":            Datatype.INT,
                "imported365Users":         Datatype.INT
            },
            tags=[
                "jobId",
                'jobName',
                'ssh_type',
                "jobSessionId" # dropped in downsampling
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "sum(protectedItems) AS sum_protectedItems",
                    "sum(selectedItems) AS sum_selectedItems",
                    "sum(imported365Users) AS sum_imported365Users"
                    ], cls.RP_DAYS_90(), "6h",
                    group_args=[
                        "jobId",
                        'jobName',
                        'ssh_type',
                    ]),
                cls._CQ_DWSMPL([
                    "sum(protectedItems) AS sum_protectedItems",
                    "sum(selectedItems) AS sum_selectedItems",
                    "sum(imported365Users) AS sum_imported365Users"
                    ], cls.RP_INF(), "1w",
                    group_args=[
                        "jobId",
                        'jobName',
                        'ssh_type',
                    ]),
            ],
            time_key="jobExecutionTime"
        ),
        cls.add_predef_table(
            name="office365TransfBytes",
            fields={
                "itemName":                 Datatype.STRING,
                "transferredBytes":         Datatype.INT
            },
            tags=[
                'itemType',
                'serverName',
                "jobId",
                'jobName',
                "jobSessionId" # dropped in downsampling
            ],
            retention_policy=cls.RP_DAYS_14(),
            continuous_queries=[
                cls._CQ_DWSMPL([
                    "sum(transferredBytes) AS transferredBytes"
                    ], cls.RP_DAYS_90(), "6h",
                    group_args=[
                        "itemType",
                        "jobId",
                        'jobName',
                        'serverName',
                    ]),
                cls._CQ_DWSMPL([
                    "sum(transferredBytes) AS transferredBytes"
                    ], cls.RP_INF(), "1w",
                    group_args=[
                        "itemType",
                        "jobId",
                        'jobName',
                        'serverName',
                    ]),
            ]
            # time key unset
        )

        # ################# SPPCheck Tables ############################

        if basename(__main__.__file__) == "sppcheck.py":

            from sppCheck.excel.excel_reader import ExcelReader
            from sppCheck.predictor.predictor_influx_connector import PredictorInfluxConnector

            cls.add_predef_table(
                name=PredictorInfluxConnector.sppcheck_table_name,
                fields={
                    PredictorInfluxConnector.sppcheck_value_name:                    Datatype.INT,
                },
                tags=[
                    PredictorInfluxConnector.sppcheck_tag_name,
                    "site",
                    "siteName"

                ],
                # this rp is unused, but in here for safety. Overwritten by prediction-RP
                retention_policy=cls.RP_INF(),
                # No continuous queries
                # timekey unset -> default key

            )

            cls.add_predef_table(
                name=ExcelReader.sppcheck_excel_table_name,
                fields={
                    ExcelReader.sppcheck_excel_value_name:                    Datatype.INT,
                },
                tags=[
                    ExcelReader.sppcheck_excel_tag_name,
                ],
                # this rp is unused, but redundancy in case of an error. Overwritten by excel-RP
                retention_policy=cls.RP_INF(),
                # No continuous queries
                # timekey unset -> default key

            )

            cls.add_predef_table(
                name='sppcheck_metrics',
                fields={
                    'duration':         Datatype.INT,
                    'errorCount':       Datatype.INT,
                    'errorMessages':    Datatype.STRING
                },
                tags=[
                    "configFile",
                    'influxdb_version',
                    'sppcheck_version',
                    'sheetPath',
                    'sizerVersion',
                    'startDate',
                    'genFakeData',
                    'predictYears',
                    'pdfReport',
                    'latestData',
                    'fakeData'
                ],
                retention_policy=cls.RP_INF(),
                # No continuous queries
                # timekey unset -> default key
            )




        # ################################################################################
        # ################### End of table definitions ###################################
        # ################################################################################
