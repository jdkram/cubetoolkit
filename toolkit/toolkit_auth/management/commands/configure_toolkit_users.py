import getpass
import django.contrib.auth.models as auth_models
import django.contrib.contenttypes as contenttypes

from django.core.management.base import BaseCommand, CommandError
from toolkit.members.models import Member, Volunteer


def _get_password(use):
    print("*" * 80)
    password = ""
    check_password = None

    while check_password != password:
        password = getpass.getpass(f"Please enter password for {use}: ")
        check_password = getpass.getpass("Please re-enter for confirmation: ")
        if check_password != password:
            print("Passwords don't match; please try again...")

    return password


def _create_or_update_user(
    name, email, permissions, is_superuser=False, is_staff=False, password=None,
    force_password=False,
):
    if not auth_models.User.objects.filter(username=name).exists():
        if password is None:
            password = _get_password(name)
        user = auth_models.User.objects.create_user(name, email, password)
        print(f"Created user '{name}'")
    else:
        user = auth_models.User.objects.get(username=name)
        if force_password and password is not None:
            user.set_password(password)
            print(f"User '{name}' exists: password updated")
        else:
            print(f"User '{name}' exists: not changing password")

    # Remove all permissions:
    user.user_permissions.clear()

    # Set to requested:
    for permission in permissions:
        user.user_permissions.add(permission)

    user.is_superuser = is_superuser
    user.is_staff = is_staff
    user.save()

    return user


def _configure_users(password=None, force_password=False):
    # Create dummy ContentType:
    ct = contenttypes.models.ContentType.objects.get_or_create(
        model="", app_label="toolkit"
    )[0]

    # Create 'write' permission:
    write_permission = auth_models.Permission.objects.get_or_create(
        name="Write access to all toolkit content",
        content_type=ct,
        codename="write",
    )[0]

    # Create 'read' permission:
    read_permission = auth_models.Permission.objects.get_or_create(
        name="Read access to all toolkit content",
        content_type=ct,
        codename="read",
    )[0]

    # retrieve permission for editing diary.models.RotaEntry rows:
    diary_content_type = contenttypes.models.ContentType.objects.get(
        app_label="diary",
        model="rotaentry",
    )

    edit_rota_permission = auth_models.Permission.objects.get(
        codename="change_rotaentry", content_type=diary_content_type
    )

    # Create the "Programmers" group (toolkit.write + toolkit.read + rota edit).
    # Programmers can create/edit events, manage templates and tags, but cannot
    # delete roles or access volunteer/member/CMS admin sections.
    programmers_group, _ = auth_models.Group.objects.get_or_create(name="Programmers")
    programmers_group.permissions.set(
        [write_permission, read_permission, edit_rota_permission]
    )

    # --- Panopticon (superuser) ---
    # The admin account also gets a Member + Volunteer record so that the
    # volunteer-specific dashboard cards (star/shadow marks, "my shifts") are
    # visible when logged in as admin, not just as a seeded volunteer account.
    admin_user = _create_or_update_user(
        "admin",
        "admin@localhost",
        [write_permission, read_permission, edit_rota_permission],
        is_superuser=True,
        is_staff=True,
        password=password,
        force_password=force_password,
    )
    admin_member, _ = Member.objects.get_or_create(
        email="admin@localhost",
        defaults={"name": "Demo Admin"},
    )
    Volunteer.objects.get_or_create(user=admin_user, defaults={"member": admin_member})

    # --- Programmer tier ---
    # Programmer accounts also get a Member + Volunteer record so the
    # volunteer-specific dashboard cards (star/shadow marks, "my shifts") work
    # when logged in as a programmer.
    programmer_users = []
    for i, (username, email) in enumerate(
        [
            ("programmer", "programmer@localhost"),
            ("programmer2", "programmer2@localhost"),
        ],
        start=1,
    ):
        user = _create_or_update_user(
            username,
            email,
            [write_permission, read_permission, edit_rota_permission],
            password=password,
            force_password=force_password,
        )
        member, _ = Member.objects.get_or_create(
            email=email,
            defaults={"name": f"Demo Programmer {i}"},
        )
        Volunteer.objects.get_or_create(user=user, defaults={"member": member})
        programmer_users.append(user)

    # Add programmer accounts to the Programmers group:
    for user in programmer_users:
        user.groups.set([programmers_group])

    # --- Volunteer tier (rota editing only) ---
    # Each volunteer account gets a Member + Volunteer record so the
    # volunteer-specific features (star/shadow marks, "my shifts", digest
    # email) work when logged in as one of these accounts.
    for i, (username, email) in enumerate(
        [
            ("volunteer", "volunteer@localhost"),
            ("volunteer2", "volunteer2@localhost"),
            ("volunteer3", "volunteer3@localhost"),
            ("volunteer4", "volunteer4@localhost"),
            ("volunteer5", "volunteer5@localhost"),
        ],
        start=1,
    ):
        user = _create_or_update_user(
            username,
            email,
            [edit_rota_permission],
            password=password,
            force_password=force_password,
        )
        member, _ = Member.objects.get_or_create(
            email=email,
            defaults={"name": f"Demo Volunteer {i}"},
        )
        Volunteer.objects.get_or_create(user=user, defaults={"member": member})


class Command(BaseCommand):
    help = (
        "Create/update the standard dev and demo user accounts at each permission tier. "
        "Use --password for non-interactive use (Docker, CI). "
        "Without --password, prompts for each new account's password interactively."
    )

    can_import_settings = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help=(
                "Password to use for all newly-created accounts (dev/Docker mode). "
                "If omitted, prompts interactively for each new account."
            ),
        )
        parser.add_argument(
            "--force-password",
            action="store_true",
            default=False,
            help=(
                "Also update the password on existing accounts. "
                "Requires --password. Do not use in production."
            ),
        )

    def handle(self, *args, **options):
        password = options.get("password")
        force_password = options.get("force_password", False)
        if password:
            self.stdout.write(
                self.style.WARNING(
                    "Using --password: all new accounts will share the same password. "
                    "Do not use this flag in production."
                )
            )
        if force_password and not password:
            raise CommandError("--force-password requires --password.")
        _configure_users(password=password, force_password=force_password)
        self.stdout.write(self.style.SUCCESS("Users configured successfully."))
