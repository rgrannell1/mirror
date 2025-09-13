from typing import Iterator

import markdown

from mirror.constants import URN_PREFIX
from mirror.data.types import SemanticTriple
from mirror.utils import deterministic_hash_str


class PhotoRelationsReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        allowed_relations = {
            "summary",
            "style",
            "location",
            "subject",
            "rating",
            "wildlife",
            "cover"
        }

        for row in db.photo_metadata_table().list():
            # not sure this is useable in practice, check it's used...
            photo_id = deterministic_hash_str(row.fpath)

            if row.relation not in allowed_relations:
                continue

            target = row.target
            if row.relation == "summary":
                target = markdown.markdown(row.target)

            yield SemanticTriple(f"{URN_PREFIX}photo:{photo_id}", row.relation, target)
