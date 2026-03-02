from django.views.generic import ListView

from toolkit.index.models import IndexLink


class ToolkitIndexView(ListView):
    model = IndexLink
    template_name = "toolkit_index.html"
