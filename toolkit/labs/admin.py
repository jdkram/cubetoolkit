# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import admin
from .models import Bulletin, Collective, ConsumableItem, DonationItem, Job, NeedFlag, SupplierRecord


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


@admin.register(Bulletin)
class BulletinAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "pinned", "created_at", "expires_at")
    list_filter = ("pinned",)
    search_fields = ("title", "body")
    ordering = ("-pinned", "-created_at")


class SupplierRecordInline(admin.TabularInline):
    model = SupplierRecord
    extra = 1
    fields = ("supplier_name", "product_code", "unit_desc", "approx_price", "product_url", "ordering_notes", "account_holder", "account_notes")


@admin.register(ConsumableItem)
class ConsumableItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "active")
    list_filter = ("category", "active")
    list_editable = ("active",)
    ordering = ("category", "name")
    inlines = [SupplierRecordInline]


@admin.register(NeedFlag)
class NeedFlagAdmin(admin.ModelAdmin):
    list_display = ("item", "flagged_by", "flagged_at", "is_resolved", "resolved_by", "resolved_at")
    list_filter = ("item",)
    readonly_fields = ("flagged_at",)
    ordering = ("-flagged_at",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "area", "urgency", "safety_risk", "skill_needed", "resolved", "posted_by", "claimed_by", "posted_at")
    list_filter = ("urgency", "resolved", "safety_risk", "skill_needed", "keyholder_required", "location_type")
    ordering = ("resolved", "urgency", "-posted_at")
