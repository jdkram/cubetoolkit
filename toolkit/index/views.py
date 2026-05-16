from datetime import timedelta

from django.db import connection, OperationalError
from django.db.models import Min, Q
from django.http import HttpResponse, HttpResponseServerError
from django.utils import timezone
from django.views.generic import ListView

from toolkit.diary.models import RotaEntry, Showing, VolunteerEventMark
from toolkit.index.models import IndexLink


class ToolkitIndexView(ListView):
    model = IndexLink
    template_name = "toolkit_index.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        try:
            volunteer = user.volunteer
        except Exception as e:
            volunteer = None

        if volunteer:
            context["has_volunteer"] = True
            context["upcoming_shifts"] = list(
                RotaEntry.objects.filter(
                    volunteer=volunteer,
                    showing__start__gte=now,
                    showing__confirmed=True,
                )
                .select_related("showing__event", "role")
                .order_by("showing__start")[:5]
            )
            context["starred_events"] = list(
                VolunteerEventMark.objects.filter(
                    volunteer=volunteer,
                    mark_type=VolunteerEventMark.MARK_STAR,
                )
                .annotate(
                    next_showing=Min(
                        "event__showings__start",
                        filter=Q(event__showings__start__gte=now),
                    )
                )
                .filter(next_showing__isnull=False)
                .select_related("event")
                .order_by("next_showing")[:5]
            )

        if user.has_perm("toolkit.write"):
            lookback_start = (
                max(user.last_login, now - timedelta(days=30))
                if user.last_login
                else now - timedelta(days=30)
            )
            new_showings = list(
                Showing.objects.filter(
                    created_at__gte=lookback_start,
                    start__gte=now,
                    event__private=False,
                )
                .select_related("event")
                .order_by("created_at")[:8]
            )
            if new_showings:
                context["new_showings"] = new_showings

        return context


def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return HttpResponseServerError("db unavailable")
    return HttpResponse("ok")
