#!/usr/bin/env python
# coding: utf-8


import pika
import json
import time
import os
from subprocess import Popen, PIPE, CalledProcessError, TimeoutExpired
from pathlib import Path
import datetime
import configparser
import textwrap
import smtplib
import signal

from database import DatabaseHelper, JobStatusEnum

import logging
from loggingutil import LoggingUtil

from email.message import EmailMessage


class Worker:
    def __init__(
        self,
        message_broker_host,
        message_broker_port,
        work_queue,
        staging_dir,
        staging_usage_threshold,
        hsi_bin_path,
        hsi_keytab_path,
        hsi_user,
        firewall_flag,
        timeout_in_secs,
        smtp_server,
        email_sender,
        contact_email,
        http_download_server,
        db_helper,
        job_table,
        logger,
    ):
        self.message_broker_host = message_broker_host
        self.message_broker_port = message_broker_port
        self.work_queue = work_queue
        self.staging_dir = staging_dir
        self.staging_usage_threshold = staging_usage_threshold

        self.hsi_bin_path = hsi_bin_path
        self.hsi_keytab_path = hsi_keytab_path
        self.hsi_user = hsi_user
        self.firewall_flag = firewall_flag
        self.timeout_in_secs = timeout_in_secs

        self.smtp_server = smtp_server
        self.email_sender = email_sender
        self.contact_email = contact_email

        if http_download_server.endswith("/"):
            http_download_server = http_download_server[:-1]

        self.http_download_server = http_download_server

        self.db_helper = db_helper
        self.job_table = job_table

        self.logger = logger

    def prepare(self):
        # turn off heartbeat
        # see post https://stackoverflow.com/questions/56859006/server-closes-after-pika-exceptions-streamlosterror-stream-connection-lost
        # https://pika.readthedocs.io/en/stable/modules/parameters.html
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.message_broker_host,
                port=self.message_broker_port,
                heartbeat=0,
            )
        )

        self.channel = self.connection.channel()

        self.channel.queue_declare(queue=self.work_queue, durable=True)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.work_queue,
            on_message_callback=lambda ch, method, properties, body: self.callback(
                ch, method, properties, body
            ),
        )

    def pullSda(self, sda_file_path):
        logger = self.logger

        basename = os.path.basename(sda_file_path)

        localfile = os.path.join(self.staging_dir, basename)

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
            cmd_part2 = ['"firewall -on; get {} : {}"'.format(localfile, sda_file_path)]
        else:
            cmd_part2 = ["get", localfile, ":", sda_file_path]

        cmd = cmd_part1 + cmd_part2
        cmdStr = " ".join(cmd)
        logger.debug("cmd to execute: {}".format(cmdStr))

        normalExit = True

        try:
            p = Popen(cmdStr, shell=True)

            p.communicate(timeout=self.timeout_in_secs)
            logger.debug("Done writing!")
            logger.debug("return code: {}".format(p.returncode))
            logger.debug("args: {}".format(p.args))

            if p.returncode != 0:
                raise CalledProcessError(p.returncode, p.args)

        except Exception as e:
            if isinstance(e, TimeoutExpired):
                msg = "SDA pulling timeout exception"
                print(msg)
                logger.error(msg)

            # cleanup, not needed when exit code is 0
            try:
                os.kill(p.pid, signal.SIGTERM)
            except Exception:
                pass

            # remove the file transferred in middle
            try:
                os.remove(localfile)
            except OSError:
                pass

            # raise the error so it can be caught by caller
            raise e

    def isInCache(self, filename):
        # this function may throw exception as the file in question
        # may be removed in the middle by other processes

        logger = self.logger

        localfile = os.path.join(self.staging_dir, filename)

        sleepInSecs = 60

        totalSizeInZeroWaitSecs = 0
        totalSizeInZeroWaitLimitInSecs = 600

        if Path(localfile).is_file():
            # check if file is stable
            fileSize = Path(localfile).stat().st_size

            while True:
                time.sleep(sleepInSecs)

                # file may be removed by another worker
                # due to timeout
                if not Path(localfile).is_file():
                    return False

                curSize = Path(localfile).stat().st_size

                # another worker is working on the downloading
                # especially for large files, filesize will stay at 0
                # for a while
                if curSize == 0:
                    totalSizeInZeroWaitSecs += sleepInSecs

                    if totalSizeInZeroWaitSecs < totalSizeInZeroWaitLimitInSecs:
                        continue
                    else:
                        # a dead file, remove it
                        Path(localfile).unlink(missing_ok=True)
                        return False

                # this indicating the downloading is progressing
                if curSize != fileSize:
                    fileSize = curSize
                else:
                    break

            logger.debug("Cache hit for {}".format(filename))
            # file exists

            # get last modified time
            stat = Path(localfile).stat()
            modification_time = stat.st_mtime

            # update most recent access to current
            ct = datetime.datetime.now()
            access_time = ct.timestamp()

            os.utime(localfile, (access_time, modification_time))

            return True
        else:
            return False

    def sendNotification(self, filename, user_email_addr):
        download_link = "{}/{}".format(self.http_download_server, filename)

        FROM = self.email_sender

        TO = [user_email_addr]

        SUBJECT = "Your requested archive is ready to download"

        SERVER = self.smtp_server

        TEXT = """You can now download your archive via the link below; please note that the link is valid only for 24 hours.\n{download_link}\n\nPlease contact Research Data Services (RDS) at {contact_email} if you need any assistance.\n""".format(
            download_link=download_link, contact_email=self.contact_email
        )

        print(TEXT)

        Worker.sendMail(FROM, TO, SUBJECT, TEXT, SERVER)

    def sendErrorNotify(self, filename, user_email_addr, err_msg):
        FROM = self.email_sender

        TO = [user_email_addr]

        SUBJECT = "Failed on retrieving your requested archive"

        SERVER = self.smtp_server

        TEXT = """We encountered an issue when retrieving your requested archive:\n\n{filename}\n\nPlease contact Research Data Services (RDS) at {contact_email} for assistance.\n""".format(
            filename=filename, contact_email=self.contact_email
        )

        print(TEXT)

        Worker.sendMail(FROM, TO, SUBJECT, TEXT, SERVER)

    def sendCancelNotify(self, filename, user_email_addr):
        FROM = self.email_sender

        TO = [user_email_addr]

        SUBJECT = "Cancelled your request for archive"

        SERVER = self.smtp_server

        TEXT = """SDS is currently processing its maximum number of requests. The system has cancelled your request.\n\nPlease resubmit your request for {filename} at a later time.\n\nPlease contact Research Data Services (RDS) at {contact_email} if you need any assistance.\n""".format(
            contact_email=self.contact_email, filename=filename
        )

        print(TEXT)

        Worker.sendMail(FROM, TO, SUBJECT, TEXT, SERVER)

    def hasEnoughSpace(self, dirloc, threshold):
        logger = self.logger

        # get size
        size = 0

        for ele in os.scandir(dirloc):
            size += os.stat(ele).st_size

        sizeInGB = size / (1024 * 1024 * 1024)

        logger.debug(
            "Checking storage usage, used: {} GB, threshold: {} GB".format(
                sizeInGB, threshold
            )
        )

        if sizeInGB >= threshold:
            return False
        else:
            return True

    @staticmethod
    def sendMail(FROM, TO, SUBJECT, TEXT, SERVER):
        """Send an email to the user list with a message"""

        message = textwrap.dedent(
            """From: {FROM}
To: {TO}
Subject: {SUBJECT}

{TEXT}
""".format(FROM=FROM, TO=", ".join(TO), SUBJECT=SUBJECT, TEXT=TEXT)
        )

        print(message)

        # Create a text/plain message
        msg = EmailMessage()
        msg.set_content(TEXT)

        msg["Subject"] = SUBJECT
        msg["From"] = FROM
        msg["To"] = TO

        # Send the mail
        server = smtplib.SMTP(SERVER)
        # server.sendmail(FROM, TO, message)
        server.send_message(msg)
        server.quit()

    # on message callback
    def callback(self, ch, method, properties, body):
        logger = self.logger

        payload = json.loads(body)
        sda_file_path = payload["sda_path"]
        user_email_addr = payload["email"]
        job_id = payload["job_id"]

        logger.info(
            "Received job request for file: {}, from user: {}, jobid: {}".format(
                sda_file_path, user_email_addr, job_id
            )
        )

        basename = os.path.basename(sda_file_path)

        cacheHit = False

        try:
            cacheHit = self.isInCache(basename)

        except Exception as e:
            msg = "Error in cache lookup: {}".format(e)
            print(msg)
            logger.warning(msg)

        if not self.hasEnoughSpace(self.staging_dir, self.staging_usage_threshold):
            if not cacheHit:
                logger.warning("Not enough space on staging area")

                # send reject and the message will be removed from the queue
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

                # update db status to cancellation
                sql = f"UPDATE {self.job_table} SET jobStatus = %s WHERE jobid = %s"

                val = (JobStatusEnum.CANCELLED, job_id)
                self.updateJobStatus(sql, val)

                # send cancellation notification
                self.sendCancelNotify(basename, user_email_addr)

                logger.info("Sent cancellation email notification to user")

                return

        try:
            logger.info("Job begins processing")

            # update job status to processing
            sql = f"UPDATE {self.job_table} SET jobStatus = %s WHERE jobid = %s"
            val = (JobStatusEnum.PROCESSING, job_id)
            self.updateJobStatus(sql, val)

            if not cacheHit:
                self.pullSda(sda_file_path)

            download_link = "{}/{}".format(self.http_download_server, basename)

            # update job status to completion
            sql = f"UPDATE {self.job_table} SET jobStatus = %s, jobSize = %s, downloadURL = %s WHERE jobid = %s"

            localfile = os.path.join(self.staging_dir, basename)

            # os.path.getsize()'s unit is in byte, convert to mb
            # megabyte is in integer, if want float, use '/ (1024 * 1024)'
            job_size = os.path.getsize(localfile) >> 20
            # job size is int type
            #             job_size = f"{job_size_in_mb} MB"

            val = (JobStatusEnum.COMPLETED, job_size, download_link, job_id)
            self.updateJobStatus(sql, val)

            logger.info("Job finished processing")

            # send email notification
            self.sendNotification(basename, user_email_addr)

            logger.info("Sent job completion email to user")

        except Exception as e:
            logger.error(
                "Encountered error when executing job: error message: {}".format(e)
            )

            # update job status to failure
            sql = f"UPDATE {self.job_table} SET jobStatus = %s WHERE jobid = %s"
            val = (JobStatusEnum.FAILED, job_id)
            self.updateJobStatus(sql, val)

            try:
                # send error notification
                self.sendErrorNotify(basename, user_email_addr, err_msg=repr(e))
                logger.info("Sent job failure email to user")
            except Exception as e:
                pass
        finally:
            # finally send ack
            try:
                msg = "Sending ack, current time: {}".format(datetime.datetime.now())
                print(msg)
                logger.info(msg)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except pika.exceptions.ChannelClosedByBroker as e:
                print(e)
                logger.error(e)
            except Exception as e:
                logger.error(
                    "Encountered error when sending ack back: error message: {}".format(
                        e
                    )
                )

    def updateJobStatus(self, sql, val):
        self.db_helper.connect()
        self.db_helper.getCursor()

        self.db_helper.execute(sql, val)

        self.db_helper.disconnect()

    def run(self):
        self.channel.start_consuming()


if __name__ == "__main__":
    CONFIG_FILENAME = "sds.cfg"
    config = configparser.ConfigParser()
    config.read(CONFIG_FILENAME)

    # configs
    hsi_bin_path = config["sds_sync"]["hsi_bin_path"]
    hsi_user = config["sds_sync"]["hsi_user"]
    hsi_keytab_path = config["sds_sync"]["hsi_keytab_path"]
    firewall_flag = config.getboolean("sds_sync", "firewall_flag")
    timeout_in_secs = config.getint("sds_sync", "timeout_in_secs")

    # configs
    message_broker_host = config["sds_async"]["message_broker_host"]
    message_broker_port = config.getint("sds_async", "message_broker_port")
    work_queue = config["sds_async"]["work_queue"]

    # worker configs
    staging_dir = config["worker"]["staging_dir"]
    smtp_server = config["worker"]["smtp_server"]
    email_sender = config["worker"]["email_sender"]
    contact_email = config["worker"]["contact_email"]
    http_download_server = config["worker"]["http_download_server"]
    staging_usage_threshold = config.getfloat("worker", "staging_usage_threshold_in_gb")

    # DB configs
    host = config["database"]["host"]
    user = config["database"]["user"]
    password = config["database"]["password"]
    db = config["database"]["db"]
    job_table = config["database"]["job_table"]

    db_helper = DatabaseHelper(host, user, password, db)

    # init logger
    logFilepath = config["logging"]["worker_log_file"]

    LoggingUtil.initLogger(logFilepath)
    logger = logging.getLogger(LoggingUtil.LOGGER_NAME)

    worker = Worker(
        message_broker_host,
        message_broker_port,
        work_queue,
        staging_dir,
        staging_usage_threshold,
        hsi_bin_path,
        hsi_keytab_path,
        hsi_user,
        firewall_flag,
        timeout_in_secs,
        smtp_server,
        email_sender,
        contact_email,
        http_download_server,
        db_helper,
        job_table,
        logger,
    )

    worker.prepare()
    worker.run()
