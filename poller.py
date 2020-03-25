#! /usr/bin/env python3

import os

from canonicalwebteam.launchpad import Launchpad
from requests import Session

launchpad = Launchpad(
    username="build.snapcraft.io",
    token=os.getenv("LP_API_TOKEN"),
    secret=os.getenv("LP_API_TOKEN_SECRET"),
    session=Session(),
)


def get_all_snaps():
    """
    Return all the snaps in Launchpad created by the user build.snapcraft.io
    """
    response = launchpad._request(
        "+snaps",
        params={"ws.op": "findByOwner", "owner": "/~build.snapcraft.io"},
    ).json()

    snaps = response["entries"]

    while "next_collection_link" in response:
        response = launchpad._request(
            response["next_collection_link"][32:]
        ).json()
        snaps.extend(response["entries"])

    return snaps


snaps = get_all_snaps()
print(len(snaps))
