class InvalidGitHubRepo(Exception):
    """
    Exception for any errors in the GitHub repo
    """

    pass


class GitHubRateLimit(Exception):
    """
    Exception for API rate limit exceeded
    """

    pass
