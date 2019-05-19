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
    ARGS = (
        ("id", "", str),
        ("showfull", 0, int),
        ("startrank", 0, int),
        ("order", "collection", str),
        ("per_page", 100, int),
    )

    def __init__(self):
        self.args = {}
        for arg, default, cast in CollTabData.ARGS:
            try:
                self.args[arg] = cast(request.args.get(arg, default))
                setattr(self, arg, self.args[arg])
            except ValueError:
                abort(400, "Invalid value for argument {}", arg)

        try:
            self.collection = Collection.query.filter(Collection.id == self.id).one()
        except NoResultFound:
            abort(404)

        self.active_tabs = tuple(tab for tab in tabs if tab.active(self.collection))

    def link_args(self, **extra):
        """Get the arguments needed for a link within the collection"""
        non_default_args = {"id": self.id}
        args = {}
        args.update(self.args, **extra)
        for arg, default, cast in CollTabData.ARGS:
            if args[arg] != cast(default):
                non_default_args[arg] = self.args[arg]
        return non_default_args

    def template_params(self, **extra):
        result = {}
        result.update(
            dict(
                id=self.id,
                collection=self.collection,
                active_tabs=self.active_tabs,
                args=self.args,
                link_args=self.link_args,
            ),
            **extra
        )
        return result


@bp.route("/coll/children", methods=("GET",))
def collection_children():
    data = CollTabData()

    return render_template(
        "collections/children.html",
        **data.template_params(collections=data.collection.children)
    )


tabs.append(
    Tab("collection_children", "Children", lambda collection: collection.children)
)


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
    records = records.offset(data.startrank).limit(data.per_page)

    return render_template(
        "collections/records.html", **data.template_params(records=records)
    )


tabs.append(Tab("collection_records", "Records", lambda _: True))


@bp.route("/coll/parents", methods=("GET",))
def collection_parents():
    data = CollTabData()

    return render_template(
        "collections/parents.html",
        **data.template_params(collections=data.collection.parents)
    )


tabs.append(
    Tab(
        "collection_parents",
        "Parent Collections",
        lambda collection: collection.parents,
    )
)
