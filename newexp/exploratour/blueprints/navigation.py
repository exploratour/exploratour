from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from exploratour.storage import Record, Collection

bp = Blueprint('navigation', __name__)

@bp.route('/', methods=('GET',))
def index():
    return render_template('index.html',
            records=Record.query.count(),
            collections=Collection.query.count(),
    )
