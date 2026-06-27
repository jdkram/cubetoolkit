# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"
from django.contrib import admin

from .models import (
    InductionRequest,
    InductionSession,
    InductionSignup,
    InductionsSettings,
)


@admin.register(InductionSession)
class InductionSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "session_type", "status", "created_by")
    list_filter = ("session_type", "status")
    search_fields = ("title", "location", "slug")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("created_by",)
    date_hierarchy = "date"
    ordering = ("-date",)


@admin.register(InductionSignup)
class InductionSignupAdmin(admin.ModelAdmin):
    list_display = ("name", "session", "status", "volunteer", "signed_up_at")
    list_filter = ("status",)
    search_fields = ("name", "email", "phone", "desired_username")
    raw_id_fields = ("session", "volunteer", "checked_in_by")
    date_hierarchy = "signed_up_at"
    ordering = ("signed_up_at",)


@admin.register(InductionRequest)
class InductionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "submitted_at",
        "linked_session",
        "volunteer",
    )
    list_filter = ("status",)
    search_fields = ("name", "email", "access_needs", "notes")
    raw_id_fields = ("linked_session", "volunteer")
    date_hierarchy = "submitted_at"
    ordering = ("-submitted_at",)


@admin.register(InductionsSettings)
class InductionsSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__",)

    # Singleton-ish: only one row is ever expected, so hide the list-add link to
    # discourage duplicate settings rows via the admin.
    def has_add_permission(self, request):
        return not InductionsSettings.objects.exists()
