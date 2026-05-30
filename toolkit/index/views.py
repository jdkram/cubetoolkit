import datetime
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db import connection, OperationalError
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Min, Q
from django.http import HttpResponse, HttpResponseServerError, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from toolkit.diary.models import RotaEntry, Showing, VolunteerEventMark, get_site_config
from toolkit.index.models import IndexLink
from toolkit.members.models import PanopticonGrant, Volunteer
from toolkit.toolkit_auth.decorators import panopticon_required


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

            # Welcome-back card: a logged-in Dormant volunteer is, by definition,
            # a returner. Offer a one-click route back to Active and nudge them
            # toward re-induction. Dismissable for the session (the card links
            # back here with ?dismiss_welcome=1).
            if self.request.GET.get("dismiss_welcome"):
                self.request.session["welcome_back_dismissed"] = True
            if (
                volunteer.status == Volunteer.STATUS_DORMANT
                and not self.request.session.get("welcome_back_dismissed")
            ):
                context["welcome_back"] = True
                context["next_induction"] = (
                    Showing.objects.filter(
                        confirmed=True,
                        start__gte=now,
                        event__tags__name__in=["induction", "training-for-volunteers"],
                    )
                    .select_related("event")
                    .order_by("start")
                    .distinct()
                    .first()
                )

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

        # Recent bulletins card (9.95). Only shows bulletins the current user
        # hasn't dismissed — "Got it" removes them from the dashboard entirely.
        from toolkit.labs.views import _unread_bulletins_for
        unread = list(_unread_bulletins_for(user)[:5])
        if unread:
            context["recent_bulletins"] = unread

        # Shopping list widget (9.88): items with open need flags.
        from toolkit.labs.models import NeedFlag
        shopping_needs = list(
            NeedFlag.objects.filter(resolved_at__isnull=True)
            .select_related("item", "flagged_by__member")
            .prefetch_related("pledge__pledged_by__member")
            .order_by("-flagged_at")[:8]
        )
        if shopping_needs:
            context["shopping_needs"] = shopping_needs

        return context


def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return HttpResponseServerError("db unavailable")
    return HttpResponse("ok")


@login_required
def toolkit_access(request):
    """Access transparency page: who holds elevated permissions and why.

    All logged-in volunteers can see this page.  It explains the three access
    tiers in plain language and lists current Panopticon and Programmer users.
    """
    panopticon_users = (
        User.objects.filter(is_superuser=True, is_active=True)
        .select_related("panopticon_grant")
        .order_by("panopticon_grant__granted_at", "username")
    )
    programmer_group = Group.objects.filter(name="Programmers").first()
    programmer_users = (
        programmer_group.user_set
        .filter(is_active=True)
        .select_related("programmer_grant")
        .order_by("username")
    ) if programmer_group else User.objects.none()

    return render(
        request,
        "toolkit_access.html",
        {
            "panopticon_users": panopticon_users,
            "programmer_users": programmer_users,
        },
    )


@panopticon_required
@require_POST
def mark_panopticon_reviewed(request, grant_id):
    """Mark a PanopticonGrant as reviewed today."""
    grant = get_object_or_404(PanopticonGrant, pk=grant_id)
    grant.last_reviewed_at = datetime.date.today()
    grant.reviewed_by = request.user
    grant.save()
    messages.success(request, f"Marked {grant.user.username}'s access as reviewed.")
    return HttpResponseRedirect(reverse("toolkit-access"))
