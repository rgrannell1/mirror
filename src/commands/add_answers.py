import os
import sqlite3
from typing import List

from src.constants import DB_PATH
from src.manifest import Manifest
from src.photo import PhotoVault


def to_relations(question_id: str, target: str):
  if question_id == 'q01':
    return [
      ('photo_subject', target)
    ]
  elif question_id == 'q02':
    return [
      ('contains', 'Animal'),
      ('contains', target)
    ]
  elif question_id == 'q03':
    return [
      ('animal_lifestyle', target)
    ]
  elif question_id == 'q03_5':
    return [
      ('animal_lifestyle', target)
    ]
  elif question_id == 'q04':
    if target == 'Unsure' or target == 'Other':
      return []

    return [
      ('contains', target)
    ]
  elif question_id == 'q05':
    return [
      ('rating', target)
    ]
  elif question_id == 'q06':
    if target == 'Yes':
      return [
        ('animal_behaviour', 'Flying')
      ]

    return []
  elif question_id == 'q07':
    if target == "Yes":
      return [
        ('contains', "Water")
      ]
    else:
      return []
  elif question_id == 'q08':
    return [
      ('waterway_type', target)
    ]
  elif question_id == 'q09':
    return [
      ('cityscape_focus', target)
    ]
  elif question_id == 'q10':
    return [
      ('waterway_type', target)
    ]
  elif question_id == 'q11':
    return [
      ('description', target)
    ]
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


def add_answers(dir: str, metadata_path: str, database_path: str):
  answers_db = AnswersDB(database_path)
  manifest = Manifest(DB_PATH, metadata_path)
  manifest.create()

  manifest.clear_photo_relations()

  for question_id, content_id, answer in answers_db.get_photo_answers():
    try:
      relations = to_relations(question_id, answer)
    except Exception as err:
      print(err)
      continue

    for relation in relations:
      rel, val = relation

      manifest.add_photo_relation(content_id, rel, val)
