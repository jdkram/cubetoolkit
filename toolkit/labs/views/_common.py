"""Labs views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; the only genuinely cross-module helper
(``_user_volunteer``) lives here. The package re-exports every public name
so ``urls.py`` (which does ``from . import views``) and the one external
importer (``toolkit/index/views.py`` pulls ``_unread_bulletins_for``) keep
working unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"

import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from toolkit.toolkit_auth.decorators import (
    feature_required,
    write_required,
    write_required_strict,
)
from django.db import models
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Exists, OuterRef

from ..models import (
    AreaPhoto,
    Bulletin,
    BulletinRead,
    Collective,
    ConsumableItem,
    ExchangeItem,
    FoundItem,
    NeedFlag,
    ProcurementPledge,
    Supplier,
    SupplierRecord,
    RoomNote,
    DonationItem,
    Job,
    LoftItem,
    LoftItemPhoto,
)
from toolkit.diary.models import SiteConfiguration, get_site_config
from .. import forms as lab_forms


def _user_volunteer(user):
    """Return user.volunteer if the user has an associated Volunteer row, else None.

    Uses hasattr (the canonical Django pattern) rather than try/except, which
    would silently swallow real errors — e.g. a corrupt Volunteer row raising
    a database error would read as "no volunteer" and hide the bug.
    Replaces 11 bare `except Exception:` blocks across collectives + shopping
    views that had drifted to swallow all errors.
    """
    return user.volunteer if hasattr(user, "volunteer") else None
