#!/usr/bin/env python
# coding: utf-8


from tornado.web import RequestHandler, Application, HTTPError, MissingArgumentError
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
import tornado
import logging
import configparser
import json
import requests
from subprocess import Popen, PIPE, CalledProcessError
import tempfile
import os

import pika
import sys

import uuid
from datetime import datetime, timedelta

from database import DatabaseHelper, JobStatusEnum

from loggingutil import LoggingUtil

import ssl
import pandas as pd


ENV = ""


# ## Definition of Listeners/Endpoints


class SyncSDSFilePullHandler(RequestHandler):
    def initialize(
        self,
        hsi_bin_path,
        hsi_keytab_path,
        hsi_user,
        firewall_flag,
        timeout_in_secs,
        logger,
    ):
        self.hsi_bin_path = hsi_bin_path
        self.hsi_keytab_path = hsi_keytab_path
        self.hsi_user = hsi_user
        self.firewall_flag = firewall_flag
        self.timeout_in_secs = timeout_in_secs
        self.logger = logger

    def set_default_headers(self):
        # need to set following attributes for a localhost dev environment to enable CORS requests
        # otherwise, should be disabled for a production like env

        #         global ENV
        #         if ENV == "dev":
        #             self.set_header("Access-Control-Allow-Origin", "*")
        #             self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        #             self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

        pass

    def get(self):
        try:
            sda_file_path = self.get_argument("p")
            print(sda_file_path)

            #             sda_filepath = '/path/to/file/on/sda'
            #             resp = {
            #                 'hsi_bin_path': self.hsi_bin_path,
            #                 'sda_filepath': sda_filepath
            #             }
            #             self.write(json.dumps(resp))

            with tempfile.TemporaryDirectory() as tmpdirname:
                print("created temporary directory", tmpdirname)

                basename = os.path.basename(sda_file_path)

                localfile = os.path.join(tmpdirname, basename)

                cmd_part1 = [
                    self.hsi_bin_path,
                    "-d2",
                    "-A",
                    "keytab",
                    "-k",
                    self.hsi_keytab_path,
                    "-l",
                    self.hsi_user,
                ]

                if self.firewall_flag:
                    cmd_part2 = [
                        '"firewall -on; get {} : {}"'.format(localfile, sda_file_path)
                    ]
                else:
                    cmd_part2 = ["get", localfile, ":", sda_file_path]

                cmd = cmd_part1 + cmd_part2
                cmdStr = " ".join(cmd)
                print("cmd to execute: {}".format(cmdStr))

                p = Popen(cmdStr, shell=True)

                p.communicate(timeout=self.timeout_in_secs)
                print("Done writing!")
                print("return code: {}".format(p.returncode))
                print("args: {}".format(p.args))

                if p.returncode != 0:
                    raise CalledProcessError(p.returncode, p.args)
                else:
                    buf_size = 4096

                    self.set_header("Content-Type", "application/octet-stream")
                    self.set_header(
                        "Content-Disposition", "attachment; filename=" + basename
                    )

                    flushSize = 10000
                    dataSize = 0
                    with open(localfile, "rb") as f:
                        data = f.read(buf_size)
                        while data:
                            self.write(data)
                            dataSize += buf_size
                            if dataSize >= flushSize:
                                self.flush()
                                dataSize = 0
                            data = f.read(buf_size)

                    self.finish()

        except MissingArgumentError as me:
            raise HTTPError(status_code=400, log_message=str(me))
        except CalledProcessError as pe:
            raise HTTPError(status_code=400, log_message=str(pe))
        except Exception as e:
            raise HTTPError(status_code=400, log_message=str(e))

    def post(self):
        #         try:
        #             data = tornado.escape.json_decode(self.request.body)
        #             sda_filepath = data['sda_filepath']

        #             resp = {}
        #             self.write(json.dumps(resp))

        #         except Exception as e:
        #             raise HTTPError(status_code=400, log_message=str(e))

        pass


class AsyncSDSFilePullHandler(RequestHandler):
    def initialize(
        self,
        message_broker_host,
        message_broker_port,
        work_queue,
        minimum_job_interval,
        black_list,
        db_helper,
        job_table,
        logger,
    ):
        self.message_broker_host = message_broker_host
        self.message_broker_port = message_broker_port
        self.work_queue = work_queue

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.message_broker_host, port=self.message_broker_port
            )
        )

        self.channel = self.connection.channel()

        self.channel.queue_declare(queue=self.work_queue, durable=True)

        self.black_list = black_list
        self.db_helper = db_helper
        self.job_table = job_table
        self.minimum_job_interval = minimum_job_interval

        self.logger = logger

    def set_default_headers(self):
        pass

    def get(self):
        logger = self.logger

        try:
            # get passed parameters
            sda_file_path = self.get_argument("p")
            user_email_addr = self.get_argument("uid")

            if user_email_addr in self.black_list:
                logger.info(f"{user_email_addr} is in black list, skip request")
                # send http response
                ackMsg = """Your request cannot be fulfilled since your email address is in deny list, please contact RDS admin if you think you are wrongly put on this list."""
                resp = {"Warning": ackMsg}

                self.write(json.dumps(resp))
                self.finish()

                return

            #             print('sda file path: {}'.format(sda_file_path))
            #             print('user email: {}'.format(user_email_addr))

            # get request source id
            remote_ip = (
                self.request.headers.get("X-Real-IP")
                or self.request.headers.get("X-Forwarded-For")
                or self.request.remote_ip
            )

            job_id = uuid.uuid1()
            job_id = str(job_id)
            job_created_datetime = datetime.now()
            job_created_datetime_str = job_created_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            job_size = None
            download_url = None

            logger.info(
                "Received job request for file: {}, from user: {}, with source ip: {}, assigned jobid: {}".format(
                    sda_file_path, user_email_addr, remote_ip, job_id
                )
            )

            #            logger.debug(f'X-Real-IP: {self.request.headers.get("X-Real-IP")}')
            #            logger.debug(f'X-Forwarded-For: {self.request.headers.get("X-Forwarded-For")}')
            #            logger.debug(f'remote_ip: {self.request.remote_ip}')

            # before composing a task, we need to check if a request for same collection item already exist within the same job minimum interval range
            validRequest = True

            sql = f"""SELECT dateCreated FROM {self.job_table} WHERE email = "{user_email_addr}" AND collection = "{os.path.basename(sda_file_path)}" AND jobStatus != "{JobStatusEnum.FAILED}" ORDER BY dateCreated DESC LIMIT 1"""

            self.db_helper.connect()
            cursor = self.db_helper.getCursor(dictionary=True)

            results = self.db_helper.query(sql)

            if cursor.rowcount > 0:
                last_request_time = results[0]["dateCreated"]
                logger.info(
                    f"Last job request for the same collection item was on {last_request_time}"
                )

                td = job_created_datetime - last_request_time

                if td < timedelta(minutes=self.minimum_job_interval):
                    validRequest = False
                    logger.info(
                        f"Timedelta is {td}, less than minimum job interval, which is set as {self.minimum_job_interval} mins"
                    )

            self.db_helper.disconnect()

            if not validRequest:
                # send http response
                ackMsg = """You submitted duplicate requests in short timeframe, please wait for completion of your prior request. Thank you for your cooperation."""
                resp = {"Invalid Request": ackMsg}

                self.write(json.dumps(resp))
                self.finish()
                return

            # compose task and send to work queue
            body = {
                "sda_path": sda_file_path,
                "email": user_email_addr,
                "job_id": job_id,
            }

            # encode
            message = json.dumps(body)

            self.channel.basic_publish(
                exchange="",
                routing_key=self.work_queue,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ),
            )

            # insert a job record into database
            sql = f"INSERT INTO {self.job_table} (email, sourceIP, jobid, dateCreated, jobSize, jobStatus, collection, downloadURL)             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"

            val = (
                user_email_addr,
                remote_ip,
                job_id,
                job_created_datetime_str,
                job_size,
                JobStatusEnum.SUBMITTED,
                os.path.basename(sda_file_path),
                download_url,
            )

            self.db_helper.connect()
            self.db_helper.getCursor()

            self.db_helper.execute(sql, val)

            self.db_helper.disconnect()

            # send http response
            ackMsg = """Your download request has been submitted. You will receive an email response to your request with a download link. Once your request has been processed, the download link will remain valid for 24 hours"""
            resp = {"Acknowledgement": ackMsg}

            self.write(json.dumps(resp))
            self.finish()

        except MissingArgumentError as me:
            raise HTTPError(status_code=400, log_message=str(me))
        except Exception as e:
            raise HTTPError(status_code=400, log_message=str(e))

    def post(self):
        pass


# ## Launch web server


if __name__ == "__main__":
    CONFIG_FILENAME = "sds.cfg"
    config = configparser.ConfigParser()
    config.read(CONFIG_FILENAME)

    #     config = get_config()

    logging.basicConfig(level=config["webserver"]["debug_level"])

    base_path = config["webserver"]["url_base_path"]
    if not base_path.endswith("/"):
        base_path = base_path + "/"

    port = config.getint("webserver", "port")

    env = config["webserver"]["env"]

    use_ssl = config.getboolean("webserver", "use_ssl")
    cert_file = config["webserver"]["cert_file"]
    key_file = config["webserver"]["key_file"]
    ssl_hostname = config["webserver"]["ssl_hostname"]

    ENV = env

    # SDS configs
    hsi_bin_path = config["sds_sync"]["hsi_bin_path"]
    hsi_user = config["sds_sync"]["hsi_user"]
    hsi_keytab_path = config["sds_sync"]["hsi_keytab_path"]
    firewall_flag = config.getboolean("sds_sync", "firewall_flag")
    timeout_in_secs = config.getint("sds_sync", "timeout_in_secs")

    # SDS async configs
    message_broker_host = config["sds_async"]["message_broker_host"]
    message_broker_port = config.getint("sds_async", "message_broker_port")
    work_queue = config["sds_async"]["work_queue"]
    same_job_minimum_interval_in_min = config.getint(
        "sds_async", "same_job_minimum_interval_in_min"
    )
    black_list_filepath = config["sds_async"]["black_list"]

    # DB configs
    host = config["database"]["host"]
    user = config["database"]["user"]
    password = config["database"]["password"]
    db = config["database"]["db"]
    job_table = config["database"]["job_table"]

    db_helper = DatabaseHelper(host, user, password, db)

    # init logger
    logFilepath = config["logging"]["api_log_file"]

    LoggingUtil.initLogger(logFilepath)
    logger = logging.getLogger(LoggingUtil.LOGGER_NAME)

    logger.info(f"Loading black list from file: {black_list_filepath}")
    df = pd.read_csv(black_list_filepath)
    black_list = set(df["email"].tolist())

    handlers = [
        (
            r"{}sds/get".format(base_path),
            SyncSDSFilePullHandler,
            {
                "hsi_bin_path": hsi_bin_path,
                "hsi_user": hsi_user,
                "hsi_keytab_path": hsi_keytab_path,
                "firewall_flag": firewall_flag,
                "timeout_in_secs": timeout_in_secs,
                "logger": logger,
            },
        ),
        (
            r"{}sds/pull".format(base_path),
            AsyncSDSFilePullHandler,
            {
                "message_broker_host": message_broker_host,
                "message_broker_port": message_broker_port,
                "work_queue": work_queue,
                "db_helper": db_helper,
                "minimum_job_interval": same_job_minimum_interval_in_min,
                "black_list": black_list,
                "job_table": job_table,
                "logger": logger,
            },
        ),
    ]

    app = Application(handlers, debug=True)

    try:
        logging.debug("Server starting at port {}.".format(port))

        if use_ssl:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(cert_file, key_file)

            server = HTTPServer(app, ssl_options=ssl_ctx)

            server.listen(port, address=ssl_hostname)

            logging.debug("Server listening on hostname: {}".format(ssl_hostname))
        else:
            #             app.listen(port)

            server = HTTPServer(app)
            server.listen(port)

            logging.debug("Server listening on all interfaces.")

        IOLoop.current().start()
    except Exception as e:
        logging.error(str(e))

    IOLoop.instance().stop()
