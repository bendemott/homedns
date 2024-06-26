import ipaddress
import sqlite3
import logging
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ipaddress import ip_address, IPv4Address, IPv6Address
import time
from datetime import datetime
from typing import Iterator, Iterable

from twisted.names import dns
from twisted.names.dns import IRecord, Record_A, Record_AAAA, Record_MX, Record_CNAME, Record_NS, Record_SOA
import threading

from tabulate import tabulate


__all__ = ['DnsRecordData', 'HostnameAndRecord', 'AddressAndRecord', 'IRecordStorage', 'SqliteStorage']

from twisted.names.error import DNSServerError, DNSNotImplementedError


@dataclass
class DnsRecordData:
    record: Record_A | Record_CNAME | Record_MX | Record_AAAA
    modified: datetime


@dataclass
class HostnameAndRecord(DnsRecordData):
    hostname: str


@dataclass
class AddressAndRecord(DnsRecordData):
    address: IPv4Address | IPv6Address


class IRecordStorage(ABC):

    RECORD_MAP = {
        dns.A: Record_A,
        dns.AAAA: Record_AAAA,
        dns.CNAME: Record_CNAME,
        dns.MX: Record_MX,
        dns.SOA: Record_SOA,
        dns.NS: Record_NS
    }
    RECORD_CLASSES = RECORD_MAP.values()
    RECORD_CLASS_NAMES = {cls.__name__: cls for cls in RECORD_CLASSES}

    @abstractmethod
    def name_search(self, hostname: str, record_types: int | Iterable[int] = None) -> Iterator[HostnameAndRecord]:
        pass

    @abstractmethod
    def address_search(self, address: str) -> Iterator[AddressAndRecord]:
        pass

    @abstractmethod
    def get_record_by_hostname(self, fqdn: str, record_type: int):
        pass

    @abstractmethod
    def delete_record_by_hostname(self, fqdn: str, record_type: int) -> int:
        pass

    @abstractmethod
    def update_record(self, record: IRecord, fqdn: str):
        """
        Replaces all records associated with `fqdn` with this record

        :param record: dns record
        :param fqdn: fully qualified domain name (the name associated with this record)
        """
        pass

    @abstractmethod
    def create_record(self, record: IRecord, fqdn: str):
        """
        Adds the record to the record database, and associates it with the domain fqdn

        :param record: dns record
        :param fqdn: fully qualified domain name (the name associated with this record)
        """
        pass


class SqliteStorage(IRecordStorage):
    MAX_RETRIES = 5
    RECORDS_TABLE = 'dns_records'
    RECORDS_DDL = textwrap.dedent(f"""
        CREATE TABLE {RECORDS_TABLE} (
            type TEXT,
            fqdn TEXT,
            alias TEXT,
            address TEXT,
            ttl INTEGER,
            priority INTEGER,
            updated DATETIME
        )
    """)
    RECORDS_INDEX_DDL = f""

    def __init__(self, database):
        self.log = logging.getLogger(self.__class__.__qualname__)
        self._database = database
        self.mutex = threading.Lock()

    def initialize(self):
        # connect to sqlite
        # detect_types will convert types back to their python counterparts (datetime)
        # because we are allowing execution on multiple threads we must perform our own lock synchronization
        conn = sqlite3.connect(self._database, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, timeout=5, check_same_thread=False)

        # make sure the database is usable (it may be locked or in use by another process)
        # wait up to MAX_RETRIES seconds to acquire database from lock or another process
        with self.mutex:
            for retries in range(self.MAX_RETRIES):
                try:
                    conn.execute("SELECT * FROM sqlite_master LIMIT 1")
                except sqlite3.OperationalError as e:
                    # operational errors may be temporary
                    self.log.warning(f'{e} - retries: {retries}')
                    if retries + 1 >= self.MAX_RETRIES:
                        raise
                    time.sleep(1)

            # TODO figure out how to hash for comparison
            cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type=? AND name = ?",
                                  ('table', self.RECORDS_TABLE))
            table = cursor.fetchone()
            dropped = False
            if table and table[1] != 'SQL':
                pass
                # table structure has changed, drop it so the program can use its current structure
                # self.log.warning(f'table DDL has changed, DROP TABLE {table[0]}') # TODO fix me
                #conn.execute(f'DROP TABLE {table[0]}')
                #conn.commit()
                #dropped = True

            if not table or dropped:
                conn.execute(self.RECORDS_DDL)
                conn.commit()

            return conn

    @classmethod
    def get_record_class(cls, class_name: str):
        """
        Given a class_name return the class object
        """
        try:
            return cls.RECORD_CLASS_NAMES[class_name]
        except KeyError:
            raise ValueError(f'Unsupported dns class: [{class_name}]')

    @staticmethod
    def construct_record(record_class: IRecord, ttl: int, alias: str = None, address: str = None, priority: int = None) \
            -> Record_A | Record_CNAME | Record_MX | Record_AAAA:
        if record_class == Record_A:
            return Record_A(address=address, ttl=ttl)
        elif record_class == Record_CNAME:
            return Record_CNAME(name=alias, ttl=ttl)
        elif record_class == Record_MX:
            return Record_MX(name=alias, priority=priority, ttl=ttl)
        elif record_class == Record_AAAA:
            return Record_AAAA(name=address, ttl=ttl)
        elif record_class == Record_NS:
            return Record_NS(name=alias, ttl=ttl)
        else:
            raise ValueError(f'unsupported record type: {record_class.__name__} [{record_class.TYPE}]')

    def name_search(self, hostname: str, record_types: int | Iterable[int] = None) -> list[HostnameAndRecord]:
        """
        Search for records by hostname, limit the search to `record_type`

        :param hostname: the hostname to search for
        :param record_types: a value like `dns.A`, `dns.CNAME`, `dns.MX`, OR a list of these values
        """
        if isinstance(record_types, int):
            record_types = [record_types]

        record_types = [r for r in record_types if r is not None]

        conn = self.initialize()

        hostname = hostname.lower()
        sql_args = [hostname]

        # query_type acts as a filter to control what record types are returned
        filter_cond = ''
        if record_types:
            tpl = ['?'] * len(record_types)
            tpl = ', '.join(tpl)
            filter_cond = f'AND type in ({tpl})'
            try:
                for rtype in record_types:
                    sql_args.append(self.RECORD_MAP[rtype].__name__)
            except KeyError as e:
                raise DNSNotImplementedError(f'Unsupported record type: [{dns.QUERY_TYPES.get(e.args[0], str(e))}]')

        records = []

        with self.mutex:
            cursor = conn.cursor()
            cursor = cursor.execute(f"SELECT type, fqdn, alias, address, ttl, priority, updated FROM "
                                    f"{self.RECORDS_TABLE} WHERE fqdn = ? {filter_cond}", sql_args)
            data = cursor.fetchall()

        cname_a_lookups = []
        for row in data:
            record_name, fqdn, alias, address, ttl, priority, updated = row

            record_class = SqliteStorage.get_record_class(record_name)
            record = SqliteStorage.construct_record(record_class, ttl=ttl, alias=alias, address=address, priority=priority)

            datum = HostnameAndRecord(record=record, modified=updated, hostname=fqdn)
            records.append(datum)

            # an A search returns cnames, and the A hostnames related to the cname
            if isinstance(record, Record_CNAME) and dns.A in record_types:
                cname_a_lookups.append(record.name.name.decode())

        for a_name in cname_a_lookups:
            records.extend(self.name_search(hostname=a_name, record_types=dns.A))

        return records

    def cname_search(self, cname: str) -> list[HostnameAndRecord]:
        """
        Find CNAME records by cname

        :param cname:
        :return:
        """
        conn = self.initialize()

        records = []

        with self.mutex:
            cursor = conn.execute(f"SELECT type, fqdn, alias, address, ttl, priority, updated FROM "
                                  f"{self.RECORDS_TABLE} WHERE alias = ? AND type = ?", [cname,
                                                                                                   Record_CNAME.__name__])
            data = cursor.fetchall()
        for row in data:
            record_type, fqdn, alias, address, ttl, priority, updated = row
            ttl = ttl if ttl > 0 else None

            record = Record_CNAME(alias, ttl)

            datum = HostnameAndRecord(record=record, modified=updated, hostname=fqdn)
            records.append(datum)

        return records

    def address_search(self, address: str) -> list[AddressAndRecord]:
        """
        Search by address field, address field is usually used for A record IP addresses
        """
        conn = self.initialize()

        records = []

        with self.mutex:
            cursor = conn.execute(f"SELECT type, fqdn, alias, address, ttl, priority, updated FROM "
                                  f"{self.RECORDS_TABLE} WHERE address = ?", [address])
            data = cursor.fetchall()
        for row in data:
            record_type, fqdn, alias, address, ttl, priority, updated = row
            ttl = ttl if ttl > 0 else None
            priority = priority or 0

            dns_class = SqliteStorage.get_record_class(record_type)
            record = SqliteStorage.create_record(dns_class, ttl, alias, address, priority)

            datum = AddressAndRecord(record=record, modified=updated, address=fqdn)
            records.append(datum)

        return records

    def update_record(self, record: IRecord, fqdn: str):
        """
        Replaces all records associated with `fqdn` with this record

        :param record:
        :param fqdn:
        :return:
        """
        conn = self.initialize()

        with self.mutex:
            record_type = record.__class__
            type_name = record_type.__name__
            assert (record.TYPE is not None)
            cursor = conn.cursor()

            updated = datetime.now()

            if record_type in (Record_A, Record_AAAA):
                # update hostname with new ip address
                cursor.execute(
                    f"""
                    UPDATE {self.RECORDS_TABLE}
                    SET
                        address = ?,
                        ttl = ?,
                        updated = ?
                    WHERE
                        type = ?
                        AND
                        fqdn = ?
                    """,
                    (str(ipaddress.ip_address(record.address)), record.ttl, updated, type_name, fqdn))

            elif record_type == Record_CNAME:
                # update the hostname that `alias` (cname) points to
                # alias is the CNAME
                # fqdn is the HOSTNAME cname redirects to
                cursor.execute(
                    f"""
                    UPDATE {self.RECORDS_TABLE}
                    SET
                        fqdn = ?,
                        ttl = ?,
                        updated = ?
                    WHERE
                        type = ?
                        AND
                        alias = ?
                    """,
                    (fqdn, record.ttl, updated, type_name, record.name.lower().decode()))

            elif record_type == Record_MX:
                # for a mx record
                #   fqdn is the domain to match the record against
                #   alias is the domain name of the mail server
                #   record.name holds the mx record
                # Update the hostname that `alias` points to
                cursor.execute(
                    f"""
                    UPDATE {self.RECORDS_TABLE}
                    SET
                        fqdn = ?,
                        ttl = ?,
                        updated = ?,
                        priority = ?
                    WHERE
                        type = ?
                        AND
                        alias = ?
                    """,
                    (fqdn, record.ttl, updated, record.priority, type_name, record.name.lower().decode()))
            else:
                raise ValueError(f'unsupported record type: {type_name} [{record_type.TYPE}]')

            conn.commit()

    def create_record(self, record: IRecord, fqdn: str):
        """
        Adds the record to the record database, and associates it with the domain fqdn

        :param record: dns record
        :param fqdn: fully qualified domain name (the name associated with this record)
        :return:
        """
        # add the record without replacing any existing records that match the fqdn
        return self._add(record, fqdn, False)

    def _add(self, record: IRecord, fqdn: str, replace: bool):
        """

        :param record:
        :param fqdn: required for CNAME, A, AAAA, MX records
        :return:
        """
        conn = self.initialize()

        with self.mutex:
            record_type = record.__class__
            type_name = record_type.__name__
            assert (record.TYPE is not None)
            fqdn = fqdn.lower()  # domain names are case-insensitive
            cursor = conn.cursor()

            updated = datetime.now()

            if replace:
                cursor.execute(f"DELETE FROM {self.RECORDS_TABLE} WHERE type = ? AND fqdn = ?", (type_name, fqdn))
                conn.commit()

            if record_type in (Record_A, Record_AAAA):
                # insert an A record
                cursor.execute(f"INSERT INTO {self.RECORDS_TABLE} (type, fqdn, address, ttl, updated) VALUES(?, ?, ?, ?, ?)",
                               (type_name, fqdn, str(ipaddress.ip_address(record.address)), record.ttl, updated))

            elif record_type == Record_CNAME:
                #  CNAME record for www.example.com pointing to example.com
                # fqdn in this case is `www.example.com` (the name the record is known by)
                # and `name` is `example.com` (the alias)
                cursor.execute(f"INSERT INTO {self.RECORDS_TABLE} (type, fqdn, alias, ttl, updated) VALUES(?, ?, ?, ?, ?)",
                               (type_name, fqdn, record.name.name.decode(), record.ttl, updated))

            elif record_type == Record_MX:
                # for a mx record
                #   fqdn is the domain to match the record against
                #   alias is the domain name of the mail server
                cursor.execute(f"INSERT INTO {self.RECORDS_TABLE} (type, fqdn, alias, priority, ttl, updated) VALUES(?, ?, ?, ?, ?, ?)",
                               (type_name, fqdn, record.name.name.decode(), record.priority, record.ttl, updated))
            else:
                raise ValueError(f'unsupported record type: {type_name} [{record_type.TYPE}]')

            conn.commit()

    def get_record_by_hostname(self, fqdn: str, record_type: int) -> list[HostnameAndRecord]:
        """
        Retrieve a record by fqdn field (hostname)
        :param fqdn: The domain name to search for
        :param record_type: A constant from `dns`... `dns.A` etc.
        """
        return self.name_search(hostname=fqdn, record_types=record_type)

    def delete_record_by_hostname(self, fqdn: str, record_type: int) -> int:
        """
        Delete any record of the given type that `fqdn` matches

        :param fqdn: The domain name to delete records for
        :record_type: the type of record to delete (required)
        :returns: Number of records deleted
        """
        if record_type not in dns.QUERY_TYPES:
            raise ValueError(f'not a valid record type constant: {record_type}')

        conn = self.initialize()

        type_name = self.RECORD_MAP[record_type].__name__

        with self.mutex:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.RECORDS_TABLE} WHERE type = ? AND fqdn = ?",
                           (type_name, fqdn))
            conn.commit()

            return cursor.rowcount

    def log_table(self):
        """
        Record in the log the contents of the records table
        """
        conn = self.initialize()

        with self.mutex:
            cursor = conn.execute(f"SELECT type, fqdn, alias, address, updated FROM {self.RECORDS_TABLE}")
            records = cursor.fetchall()
            self.log.warning(f'logging table: {self.RECORDS_TABLE}, rows: [{len(records)}]')
            columns = [d[0] for d in cursor.description]
            self.log.warning(tabulate(records, headers=columns, showindex=True))

