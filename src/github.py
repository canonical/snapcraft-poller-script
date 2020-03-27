import dateutil.parser
from ruamel import yaml

from .exceptions import InvalidGitHubRepo

yaml_parser = yaml.YAML(typ="safe")


class GitHub:
    """
    Provides authentication for GitHub users. Helper methods are also provided
    for checking organization access and getting user data from the Github API.
    """

    REST_API_URL = "https://api.github.com"
    RAW_CONTENT_URL = "https://raw.githubusercontent.com"

    YAML_LOCATIONS = [
        "snapcraft.yaml",
        ".snapcraft.yaml",
        "snap/snapcraft.yaml",
        "build-aux/snap/snapcraft.yaml",
    ]

    def __init__(self, access_token, session):
        self.access_token = access_token
        self.session = session
        self.session.headers["Accept"] = "application/json"

    def _request(
        self, method="GET", url="", params={}, data={}, raise_exceptions=True
    ):
        """
        Makes a raw HTTP request and returns the response.
        """
        response = self.session.request(
            method,
            f"{self.REST_API_URL}/{url}",
            headers={"Authorization": f"token {self.access_token}"},
            params=params,
            json=data,
        )

        if raise_exceptions:
            response.raise_for_status()

        return response

    def is_github_repository_url(self, url):
        """
        Return True if the url is a GitHub repo
        """
        if (
            isinstance(url, str)
            and url.startswith("https://github.com")
            and url.count("/") == 4
        ):
            return True
        return False

    def get_default_branch(self, owner, repo):
        response = self._request(
            "GET", f"repos/{owner}/{repo}", raise_exceptions=False
        )
        if response.status_code in [404, 403]:
            raise InvalidGitHubRepo("The repo doesn't exists")

        response.raise_for_status()
        return response.json()["default_branch"]

    def get_snapcraft_yaml_location(self, owner, repo):
        """
        Return the snapcraft.yaml file location in the GitHub repo
        """
        yaml_location = None

        for loc in self.YAML_LOCATIONS:
            response = self._request(
                "GET",
                f"repos/{owner}/{repo}/contents/{loc}",
                raise_exceptions=False,
            )
            if response.status_code in [404, 403]:
                continue
            elif response.status_code == 200:
                yaml_location = loc
                break

            response.raise_for_status()

        if not yaml_location:
            raise InvalidGitHubRepo("Missing snapcraft.yaml")

        return yaml_location

    def get_last_commit(self, owner, repo, branch=None):
        if not branch:
            branch = self.get_default_branch(owner, repo)

        response = self._request(
            "GET",
            f"repos/{owner}/{repo}/commits/{branch}",
            raise_exceptions=False,
        )

        if response.status_code in [404, 403]:
            raise InvalidGitHubRepo(
                "Fail to get the last commit, the branch doesn't exist"
            )

        response.raise_for_status()
        return response.json()["sha"]

    def verify_snapcraft_yaml_name(self, owner, repo, loc, snap_name):
        """
        Verify the name in the snapcraft.yaml is valid
        """

        # Get last commit to avoid cache issues with raw.github.com
        last_commit = self.get_last_commit(owner, repo)

        response = self.session.request(
            "GET",
            f"{self.RAW_CONTENT_URL}/{owner}/{repo}/{last_commit}/{loc}",
        )

        try:
            content = yaml_parser.load(response.content)
        except Exception:
            raise InvalidGitHubRepo("Error while parsing snapcraft.yaml")

        if not isinstance(content, dict):
            raise InvalidGitHubRepo("Invalid snapcraft.yaml")

        # The property name inside the yaml file doesn't match the snap
        if content.get("name", "") != snap_name:
            raise InvalidGitHubRepo(
                'Name mismatch: the snapcraft.yaml uses the snap name "'
                + content.get("name", "")
                + '", but the user registered the name "'
                + snap_name
                + '".'
            )

        return True

    def get_defined_parts(self, owner, repo, loc):
        """
        Return defined GitHub parts
        """

        # Get last commit to avoid cache issues with raw.github.com
        last_commit = self.get_last_commit(owner, repo)

        response = self.session.request(
            "GET",
            f"{self.RAW_CONTENT_URL}/{owner}/{repo}/{last_commit}/{loc}",
        )

        try:
            content = yaml_parser.load(response.content)
        except Exception:
            raise InvalidGitHubRepo("Error while parsing snapcraft.yaml")

        parts = []
        yaml_parts = (
            content.get("parts") if isinstance(content, dict) else None
        )

        if yaml_parts:
            for part in yaml_parts:
                if content["parts"][part] and self.is_github_repository_url(
                    content["parts"][part].get("source")
                ):
                    gh_part = {}
                    gh_part["url"] = (
                        content["parts"][part].get("source").rstrip(".git")
                    )
                    gh_part["branch"] = content["parts"][part].get(
                        "source-branch"
                    )
                    gh_part["tag"] = content["parts"][part].get("source-tag")
                    parts.append(gh_part)

        return parts

    def has_repo_changed_since(self, owner, repo, timestamp, branch=None):
        if not branch:
            branch = self.get_default_branch(owner, repo)

        response = self._request(
            "GET",
            f"repos/{owner}/{repo}/commits/{branch}",
            raise_exceptions=False,
        )

        if response.status_code in [404, 403]:
            raise InvalidGitHubRepo("The branch doesn't exist")

        response.raise_for_status()

        last_commit = dateutil.parser.parse(
            response.json()["commit"]["committer"]["date"]
        ).timestamp()

        if last_commit > timestamp:
            return True

        return False
