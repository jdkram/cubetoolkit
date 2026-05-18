from datetime import timedelta

from django.db import connection, OperationalError
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Min, Q
from django.http import HttpResponse, HttpResponseServerError
from django.utils import timezone
from django.views.generic import ListView

from toolkit.diary.models import RotaEntry, Showing, VolunteerEventMark, get_site_config
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

            unconfirmed_showings = list(
                Showing.objects.filter(
                    confirmed=False,
                    start__gte=now,
                    start__lte=now + timedelta(days=42),
                )
                .select_related("event")
                .order_by("start")[:8]
            )
            if unconfirmed_showings:
                context["unconfirmed_showings"] = unconfirmed_showings

        # Rota gaps — all logged-in users (9.91)
        cfg = get_site_config()
        if cfg.rota_gap_min_missing or cfg.rota_gap_min_pct:
            qs = (
                Showing.objects.filter(
                    start__gte=now,
                    start__lte=now + timedelta(days=21),
                    confirmed=True,
                )
                .annotate(
                    total_required=Count(
                        "rotaentry", filter=Q(rotaentry__required=True)
                    ),
                    filled=Count(
                        "rotaentry",
                        filter=Q(rotaentry__required=True)
                        & (
                            Q(rotaentry__volunteer__isnull=False)
                            | Q(rotaentry__name__gt="")
                        ),
                    ),
                )
                .annotate(
                    missing=ExpressionWrapper(
                        F("total_required") - F("filled"),
                        output_field=IntegerField(),
                    )
                )
                .select_related("event")
                .order_by("start")
            )
            gap_filter = Q()
            if cfg.rota_gap_min_missing:
                gap_filter |= Q(missing__gte=cfg.rota_gap_min_missing)
            if cfg.rota_gap_min_pct:
                gap_filter |= Q(
                    total_required__gt=0,
                    missing__gte=ExpressionWrapper(
                        F("total_required") * cfg.rota_gap_min_pct / 100,
                        output_field=IntegerField(),
                    ),
                )
            showings_with_gaps = list(qs.filter(gap_filter)[:8])
            if showings_with_gaps:
                context["showings_with_gaps"] = showings_with_gaps

        # Upcoming inductions & training — all logged-in users (9.93)
        upcoming_training = list(
            Showing.objects.filter(
                confirmed=True,
                start__gte=now,
                start__lte=now + timedelta(days=42),
                event__tags__name__in=["induction", "training-for-volunteers"],
            )
            .select_related("event")
            .order_by("start")
            .distinct()[:8]
        )
        if upcoming_training:
            context["upcoming_training"] = upcoming_training

        return context


def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return HttpResponseServerError("db unavailable")
    return HttpResponse("ok")
