# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import admin
from .models import Collective, DonationItem, Job


@admin.register(Collective)
class CollectiveAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "display_order", "contact")
    list_filter = ("active",)
    list_editable = ("active", "display_order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")
    fieldsets = (
        (None, {"fields": ("name", "slug", "colour", "display_order", "active")}),
        ("Content", {"fields": ("volunteer_count", "about", "roles", "organising", "proud_of", "get_involved", "contact")}),
    )


@admin.register(DonationItem)
class DonationItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "active", "display_order")
    list_filter = ("status", "category", "active")
    list_editable = ("status", "active", "display_order")
    ordering = ("category", "display_order", "name")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "area", "urgency", "safety_risk", "skill_needed", "resolved", "posted_by", "claimed_by", "posted_at")
    list_filter = ("urgency", "resolved", "safety_risk", "skill_needed", "keyholder_required", "location_type")
    ordering = ("resolved", "urgency", "-posted_at")
