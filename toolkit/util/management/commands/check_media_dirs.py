# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Management command: check_media_dirs

Scans every installed app model for ImageField and FileField with a static
upload_to path, then verifies that each target directory exists and is
writable under MEDIA_ROOT.

Run automatically by tk_run.sh at container startup (gunicorn and runserver
modes). Exits with a non-zero code on failure so the container doesn't start
with a broken media layout.

WHY THIS EXISTS
---------------
The production Docker image pre-creates upload subdirectories at build time
(see Dockerfile). If a new ImageField is added with a new upload_to path and
the Dockerfile is not updated, the directory won't exist, and the first upload
attempt will raise PermissionError.

This check catches that mismatch at startup rather than at first use.

HOW TO FIX A FAILURE
---------------------
1. Add the missing path to the Dockerfile:
       install -D --owner=toolkit --group=toolkit --directory /site/media/<path>
2. Rebuild the image: docker compose up --build -d
3. For a running container without a rebuild:
       docker compose exec --user root toolkit mkdir -p /site/media/<path>
       docker compose exec --user root toolkit chown toolkit:toolkit /site/media/<path>
"""
import os
import stat

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import FileField


class Command(BaseCommand):
    help = "Verify that all ImageField/FileField upload_to directories exist and are writable."

    def handle(self, *args, **options):
        media_root = settings.MEDIA_ROOT
        verbosity = options.get("verbosity", 1)

        if verbosity >= 2:
            self.stdout.write(f"MEDIA_ROOT: {media_root}")

        upload_paths = self._collect_upload_paths(verbosity)

        if not upload_paths:
            if verbosity >= 1:
                self.stdout.write("No static upload_to paths found.")
            return

        failures = []
        for path, source in sorted(upload_paths.items()):
            full_path = os.path.join(media_root, path)
            ok, reason = self._check_dir(full_path)
            if ok:
                if verbosity >= 2:
                    self.stdout.write(self.style.SUCCESS(f"  OK  {path}  ({source})"))
            else:
                failures.append((path, source, reason))
                self.stderr.write(self.style.ERROR(f"  FAIL  {path}  ({source}): {reason}"))

        if failures:
            self.stderr.write(
                self.style.ERROR(
                    f"\n{len(failures)} media director{'y' if len(failures) == 1 else 'ies'} "
                    f"missing or not writable under {media_root}.\n"
                    "Add them to the Dockerfile and rebuild, or create them manually.\n"
                    "See the docstring in check_media_dirs.py for instructions."
                )
            )
            raise SystemExit(1)

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"All {len(upload_paths)} media director"
                    f"{'y' if len(upload_paths) == 1 else 'ies'} OK."
                )
            )

    def _collect_upload_paths(self, verbosity):
        """Return a dict mapping upload subpath → 'AppLabel.ModelName.field_name'."""
        paths = {}
        for model in apps.get_models():
            for field in model._meta.get_fields():
                if not isinstance(field, FileField):
                    continue
                upload_to = field.upload_to
                if callable(upload_to):
                    # Dynamic paths can't be checked without an instance — skip.
                    if verbosity >= 2:
                        label = f"{model._meta.app_label}.{model.__name__}.{field.name}"
                        self.stdout.write(
                            f"  SKIP  {label}: upload_to is callable, cannot check statically"
                        )
                    continue
                if not upload_to:
                    continue
                # Normalise: strip leading slash, ensure trailing slash.
                upload_to = upload_to.strip("/") + "/"
                label = f"{model._meta.app_label}.{model.__name__}.{field.name}"
                # Keep first label seen for any given path (multiple fields can share a dir).
                paths.setdefault(upload_to, label)
        return paths

    def _check_dir(self, full_path):
        """Return (ok: bool, reason: str)."""
        if not os.path.exists(full_path):
            return False, "directory does not exist"
        try:
            mode = os.stat(full_path).st_mode
        except OSError as exc:
            return False, f"stat failed: {exc}"
        if not stat.S_ISDIR(mode):
            return False, "path exists but is not a directory"
        if not os.access(full_path, os.W_OK):
            return False, "directory is not writable by the current user"
        return True, ""
