from django.contrib import admin

from toolkit.diary.models import Event, Showing, Room, Role, EventTag


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


class ShowingInline(admin.TabularInline):
    model = Showing
    extra = 0
    fields = ("start", "booked_by", "confirmed", "cancelled", "hide_in_programme")
    readonly_fields = ("start",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "private")
    list_filter = ("private", "tags")
    search_fields = ("name", "copy", "booked_by")
    readonly_fields = ("created_at", "updated_at", "legacy_id")
    inlines = (ShowingInline,)


@admin.register(Showing)
class ShowingAdmin(admin.ModelAdmin):
    list_display = ("event", "start", "booked_by", "confirmed", "cancelled")
    list_filter = ("confirmed", "cancelled", "hide_in_programme", "discounted")
    search_fields = ("event__name", "booked_by", "rota_notes")
    date_hierarchy = "start"
    readonly_fields = ("created_at", "updated_at")
