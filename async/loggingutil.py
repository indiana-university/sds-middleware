#!/usr/bin/env python
# coding: utf-8


import logging
import logging.handlers


class LoggingUtil:
    LOGGER_NAME = "app.logger"

    @staticmethod
    def initLogger(logFilepath, backupCount=0, logLevel=logging.DEBUG):
        logger = logging.getLogger(LoggingUtil.LOGGER_NAME)

        logger.setLevel(logLevel)

        # see https://docs.python.org/3/library/logging.handlers.html#logging.handlers.TimeRotatingFileHandler
        hdlr = logging.handlers.TimedRotatingFileHandler(
            logFilepath,
            when="W6",
            interval=1,
            backupCount=backupCount,
            encoding="utf-8",
        )

        hdlr.setLevel(logLevel)

        formatter = logging.Formatter(
            "%(asctime)s;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S"
        )

        hdlr.setFormatter(formatter)

        logger.addHandler(hdlr)
