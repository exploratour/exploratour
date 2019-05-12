import os

TOP_DIR = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
DATA_PATH = os.path.join(TOP_DIR, "data")
DB_PATH = os.path.join(DATA_PATH, "db.sqlite")
