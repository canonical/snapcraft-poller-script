import dateutil.parser
from .exceptions import InvalidGitHubRepo


def get_all_snaps(launchpad, logging):
    """
    Return all the snaps in Launchpad created by the user build.snapcraft.io
    """
    page = 1
    logging.debug(f"Getting Snaps from Launchpad - Page {page}")

    response = launchpad._request(
        "+snaps",
        params={"ws.op": "findByOwner", "owner": "/~build.snapcraft.io"},
    ).json()

    snaps = response["entries"]

    while "next_collection_link" in response:
        page += 1
        logging.debug(f"Getting Snaps from Launchpad - Page {page}")

        response = launchpad._request(
            response["next_collection_link"][32:]
        ).json()

        snaps.extend(response["entries"])

    logging.debug(f"Total snaps received: {len(snaps)}")

    return snaps


def get_last_build_date(launchpad, snap_name, logging):
    """
    Return POSIX timestamp corresponding to the last build
    """

    logging.debug(f"Getting launchpad builds for {snap_name}")
    builds = launchpad.get_snap_builds(snap_name)

    if not builds:
        return None

    last_build = builds[0]["datecreated"]
    logging.debug(f"{snap_name} last build was on {last_build}")

    return dateutil.parser.parse(last_build).timestamp()


def has_parts_changed(github, snap_name, parts, last_build, logging):
    """
    Return True if the snap parts have changed since last built
    """
    for part in parts:
        logging.debug(f"Checking part {part['url']}")

        # We are not supporting GitHub tags
        if part["tag"]:
            logging.debug(f"Skipping part becuase is ussing GitHub tags")
            continue

        part_gh_owner, part_gh_repo = part["url"][19:].split("/")

        try:
            if github.has_repo_changed_since(
                part_gh_owner, part_gh_repo, last_build, part["branch"]
            ):
                logging.info(f"Part defined in snap {snap_name} has changed")
                return True
        except InvalidGitHubRepo as e:
            logging.debug(f"Skipping part: {str(e)}")

    return False
