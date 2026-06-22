# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import csv
import io
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth.decorators import panopticon_required
from toolkit.members.models import Member, Volunteer

from .emails import (
    send_access_needs_ack,
    send_organiser_notification,
    send_signup_confirmation,
    send_welcome_email,
)
from .forms import (
    AccessNeedsForm,
    InductionRequestAdminForm,
    InductionSessionForm,
    InductionsSettingsForm,
    SignupForm,
)
from .models import (
    InductionRequest,
    InductionSession,
    InductionSignup,
    InductionsSettings,
    get_inductions_settings,
)

logger = logging.getLogger(__name__)


def _check_enabled():
    if not get_inductions_settings().inductions_enabled:
        raise Http404


# ─── Public views ────────────────────────────────────────────────────────────


def signup(request, slug):
    _check_enabled()
    session = get_object_or_404(InductionSession, slug=slug, status=InductionSession.STATUS_OPEN)

    if request.method == "POST":
        form = SignupForm(request.POST, session=session)
        if form.is_valid():
            InductionSignup.objects.create(
                session=session,
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                custom_responses=form.get_custom_responses(),
            )
            try:
                send_signup_confirmation(request, InductionSignup.objects.filter(
                    session=session,
                    email=form.cleaned_data["email"],
                ).order_by("-signed_up_at").first())
            except Exception:
                logger.exception("Failed to send signup confirmation email")
            return redirect("inductions:signup_thanks", slug=slug)
    else:
        form = SignupForm(session=session)

    return render(request, "inductions/signup.html", {
        "form": form,
        "session": session,
    })


def signup_thanks(request, slug):
    _check_enabled()
    session = get_object_or_404(InductionSession, slug=slug)
    return render(request, "inductions/signup_thanks.html", {"session": session})


def calendar_ics(request, slug):
    _check_enabled()
    session = get_object_or_404(InductionSession, slug=slug)
    venue = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    start = session.date.strftime("%Y%m%dT%H%M%S")
    # Assume 2-hour induction if no end time
    end_dt = session.date + timezone.timedelta(hours=2)
    end = end_dt.strftime("%Y%m%dT%H%M%S")
    uid = f"induction-{session.slug}@{request.get_host()}"
    summary = f"{session.title} — {venue} Induction"
    location = session.location or venue

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cube Toolkit//Inductions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=Europe/London:{start}",
        f"DTEND;TZID=Europe/London:{end}",
        f"SUMMARY:{summary}",
        f"LOCATION:{location}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    content = "\r\n".join(ics_lines) + "\r\n"
    return HttpResponse(content, content_type="text/calendar; charset=utf-8")


def access_needs_signup(request):
    _check_enabled()
    if request.method == "POST":
        form = AccessNeedsForm(request.POST)
        if form.is_valid():
            req = InductionRequest.objects.create(
                name=form.cleaned_data["name"],
                email=form.cleaned_data["email"],
                access_needs=form.cleaned_data["access_needs"],
                rough_availability=form.cleaned_data.get("rough_availability", ""),
            )
            try:
                send_access_needs_ack(request, req)
            except Exception:
                logger.exception("Failed to send access needs ack email")
            try:
                send_organiser_notification(req)
            except Exception:
                logger.exception("Failed to send organiser notification email")
            return redirect("inductions:access_needs_thanks")
    else:
        form = AccessNeedsForm()

    return render(request, "inductions/access_needs_signup.html", {"form": form})


def access_needs_thanks(request):
    _check_enabled()
    return render(request, "inductions/access_needs_thanks.html")


def session_list_public(request):
    """Public listing of all currently-open induction sessions."""
    _check_enabled()
    sessions = (
        InductionSession.objects
        .filter(status=InductionSession.STATUS_OPEN)
        .order_by("date")
    )
    return render(request, "inductions/session_list_public.html", {"sessions": sessions})


# ─── Panopticon management views ─────────────────────────────────────────────


@panopticon_required
def manage_session_list(request):
    sessions = InductionSession.objects.prefetch_related("signups").order_by("-date")
    return render(request, "inductions/manage/session_list.html", {
        "sessions": sessions,
    })


@panopticon_required
def manage_session_new(request):
    if request.method == "POST":
        form = InductionSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            messages.success(request, f"Session '{session.title}' created.")
            return redirect("inductions:manage_session_detail", slug=session.slug)
    else:
        form = InductionSessionForm()

    return render(request, "inductions/manage/session_form.html", {
        "form": form,
        "title": "New induction session",
        "custom_questions_json": "[]",
    })


@panopticon_required
def manage_session_edit(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    import json
    if request.method == "POST":
        form = InductionSessionForm(request.POST, instance=session)
        raw_questions = request.POST.get("custom_questions_raw", "[]")
        try:
            questions = json.loads(raw_questions)
        except (ValueError, TypeError):
            questions = session.custom_questions

        if form.is_valid():
            s = form.save(commit=False)
            s.custom_questions = questions
            s.save()
            messages.success(request, "Session updated.")
            return redirect("inductions:manage_session_detail", slug=s.slug)
    else:
        form = InductionSessionForm(instance=session)

    return render(request, "inductions/manage/session_form.html", {
        "form": form,
        "session": session,
        "title": f"Edit — {session.title}",
        "custom_questions_json": json.dumps(session.custom_questions),
    })


@panopticon_required
def manage_session_detail(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    signups = list(session.signups.select_related("volunteer__member", "volunteer__user", "checked_in_by"))
    signup_url = request.build_absolute_uri(
        reverse("inductions:signup", kwargs={"slug": slug})
    )
    accounts_created = sum(1 for s in signups if s.volunteer_id)
    return render(request, "inductions/manage/session_detail.html", {
        "session": session,
        "signups": signups,
        "signup_url": signup_url,
        "accounts_created": accounts_created,
    })


@require_POST
@panopticon_required
def manage_session_close(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    session.status = InductionSession.STATUS_CLOSED
    session.save()
    messages.success(request, f"'{session.title}' is now closed to new sign-ups.")
    return redirect("inductions:manage_session_detail", slug=slug)


@require_POST
@panopticon_required
def manage_session_purge(request, slug):
    session = get_object_or_404(InductionSession, slug=slug)
    count = _purge_session(session)
    messages.success(request, f"Purged {count} pending/no-show record(s).")
    return redirect("inductions:manage_session_detail", slug=slug)


@require_POST
@panopticon_required
def manage_check_in(request, slug, signup_id):
    """Legacy AJAX endpoint kept for backwards compatibility — creates account immediately."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        return JsonResponse({"ok": False, "error": "Already checked in."})

    try:
        volunteer = _create_volunteer_from_signup(signup)
        send_welcome_email(request, signup, volunteer.user)
        signup.status = InductionSignup.STATUS_CHECKED_IN
        signup.volunteer = volunteer
        signup.checked_in_at = timezone.now()
        signup.checked_in_by = request.user
        signup.save()
        logger.info(
            f"{request.user} checked in {signup.name} (signup #{signup.pk}) "
            f"for session '{session.title}'"
        )
        return JsonResponse({
            "ok": True,
            "volunteer_id": volunteer.pk,
            "checked_in_at": signup.checked_in_at.strftime("%H:%M"),
        })
    except Exception as exc:
        logger.exception(f"Check-in failed for signup #{signup_id}")
        return JsonResponse({"ok": False, "error": str(exc)})


@require_POST
@panopticon_required
def manage_mark_attendance(request, slug, signup_id):
    """AJAX: toggle a signup's attendance status (CHECKED_IN <-> PENDING).

    Does NOT create a volunteer account. The 'Create accounts' step does that.
    """
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.volunteer_id:
        # Account already created — cannot unmark
        return JsonResponse({"ok": False, "error": "Account already created — cannot unmark attendance."})

    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        signup.status = InductionSignup.STATUS_PENDING
        signup.checked_in_at = None
        signup.checked_in_by = None
        signup.save()
        return JsonResponse({"ok": True, "status": "pending"})

    if signup.status == InductionSignup.STATUS_PENDING:
        signup.status = InductionSignup.STATUS_CHECKED_IN
        signup.checked_in_at = timezone.now()
        signup.checked_in_by = request.user
        signup.save()
        return JsonResponse({"ok": True, "status": "checked_in"})

    return JsonResponse({"ok": False, "error": f"Cannot mark attendance for a {signup.get_status_display()} signup."})


@require_POST
@panopticon_required
def manage_create_accounts(request, slug):
    """Create volunteer accounts and send welcome emails for all CHECKED_IN signups.

    Only processes signups that are CHECKED_IN and do not yet have a volunteer FK.
    This is the irreversible step, separated from the checkbox attendance-marking.
    """
    session = get_object_or_404(InductionSession, slug=slug)
    pending_checkins = session.signups.filter(
        status=InductionSignup.STATUS_CHECKED_IN,
        volunteer__isnull=True,
    )

    created = []
    errors = []
    for signup in pending_checkins:
        try:
            volunteer = _create_volunteer_from_signup(signup)
            send_welcome_email(request, signup, volunteer.user)
            signup.volunteer = volunteer
            signup.save()
            created.append({"signup_id": signup.pk, "name": signup.name, "volunteer_id": volunteer.pk, "username": volunteer.user.username})
            logger.info(
                f"{request.user} created account for {signup.name} (signup #{signup.pk}) "
                f"for session '{session.title}'"
            )
        except Exception as exc:
            logger.exception(f"Account creation failed for signup #{signup.pk}")
            errors.append({"signup_id": signup.pk, "name": signup.name, "error": str(exc)})

    return JsonResponse({"ok": True, "created": created, "errors": errors})


@require_POST
@panopticon_required
def manage_edit_signup(request, slug, signup_id):
    """AJAX: edit name and/or email for a signup (before account creation)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)

    if signup.volunteer_id:
        return JsonResponse({"ok": False, "error": "Account already created — edit the volunteer profile instead."})

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    desired_username = request.POST.get("desired_username", "").strip()

    if name:
        signup.name = name
    if email:
        signup.email = email
    signup.desired_username = desired_username
    signup.save()

    return JsonResponse({
        "ok": True,
        "name": signup.name,
        "email": signup.email,
        "desired_username": signup.desired_username,
    })


@require_POST
@panopticon_required
def manage_no_show(request, slug, signup_id):
    """AJAX endpoint: toggle no-show (pending → no_show, or no_show → pending)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    if signup.status == InductionSignup.STATUS_CHECKED_IN:
        return JsonResponse({"ok": False, "error": "Already checked in — cannot mark as no-show."})
    if signup.status == InductionSignup.STATUS_NO_SHOW:
        signup.status = InductionSignup.STATUS_PENDING
        signup.save()
        return JsonResponse({"ok": True, "new_status": "pending"})
    signup.status = InductionSignup.STATUS_NO_SHOW
    signup.save()
    return JsonResponse({"ok": True, "new_status": "no_show"})


@panopticon_required
def manage_export_csv(request, slug):
    """Download a Simplelists-ready CSV of checked-in attendees."""
    session = get_object_or_404(InductionSession, slug=slug)
    checked_in = session.signups.filter(status=InductionSignup.STATUS_CHECKED_IN)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="induction-{slug}-checked-in.csv"'
    )
    writer = csv.writer(response)
    for s in checked_in:
        writer.writerow([s.first_name, s.last_name, s.email])
    return response


@panopticon_required
def manage_access_needs_list(request):
    requests = InductionRequest.objects.exclude(status=InductionRequest.STATUS_PURGED)
    status_filter = request.GET.get("status")
    if status_filter:
        requests = requests.filter(status=status_filter)
    return render(request, "inductions/manage/access_needs_list.html", {
        "requests": requests,
        "status_choices": InductionRequest.STATUS_CHOICES,
        "current_status": status_filter,
    })


@panopticon_required
def manage_access_needs_detail(request, request_id):
    req = get_object_or_404(InductionRequest, pk=request_id)
    if request.method == "POST":
        form = InductionRequestAdminForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            messages.success(request, "Request updated.")
            return redirect("inductions:manage_access_needs_detail", request_id=request_id)
    else:
        form = InductionRequestAdminForm(instance=req)

    return render(request, "inductions/manage/access_needs_detail.html", {
        "req": req,
        "form": form,
    })


@panopticon_required
def manage_settings(request):
    cfg = InductionsSettings.load()
    if request.method == "POST":
        form = InductionsSettingsForm(request.POST, instance=cfg)
        if form.is_valid():
            form.save()
            messages.success(request, "Inductions settings saved.")
            return redirect("inductions:manage_settings")
    else:
        form = InductionsSettingsForm(instance=cfg)

    return render(request, "inductions/manage/settings.html", {"form": form})


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _create_volunteer_from_signup(signup: InductionSignup) -> Volunteer:
    """Create Member + User + Volunteer records from an InductionSignup."""
    name = signup.name or ""
    email = signup.email or ""

    member = Member(
        name=name,
        email=email,
        gdpr_opt_in=timezone.now(),
    )
    member.save()

    base = (slugify(signup.desired_username)[:40] if signup.desired_username else None) or slugify(name)[:40] or "volunteer"
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}-{n}"
        n += 1

    user = User(
        username=username,
        email=email,
        first_name=name.split()[0] if name else "",
        last_name=" ".join(name.split()[1:]) if name else "",
    )
    user.set_unusable_password()
    user.save()

    volunteer = Volunteer(user=user, member=member)
    volunteer.save()

    return volunteer


def _purge_session(session: InductionSession) -> int:
    """Null PII on pending/no-show signups. Returns count of records purged."""
    to_purge = session.signups.filter(
        status__in=[InductionSignup.STATUS_PENDING, InductionSignup.STATUS_NO_SHOW]
    )
    count = to_purge.count()
    to_purge.update(name="", email="", custom_responses={})
    session.status = InductionSession.STATUS_PURGED
    session.save()
    return count
