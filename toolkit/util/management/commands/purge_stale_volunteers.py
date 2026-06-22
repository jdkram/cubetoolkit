# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
"""Anonymise volunteers whose records are past the retention window (GDPR).

Deliberately hard to fire by accident:
  - Reports only by default. Nothing changes unless you pass --apply.
  - --apply also requires --confirm "<phrase>", where the phrase must exactly
    match "anonymise N volunteers" (N = the candidate count). This makes the
    operator acknowledge how many records they are about to erase.

Anonymisation (not deletion) is reused from Volunteer.anonymise, so rota history
and the audit log survive while personal data is cleared. This command is never
scheduled — it is a conscious, manual action.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.members.models import Volunteer


class Command(BaseCommand):
    help = (
        "Anonymise dormant/retired volunteers whose last activity is older than "
        "volunteer_purge_days (Site settings). Reports only unless --apply is given; "
        "--apply requires --confirm with a phrase matching the candidate count. "
        "Irreversible. Never run automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually anonymise the candidates. Without this, only reports (dry run).",
        )
        parser.add_argument(
            "--confirm",
            default="",
            help='Required with --apply. Must equal "anonymise N volunteers" (N = candidate count).',
        )
        parser.add_argument(
            "--include-members",
            action="store_true",
            help="Include candidates with an active membership. By default these are skipped with a warning.",
        )

    def handle(self, *args, **options):
        config = get_site_config()
        purge_days = config.volunteer_purge_days

        if not purge_days:
            self.stdout.write(
                "Purge candidate flagging is disabled (volunteer_purge_days = 0). "
                "Nothing to do."
            )
            return

        include_members = options["include_members"]
        today = timezone.now().date()

        all_candidates = list(
            Volunteer.objects.purge_candidates(purge_days).select_related(
                "member", "user"
            )
        )

        # Separate out those with active memberships unless --include-members is set.
        active_member_skipped = []
        candidates = []
        for vol in all_candidates:
            m = vol.member
            is_active_member = (
                m.membership_expires is not None and m.membership_expires >= today
            )
            if is_active_member and not include_members:
                active_member_skipped.append(vol)
            else:
                candidates.append(vol)

        if active_member_skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"\nSkipping {len(active_member_skipped)} candidate(s) with an active membership "
                    f"(re-run with --include-members to include them):"
                )
            )
            for vol in active_member_skipped:
                self.stdout.write(
                    f"  pk={vol.pk} {vol.member.name} "
                    f"(expires: {vol.member.membership_expires})"
                )

        count = len(candidates)

        self.stdout.write(
            f"\n{count} volunteer(s) past the {purge_days}-day retention window:"
        )
        for vol in candidates:
            last_login = vol.user.last_login
            self.stdout.write(
                f"  pk={vol.pk} {vol.member.name} "
                f"(status: {vol.status}, last login: "
                f"{last_login.date() if last_login else 'never'})"
            )

        if not count:
            return

        apply = options["apply"]
        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run — no changes made. To anonymise these records, re-run with:\n"
                    f'  --apply --confirm "anonymise {count} volunteers"'
                )
            )
            return

        expected_phrase = f"anonymise {count} volunteers"
        if options["confirm"].strip() != expected_phrase:
            raise CommandError(
                f'--apply requires --confirm "{expected_phrase}". '
                "No changes were made."
            )

        anonymised = 0
        for vol in candidates:
            name = vol.member.name
            rota_cleared = vol.anonymise(performed_by=None)
            anonymised += 1
            self.stdout.write(
                f"  Anonymised pk={vol.pk} ({name}); {rota_cleared} rota entry/entries cleared."
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nAnonymised {anonymised} volunteer(s).")
        )
