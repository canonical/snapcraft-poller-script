#! /usr/bin/env python3

import argparse
import datetime
import logging.config
import os
import dateutil.parser

from canonicalwebteam.launchpad import Launchpad
from requests import Session

from src.exceptions import InvalidGitHubRepo
from src.github import GitHub
from src import helper

launchpad = Launchpad(
    username="build.snapcraft.io",
    token=os.getenv("LP_API_TOKEN"),
    secret=os.getenv("LP_API_TOKEN_SECRET"),
    session=Session(),
)

github = GitHub(os.getenv("GITHUB_SNAPCRAFT_USER_TOKEN"), Session())

# Dates
now = datetime.datetime.now()
yesterday = now - dateutil.relativedelta.relativedelta(days=1)


def needs_building(snap, logging):
    if not snap["store_name"]:
        logging.info(f"Launchpad snap {snap['name']} doesn't have store name")
        return False

    snap_name = snap["store_name"]

    if not snap["store_upload"]:
        logging.info(f"{snap_name}: Can't be publish from Launchpad")
        return False

    if not github.is_github_repository_url(snap["git_repository_url"]):
        logging.info(f"{snap_name}: Is not ussing GitHub")
        return False

    gh_link = snap["git_repository_url"][19:]
    gh_owner, gh_repo = gh_link.split("/")

    logging.debug(f"Verifying snap {snap_name} with GitHub repo {gh_link}")

    try:
        yaml_file = github.get_snapcraft_yaml_location(gh_owner, gh_repo)
        github.verify_snapcraft_yaml_name(
            gh_owner, gh_repo, yaml_file, snap_name
        )
    except InvalidGitHubRepo as e:
        logging.info(f"Snap {snap_name} SKIPPED: {str(e)}")
        return False

    last_build = helper.get_last_build_date(launchpad, snap_name, logging)

    if not last_build:
        logging.info(
            f"Snap {snap_name} SKIPPED: The snap has never been built"
        )
        return False

    if last_build > yesterday.timestamp():
        logging.info(
            f"Snap {snap_name} SKIPPED: The snap has been recently built"
        )
        return False

    logging.debug(f"Checking if the repo has been updated since last build")
    try:
        if github.has_repo_changed_since(gh_owner, gh_repo, last_build):
            logging.debug(
                f"Snap {snap_name} repo has changed since last build"
            )
            return True
    except InvalidGitHubRepo as e:
        logging.debug(f"Snap {snap_name} SKIPPED: {str(e)}")
        return False

    logging.debug(f"Getting defined parts for snap {snap_name}")
    parts = github.get_defined_parts(gh_owner, gh_repo, yaml_file)

    if helper.has_parts_changed(github, snap_name, parts, last_build, logging):
        logging.debug(f"Snap {snap_name} parts needs building")
        return True

    return False


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

    # Disable logs from imported modules
    logging.config.dictConfig({"version": 1, "disable_existing_loggers": True})
    logging.basicConfig(
        format="%(levelname)s - %(message)s", level=logging_level
    )

    for snap in helper.get_all_snaps(launchpad, logging):
        try:
            if needs_building(snap, logging):
                logging.debug(f"Snap {snap['store_name']} needs building")

                if launchpad.is_snap_building(snap["store_name"]):
                    logging.debug(
                        f"Snap {snap['store_name']} is already being build"
                    )
                else:
                    logging.warning(f"Snap {snap['store_name']} is building")
                    launchpad.build_snap(snap["store_name"])
        except Exception as e:
            logging.error(
                f"An error occurrent with snap {snap['store_name']}: {str(e)}"
            )
