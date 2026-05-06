from django.db import connection, OperationalError
from django.http import HttpResponse, HttpResponseServerError
from django.views.generic import ListView

from toolkit.index.models import IndexLink


class ToolkitIndexView(ListView):
    model = IndexLink
    template_name = "toolkit_index.html"


def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return HttpResponseServerError("db unavailable")
    return HttpResponse("ok")
