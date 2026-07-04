"""Custom exceptions"""


class MirrorAuditError(Exception):
    """Raised to abort the pipeline when blocking publication issues are found."""


class InvalidVideoDimensionsError(Exception):
    pass


class VideoResolutionLookupError(Exception):
    pass


class VideoReadError(Exception):
    pass
