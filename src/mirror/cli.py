import logging
import multiprocessing
from pathlib import Path

from mirror.workflows.workflow import MirrorWorkflow
from zahir import LocalScope, LocalWorkflow, MemoryContext, SQLiteJobRegistry

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

_WORKFLOWS_DIR = Path(__file__).resolve().parent / "workflows"


def main():
    """Execute the upload media workflow"""

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    job_registry = SQLiteJobRegistry("mirror_jobs.db")
    context = MemoryContext(
        scope=LocalScope().scan(_WORKFLOWS_DIR),
        job_registry=job_registry,
    )

    start = MirrorWorkflow({ "upload_videos": False, "upload_images": True }, {})

    for event in LocalWorkflow(context, max_workers=15, otel_output_dir=None).run(start):
        print(event.output)

if __name__ == "__main__":
    main()
