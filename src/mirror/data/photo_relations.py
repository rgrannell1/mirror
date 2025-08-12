from typing import Iterator

import markdown

from mirror.data.types import SemanticTriple
from mirror.utils import deterministic_hash_str


class PhotoRelationsReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        allowed_relations = {
            "bird_binomial",
            "summary",
            "style",
            "location",
            "mammal_binomial",
            "subject",
            "rating",
            "living_conditions",
            "wildlife",
            "plane_model",
            "vehicle",
        }

        for row in db.photo_metadata_table().list():
            # not sure this is useable in practice, check it's used...
            photo_id = deterministic_hash_str(row.fpath)

            if row.relation not in allowed_relations:
                continue

            target = row.target
            if row.relation == "summary":
                target = markdown.markdown(row.target)

            yield SemanticTriple(photo_id, row.relation, target)
