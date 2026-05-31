# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""
Management command: backfill_qualifications_from_training

One-off migration aid. For every ROLE_TRAINING record where the role
has a required_qualification, awards that qualification to the volunteer
if they don't already hold it.

The earliest training date per (volunteer, qualification) pair is used
as the granted_on date — honouring the original training event.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from toolkit.members.models import (
    TrainingRecord,
    VolunteerQualification,
)


class Command(BaseCommand):
    help = (
        "Award qualifications to volunteers based on their existing role training records. "
        "Safe to run repeatedly — skips awards that already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be done without writing anything.",
        )
        parser.add_argument(
            "--granted-by",
            default="backfill_qualifications_from_training",
            help=(
                "Value to record in the granted_by field on new VolunteerQualification rows "
                "(default: 'backfill_qualifications_from_training')."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        granted_by = options["granted_by"]

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN — no changes will be written --\n"))

        # Pull all role-training records where the role actually has a qualification gate.
        # Use select_related to avoid N+1 across role → qualification.
        records = (
            TrainingRecord.objects.filter(
                training_type=TrainingRecord.ROLE_TRAINING,
                role__required_qualification__isnull=False,
            )
            .select_related("volunteer", "role__required_qualification")
            .order_by("training_date")  # earliest first for granted_on deduplication
        )

        if not records.exists():
            self.stdout.write("No role training records with a qualification gate found. Nothing to do.")
            return

        # Build a map of (volunteer_id, qualification_id) → earliest training_date.
        # This covers the case where a volunteer has multiple training records for
        # roles that share the same qualification.
        earliest: dict[tuple[int, int], tuple] = {}
        for record in records:
            qual = record.role.required_qualification
            key = (record.volunteer_id, qual.pk)
            if key not in earliest:
                earliest[key] = (record.volunteer, qual, record.training_date)

        # Filter out pairs that already have a VolunteerQualification row.
        existing = set(
            VolunteerQualification.objects.filter(
                volunteer_id__in={k[0] for k in earliest},
                qualification_id__in={k[1] for k in earliest},
            ).values_list("volunteer_id", "qualification_id")
        )

        to_create = {k: v for k, v in earliest.items() if k not in existing}

        self.stdout.write(
            f"Training records examined: {records.count()}\n"
            f"Unique (volunteer, qualification) pairs: {len(earliest)}\n"
            f"Already have qualification:              {len(existing & set(earliest))}\n"
            f"To award:                                {len(to_create)}\n"
        )

        if not to_create:
            self.stdout.write(self.style.SUCCESS("All relevant qualifications are already awarded. Nothing to do."))
            return

        # Preview
        for (vol_id, qual_id), (volunteer, qual, date) in sorted(
            to_create.items(), key=lambda x: (x[1][0].name, x[1][1].name)
        ):
            self.stdout.write(
                f"  {'[DRY RUN] ' if dry_run else ''}Award '{qual.name}' "
                f"to {volunteer.name} (pk={vol_id}, granted_on={date})"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run complete — no rows written."))
            return

        with transaction.atomic():
            created = VolunteerQualification.objects.bulk_create([
                VolunteerQualification(
                    volunteer=volunteer,
                    qualification=qual,
                    granted_on=date,
                    granted_by=granted_by,
                    notes="Backdated from training records.",
                )
                for (vol_id, qual_id), (volunteer, qual, date) in to_create.items()
            ])

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {len(created)} qualification(s) awarded.")
        )
