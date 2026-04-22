from django.contrib import admin

from toolkit.diary.models import (
    Event,
    EventLink,
    EventTermsRevision,
    MediaItem,
    Showing,
    Room,
    Role,
    EventTag,
    SiteConfiguration,
)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "colour", "is_primary")
    list_editable = ("is_primary",)
    search_fields = ("name",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "standard", "read_only")
    list_filter = ("standard", "read_only")
    search_fields = ("name",)


@admin.register(EventTag)
class EventTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("pk", "media_file", "credit", "alt_text_short")
    search_fields = ("credit", "alt_text", "caption")
    readonly_fields = ("mimetype",)
    fields = ("media_file", "credit", "alt_text", "mimetype")

    @admin.display(description="Alt text")
    def alt_text_short(self, obj):
        return obj.alt_text[:60] + "…" if len(obj.alt_text) > 60 else obj.alt_text or "—"


class ShowingInline(admin.TabularInline):
    model = Showing
    extra = 0
    fields = ("start", "booked_by", "confirmed", "cancelled", "hide_in_programme")
    readonly_fields = ("start",)


class EventLinkInline(admin.TabularInline):
    model = EventLink
    extra = 1
    max_num = 3
    fields = ("label", "url", "order")


class EventTermsRevisionInline(admin.TabularInline):
    model = EventTermsRevision
    extra = 0
    readonly_fields = ("saved_at", "saved_by", "terms_text", "outside_hire", "private")
    can_delete = False
    ordering = ("-saved_at",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "private")
    list_filter = ("private", "tags")
    search_fields = ("name", "copy", "booked_by")
    readonly_fields = ("created_at", "updated_at", "legacy_id")
    inlines = (ShowingInline, EventLinkInline, EventTermsRevisionInline)


@admin.register(Showing)
class ShowingAdmin(admin.ModelAdmin):
    list_display = ("event", "start", "booked_by", "confirmed", "cancelled")
    list_filter = ("confirmed", "cancelled", "hide_in_programme", "discounted")
    search_fields = ("event__name", "booked_by", "rota_notes")
    date_hierarchy = "start"
    readonly_fields = ("created_at", "updated_at")


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    # The custom /toolkit/diary/edit/site-config/ page is the recommended UI;
    # this registration is mainly so superusers can spot the singleton in
    # Django admin if they go looking.

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
