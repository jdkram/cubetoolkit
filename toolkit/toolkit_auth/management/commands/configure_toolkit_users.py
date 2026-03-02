import getpass
import django.contrib.auth.models as auth_models
import django.contrib.contenttypes as contenttypes

from django.core.management.base import BaseCommand, CommandError


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
    name, email, permissions, is_superuser=False, is_staff=False, password=None
):
    if not auth_models.User.objects.filter(username=name).exists():
        if password is None:
            password = _get_password(name)
        user = auth_models.User.objects.create_user(name, email, password)
        print(f"Created user '{name}'")
    else:
        print(f"User '{name}' exists: not changing password")
        user = auth_models.User.objects.get(username=name)

    # Remove all permissions:
    user.user_permissions.clear()

    # Set to requested:
    for permission in permissions:
        user.user_permissions.add(permission)

    user.is_superuser = is_superuser
    user.is_staff = is_staff
    user.save()

    return user


def _configure_users(password=None):
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
    _create_or_update_user(
        "admin",
        "admin@localhost",
        [write_permission, read_permission, edit_rota_permission],
        is_superuser=True,
        is_staff=True,
        password=password,
    )

    # --- Programmer tier ---
    programmer_users = []
    for username, email in [
        ("programmer", "programmer@localhost"),
        ("programmer2", "programmer2@localhost"),
    ]:
        user = _create_or_update_user(
            username,
            email,
            [write_permission, read_permission, edit_rota_permission],
            password=password,
        )
        programmer_users.append(user)

    # Add programmer accounts to the Programmers group:
    for user in programmer_users:
        user.groups.set([programmers_group])

    # --- Volunteer tier (rota editing only) ---
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
        _create_or_update_user(
            username,
            email,
            [edit_rota_permission],
            password=password,
        )


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

    def handle(self, *args, **options):
        password = options.get("password")
        if password:
            self.stdout.write(
                self.style.WARNING(
                    "Using --password: all new accounts will share the same password. "
                    "Do not use this flag in production."
                )
            )
        _configure_users(password=password)
        self.stdout.write(self.style.SUCCESS("Users configured successfully."))
