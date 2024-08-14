import os
import csv
import sqlite3
import sys

from src.constants import DB_PATH
from src.manifest import Manifest


def read_birds():
  birds = {}

  with open('/home/rg/Code/mirror/src/data/birds.csv', 'r') as conn:
    reader = csv.reader(conn)
    next(reader)

    for name, species in reader:
      birds[species] = name

  return birds

birds = read_birds()

def to_relations(question_id: str, source: str, target: str):
  if question_id == 'q01':
    return [
      (source, 'photo_subject', target)
    ]
  elif question_id == 'q02':
    return [
      (source, 'contains', 'Animal'),
      (source, 'contains', target),
      (target, 'is-a', 'Animal')
    ]
  elif question_id == 'q03':
    return [
      (source, 'animal_lifestyle', target),
      (source, 'contains', 'Animal'),
      (target, 'is-a', 'Animal')
    ]
  elif question_id == 'q03_5':
    return [
      (source, 'animal_lifestyle', target),
      (source, 'contains', 'Animal'),
      (target, 'is-a', 'Animal')
    ]
  elif question_id == 'q04':
    if target == 'Unsure' or target == 'Other':
      return []

    return [
      (source, 'contains', target)
    ]
  elif question_id == 'q05':
    return [
      (source, 'rating', target)
    ]
  elif question_id == 'q06':
    if target == 'Yes':
      return [
        (source, 'animal_behaviour', 'Flying')
      ]

    return []
  elif question_id == 'q07':
    if target == "Yes":
      return [
        (source, 'contains', "Water")
      ]
    else:
      return []
  elif question_id == 'q08':
    return [
      (source, 'waterway_type', target)
    ]
  elif question_id == 'q09':
    return [
      (source, 'cityscape_focus', target)
    ]
  elif question_id == 'q10':
    return [
      (source, 'waterway_type', target)
    ]
  elif question_id == 'q11':
    return [
      (source, 'description', target),
      (target, 'is-a', 'Description')
    ]
  elif question_id == 'q12':
    return [
      (source, 'contains', target)
    ]
  elif question_id == 'q13':
    return [
      (source, 'contains', target),
      (target, 'is-a', 'Plane')
    ]
  elif question_id == 'q14':
    bird_species = target.split(',')

    for bird in bird_species:
      if bird.strip() not in birds:
        print(f"Unknown bird species: {bird}", file=sys.stderr)

    rows = []

    for species in bird_species:
      if species in birds:
        rows += [
          (source, 'contains', birds[species.strip()]),
          (birds[species.strip()], 'is-a', 'Bird'),
          (birds[species.strip()], 'is-a', 'Animal'),
        ]
      else:
        print(f"Unknown bird species: {species}")

    return rows
  else:
    raise Exception(f"Unknown question_id: {question_id}")


class AnswersDB:
  def __init__(self, db_path: str):
    fpath = os.path.expanduser(db_path)
    self.conn = sqlite3.connect(fpath)

  def get_photo_answers(self):
    cursor = self.conn.cursor()
    cursor.execute("select questionId, contentId, answer from answers", ())

    return [row for row in cursor.fetchall()]


def add_answers(_: str, metadata_path: str, database_path: str):
  answers_db = AnswersDB(database_path)
  manifest = Manifest(DB_PATH, metadata_path)
  manifest.create()

  manifest.clear_photo_relations()

  for question_id, content_id, answer in answers_db.get_photo_answers():
    try:
      relations = to_relations(question_id, content_id, answer)
    except Exception as err:
      print(err)
      continue

    for source, relation, target in relations:
      manifest.add_photo_relation(source, relation, target)
