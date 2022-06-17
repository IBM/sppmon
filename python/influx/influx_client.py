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
    Module with influx client. Contains all functionality around sending and accessing influx database.

Classes:
    InfluxClient
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

import requests
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from influxdb.resultset import ResultSet
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from utils.exception_utils import ExceptionUtils
from utils.spp_utils import SppUtils

import influx.definitions as df
from influx.database_tables import Database, RetentionPolicy, Table
from influx.influx_queries import (ContinuousQuery, InsertQuery, Keyword,
                                   SelectionQuery)

LOGGER = logging.getLogger("sppmon")

disable_warnings(InsecureRequestWarning)

class InfluxClient:
    """Class uses for accessing and working with the influx client.

    Attributes:
        database - database with predefined tables
        use_ssl - whether the client should use ssl.

    Methods:
        connect - connects the client to remote sever
        disconnect - disconnects the client from remote server and flush buffer
        create_rp - Creates a new retention policy for the specified database
        check_create_rp - Checks if any retention policy needs to be altered or added
        check_create_cq - Checks if any continuous query needs to be altered or added
        insert_dicts_to_buffer - Method to insert data into InfluxDB
        flush_insert_buffer - flushes buffer, send queries to influxdb
        send_selection_query - sends a single `SelectionQuery` to influxdb
        copy_database - copies whole database into a new one

        @deprecated
        update_row - updates values and tags of already saved data

    """

    @property
    def grafanaReader_name(self):
        return "GrafanaReader"

    @property
    def version(self):
        """Version of the influxdb client"""
        return self.__version

    @property
    def use_ssl(self):
        """Whether the client should use ssl"""
        return self.__use_ssl

    @property
    def database(self):
        """Database with predef tables. Access by [tablename] to gain instance"""
        return self.__database

    __insert_buffer: Dict[Table, List[InsertQuery]] = {}
    """used to send all insert-queries at once. Multiple Insert-queries per table"""

    __query_max_batch_size = 10000
    """Maximum amount of queries sent at once to the influxdb. Recommended is 5000-10000.
    Queries automatically abort after 5 sec, but still try to write afterwards."""

    __fallback_max_batch_size = 500
    """Batch size on write requests once the first request failed to avoid the 5 second request limit"""

    def __init__(self, config_file: Dict[str, Any]):
        """Initialize the influx client from a config dict. Call `connect` before using the client.

        Arguments:
            auth_influx {dictionary} -- Dictionary with required parameters.

        Raises:
            ValueError: Raises a ValueError if any important parameters are missing within the file
        """
        if(not config_file):
            raise ValueError("A config file is required to setup the InfluxDB client.")

        auth_influx = SppUtils.get_cfg_params(param_dict=config_file, param_name="influxDB")
        if(not isinstance(auth_influx, dict)):
            raise ValueError("The InfluxDB config is corrupted within the file: Needs to be a dictionary.")

        try:
            self.__user: str = auth_influx["username"]
            self.__password: str = auth_influx["password"]
            self.__use_ssl: bool = auth_influx["ssl"]
            if(self.__use_ssl):
                self.__verify_ssl: bool = auth_influx["verify_ssl"]
            else:
                self.__verify_ssl = False
            self.__port: int = auth_influx["srv_port"]
            self.__address: str = auth_influx["srv_address"]
            self.__database: Database = Database(auth_influx["dbName"])

            # Create table definitions in code
            df.Definitions.add_table_definitions(self.database)

            self.__metrics_table: Table = self.database['influx_metrics']
        except KeyError as key_error:
            ExceptionUtils.exception_info(error=key_error)
            raise ValueError(
                "Missing Influx-Config arg", str(key_error))

        # declare for later
        self.__client: InfluxDBClient
        self.__version: str

    def connect(self) -> None:
        """Connect client to remote server. Call this before using any other methods.

        Raises:
            ValueError: Login failed
        """
        try:
            self.__client: InfluxDBClient = InfluxDBClient(
                host=self.__address,
                port=self.__port,
                username=self.__user,
                password=self.__password,
                ssl=self.__use_ssl,
                verify_ssl=self.__verify_ssl,
                timeout=20
            )

            # ping to make sure connection works
            self.__version: str = self.__client.ping()
            LOGGER.debug(f"Connected to influxdb, version: {self.__version}")

            self.setup_db(self.database.name)

            self.check_grant_user(self.grafanaReader_name, "READ")

            # check for existing retention policies and continuous queries in the influxdb
            self.check_create_rp(self.database.name)
            self.check_create_cq()
            self.flush_insert_buffer()

        except (ValueError, InfluxDBClientError, InfluxDBServerError, requests.exceptions.ConnectionError) as error: # type: ignore
            ExceptionUtils.exception_info(error=error) # type: ignore
            raise ValueError("Login into influxdb failed")

    def disconnect(self) -> None:
        """Disconnects client from remote server and finally flushes buffer."""
        LOGGER.debug("disconnecting Influx database")

        # Double send to make sure all metrics are send
        try:
            self.flush_insert_buffer()
            self.flush_insert_buffer()
        except ValueError as error:
            ExceptionUtils.exception_info(
                error=error,
                extra_message="Failed to flush buffer on logout, possible data loss")
        self.__client.close()
        self.__client = None # unset client

    def setup_db(self, database_name: str) -> None:
        if(not self.__client):
            raise ValueError("Tried to setup DB while client wasn't connected.")
        try:
            # Check if database already exits -> nothing to do
            db_list: List[Dict[str, str]] = self.__client.get_list_database()
            if(database_name in map(lambda entry: entry["name"], db_list)):
                LOGGER.debug(f"SetupDB: DB {database_name} already exits")
                # nothing to do since db exits
                return

            # create db, nothing happens if it already exists
            self.__client.create_database(database_name)
            LOGGER.info(f"> Created database {database_name}")

            # Check if GrafanaReader exists and give him permissions
            user_list: List[Dict[str, str]] = self.__client.get_list_users()
            if(self.grafanaReader_name not in map(lambda entry: entry["user"], user_list)):
                LOGGER.debug("SetupDB: Grafana User does not exits")
                ExceptionUtils.error_message(f"WARNING: User '{self.grafanaReader_name}' does not exist")
                # nothing to do since GrafanaReader does not exit
                return
            self.__client.grant_privilege("read", database_name, self.grafanaReader_name)
            LOGGER.info(f"> Granted read privileges for user {self.grafanaReader_name} on db {database_name}")


        except (ValueError, InfluxDBClientError, InfluxDBServerError, requests.exceptions.ConnectionError) as error: # type: ignore
            ExceptionUtils.exception_info(error=error) # type: ignore
            raise ValueError(f"Setup of the new database failed. Maybe the connection failed or the user '{self.__user}' has no admin privileges.")


    def create_rp(self, retention_policy: RetentionPolicy, database_name: Optional[str] = None) -> None:
        """Generates a new retention policy for the given database

        The database name is not taken from the rp to allow creating rps for a different than default database.
        To simplify /straighten the code changes to the definitions.py class might be recommended, changing classmethods into regular methods

        Args:
            retention_policy (RetentionPolicy): Instance of the retention policy, database is ignored if database_name is given
            database_name (str): name of the database to add the rp to, ignoring the db of the rp
        """

        if not database_name:
            database_name = retention_policy.database.name

        self.__client.create_retention_policy( # type: ignore
                    name=retention_policy.name,
                    duration=retention_policy.duration,
                    replication=retention_policy.replication,
                    database=database_name,
                    default=retention_policy.default,
                    shard_duration=retention_policy.shard_duration
                )

    def drop_rp(self, rp_name: str, database_name: Optional[str] = None) -> None:
        """Drops a retention policy for the given database, if it exists

        The database name is optional to allow deleting rps for a different than the default database.

        Args:
            rp_name (str): name of the retention policy
            database_name (str): name of the database to remove the rp from, defaults to the current influxclient used one.
        """

        if not database_name:
            database_name = self.database.name

        results: List[Dict[str, Any]] = self.__client.get_list_retention_policies(database_name)
        if not any(filter(lambda rp_dict: rp_dict['name']==rp_name, results)):
            return

        self.__client.drop_retention_policy( # type: ignore
                name=rp_name,
                database=database_name
            )


    def check_create_rp(self, database_name: str) -> None:
        """Checks if any retention policy needs to be altered or added

        Raises:
            ValueError: Multiple RP declared as default
            ValueError: Check failed due Database error
        """
        try:
            results: List[Dict[str, Any]] = self.__client.get_list_retention_policies(database_name)

            rp_dict: Dict[str, Dict[str, Any]] = {}
            for result in results:
                rp_dict[result['name']] = result

            add_rp_list: List[RetentionPolicy] = []
            alter_rp_list: List[RetentionPolicy] = []
            default_used = False

            for retention_policy in self.database.retention_policies:
                # make sure only one RP is default
                if(retention_policy.default):
                    if(default_used):
                        raise ValueError("multiple Retention Policies are declared as default")
                    default_used = True

                result_rp = rp_dict.get(retention_policy.name, None)
                if(result_rp is None):
                    add_rp_list.append(retention_policy)
                elif(result_rp != retention_policy.to_dict()):
                    alter_rp_list.append(retention_policy)
                # else: all good
            LOGGER.debug(f"missing {len(add_rp_list)} RP's. Adding {add_rp_list}")
            for retention_policy in add_rp_list:
                # the database name is not taken from the rp to allow creating rps for a different than default database
                self.create_rp(
                    retention_policy=retention_policy,
                    database_name=database_name)
                self.__client.create_retention_policy( # type: ignore
                    name=retention_policy.name,
                    duration=retention_policy.duration,
                    replication=retention_policy.replication,
                    # the database name is not taken from the rp to allow creating rps for a different than default database
                    database=database_name,
                    default=retention_policy.default,
                    shard_duration=retention_policy.shard_duration
                )
            LOGGER.debug(f"altering {len(add_rp_list)} RP's. altering {add_rp_list}")
            for retention_policy in alter_rp_list:
                self.__client.alter_retention_policy( # type: ignore
                    name=retention_policy.name,
                    duration=retention_policy.duration,
                    replication=retention_policy.replication,
                    database=database_name,
                    default=retention_policy.default,
                    shard_duration=retention_policy.shard_duration
                )

        except (ValueError, InfluxDBClientError, InfluxDBServerError, requests.exceptions.ConnectionError) as error: # type: ignore
            ExceptionUtils.exception_info(error=error) # type: ignore
            raise ValueError("Retention Policies check failed")

    def check_create_cq(self) -> None:
        """Checks if any continuous query needs to be altered or added

        Raises:
            ValueError: Check failed due Database error
        """
        try:
            # returns a list of dictionaries with db name as key
            # inside the dicts there is a list of each cq
            # the cqs are displayed as a 2 elem dict: 'name' and 'query'
            results: List[Dict[str, List[Dict[str, str]]]] = self.__client.get_list_continuous_queries()

            # get the cq's of the correct db
            # list of 2-elem cqs: 'name' and 'query'
            cq_result_list: List[Dict[str, str]] = next(
                (cq.get(self.database.name, []) for cq in results
                # only if matches the db name
                if cq.get(self.database.name, False)), [])

            # save all results into a dict for quicker accessing afterwards
            cq_result_dict: Dict[str, str] = {}
            for cq_result in cq_result_list:
                cq_result_dict[cq_result['name']] = cq_result['query']

            # queries which need to be added
            add_cq_list: List[ContinuousQuery] = []
            # queries to be deleted (no alter possible): save name only
            drop_cq_list: List[str] = []

            # check for each cq if it needs to be 1. dropped and 2. added
            for continuous_query in self.database.continuous_queries:

                result_cq = cq_result_dict.get(continuous_query.name, None)
                if(result_cq is None):
                    add_cq_list.append(continuous_query)
                elif(result_cq != continuous_query.to_query()):
                    LOGGER.debug(f"result_cq: {result_cq}")
                    LOGGER.debug(f"desired_cq: {continuous_query.to_query()}")
                    # delete result cq and then add it new
                    # save name only
                    drop_cq_list.append(continuous_query.name)
                    add_cq_list.append(continuous_query)
                # else: all good

            LOGGER.debug(f"deleting {len(drop_cq_list)} CQ's: {drop_cq_list}")
            # alter not possible -> drop and readd
            for query_name in drop_cq_list:
                self.__client.drop_continuous_query(  # type: ignore
                    name=query_name,
                    database=self.database.name
                )

            # adding new / altered CQ's
            LOGGER.debug(f"adding {len(add_cq_list)} CQ's. adding {add_cq_list}")
            for continuous_query in add_cq_list:
                self.__client.create_continuous_query( # type: ignore
                    name=continuous_query.name,
                    select=continuous_query.select,
                    database=continuous_query.database.name,
                    resample_opts=continuous_query.resample_opts)


        except (ValueError, InfluxDBClientError, InfluxDBServerError, requests.exceptions.ConnectionError) as error: # type: ignore
            ExceptionUtils.exception_info(error=error) # type: ignore
            raise ValueError("Continuous Query check failed")

    def check_grant_user(self, username: str, permission: str):
        """Checks and Grants the permissions for a user to match at least the required permission or a higher one.

        Warns if user does not exists. Grants permission if current permissions to not fullfil the requirement.
        This method does not abort if the check or grant was unsuccessful!

        Args:
            username (str): name of the user to be checked
            permission (str): permissions to be granted: READ, WRITE, ALL

        Raises:
            ValueError: No username provided
            ValueError: no permissions provided
        """
        try:
            LOGGER.debug(f"Checking/Granting user {username} for {permission} permissions on db {self.database.name}.")
            if(not username):
                raise ValueError("checking/granting a user permissions require an username")
            if(not permission):
                raise ValueError("checking/granting a user permissions require a defined set of permissions")

            # Get all users to check for the required user
            user_list: List[Dict[str, Union[str, bool]]] = self.__client.get_list_users()
            LOGGER.debug(f"Returned list of users: {user_list}")

            # get the wanted user if it exists. Default value to not throw an error.
            user_dict = next(filter(lambda user_dict: user_dict['user'] == username , user_list), None)
            LOGGER.debug(f"Found user: {user_dict}")

            # SPPMon should not create a user since then a default password will be used
            # It is very unlikely that this one is getting changed and therefore a risk of leaking data.
            if(not user_dict):
                ExceptionUtils.error_message(f"The user '{username}' does not exist. Please create it according to the documentation.")
                return # not abort SPPMon, only minor error

            if(user_dict['admin']):
                LOGGER.debug(f"{username} is already admin. Finished check")
                return

            # get privileges of user to check if he already has matching permissions
            db_privileges: List[Dict[str, str]] = self.__client.get_list_privileges(username)
            LOGGER.debug(db_privileges)

            # check for existing privileges
            db_entry = next(filter(lambda entry_dict: entry_dict['database'] == self.database.name , db_privileges), None)
            # there must be permissions of either wanted permission or higher (all)
            if(db_entry and (db_entry['privilege'] == permission or db_entry['privilege'] == "ALL")):
                LOGGER.debug(f"{username} has already correct permissions. Finished check")
                return

            # else give permissions
            LOGGER.info(f"Permissions missing for user {username}, granting {permission} permissions.")
            self.__client.grant_privilege(permission, self.database.name, username)

            LOGGER.debug(f"Granted permissions to {username}")


        except (ValueError, InfluxDBClientError, InfluxDBServerError, requests.exceptions.ConnectionError) as error: # type: ignore
            ExceptionUtils.exception_info(error=error, extra_message="User check failed for user {username} with permissions {permission} on db {self.database.name}") # type: ignore

    def copy_database(self, new_database_name: str) -> None:
        if(not new_database_name):
            raise ValueError("copy_database requires a new database name to copy to.")

        # Program information
        LOGGER.info(f"Copy Database: transferring the data from database {self.database.name} into {new_database_name}.")
        LOGGER.info("> Info: This also includes all data from `autogen` retention policy, sorted into the correct retention policies.")

        # create db, nothing happens if it already exists
        LOGGER.info("> Creating the new database if it didn't already exist")
        self.setup_db(new_database_name)

        # check for existing retention policies and continuous queries in the influxdb
        LOGGER.info(">> Checking and creating retention policies for the new database. Ignoring continuous queries.")
        self.check_create_rp(new_database_name)
        # self.check_create_cq() # Note: Not possible due full qualified statements. this would also not truly conserve the data

        LOGGER.info("> Computing queries to be send to the server.")
        queries: List[str] = []
        # copies all tables into their respective duplicate, data over RP-time will be dropped.
        for table in self.database.tables.values():
            autogen_query_str = f"SELECT * INTO {new_database_name}.{table.retention_policy.name}.{table.name} FROM {table.database.name}.autogen.{table.name} WHERE time > now() - {table.retention_policy.duration} GROUP BY *"
            queries.append(autogen_query_str)

            rp_query_str = f"SELECT * INTO {new_database_name}.{table.retention_policy.name}.{table.name} FROM {table} WHERE time > now() - {table.retention_policy.duration} GROUP BY *"
            queries.append(rp_query_str)

        # Compute data with a timestamp over the initial RP-duration into other RP's.
        for con_query in self.database.continuous_queries:
            cq_query_str: str = con_query.to_query()

            # replacing the rp inside of the toString representation
            # this is easier than individual matching/code replacement
            # Not every database name should be replaced
            match = re.search(r"BEGIN(.*(INTO\s+(.+)\..+\..+)\s+(FROM\s+\w+\.(\w+)\.\w+)(?:\s+WHERE\s+(.+))?\s+GROUP BY.*)END", cq_query_str)
            if(not match):
                raise ValueError(f">> error when matching continuos query {cq_query_str}. Aborting.")

            full_match = match.group(1)
            into_clause = match.group(2)
            old_database_str = match.group(3)
            from_clause = match.group(4)
            from_rp = match.group(5)
            where_clause = match.group(6)

            # Add timelimit in where clause to prevent massive truncation due the retention-policy time limit
            new_full_match = full_match
            if(not con_query.select_query or con_query.select_query.into_table is None):
                    ExceptionUtils.error_message(f">> Into table of continuos query is none. Adjust query manually! {full_match}")
            elif(con_query.select_query.into_table.retention_policy.duration != '0s'):
                    # Caution: if truncation of a query is above 10.000 it won't be saved!
                    clause = f"time > now() - {con_query.select_query.into_table.retention_policy.duration}"
                    if(where_clause):
                        new_full_match = new_full_match.replace(where_clause, where_clause + " AND " + clause)
                    else:
                        new_full_match = new_full_match.replace(from_clause, from_clause + " WHERE " + clause)

            # replace old dbname with new one
            new_into_clause = into_clause.replace(old_database_str, new_database_name)
            new_full_match = new_full_match.replace(into_clause, new_into_clause)

            # case 1: keep retention policy
            queries.append(new_full_match)

            # case 2: autogen as from RP
            new_from_clause = from_clause.replace(from_rp, "autogen")
            auto_gen_match = new_full_match.replace(from_clause, new_from_clause)
            queries.append(auto_gen_match)

        LOGGER.info("> Finished Computing, starting to send.")

        # how many lines were transferred
        line_count: int = 0
        # how often was a query partially written, not line count!
        dropped_count: int = 0
        # how often was data dropped above the 10.000 limit?
        critical_drop: int = 0

        # print statistics
        # send time since last print
        send_time_collection: float = 0
        # line count since last print
        line_collection: int = 0

        # disable timeout
        old_timeout = self.__client._timeout # type: ignore
        self.__client = InfluxDBClient(
            host=self.__address,
            port=self.__port,
            username=self.__user,
            password=self.__password,
            ssl=self.__use_ssl,
            verify_ssl=self.__verify_ssl,
            timeout=7200
        )
        # ping to make sure connection works
        version: str = self.__client.ping()
        LOGGER.info(f">> Connected to influxdb with new timeout of {self.__client._timeout}, version: {version}") # type: ignore
        LOGGER.info(">> Starting transfer of data")
        i = 0

        for query in queries:
            try:
                start_time = time.perf_counter()
                # seems like you may only send one SELECT INTO at once via python
                result = self.__client.query( # type: ignore
                    query=query, epoch='s', database=self.database.name)
                end_time = time.perf_counter()

                # count lines written, max 1
                for result in result.get_points(): # type: ignore
                    i += 1
                    line_count += result["written"]

                    # print statistics
                    send_time_collection += end_time-start_time
                    line_collection += result["written"]

                    # Print only all 10 queries or if the collected send time is too high
                    if(i % 10 == 0 or send_time_collection >= 2):
                        LOGGER.info(f'query {i}/{len(queries)}: {line_collection} new lines in {send_time_collection}s.')
                        line_collection = 0
                        send_time_collection = 0

            except InfluxDBClientError as error:
                # only raise if the error is unexpected
                if(re.search(f"partial write: points beyond retention policy dropped=10000", error.content)): # type: ignore
                    critical_drop += 1
                    raise ValueError(">> transfer of data failed, retry manually with a shorter WHERE-clause", query)
                if(re.search(f"partial write: points beyond retention policy dropped=", error.content)): # type: ignore
                    dropped_count += 1
                else:
                    ExceptionUtils.exception_info(error=error, extra_message=f">> transfer of data failed for query {query}")
                    critical_drop += 1

            except (InfluxDBServerError, requests.exceptions.ConnectionError) as error:
                ExceptionUtils.exception_info(error=error, extra_message=f">> transfer of data failed for query {query}")
                critical_drop += 1

        # reset timeout
        self.__client = InfluxDBClient( # type: ignore
            host=self.__address,
            port=self.__port,
            username=self.__user,
            password=self.__password,
            ssl=self.__use_ssl,
            verify_ssl=self.__verify_ssl,
            timeout=old_timeout
        )
        # ping to make sure connection works
        version: str = self.__client.ping()
        LOGGER.info(f">> Changed timeout of influxDB to old timeout of {self.__client._timeout}, version: {version}") # type: ignore

        LOGGER.info(f"> Total transferred {line_count} lines of results.")
        if(dropped_count):
            LOGGER.info(f"> WARNING: Could not count lines of {dropped_count} queries due an expected error. No need for manual action.")
        if(critical_drop):
            msg: str = (f"ERROR: Could not transfer data of {critical_drop} tables, check messages above to retry manually!\n"+
                        "Please send the query manually with a adjusted 'from table': '$database.autogen.tablename'\n "+
                        "Adjust other values as required. Drop due Retention Policy is 'OK' until 10.000.\n"+
                        "If the drop count reaches 10.000 you need to cut the query into smaller bits.")
            ExceptionUtils.error_message(msg)
        elif(line_count == 0):
            ExceptionUtils.error_message("ERROR: No data was transferred, make sure your database name is correct and the db is not empty.")
        else:
            LOGGER.info("Database copied successfully")



    def insert_dicts_to_buffer(self, table_name: str, list_with_dicts: List[Dict[str, Any]],
                               other_retention_policy: Optional[RetentionPolicy] = None) -> None:
        """Insert a list of dicts with data into influxdb. Splits according to table definition.

        It is highly recommended to define a table before in database_table.py. If not present, splits by type analysis.
        Important: Queries are only buffered, not sent. Call flush_insert_buffer to flush.
        All timestamps are changed into second precision

        Arguments:
            table_name {str} -- Name of the table to be inserted
            list_with_dicts {List[Dict[str, Any]]} -- List with dicts with colum name as key.

        Raises:
            ValueError: No list with dictionaries are given or of wrong type.
            ValueError: No table name is given
        """
        LOGGER.debug(f"Enter insert_dicts for table: {table_name}")
        if(list_with_dicts is None): # empty list is allowed
            raise ValueError("missing list with dictionaries in insert")
        if(not table_name):
            raise ValueError("table name needs to be set in insert")

        # Only insert of something is there to insert
        if(not list_with_dicts):
            LOGGER.debug("nothing to insert for table %s due empty list", table_name)
            return

        # get table instance
        table = self.database[table_name]

        if(other_retention_policy):
            table = Table(table.database, table.name, table.fields, table.tags, table.time_key, other_retention_policy)

        # Generate queries for each dict
        query_buffer = []
        for mydict in list_with_dicts:
            try:
                # split dict according to default tables
                (tags, values, timestamp) = table.split_by_table_def(mydict=mydict)

                if(isinstance(timestamp, str)):
                    timestamp = int(timestamp)
                # LOGGER.debug("%d %s %s %d",appendCount,tags,values,timestamp)

                # create query and append to query_buffer
                query_buffer.append(InsertQuery(table, values, tags, timestamp))
            except ValueError as err:
                ExceptionUtils.exception_info(error=err, extra_message="skipping single dict to insert")
                continue

        # extend existing inserts by new one and add to insert_buffer
        table_buffer = self.__insert_buffer.get(table, list())
        table_buffer.extend(query_buffer)
        self.__insert_buffer[table] = table_buffer
        LOGGER.debug("Appended %d items to the insert buffer", len(query_buffer))

        # safeguard to avoid memoryError
        if(len(self.__insert_buffer[table]) > 2 * self.__query_max_batch_size):
            self.flush_insert_buffer()

        LOGGER.debug(f"Exit insert_dicts for table: {table_name}")

    def flush_insert_buffer(self, fallback: bool = False) -> None:
        """Flushes the insert buffer, send queries to influxdb server.

        Sends in batches defined by `__batch_size` to reduce http overhead.
        Only send-statistics remain in buffer, flush again to send those too.
        Retries once into fallback mode if first request fails with modified settings.

        Keyword Arguments:
            fallback {bool} -- Whether to use fallback-options. Does not repeat on fallback (default: {False})

        Raises:
            ValueError: Critical: The query Buffer is None.
        """

        if(self.__insert_buffer is None):
            raise ValueError("query buffer is somehow None, this should never happen!")
        # Only send if there is something to send
        if(not self.__insert_buffer):
            return

        # pre-save the keys to avoid Runtime-Error due "dictionary keys changed during iteration"
        # happens due re-run changing insert_buffer
        insert_keys = list(self.__insert_buffer.keys())
        for table in insert_keys:
            # get empty in case the key isn't valid anymore (due fallback option)
            queries = list(map(lambda query: query.to_query(), self.__insert_buffer.get(table, [])))
            item_count = len(queries)
            if(item_count == 0):
                continue

            # stop time for send progress
            if(not fallback):
                batch_size = self.__query_max_batch_size
            else:
                batch_size = self.__fallback_max_batch_size

            re_send: bool = False
            error_msg: Optional[str] = None
            start_time = time.perf_counter()
            try:
                self.__client.write_points(
                    points=queries,
                    database=self.database.name,
                    retention_policy=table.retention_policy.name,
                    batch_size=batch_size,
                    time_precision='s', protocol='line')
                end_time = time.perf_counter()
            except InfluxDBClientError as error: # type: ignore
                match = re.match(r".*partial write:[\s\w]+=(\d+).*", error.content) # type: ignore

                if(match and int(match.group(1)) < batch_size):
                    # beyond 10.000 everything will be lost, below still written
                    # ignore this case, its unavoidable and doesn't change anything
                    pass
                elif(re.match(r".*partial write: unable to parse .*", error.content)): # type: ignore
                    # some messages are lost, other written
                    ExceptionUtils.exception_info(error=error,
                    extra_message=f"Some messages were lost when sending buffer for table {table.name}, but everything else should be OK")
                    error_msg = getattr(error, 'message', repr(error))
                else:
                    ExceptionUtils.exception_info(error=error,
                        extra_message=f"Client error when sending insert buffer for table {table.name}.")
                    error_msg = getattr(error, 'message', repr(error))
                    # re-try with a smaller batch size, unsure if this helps
                    re_send = True

            except (InfluxDBServerError, ConnectionError, requests.exceptions.ConnectionError) as error: # type: ignore
                ExceptionUtils.exception_info(error=error,
                    extra_message=f"Connection error when sending insert buffer for table {table.name}.")
                error_msg = getattr(error, 'message', repr(error))
                re_send = True

            # measure timing
            end_time = time.perf_counter()

            # clear the table which just got sent
            if(re_send and not fallback):
                ExceptionUtils.error_message("Trying to send influx buffer again with fallback options")
                self.flush_insert_buffer(fallback=True)

            # None to avoid key error if table is popped on fallback
            self.__insert_buffer.pop(table, None)

            # add metrics for the next sending process.
            # compute duration, metrics computed per batch
            self.__insert_metrics_to_buffer(
                Keyword.INSERT, table, end_time-start_time, item_count,
                error=error_msg)

    def __insert_metrics_to_buffer(self, keyword: Keyword, table_or_query: Union[Table, SelectionQuery],
                                   duration_s: float, item_count: int,
                                   error: Optional[str] = None) -> None:
        """Generates statistics of influx-requests and append them to be sent

        Arguments:
            keyword {Keyword} -- Kind of query.
            tables_count {dict} -- Tables send in this batch, key is table, value is count of items.
            duration_s {Optional[float]} -- Time needed to send the batch in seconds. None if a error occurred
            item_count {int} -- Amount of queries sent to the server

        Keyword Arguments:
            error {Optional[str]} -- Error message if an error occurred.

        Raises:
            ValueError: Any arg does not match the defined parameters or value is unsupported
        """
        # Arg checks
        if(list(filter(lambda arg: arg is None, [keyword, table_or_query, duration_s, item_count]))):
            raise ValueError("One of the insert metrics to influx args is None. This is not supported")

        if isinstance(table_or_query, SelectionQuery):
            table_name = f"InnerQuery to {table_or_query.table_or_query}"
        else:
            table_name = table_or_query.name
        query = InsertQuery(
            table=self.__metrics_table,
            fields={
                'error': error,
                # Calculating relative duration for this part of whole query
                'duration_ms':  duration_s*1000,
                'item_count':   item_count,
            },
            tags={
                'keyword':      keyword,
                'tableName':    table_name,
            },
            time_stamp=SppUtils.get_actual_time_sec()
        )
        old_queries = self.__insert_buffer.get(self.__metrics_table, [])
        old_queries.append(query)
        self.__insert_buffer[self.__metrics_table] = old_queries

    def update_row(self, table_name: str, tag_dic: Dict[str, str] = None,
                   field_dic: Dict[str, Union[str, int, float, bool]] = None, where_str: str = None):
        """DEPRECATED: Updates a row of the given table by given tag and field dict.

        Applies on multiple rows if `where` clause is fulfilled.
        Updates row by row, causing a high spike in call times: 3 Influx-query's per call.
        Simple overwrite if no tag is changed, otherwise deletes old row first.
        Possible to add new values to old records.
        No replacement method available yet, check jobLogs (jobs update) how to query, then delete / update all at once.

        Arguments:
            table_name {str} -- name of table to be updated

        Keyword Arguments:
            tag_dic {Dict[str, str]} -- new tag values (default: {None})
            field_dic {Dict[str, Union[str, int, float, bool]]} -- new field values (default: {None})
            where_str {str} -- clause which needs to be fulfilled, any matched rows are updated (default: {None})

        Raises:
            ValueError: No table name is given.
            ValueError: Neither tag nor field dic given.
        """
        # None or empty checks
        if(not table_name):
            raise ValueError("Need table_name to update row")
        if(not tag_dic and not field_dic):
            raise ValueError(f"Need either new field or tag to update row in table {table_name}")

        keyword = Keyword.SELECT
        table = self.database[table_name]
        query = SelectionQuery(
            keyword=keyword,
            fields=['*'],
            table_or_query=table,
            where_str=where_str
            )

        result = self.send_selection_query(query) # type: ignore
        result_list: List[Dict[str, Union[int, float, bool, str]]] = list(result.get_points()) # type: ignore

        # no results found
        if(not result_list):
            return

        # split between remove and insert
        # if tag are replaced it is needed to remove the old row first
        if(tag_dic):
            # WHERE clause reused
            keyword = Keyword.DELETE
            table = self.database[table_name]
            query = SelectionQuery(
                keyword=keyword,
                table_or_query=table,
                where_str=where_str
                )

            self.send_selection_query(query)

        insert_list = []
        for row in result_list:
            if(tag_dic):
                for (key, value) in tag_dic.items():
                    row[key] = value
            if(field_dic):
                for (key, value) in field_dic.items():
                    row[key] = value
            insert_list.append(row)

        # default insert method
        self.insert_dicts_to_buffer(table_name, insert_list)


    def send_selection_query(self, query: SelectionQuery) -> ResultSet: # type: ignore
        """Sends a single `SELECT` or `DELETE` query to influx server.

        Arguments:
            query {Selection_Query} -- Query which should be executed

        Raises:
            ValueError: no SelectionQuery is given.
            ValueError: Execution of the SelectionQuery failed.

        Returns:
            ResultSet -- Result of the Query, Empty if `DELETE`
        """
        if(not query or not isinstance(query, SelectionQuery)):
            raise ValueError("a selection query must be given")

        # check if any buffered table is selected, flushes buffer
        if(query.table_or_query in self.__insert_buffer):
            self.flush_insert_buffer()

        # Convert queries to strings
        query_str = query.to_query()

        start_time = time.perf_counter()
        # Send queries
        try:
            result = self.__client.query( # type: ignore
                query=query_str, epoch='s', database=self.database.name)

        except (InfluxDBServerError, InfluxDBClientError) as err:
            ExceptionUtils.exception_info(error=err)
            raise ValueError("Error when sending select statement")

        end_time = time.perf_counter()

        # if nothing is returned add count = 0 and table
        # also possible by `list(result.get_points())`, but that is lot of compute action
        if(result):
            length = len(result.raw['series'][0]['values']) # type: ignore
        else:
            length = 0

        self.__insert_metrics_to_buffer(query.keyword, query.table_or_query, end_time-start_time, length)

        return result # type: ignore
