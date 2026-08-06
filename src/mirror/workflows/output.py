"""User-facing workflow messages, relayed through the telemetry event stream.

Jobs must not print. Yield workflow_output(message) instead. The CLI collects
these events and prints them after the progress bar has stopped.
"""

from bookman.events import Event
from tertius import EEmit
from zahir.core.telemetry.events import tagged_point

# telemetry tag marking a user-facing workflow message
WORKFLOW_OUTPUT_TAG = "workflow_output"


def workflow_output(message: str) -> EEmit:
    """Build an emit effect carrying a user-facing message."""
    return EEmit(tagged_point(WORKFLOW_OUTPUT_TAG, {"message": [message]}))


def workflow_output_message(event: Event) -> str | None:
    """Return the message when the event is a workflow output, else None."""
    if WORKFLOW_OUTPUT_TAG not in event.dims.get("tag", []):
        return None
    return event.dims.get("message", [""])[0]
