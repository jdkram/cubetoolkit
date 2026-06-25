# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import csv
import io
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth.decorators import panopticon_required
from toolkit.members.models import Member, Volunteer

from .emails import (
    send_access_needs_ack,
    send_new_signup_notification,
    send_organiser_notification,
    send_session_full_notification,
    send_signup_confirmation,
    send_test_notification_email,
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

    if session.is_full:
        return render(request, "inductions/signup_full.html", {"session": session})

    if request.method == "POST":
        form = SignupForm(request.POST, session=session)
        if form.is_valid():
            new_signup = InductionSignup.objects.create(
                session=session,
                name=form.get_name(),
                email=form.cleaned_data["email"],
                phone=form.cleaned_data.get("phone", ""),
                address=form.cleaned_data.get("address", ""),
                postcode=form.cleaned_data.get("postcode", ""),
                custom_responses=form.get_custom_responses(),
            )
            try:
                send_signup_confirmation(request, new_signup)
            except Exception:
                logger.exception("Failed to send signup confirmation email")
            try:
                send_new_signup_notification(session, new_signup)
            except Exception:
                logger.exception("Failed to send new-signup organiser notification")
            if session.is_full:
                try:
                    send_session_full_notification(session)
                except Exception:
                    logger.exception("Failed to send session-full organiser notification")
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
    cfg = get_inductions_settings()
    if not cfg.access_needs_enabled:
        raise Http404
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

    return render(request, "inductions/access_needs_signup.html", {
        "form": form,
        "intro_text": cfg.access_needs_intro_text,
    })


def access_needs_thanks(request):
    _check_enabled()
    cfg = get_inductions_settings()
    if not cfg.access_needs_enabled:
        raise Http404
    return render(request, "inductions/access_needs_thanks.html", {
        "organiser_email": cfg.organiser_notification_email,
    })


def session_list_public(request):
    """Public listing of all currently-open induction sessions."""
    _check_enabled()
    sessions = (
        InductionSession.objects
        .filter(status=InductionSession.STATUS_OPEN)
        .exclude(session_type=InductionSession.TYPE_ONE_TO_ONE)
        .order_by("date")
    )
    return render(request, "inductions/session_list_public.html", {
        "sessions": sessions,
        "cfg": get_inductions_settings(),
    })


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
    Before creating, checks for existing accounts with matching email or name and
    surfaces them as `duplicates` in the response for the inductor to resolve.
    Pass `force_signup_ids` (comma-separated) to bypass the duplicate check for
    specific signups.
    """
    session = get_object_or_404(InductionSession, slug=slug)
    pending_checkins = session.signups.filter(
        status=InductionSignup.STATUS_CHECKED_IN,
        volunteer__isnull=True,
    )
    forced_ids = set()
    for raw in request.POST.get("force_signup_ids", "").split(","):
        raw = raw.strip()
        if raw.isdigit():
            forced_ids.add(int(raw))

    created = []
    errors = []
    duplicates = []
    for signup in pending_checkins:
        if signup.pk not in forced_ids:
            existing = _find_existing_volunteer(signup)
            if existing:
                duplicates.append({
                    "signup_id": signup.pk,
                    "name": signup.name,
                    "match_type": "email" if (signup.email and existing.user.email.lower() == signup.email.lower()) else "name",
                    "existing_volunteer_id": existing.pk,
                    "existing_username": existing.user.username,
                    "existing_email": existing.user.email,
                })
                continue
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

    return JsonResponse({"ok": True, "created": created, "errors": errors, "duplicates": duplicates})


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


@require_POST
@panopticon_required
def manage_add_walkin(request, slug):
    """AJAX: register a walk-in attendee directly from the session manage page."""
    session = get_object_or_404(InductionSession, slug=slug)
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    postcode = request.POST.get("postcode", "").strip()

    if not first_name:
        return JsonResponse({"ok": False, "error": "First name is required."})
    if not email:
        return JsonResponse({"ok": False, "error": "Email address is required — it's needed to create a volunteer account."})

    name = f"{first_name} {last_name}".strip()
    signup = InductionSignup.objects.create(
        session=session,
        name=name,
        email=email,
        phone=phone,
        address=address,
        postcode=postcode,
        status=InductionSignup.STATUS_PENDING,
    )
    return JsonResponse({
        "ok": True,
        "signup_id": signup.pk,
        "name": signup.name,
        "email": signup.email,
        "preview_username": signup.preview_username,
        "signed_up_at": signup.signed_up_at.strftime("%-d %b %H:%M"),
    })


@require_POST
@panopticon_required
def manage_remove_signup(request, slug, signup_id):
    """AJAX: remove a pending signup (only; checked-in and no-show cannot be removed)."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    if signup.status != InductionSignup.STATUS_PENDING:
        return JsonResponse({"ok": False, "error": "Only pending sign-ups can be removed."})
    signup.delete()
    logger.info(f"{request.user} removed signup #{signup_id} ({signup.name}) from session '{session.title}'")
    return JsonResponse({"ok": True})


@require_POST
@panopticon_required
def manage_link_existing(request, slug, signup_id):
    """AJAX: link a signup to an existing volunteer account and send a login email."""
    session = get_object_or_404(InductionSession, slug=slug)
    signup = get_object_or_404(InductionSignup, pk=signup_id, session=session)
    existing_volunteer_id = request.POST.get("existing_volunteer_id")
    try:
        volunteer = Volunteer.objects.select_related("user").get(pk=existing_volunteer_id)
    except (Volunteer.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Volunteer not found."})

    signup.volunteer = volunteer
    signup.status = InductionSignup.STATUS_CHECKED_IN
    signup.save()

    if volunteer.user and volunteer.user.email:
        try:
            _send_password_reset_email(request, volunteer.user)
        except Exception:
            logger.exception(f"Password reset email failed for volunteer #{volunteer.pk}")
            return JsonResponse({"ok": True, "warning": "Linked, but the login email could not be sent."})

    logger.info(
        f"{request.user} linked signup #{signup.pk} ({signup.name}) to existing volunteer #{volunteer.pk}"
    )
    return JsonResponse({"ok": True})


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

    return render(request, "inductions/manage/settings.html", {
        "form": form,
        "sample_vars": _test_template_vars(request, cfg),
        "test_email_url": reverse("inductions:manage_send_test_email"),
        "user_email": request.user.email or "",
    })


@require_POST
@panopticon_required
def manage_send_test_email(request):
    template_type = request.POST.get("template_type", "notification")

    if template_type == "notification":
        cfg = InductionsSettings.load()
        recipient = cfg.organiser_notification_email
        if not recipient:
            return JsonResponse({"ok": False, "error": "No organiser notification email is configured."})
        try:
            send_test_notification_email(recipient)
        except Exception as exc:
            logger.exception("Failed to send test notification email")
            return JsonResponse({"ok": False, "error": str(exc)})
        return JsonResponse({"ok": True, "recipient": recipient})

    # Template preview: render the named template with sample data and send to
    # the requesting user's own email address so they can see what variables resolve to.
    recipient = request.user.email
    if not recipient:
        return JsonResponse({"ok": False, "error": "Your account has no email address set."})

    cfg = InductionsSettings.load()
    sample_vars = _test_template_vars(request, cfg)
    from_email = settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL

    template_map = {
        "confirmation": (cfg.get_confirmation_subject(), cfg.get_confirmation_body()),
        "reminder": (cfg.get_reminder_subject(), cfg.get_reminder_body()),
        "welcome": (cfg.get_welcome_subject(), cfg.get_welcome_body()),
        "access_needs_ack": (cfg.get_access_needs_ack_subject(), cfg.get_access_needs_ack_body()),
    }
    if template_type not in template_map:
        return JsonResponse({"ok": False, "error": f"Unknown template type: {template_type}"})

    raw_subject, raw_body = template_map[template_type]
    try:
        subject = raw_subject.format(**sample_vars)
    except KeyError:
        subject = raw_subject
    try:
        body = raw_body.format(**sample_vars)
    except KeyError:
        body = raw_body

    preview_note = (
        f"--- PREVIEW (sent to {recipient} with sample data) ---\n\n"
    )

    try:
        send_mail(
            subject=f"[Preview] {subject}",
            message=preview_note + body,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception("Failed to send template preview email")
        return JsonResponse({"ok": False, "error": str(exc)})

    return JsonResponse({"ok": True, "recipient": recipient})


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _create_volunteer_from_signup(signup: InductionSignup) -> Volunteer:
    """Create Member + User + Volunteer records from an InductionSignup."""
    name = signup.name or ""
    email = signup.email or ""

    member = Member(
        name=name,
        email=email,
        phone=signup.phone,
        address=signup.address,
        postcode=signup.postcode,
        gdpr_opt_in=timezone.now(),
    )
    member.save()

    if signup.desired_username:
        base = slugify(signup.desired_username)[:40] or "volunteer"
    else:
        parts = name.split()
        first = parts[0] if parts else "volunteer"
        last = parts[-1] if len(parts) > 1 else ""
        base = f"{first}{last}" or "volunteer"
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


def _find_existing_volunteer(signup: InductionSignup):
    """Return a matching Volunteer if one exists with the same email or name, else None."""
    if signup.email:
        user = User.objects.filter(email__iexact=signup.email).select_related("volunteer").first()
        if user and hasattr(user, "volunteer"):
            return user.volunteer
    if signup.name:
        member = Member.objects.filter(name__iexact=signup.name).select_related("volunteer").first()
        if member and hasattr(member, "volunteer"):
            return member.volunteer
    return None


def _send_password_reset_email(request, user):
    """Send a password-reset link to an existing volunteer account."""
    token = default_token_generator.make_token(user)
    uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = request.build_absolute_uri(
        reverse("password_reset_confirm", kwargs={"uidb64": uid_b64, "token": token})
    )
    timeout_days = max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)
    validity = f"{timeout_days} day" if timeout_days == 1 else f"{timeout_days} days"
    venue = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
    from_email = settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL
    name = user.first_name or user.username
    send_mail(
        subject=f"[{venue}] Log in to the toolkit",
        message=(
            f"Hi {name},\n\n"
            f"A volunteer inductor has confirmed your attendance at a recent induction.\n\n"
            f"Use the link below to log in to the {venue} volunteer toolkit (valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this email, please contact us."
        ),
        from_email=from_email,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _test_template_vars(request, cfg: InductionsSettings) -> dict:
    """Sample variable values used when sending template preview emails and rendering tooltips."""
    timeout_days = max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)
    validity = f"{timeout_days} day" if timeout_days == 1 else f"{timeout_days} days"
    sample_date = (timezone.now().replace(hour=18, minute=30, second=0, microsecond=0)
                   + timezone.timedelta(days=7))
    venue = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
    requester_name = request.user.get_full_name() or request.user.username
    return {
        "name": requester_name,
        "username": request.user.username,
        "venue": venue,
        "session_title": "Test Induction Session",
        "session_date": sample_date.strftime("%A %-d %B %Y at %H:%M"),
        "session_location": "Cinema",
        "calendar_url": request.build_absolute_uri("/inductions/test-session/calendar.ics"),
        "password_url": request.build_absolute_uri("/accounts/reset/Mg/abc-123-def456/"),
        "password_reset_url": request.build_absolute_uri(reverse("password_reset")),
        "validity": validity,
        "welcome_pack_url": cfg.welcome_pack_url or "(no welcome pack URL configured)",
    }


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
