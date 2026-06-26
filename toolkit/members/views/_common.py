# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""
Shared imports and helpers for the volunteer views subpackage.

volunteer_views.py was split per-feature in commit <this> — see
MAINTAINABILITY_PASS.md chunk 5. Each submodule does
`from ._common import *` to pull in imports + logger + the two cross-feature
helpers (_render_admin_email, _notify_vols_admin_status_change). Underscored
helpers are exported via __all__.
"""
import csv
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.signing import BadSignature, Signer
from django.db import transaction
from django.db.models import (
    Count,
    Exists,
    F,
    Max,
    OuterRef,
    Prefetch,
    Value,
)
from django.db.models.functions import Coalesce, NullIf
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_safe

from toolkit.diary.models import Role, RotaEntry, get_site_config
from toolkit.members.forms import (
    UserForm,
    VolunteerForm,
    MemberFormWithoutNotes,
    TrainingRecordForm,
    GroupTrainingForm,
)
from toolkit.members.models import (
    Member,
    Volunteer,
    TrainingRecord,
    ExportAuditLog,
    LastGaspEmailLog,
)
from toolkit.toolkit_auth import password_emails
from toolkit.toolkit_auth.decorators import panopticon_required

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _render_admin_email(template, name, venue):
    """Substitute {name} and {venue} placeholders in an admin-configured email template.

    Used for last-gasp and suspension emails whose subject/body are editable
    in Site settings. Plain .replace (not str.format) so stray { } chars in
    admin text don't crash rendering.
    """
    return template.replace("{name}", name).replace("{venue}", venue)


def _notify_vols_admin_status_change(request, vol, now_active):
    # Volunteer status (active / dormant / retired) is edited on the volunteer's
    # own profile page. When that change moves a volunteer on or off the active
    # roster, email the volunteers admin so the mailing list can be kept in step.
    # No-op when no vols_admin_address is configured.
    vols_admin = settings.VENUE.get("vols_admin_address") or []
    if not vols_admin:
        return

    status_label = vol.get_status_display()
    if now_active:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please add them back to the volunteers mailing list "
            f"at your earliest convenience."
        )
    else:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please remove them from the volunteers mailing list "
            f"at your earliest convenience."
        )
    admin_body = (
        f"{request.user.last_name} has updated the status of volunteer\n\n"
        f"{vol.member.name} <{vol.member.email}>\n\n"
        f"{action_line}"
    )
    send_mail(
        f"[{settings.VENUE['longname']}] Change in volunteer status {vol.member.name}",
        admin_body,
        settings.VENUE["mailout_from_address"],
        vols_admin,
        fail_silently=False,
    )


__all__ = [
    # stdlib
    "csv",
    "logging",
    "datetime",
    "timedelta",
    # django
    "settings",
    "messages",
    "login_required",
    "permission_required",
    "SetPasswordForm",
    "User",
    "PermissionDenied",
    "send_mail",
    "BadSignature",
    "Signer",
    "transaction",
    "Count",
    "Exists",
    "F",
    "Max",
    "OuterRef",
    "Prefetch",
    "Value",
    "Coalesce",
    "NullIf",
    "HttpResponse",
    "HttpResponseRedirect",
    "JsonResponse",
    "get_object_or_404",
    "render",
    "reverse",
    "timezone",
    "slugify",
    "require_POST",
    "require_safe",
    # toolkit
    "Role",
    "RotaEntry",
    "get_site_config",
    "UserForm",
    "VolunteerForm",
    "MemberFormWithoutNotes",
    "TrainingRecordForm",
    "GroupTrainingForm",
    "Member",
    "Volunteer",
    "TrainingRecord",
    "ExportAuditLog",
    "LastGaspEmailLog",
    "password_emails",
    "panopticon_required",
    # module state
    "logger",
    # cross-feature helpers
    "_render_admin_email",
    "_notify_vols_admin_status_change",
]