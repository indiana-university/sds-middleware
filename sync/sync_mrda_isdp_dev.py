# coding: utf-8


from tornado.web import RequestHandler, Application, HTTPError, MissingArgumentError
from tornado.ioloop import IOLoop
import tornado
import logging
import configparser
import json
import requests
from subprocess import Popen, PIPE, CalledProcessError
import tempfile
import os


ENV = ""


# ## Definition of Listeners/Endpoints


class ISDPFilePullHandler(RequestHandler):
    def initialize(
        self, hsi_bin_path, hsi_keytab_path, hsi_user, firewall_flag, timeout_in_secs
    ):
        self.hsi_bin_path = hsi_bin_path
        self.hsi_keytab_path = hsi_keytab_path
        self.hsi_user = hsi_user
        self.firewall_flag = firewall_flag
        self.timeout_in_secs = timeout_in_secs

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


# ## Launch web server


if __name__ == "__main__":
    CONFIG_FILENAME = "mrda_isdp_dev.cfg"
    config = configparser.ConfigParser()
    config.read(CONFIG_FILENAME)

    #     config = get_config()

    logging.basicConfig(level=config["webserver"]["debug_level"])

    base_path = config["webserver"]["url_base_path"]
    if not base_path.endswith("/"):
        base_path = base_path + "/"

    port = config.getint("webserver", "port")

    env = config["webserver"]["env"]

    ENV = env

    # ISDP configs
    hsi_bin_path = config["isdp"]["hsi_bin_path"]
    hsi_user = config["isdp"]["hsi_user"]
    hsi_keytab_path = config["isdp"]["hsi_keytab_path"]
    firewall_flag = config.getboolean("isdp", "firewall_flag")
    timeout_in_secs = config.getint("isdp", "timeout_in_secs")

    handlers = [
        (
            r"{}isdp/get".format(base_path),
            ISDPFilePullHandler,
            {
                "hsi_bin_path": hsi_bin_path,
                "hsi_user": hsi_user,
                "hsi_keytab_path": hsi_keytab_path,
                "firewall_flag": firewall_flag,
                "timeout_in_secs": timeout_in_secs,
            },
        )
    ]

    app = Application(handlers, debug=True)
    try:
        logging.debug("Server starting at http://localhost:{}.".format(port))
        app.listen(port)
        IOLoop.current().start()
    except Exception as e:
        logging.error(str(e))

#     IOLoop.instance().stop()


# ## Server Test


url = "http://localhost:8080/isdp/get?p=/path/to/sda"
url = "http://localhost:8080/isdp/get?p=state/2016/geotiff/statewide/in2016_31151427_06.zip"


# ## HSI Test


import shutil


hsi_bin_path = "/vagrant/data/hpss/bin/hsi"
hsi_keytab_path = "/vagrant/data/hpss/credentials/doqqs.keytab"
hsi_user = "doqqs"
sda_file_path = "state/2016/geotiff/statewide/in2016_31151427_06.zip"
firewall_flag_on = True
buffer_size = 4096
outfile = "./file.zip"


def test_hsi_method1(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    with tempfile.NamedTemporaryFile() as temp:
        print(temp.name)

        cmd_part1 = [
            hsi_bin_path,
            "-d2",
            "-A",
            "keytab",
            "-k",
            hsi_keytab_path,
            "-l",
            hsi_user,
        ]
        if firewall_flag_on:
            cmd_part2 = ['"firewall -on; get {} : {}"'.format(temp.name, sda_file_path)]
        else:
            cmd_part2 = ["get", temp.name, ":", sda_file_path]

        cmd = cmd_part1 + cmd_part2
        cmdStr = " ".join(cmd)
        print("cmd to execute: {}".format(cmdStr))

        p = Popen(cmdStr, shell=True)
        timeoutInSecs = 300
        p.communicate(timeout=timeoutInSecs)
        print("Done writing!")
        print("return code: {}".format(p.returncode))
        print("args: {}".format(p.args))

        src = temp.name
        dst = outfile
        shutil.copyfile(src, dst)
        print("copied {} to {}".format(src, dst))


test_hsi_method1(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


def test_hsi_method2(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    cmd_part1 = [
        hsi_bin_path,
        "-d2",
        "-A",
        "keytab",
        "-k",
        hsi_keytab_path,
        "-l",
        hsi_user,
    ]
    if firewall_flag_on:
        cmd_part2 = ['"firewall -on; get {} : {}"'.format(outfile, sda_file_path)]
    else:
        cmd_part2 = ["get", outfile, ":", sda_file_path]

    cmd = cmd_part1 + cmd_part2
    cmdStr = " ".join(cmd)
    print("cmd to execute: {}".format(cmdStr))

    p = Popen(cmdStr, shell=True)
    timeoutInSecs = 300
    p.communicate(timeout=timeoutInSecs)
    print("Done writing!")
    print("return code: {}".format(p.returncode))
    print("args: {}".format(p.args))


test_hsi_method2(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


def test_hsi_method3(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    # Example
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs "firewall -on; get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip"
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip

    cmd_part1 = [
        hsi_bin_path,
        "-d2",
        "-A",
        "keytab",
        "-k",
        hsi_keytab_path,
        "-l",
        hsi_user,
    ]
    if firewall_flag_on:
        cmd_part2 = ['"firewall -on; get - : {}"'.format(sda_file_path)]
    else:
        cmd_part2 = ["get", "-", ":", sda_file_path]

    cmd = cmd_part1 + cmd_part2
    cmdStr = " ".join(cmd)
    print("cmd to execute: {}".format(cmdStr))

    with Popen(cmd, stdout=PIPE, bufsize=-1) as p:
        with open(outfile, "wb") as f:
            chunk = p.stdout.read(buffer_size)
            while chunk:
                f.write(chunk)
                chunk = p.stdout.read(buffer_size)

        print("Done writing!")
        print("return code: {}".format(p.returncode))


test_hsi_method3(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


def test_hsi_method4(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    # Example
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs "firewall -on; get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip"
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip

    cmd_part1 = [
        hsi_bin_path,
        "-d2",
        "-A",
        "keytab",
        "-k",
        hsi_keytab_path,
        "-l",
        hsi_user,
    ]
    if firewall_flag_on:
        cmd_part2 = ['"firewall -on; get - : {}"'.format(sda_file_path)]
    else:
        cmd_part2 = ["get", "-", ":", sda_file_path]

    cmd = cmd_part1 + cmd_part2
    cmdStr = " ".join(cmd)
    print("cmd to execute: {}".format(cmdStr))

    with open(outfile, "wb") as f:
        p = Popen(cmd, stdout=PIPE, bufsize=-1)

        while not p.poll():
            chunk = p.stdout.read(buffer_size)
            while chunk:
                f.write(chunk)
                chunk = p.stdout.read(buffer_size)

        print("Done writing!")
        print("return code: {}".format(p.returncode))
        print("args: {}".format(p.args))


test_hsi_method4(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


def test_hsi_method5(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    # Example
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs "firewall -on; get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip"
    # hsi -d2 -A keytab -k credentials/doqqs.keytab -l doqqs get file.zip : state/2016/geotiff/statewide/in2016_31151427_06.zip

    cmd_part1 = [
        hsi_bin_path,
        "-d2",
        "-A",
        "keytab",
        "-k",
        hsi_keytab_path,
        "-l",
        hsi_user,
    ]
    if firewall_flag_on:
        cmd_part2 = ['"firewall -on; get - : {}"'.format(sda_file_path)]
    else:
        cmd_part2 = ["get", "-", ":", sda_file_path]

    cmd = cmd_part1 + cmd_part2
    cmdStr = " ".join(cmd)
    print("cmd to execute: {}".format(cmdStr))

    with open(outfile, "wb") as f:
        p = Popen(cmdStr, shell=True, stdout=PIPE, bufsize=-1)

        while not p.poll():
            chunk = p.stdout.read(buffer_size)
            while chunk:
                print(chunk)
                f.write(chunk)
                chunk = p.stdout.read(buffer_size)

        print("Done writing!")
        print("return code: {}".format(p.returncode))
        print("args: {}".format(p.args))


# no call, as it runs into deadlock
test_hsi_method5(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


def test_hsi_method6(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
):
    with tempfile.TemporaryDirectory() as tmpdirname:
        print("created temporary directory", tmpdirname)

        basename = os.path.basename(sda_file_path)

        localfile = os.path.join(tmpdirname, basename)

        cmd_part1 = [
            hsi_bin_path,
            "-d2",
            "-A",
            "keytab",
            "-k",
            hsi_keytab_path,
            "-l",
            hsi_user,
        ]
        if firewall_flag_on:
            cmd_part2 = ['"firewall -on; get {} : {}"'.format(localfile, sda_file_path)]
        else:
            cmd_part2 = ["get", localfile, ":", sda_file_path]

        cmd = cmd_part1 + cmd_part2
        cmdStr = " ".join(cmd)
        print("cmd to execute: {}".format(cmdStr))

        p = Popen(cmdStr, shell=True)
        timeoutInSecs = 300
        p.communicate(timeout=timeoutInSecs)
        print("Done writing!")
        print("return code: {}".format(p.returncode))
        print("args: {}".format(p.args))

        buf_size = 4096
        with open(localfile, "rb") as in_file:
            with open(outfile, "wb") as out_file:
                data = in_file.read(buf_size)
                while data:
                    out_file.write(data)
                    data = in_file.read(buf_size)

                print("copied {} to {}".format(localfile, outfile))


test_hsi_method6(
    hsi_bin_path,
    hsi_user,
    hsi_keytab_path,
    sda_file_path,
    firewall_flag_on,
    buffer_size,
    outfile,
)


with tempfile.NamedTemporaryFile() as temp:
    print(temp.name)


with tempfile.TemporaryDirectory() as tmpdirname:
    print("created temporary directory", tmpdirname)
