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

def read_mammals():
  mammals = {}

  with open('/home/rg/Code/mirror/src/data/mammals.csv', 'r') as conn:
    reader = csv.reader(conn)
    next(reader)

    for name, species in reader:
      mammals[species] = name

  return mammals

def read_flags():
  flags = {}

  with open('/home/rg/Code/mirror/src/data/flags.csv', 'r') as conn:
    reader = csv.reader(conn)
    next(reader)

    for name, flag in reader:
      flags[name] = flag

  return flags

birds = read_birds()
mammals = read_mammals()
flags = read_flags()

def image_answers_to_relations(question_id: str, source: str, target: str):
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
      (source, 'contains', target),
      (target, 'is-a', 'Animal'),
      (target, 'is-a', 'Amphibian'),
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
  elif question_id == 'q15':
    mammal_species = target.split(',')

    for mammal in mammal_species:
      if mammal.strip() not in mammals:
        print(f"Unknown mammal species: {mammal}", file=sys.stderr)

    rows = []

    for species in mammal_species:
      if species in mammals:
        rows += [
          (source, 'contains', mammals[species.strip()]),
          (mammals[species.strip()], 'is-a', 'Mammal'),
          (mammals[species.strip()], 'is-a', 'Animal'),
        ]
      else:
        print(f"Unknown mammal species: {species}")
  elif question_id == 'q16':
    return [
      (source, 'contains', target),
      (target, 'is-a', 'Named Body of Water')
    ]
  elif question_id == 'q17':
    return [
      (source, 'contains', target),
      (target, 'is-a', 'Helicopter')
    ]
  else:
    raise Exception(f"Unknown question_id: {question_id}")

  return rows

def album_answers_to_relations(question_id: str, album_id: str, target: str):
  rows = []
  if question_id == 'q01':
    countries = target.split(',')

    for country in countries:
      flag = flags.get(country.strip())

      if flag is None:
        rows += [(album_id, 'country', country.strip())]

      rows += [(album_id, 'country', country.strip()), (country.strip(), 'flag', flag)]

  elif question_id == 'q02':
    return [(album_id, 'description', target)]
  elif question_id == 'q03':
    return [(album_id, 'album_name', target)]
  elif question_id == 'q04':
    return [(album_id, 'permalink', target)]

  return rows

class AnswersDB:
  def __init__(self, db_path: str):
    fpath = os.path.expanduser(db_path)
    self.conn = sqlite3.connect(fpath)

  def get_image_answers(self):
    cursor = self.conn.cursor()
    cursor.execute("select questionId, contentId, answer from image_answers", ())

    return [row for row in cursor.fetchall()]

  def get_album_answers(self):
    cursor = self.conn.cursor()
    cursor.execute("select questionId, contentId, answer from album_answers", ())

    return [row for row in cursor.fetchall()]

def add_answers(_: str, metadata_path: str, database_path: str):
  answers_db = AnswersDB(database_path)

  manifest = Manifest(DB_PATH, metadata_path)
  manifest.create()

  manifest.clear_photo_relations()

  for question_id, content_id, answer in answers_db.get_image_answers():
    try:
      relations = image_answers_to_relations(question_id, content_id, answer)
    except Exception as err:
      print(err)
      continue

    for source, relation, target in relations:
      manifest.add_photo_relation(source, relation, target)

  for question_id, content_id, answer in answers_db.get_album_answers():
    try:
      relations = album_answers_to_relations(question_id, content_id, answer)
    except Exception as err:
      print(err)
      continue

    for source, relation, target in relations:
      manifest.add_photo_relation(source, relation, target)
