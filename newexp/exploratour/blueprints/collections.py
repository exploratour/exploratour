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
from exploratour.storage import Record, Collection, NoResultFound

bp = Blueprint("collections", __name__, url_prefix="/coll")


@bp.route("/list", methods=("GET",))
def index():
    groups = Collection.query.filter(Collection.parents == None).order_by(
        Collection.title, Collection.id
    )
    if groups:
        group_id = request.args.get("group", groups[0].id)
        collections = Collection.query.filter(Collection.id == group_id).order_by(
            Collection.title, Collection.id
        )

    else:
        collections = []

    return render_template(
        "collections/index.html", groups=groups, collections=collections
    )


@bp.route("/coll/", methods=("GET",))
def collection():
    return redirect(url_for("collections.collection_records", **request.args))


Tab = namedtuple("Tab", ("route", "title", "active"))
tabs = []


class CollTabData:
    def __init__(self):
        self.collid = request.args.get("id")

        try:
            self.collection = Collection.query.filter(
                Collection.id == self.collid
            ).one()
        except NoResultFound:
            abort(404)

        self.active_tabs = tuple(tab for tab in tabs if tab.active(self.collection))

        self.args = {"id": self.collid}
        for arg, default, cast in (
            ("showfull", 0, int),
            ("startrank", 0, int),
            ("order", "collection", str),
            ("per_page", 100, int),
        ):
            try:
                self.args[arg] = cast(request.args.get(arg, default))
                setattr(self, arg, self.args[arg])
            except ValueError:
                abort(400, "Invalid value for argument {}", arg)

    def template_params(self, **extra):
        result = {}
        result.update(
            dict(
                id=self.collid,
                collection=self.collection,
                active_tabs=self.active_tabs,
                args=self.args,
            ),
            **extra
        )
        print(result)
        return result


@bp.route("/coll/records", methods=("GET",))
def collection_records():
    data = CollTabData()

    records = data.collection.records
    if data.order == "collection":
        records = records.order_by(Record.mtime.desc(), Record.id)
    elif data.order == "mtime":
        records = records.order_by(Record.mtime.asc(), Record.id)
    elif data.order == "-mtime":
        records = records.order_by(Record.mtime.desc(), Record.id.desc())
    elif data.order == "title":
        records = records.order_by(Record.title.asc(), Record.id.asc())
    elif data.order == "-title":
        records = records.order_by(Record.title.desc(), Record.id.desc())
    records = records.offset(data.args["startrank"]).limit(100)

    return render_template(
        "collections/records.html", **data.template_params(records=records)
    )


tabs.append(Tab("collection_records", "Records", lambda _: True))
