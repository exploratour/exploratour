from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    abort,
)
from collections import namedtuple
from exploratour.storage import Record, NoResultFound

bp = Blueprint("records", __name__, url_prefix="/record")


@bp.route("/", methods=("GET",))
def view():
    id = request.args.get("id")
    try:
        record = Record.query.filter(Record.id==id).one()
    except NoResultFound:
        abort(404, "No record with given id")

    return render_template(
        "records/view.html",
        record=record
    )
