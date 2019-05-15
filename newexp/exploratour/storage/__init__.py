import config
import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from .base import Base
from .record import Record
from .collection import Collection


class Storage:
    def __init__(self):
        self.engine = sqlalchemy.create_engine(
            "sqlite:///" + config.DB_PATH, echo=False
        )
        self.session = scoped_session(sessionmaker(bind=self.engine))
        Base.query = self.session.query_property()

    def create_tables(self):
        if not os.path.isdir(config.DATA_PATH):
            os.makedirs(config.DATA_PATH)
        Base.metadata.create_all(self.engine)
