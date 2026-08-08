"""Detect subject bounding boxes in photos with GroundingDINO."""

import logging
from functools import lru_cache
from typing import Any

from PIL import Image

from mirror.commons.constants import (
    DETECTION_CONFIDENCE_THRESHOLD,
    DETECTION_MODEL_ID,
    DETECTION_PROMPT_OVERRIDES,
    DETECTION_TORCH_THREADS,
)
from mirror.models.detection import DetectionBox, box_volume


def normalise_phrase(phrase: str) -> str:
    """Lower-case a prompt phrase and give it the trailing full stop GroundingDINO expects."""
    phrase = phrase.lower().strip()

    if not phrase.endswith("."):
        return f"{phrase}."
    return phrase


def prompt_for_type(subject_type: str) -> str:
    """Map a subject URN type to a GroundingDINO text prompt."""
    return normalise_phrase(DETECTION_PROMPT_OVERRIDES.get(subject_type, subject_type))


def build_prompt(subject_type: str, names: tuple[str, ...] = ()) -> str:
    """Compose the detection prompt: each known subject name, then the type prompt.

    Names like "grey heron" ground better than category words like "bird", but
    the type prompt stays as a fallback for names the model does not know.
    """
    phrases = [normalise_phrase(name) for name in names]
    phrases.append(prompt_for_type(subject_type))

    deduped = list(dict.fromkeys(phrases))
    return " ".join(deduped)


@lru_cache(maxsize=1)
def load_detection_model() -> tuple[Any, Any]:
    """Load the GroundingDINO processor and model once per process."""
    # torch and transformers take seconds to import. A top-level import would slow
    # every mirror command; only detection jobs pay the cost here.
    import torch  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        AutoModelForZeroShotObjectDetection,
        AutoProcessor,
    )

    # The hub client logs every revalidation request at INFO; that is noise here.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

    torch.set_num_threads(DETECTION_TORCH_THREADS)

    # Cached weights load without any hub requests; fall back online for first fetch.
    try:
        processor = AutoProcessor.from_pretrained(DETECTION_MODEL_ID, local_files_only=True)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(
            DETECTION_MODEL_ID, local_files_only=True
        )
    except OSError:
        processor = AutoProcessor.from_pretrained(DETECTION_MODEL_ID)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(DETECTION_MODEL_ID)

    model.eval()
    return processor, model


def result_to_boxes(result: dict, width: int, height: int) -> list[DetectionBox]:
    """Convert one post-processed GroundingDINO result to DetectionBox dicts.

    The model can overshoot the image edges slightly, so boxes are clamped to it.
    """
    boxes: list[DetectionBox] = []

    for coords, score in zip(result["boxes"].tolist(), result["scores"].tolist()):
        x1_coord, y1_coord, x2_coord, y2_coord = (float(coord) for coord in coords)
        clamped = [
            round(min(max(x1_coord, 0), width), 1),
            round(min(max(y1_coord, 0), height), 1),
            round(min(max(x2_coord, 0), width), 1),
            round(min(max(y2_coord, 0), height), 1),
        ]
        boxes.append({
            "coords": clamped,
            "volume": box_volume(clamped),
            "confidence": round(float(score), 3),
        })

    return boxes


def detect_boxes(
    image_path: str,
    prompt: str,
    threshold: float = DETECTION_CONFIDENCE_THRESHOLD,
) -> tuple[list[DetectionBox], int]:
    """Find bounding boxes matching a prompt (see build_prompt) in an image.

    Returns (boxes, image pixel area). Boxes are [x1, y1, x2, y2] in the pixels
    of the searched file. An empty list means the image was searched and nothing
    passed the threshold.
    """
    import torch  # noqa: PLC0415

    processor, model = load_detection_model()

    with Image.open(image_path) as image_fh:
        image = image_fh.convert("RGB")

    inputs = processor(images=image, text=prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=threshold,
        text_threshold=threshold,
        target_sizes=[(image.height, image.width)],
    )
    boxes = result_to_boxes(results[0], image.width, image.height)
    return boxes, image.width * image.height
