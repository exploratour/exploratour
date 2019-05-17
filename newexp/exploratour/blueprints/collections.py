from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from exploratour.storage import Record, Collection

bp = Blueprint('collections', __name__, url_prefix='/coll')

@bp.route('/', methods=('GET',))
def index():
    groups = Collection.query.filter(Collection.parents==None).order_by(Collection.id)
    return render_template('collections/index.html',
        groups = groups,
        collections = Collection.query.all()
    )
