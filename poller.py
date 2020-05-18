#! /usr/bin/env python3
import csv
import argparse
import logging.config
import os
from email.message import EmailMessage
from smtplib import SMTP

import logaugment
from canonicalwebteam.launchpad import Launchpad
from requests import Session

from src import helper

launchpad = Launchpad(
    username="build.snapcraft.io",
    token=os.getenv("LP_API_TOKEN"),
    secret=os.getenv("LP_API_TOKEN_SECRET"),
    session=Session(),
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "This script is executed regularly to trigger builds for snaps "
            "that were updated - dependencies were changed (GitHub only), ",
            "or the snap repo itself was changed.",
        )
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
    )

    args = parser.parse_args()
    logging_level = logging.INFO

    if args.verbose:
        logging_level = logging.DEBUG

    logger = helper.get_logger(logging_level)

    snaps = helper.get_all_snaps(launchpad, logger)
    current_snap = 0

    # Stats
    snaps_with_store_name = 0
    snaps_without_store_name = 0
    total_snaps = len(snaps)
    all_snap_data = []

    for snap in snaps:
        current_snap += 1
        logaugment.add(logger, current_snap=current_snap)

        if snap["store_name"]:
            snaps_with_store_name += 1
            continue
        else:
            snaps_without_store_name += 1

            builds = launchpad.get_collection_entries(
                snap["builds_collection_link"]
            )

            snap_data = {}
            snap_data["name"] = snap["name"]
            snap_data["link"] = snap["web_link"]
            snap_data["has_builds"] = "Yes" if builds else "No"
            snap_data["can_upload_to_store"] = snap["can_upload_to_store"]
            snap_data["date_created"] = snap["date_created"].split("T")[0]
            snap_data["date_last_modified"] = snap["date_last_modified"].split(
                "T"
            )[0]
            all_snap_data.append(snap_data)

    with open("output.csv", "w") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "name",
                "link",
                "has_builds",
                "can_upload_to_store",
                "date_created",
                "date_last_modified",
            ],
        )
        writer.writeheader()

        for snap_data in all_snap_data:
            writer.writerow(snap_data)

    logger.info(
        "Process finished\n\n"
        f"Total snaps: {str(total_snaps)}\n"
        f"Snaps with store name: {str(snaps_with_store_name)}\n"
        f"Snaps without store name: {str(snaps_without_store_name)}\n"
    )
