from flask import (
    Blueprint,
)
from config import MEDIA_PATH

bp = Blueprint("media", __name__, static_url_path="/media", static_folder=MEDIA_PATH)
