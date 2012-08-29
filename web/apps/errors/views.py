from apps.templates.render import render
from apps.record.views import add_search_to_context
from apps.store.models import Record, Template, Collection

class ErrorController(object):
    def error_page_404(self, status, message, traceback, version):
        context = dict(
            status=status,
            message=message,
            traceback=traceback,
            version=version,
            records = len(Record.objects),
            collections = len(Collection.objects),
            templates = len(Template.objects),
        )
        add_search_to_context(context)
        return render('errorpages/404.html', context)
