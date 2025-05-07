#!/usr/bin/env python
# coding: utf-8


import argparse
from glob import glob
import os
import datetime
import pandas as pd


class HouseKeeper:
    @staticmethod
    def purgeTTL(folder, ttl_in_min, whiteListFiles):
        whiteListFiles = set(whiteListFiles)
        pattern = os.path.join(folder, "**", "*")

        files = glob(pattern, recursive=True)
        files = [f for f in files if os.path.isfile(f)]

        ct = datetime.datetime.now()
        ct = ct.timestamp()
        print("Current unix epoch: {}".format(ct))

        for file in files:
            print("Examine file: {}".format(file))

            basename = os.path.basename(file)
            if basename in whiteListFiles:
                print("In white list, skip")
                continue

            access_time = os.stat(file).st_atime
            print("Last access time in unix epoch: {}".format(access_time))

            elapsed_mins = (ct - access_time) / 60
            print("Elapsed min: {}".format(elapsed_mins))

            if elapsed_mins >= ttl_in_min:
                print("Going to purge the file")

                os.remove(file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SDS House Keeper")

    parser.add_argument(
        "-dataroot", "--dataroot", type=str, action="store", help="data root folder"
    )
    parser.add_argument(
        "-ttl_in_min", "--ttl_in_min", type=int, action="store", help="ttl in minutes"
    )
    parser.add_argument(
        "-white_list",
        "--white_list",
        type=str,
        action="store",
        help="files not subject to ttl",
    )

    args = parser.parse_args()

    df = pd.read_csv(args.white_list)
    whiteListFiles = df["file"].tolist()

    print(f"******* House Keeping at *******".format(datetime.datetime.now()))

    HouseKeeper.purgeTTL(args.dataroot, args.ttl_in_min, whiteListFiles)

    print("Done")
