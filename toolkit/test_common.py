# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""
Shared helpers for test setUp across apps.

create_toolkit_test_users() collapses the copy-pasted setup that appeared
in three test-common files (diary/tests/common.py:ToolkitUsersFixture,
members/tests/common.py:_setup_test_users, labs/tests/common.py:
_setup_test_users) — each duplicated the dummy 'toolkit' ContentType +
write/read permissions + admin/read_only/no_perm user triple.

Returns a TestUsers namedtuple so callers can opt-in to a subset:

    users = create_toolkit_test_users()
    self.user_admin = users.admin
    self.user_ro = users.read_only
    self.user_none = users.no_perm

Or including the rota-only editor (used by diary):

    users = create_toolkit_test_users(include_rota_editor=True)

The inductions tests use a different shape (no toolkit.write/read perms
at all, superuser-only access) so they keep their own setUp and do not
call this. Labs layers its own Volunteer+Member fixture on top of these
users (see labs/tests/common.py:_setup_test_users).
"""
from collections import namedtuple

from django.contrib.auth import models as auth_models
from django.contrib.contenttypes import models as contenttypes


TestUsers = namedtuple("TestUsers", ["admin", "read_only", "no_perm", "rota_editor"])


def _create_toolkit_permissions():
    """Dummy ContentType + toolkit.write/read permissions. Idempotent.

    The 'toolkit' app has no real models, so we attach the permissions to a
    ContentType with model="" — Django tolerates this and the toolkit's
    feature_required / write_required decorators look up permissions by
    codename. This pattern is legacy but matches what the seeded prod
    permissions look like.
    """
    ct = contenttypes.ContentType.objects.get_or_create(
        model="", app_label="toolkit"
    )[0]
    write_perm = auth_models.Permission.objects.get_or_create(
        name="Write access to all toolkit content",
        content_type=ct,
        codename="write",
    )[0]
    read_perm = auth_models.Permission.objects.get_or_create(
        name="Read access to all toolkit content",
        content_type=ct,
        codename="read",
    )[0]
    return write_perm, read_perm


def create_toolkit_test_users(include_rota_editor=False, is_admin_superuser=True):
    """Create the standard admin / read_only / no_perm (+ optional rota_editor) users.

    Returns a TestUsers namedtuple. The admin user carries both toolkit.write
    and toolkit.read; read_only carries only toolkit.read; no_perm carries
    neither; rota_editor carries django.contrib.auth's change_rotaentry
    permission on the diary.RotaEntry content type.

    Email addresses, usernames and passwords are stable so tests can also
    log in by username (e.g. self.client.login(username='admin',
    password='T3stPassword!')) without holding references.
    """
    write_perm, read_perm = _create_toolkit_permissions()

    admin = auth_models.User.objects.create_user(
        "admin", "toolkit_admin@localhost", "T3stPassword!",
        is_superuser=is_admin_superuser,
    )
    admin.user_permissions.add(write_perm, read_perm)

    read_only = auth_models.User.objects.create_user(
        "read_only", "toolkit_admin@localhost", "T3stPassword!1"
    )
    read_only.user_permissions.add(read_perm)

    no_perm = auth_models.User.objects.create_user(
        "no_perm", "toolkit_admin@localhost", "T3stPassword!2"
    )

    rota_editor = None
    if include_rota_editor:
        rota_editor = auth_models.User.objects.create_user(
            "rota_editor", "toolkit_admin@localhost", "T3stPassword!3"
        )
        diary_ct = contenttypes.ContentType.objects.get(
            app_label="diary", model="rotaentry"
        )
        edit_rota = auth_models.Permission.objects.get(
            codename="change_rotaentry", content_type=diary_ct
        )
        rota_editor.user_permissions.add(edit_rota)

    return TestUsers(
        admin=admin,
        read_only=read_only,
        no_perm=no_perm,
        rota_editor=rota_editor,
    )