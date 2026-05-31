from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from toolkit.members.models import Member, Volunteer


class VolunteerInline(admin.StackedInline):
    model = Volunteer
    can_delete = False
    verbose_name_plural = "Volunteer"
    fields = ("status", "notes")
    readonly_fields = ()


class CustomUserAdmin(UserAdmin):
    inlines = (VolunteerInline,)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_member", "membership_expires", "mailout", "created_at")
    list_filter = ("is_member", "mailout", "mailout_failed")
    search_fields = ("name", "email", "postcode", "number")
    readonly_fields = ("number", "created_at", "updated_at", "mailout_key")
    date_hierarchy = "created_at"


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ("member", "status", "get_email", "created_at")
    list_filter = ("status",)
    search_fields = ("member__name", "member__email", "notes")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.member.email
