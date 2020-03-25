This script is executed regularly in our Kubernetes cluster to trigger builds for snaps that:
- Parts dependencies defined in the snapcraft.yaml were changed (Only the ones that are GitHub repos)
- The snap GitHub repo itself was changed since the last build.

This script is a Python version of the [old javascript script](https://github.com/canonical-web-and-design/build.snapcraft.io/blob/master/src/server/scripts/poller.js).

## How it works:

All the script does is:

1. Get all the snaps created with the build.snapcraft.io user, and for each repo, it will:
2. Verify the content in the repo:
    1. There is a scraftcraft.yaml
    2. The snap name in the snapcraft.yaml is valid
3. Get the date of the last built and skip if the snap was built in the previous 24h
4. Trigger a build if any of the following condition happen:
    3. Repository of the snap has changed after the last built.
    4. Any of the GitHub repos from the parts defined in the snapcraft.yaml has changed since the last build.
