import os
import logging

import dateutil.parser
import logaugment
from .exceptions import InvalidGitHubRepo


def get_all_snaps(launchpad, logger):
    """
    Return all the snaps in Launchpad created by the user build.snapcraft.io
    """
    page = 1
    logger.debug(f"Getting Snaps from Launchpad - Page {page}")

    response = launchpad.request(
        "https://api.launchpad.net/devel/+snaps",
        params={"ws.op": "findByOwner", "owner": "/~build.snapcraft.io"},
    ).json()

    snaps = response["entries"]
    logaugment.add(logger, total_snaps=len(snaps))

    while "next_collection_link" in response:
        page += 1
        logger.debug(f"Getting Snaps from Launchpad - Page {page}")

        response = launchpad.request(response["next_collection_link"]).json()

        snaps.extend(response["entries"])
        logaugment.add(logger, total_snaps=len(snaps))

    logger.debug(f"Total snaps received: {len(snaps)}")

    return snaps


def get_last_build_date(launchpad, snap_name, logger):
    """
    Return POSIX timestamp corresponding to the last build
    """

    logger.debug(f"Getting launchpad builds for {snap_name}")
    builds = launchpad.get_snap_builds(snap_name)

    if not builds:
        return None

    last_build = builds[0]["datecreated"]
    logger.debug(f"{snap_name} last build was on {last_build}")

    return dateutil.parser.parse(last_build).timestamp()


def has_parts_changed(github, snap_name, parts, last_build, logger):
    """
    Return True if the snap parts have changed since last built
    """
    for part in parts:
        logger.debug(f"Checking part {part['url']}")

        # We are not supporting GitHub tags or commits
        if part["tag"] or part["commit"]:
            logger.debug(f"Skipping part because it is using GitHub tag or commit")
            continue

        part_gh_owner, part_gh_repo = part["url"][19:].split("/")

        try:
            if github.has_repo_changed_since(
                part_gh_owner, part_gh_repo, last_build, part["branch"]
            ):
                logger.info(f"Part defined in snap {snap_name} has changed")
                return True
        except InvalidGitHubRepo as e:
            logger.debug(f"Skipping part: {str(e)}")

    return False


def get_logger(level):
    logger = logging.getLogger("script.output")
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(current_snap)s/%(total_snaps)s"
        " - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

    logaugment.add(logger, current_snap=0, total_snaps=0)

    return logger
