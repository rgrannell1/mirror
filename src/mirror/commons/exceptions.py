"""Custom exceptions"""


class MirrorAuditError(Exception):
    """Raised to abort the pipeline when blocking publication issues are found."""


class GithubPublishError(Exception):
    """Raised when the manifest cannot be published to GitHub."""


class WebsiteBuildError(Exception):
    """Raised when a website build step fails, carrying the output tail."""


class InvalidVideoDimensionsError(Exception):
    pass


class VideoResolutionLookupError(Exception):
    pass


class VideoReadError(Exception):
    pass
