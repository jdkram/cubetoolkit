# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from toolkit.toolkit_auth.decorators import write_required_strict

from .. import forms as operations_forms
from ..models import MaintenanceTask


def _user_volunteer(user):
    """Return user.volunteer if the user has an associated Volunteer row, else None."""
    return user.volunteer if hasattr(user, "volunteer") else None


@login_required
def schedule(request):
    tasks = (
        MaintenanceTask.objects.filter(active=True)
        .select_related("committed_to__member")
        .prefetch_related("records")
        .order_by("name")
    )
    tasks = sorted(tasks, key=lambda t: (t.next_due is None, t.next_due))
    return render(
        request,
        "operations/schedule.html",
        {
            "tasks": tasks,
            "STATUS_OVERDUE": MaintenanceTask.STATUS_OVERDUE,
            "STATUS_DUE_SOON": MaintenanceTask.STATUS_DUE_SOON,
        },
    )


@login_required
@write_required_strict
def task_add(request):
    if request.method == "POST":
        form = operations_forms.MaintenanceTaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, f"Maintenance task '{task.name}' added.")
            return redirect("operations-schedule")
    else:
        form = operations_forms.MaintenanceTaskForm()
    return render(request, "operations/maintenance_task_form.html", {"form": form, "action": "Add"})


@login_required
@write_required_strict
def task_edit(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    if request.method == "POST":
        form = operations_forms.MaintenanceTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f"Maintenance task '{task.name}' updated.")
            return redirect("operations-schedule")
    else:
        form = operations_forms.MaintenanceTaskForm(instance=task)
    return render(request, "operations/maintenance_task_form.html", {"form": form, "task": task, "action": "Edit"})


@login_required
@write_required_strict
def task_mark_done(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    if request.method == "POST":
        form = operations_forms.MaintenanceRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.task = task
            record.completed_by = _user_volunteer(request.user)
            record.save()
            # Completing the task closes out any outstanding commitment.
            if task.committed_to is not None:
                task.committed_to = None
                task.committed_on = None
                task.save(update_fields=["committed_to", "committed_on"])
            messages.success(request, f"'{task.name}' marked as done.")
            return redirect("operations-schedule")
    else:
        form = operations_forms.MaintenanceRecordForm()
    return render(request, "operations/mark_done_form.html", {"form": form, "task": task})


@login_required
@require_POST
def task_commit(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    volunteer = _user_volunteer(request.user)
    if volunteer is not None and task.committed_to is None:
        task.committed_to = volunteer
        task.committed_on = datetime.date.today()
        task.save(update_fields=["committed_to", "committed_on"])
        messages.success(request, f"You've committed to '{task.name}'.")
    return redirect("operations-schedule")


@login_required
@require_POST
def task_uncommit(request, task_id):
    task = get_object_or_404(MaintenanceTask, pk=task_id)
    volunteer = _user_volunteer(request.user)
    if task.committed_to == volunteer or request.user.has_perm("toolkit.write"):
        task.committed_to = None
        task.committed_on = None
        task.save(update_fields=["committed_to", "committed_on"])
        messages.success(request, f"Commitment to '{task.name}' cleared.")
    return redirect("operations-schedule")
