import config
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import os
from .base import Base
from .record import Record
from .collection import Collection


class Storage:
    def __init__(self):
        if not os.path.exists(config.DATA_PATH):
            os.mkdir(config.DATA_PATH)
        self.engine = sqlalchemy.create_engine(
            "sqlite:///" + config.DB_PATH, echo=False
        )
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def start_session(self):
        return self.Session()


storage = Storage()
