#!/usr/bin/env python
# coding: utf-8


import mysql.connector


class DatabaseHelper:
    def __init__(self, host, user, passwd, database):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.database = database
        self.conn = None
        self.cursor = None

    """
        create connection
    """

    def connect(self):
        self.conn = mysql.connector.connect(
            host=self.host, user=self.user, passwd=self.passwd, database=self.database
        )

    """
        disconnect
    """

    def disconnect(self):
        if self.conn is not None:
            self.conn.close()

    """
        create cursor
    """

    def getCursor(self, dictionary=False):
        if self.conn is None:
            self.connect()

        self.cursor = self.conn.cursor(dictionary=dictionary)

        return self.cursor

    def execute(self, sql, val):
        self.cursor.execute(sql, val)
        self.conn.commit()

    def query(self, sql):
        self.cursor.execute(sql)

        # Fetch all rows from the result set
        results = self.cursor.fetchall()

        return results


class JobStatusEnum:
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
