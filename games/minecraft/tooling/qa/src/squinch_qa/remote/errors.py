class RemoteError(Exception):
    """Base class for remote GitHub Actions orchestration failures."""


class GhError(RemoteError):
    """A `gh` subprocess failed, timed out, or emitted unusable data."""


class DispatchError(RemoteError):
    """The workflow_dispatch request could not be submitted."""


class PollError(RemoteError):
    """The dispatched workflow run could not be found or inspected."""


class PollTimeoutError(PollError):
    """The workflow run did not reach a terminal state in time."""


class DownloadError(RemoteError):
    """The expected GitHub Actions artifact could not be downloaded or verified."""
