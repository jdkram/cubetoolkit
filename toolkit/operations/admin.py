# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import admin

from .models import MaintenanceRecord, MaintenanceTask


class MaintenanceRecordInline(admin.TabularInline):
    model = MaintenanceRecord
    extra = 0
    fields = ("completed_date", "completed_by", "completed_by_name", "notes", "next_due_override")


@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "frequency", "next_due", "committed_to", "active")
    list_filter = ("category", "frequency", "active")
    search_fields = ("name", "notes")
    inlines = [MaintenanceRecordInline]


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("task", "completed_date", "completed_by", "completed_by_name")
    list_filter = ("task",)
