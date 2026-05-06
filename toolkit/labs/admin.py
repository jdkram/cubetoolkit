# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import admin
from .models import DonationItem, Job


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
