import logging
from functools import wraps

from django.contrib.auth.decorators import permission_required, user_passes_test
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.signals import user_logged_out
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


_LEVEL_LABELS = {
    "volunteer": "All volunteers",
    "programmer": "Programmer+",
    "panopticon": "Panopticon only",
}


def write_required(func):
    """Restrict a view to programmer+ (toolkit.write). Sets view_access_level for the footer badge."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login
        if not request.user.is_authenticated or not request.user.has_perm("toolkit.write"):
            return redirect_to_login(request.get_full_path())
        request.view_access_level = "Programmer+"
        return func(request, *args, **kwargs)
    return wrapper


def read_required(func):
    """Restrict a view to volunteer+ (toolkit.read). Sets view_access_level for the footer badge."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login
        if not request.user.is_authenticated or not request.user.has_perm("toolkit.read"):
            return redirect_to_login(request.get_full_path())
        request.view_access_level = "All volunteers"
        return func(request, *args, **kwargs)
    return wrapper


def write_required_strict(func):
    """Like write_required but raises 403 (instead of redirecting) for authenticated users without toolkit.write."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.has_perm("toolkit.write"):
            raise PermissionDenied
        request.view_access_level = "Programmer+"
        return func(request, *args, **kwargs)
    return wrapper


def panopticon_required(func):
    """Restrict a view to superusers (Panopticon tier) only."""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            raise PermissionDenied
        request.view_access_level = "Panopticon only"
        return func(request, *args, **kwargs)
    return wrapper


def feature_required(feature_name):
    """Restrict a view based on the runtime-configurable permission level for a named feature.

    The level is read from SiteConfiguration.perm_<feature_name> on each request,
    so Panopticons can change access without a code deploy. Sets
    request.view_access_level for the access-level footer badge.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            from toolkit.diary.models import SiteConfiguration, get_site_config
            cfg = get_site_config()
            level = getattr(cfg, f"perm_{feature_name}", SiteConfiguration.PERM_PROGRAMMER)
            if not SiteConfiguration._passes_level(request.user, level):
                raise PermissionDenied
            request.view_access_level = _LEVEL_LABELS.get(level, level)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class ip_or_permission_required:
    """
    Decorator that requires a request to either originate from one of a fixed
    set of IP addresses, or for the request to originate from a logged in user
    with the supplied permissions.
    """

    def __init__(self, ip_addresses, permission):
        self.ip_addresses = ip_addresses
        self.permission = permission

    def __call__(self, function):
        permission_req_wrapper = permission_required(self.permission)(function)

        def wrapper(request, *args, **kwargs):
            if request.META["REMOTE_ADDR"] in self.ip_addresses:
                return function(request, *args, **kwargs)
            else:
                return permission_req_wrapper(request, *args, **kwargs)

        return wrapper


# http://stackoverflow.com/questions/37618473/how-can-i-log-both-successful-and-failed-login-and-logout-attempts-in-django
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):

    # to cover more complex cases:
    # http://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    ip = request.META.get("REMOTE_ADDR")
    logger.info(f"{user} logged in from {ip}")


@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):

    ip = request.META.get("REMOTE_ADDR")

    logger.info(f"{user} logged out from {ip}")


@receiver(user_login_failed)
def user_login_failed_callback(sender, request, credentials, **kwargs):

    ip = request.META.get("REMOTE_ADDR")

    logger.warning(f"login failed for: {credentials} from {ip}")
