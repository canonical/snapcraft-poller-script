#! /usr/bin/env python3

import argparse
import datetime
import logging.config
import os

import dateutil.parser
import logaugment
from canonicalwebteam.launchpad import Launchpad
from requests import Session
from sentry_sdk import capture_exception, init
from sentry_sdk.integrations.logging import ignore_logger

from src import helper
from src.exceptions import GitHubRateLimit, InvalidGitHubRepo
from src.github import GitHub

# Set up Sentry
init(os.getenv("SENTRY_DSN"))
ignore_logger("script.output")

launchpad = Launchpad(
    username="build.snapcraft.io",
    token=os.getenv("LP_API_TOKEN"),
    secret=os.getenv("LP_API_TOKEN_SECRET"),
    session=Session(),
)

github = GitHub(os.getenv("GITHUB_SNAPCRAFT_POLLER_TOKENS").split(), Session())

# Skip Snaps built in the last 24 hours
threshold = datetime.datetime.now() - dateutil.relativedelta.relativedelta(
    days=1
)


def needs_building(snap, logger):
    if not snap["store_name"]:
        logger.info(f"Launchpad snap {snap['name']} doesn't have store name")
        return False

    snap_name = snap["store_name"]

    if not snap["store_upload"]:
        logger.info(f"{snap_name}: Can't be publish from Launchpad")
        return False

    if not github.is_github_repository_url(snap["git_repository_url"]):
        logger.info(f"{snap_name}: Is not ussing GitHub")
        return False

    gh_link = snap["git_repository_url"][19:]
    gh_owner, gh_repo = gh_link.split("/")

    logger.debug(f"Verifying snap {snap_name} with GitHub repo {gh_link}")

    try:
        yaml_file = github.get_snapcraft_yaml_location(gh_owner, gh_repo)
        github.verify_snapcraft_yaml_name(
            gh_owner, gh_repo, yaml_file, snap_name
        )
    except InvalidGitHubRepo as e:
        logger.info(f"Snap {snap_name} SKIPPED: {str(e)}")
        return False

    last_build = helper.get_last_build_date(launchpad, snap_name, logger)

    if not last_build:
        logger.info(f"Snap {snap_name} SKIPPED: The snap has never been built")
        return False

    if last_build > threshold.timestamp():
        logger.info(
            f"Snap {snap_name} SKIPPED: The snap has been recently built"
        )
        return False

    logger.debug(f"Checking if the repo has been updated since last build")
    try:
        if github.has_repo_changed_since(gh_owner, gh_repo, last_build):
            logger.debug(f"Snap {snap_name} repo has changed since last build")
            return True
    except InvalidGitHubRepo as e:
        logger.debug(f"Snap {snap_name} SKIPPED: {str(e)}")
        return False

    logger.debug(f"Getting defined parts for snap {snap_name}")
    parts = github.get_defined_parts(gh_owner, gh_repo, yaml_file)

    if helper.has_parts_changed(github, snap_name, parts, last_build, logger):
        logger.debug(f"Snap {snap_name} parts needs building")
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

    logger = helper.get_logger(logging_level)
    snaps = helper.get_all_snaps(launchpad, logger)
    current_snap = 0

    for snap in snaps:
        current_snap += 1
        logaugment.add(logger, current_snap=current_snap)

        try:
            if needs_building(snap, logger):
                logger.debug(f"Snap {snap['store_name']} needs building")

                if launchpad.is_snap_building(snap["store_name"]):
                    logger.debug(
                        f"Snap {snap['store_name']} is already being build"
                    )
                else:
                    logger.warning(f"Snap {snap['store_name']} is building")
                    launchpad.build_snap(snap["store_name"])
        except GitHubRateLimit as e:
            logger.error("GitHub API rate limit exceeded")
            # Raise the exception to abort the script and catch it on Sentry
            raise e
        except Exception as e:
            # Extra info for Sentry
            e.snap_launchpad_name = snap["name"]
            e.snap_name = snap["store_name"]
            e.snap_github_repo = snap["git_repository_url"]

            # Send this exception to Sentry but script will continue
            capture_exception(e)

            logger.error(
                f"An error occurrent with snap {snap['store_name']}: {str(e)}"
            )
