import logging
import binascii
import datetime

from django import forms
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from toolkit.members.models import Member, TrainingRecord
import toolkit.diary.models
from toolkit.diary.form_widgets import ChosenSelectMultiple
from django.conf import settings

logger = logging.getLogger(__name__)


class NewMemberForm(forms.ModelForm):
    class Meta:
        model = toolkit.members.models.Member
        fields = ("name", "email", "postcode", "is_member")
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": ""}),
        }


class MemberForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        hide_internal_fields = kwargs.pop("hide_internal_fields", True)
        super().__init__(*args, **kwargs)

        if not settings.MEMBERSHIP_EXPIRY_ENABLED or hide_internal_fields:
            del self.fields["membership_expires"]
        if hide_internal_fields:
            del self.fields["is_member"]
            del self.fields["mailout_failed"]
        del self.fields["gdpr_opt_in"]

    class Meta:
        model = toolkit.members.models.Member
        exclude = ()
        widgets = {
            "phone": forms.TelInput(),
            "altphone": forms.TelInput(),
        }


class MemberFormWithoutNotes(forms.ModelForm):
    # Specify prefix to allow this to coexist in a single <form> alongside
    # VolunteerForm
    prefix = "mem"

    class Meta:
        model = toolkit.members.models.Member
        exclude = (
            "is_member",
            "notes",
            "mailout_failed",
            "membership_expires",
            "gdpr_opt_in",
        )
        widgets = {
            "phone": forms.TelInput(),
            "altphone": forms.TelInput(),
        }


class UserForm(forms.ModelForm):
    prefix = "user"

    programmer = forms.BooleanField(
        required=False,
        label="Programmer status",
        help_text="Grants permission to create and edit events and showings.",
    )

    class Meta:
        model = User
        fields = ("username", "is_active", "is_superuser")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_superuser"].label = "Panopticon access"
        if self.instance and self.instance.pk:
            self.fields["programmer"].initial = self.instance.groups.filter(
                name="Programmers"
            ).exists()

    def save(self, commit=True):
        user = super().save(commit=False)
        # Django admin requires is_staff; mirror is_superuser
        user.is_staff = user.is_superuser
        user.save()
        from django.contrib.auth.models import Group

        programmers = Group.objects.get_or_create(name="Programmers")[0]
        if self.cleaned_data.get("programmer"):
            user.groups.add(programmers)
        else:
            user.groups.remove(programmers)
        return user


class VolunteerForm(forms.ModelForm):
    # Extra non-model field. If this is returned with a base64 encoded PNG data
    # URI then this is saved as the volunteer portrait.
    image_data = forms.CharField(
        label="", required=False, widget=forms.HiddenInput
    )

    # Specify prefix to allow this to coexist in a single <form> alongside
    # MemberFormWithoutNotes
    prefix = "vol"

    # dir_share_name has choices; make it non-required so existing code that
    # submits minimal POST data doesn't fail — clean_dir_share_name defaults it.
    dir_share_name = forms.ChoiceField(
        choices=toolkit.members.models.Volunteer.DIR_SHARE_NAME_CHOICES,
        required=False,
        initial=toolkit.members.models.Volunteer.DIR_SHARE_NONE,
        widget=forms.RadioSelect(),
    )

    def __init__(self, *args, is_superuser=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_superuser = is_superuser

        # Force ordering of roles list to be by "standard" role type, then name
        self.fields["roles"].queryset = self.fields["roles"].queryset.order_by(
            "-standard", "name"
        )

        # Collectives: superusers see all; others see only open collectives.
        from toolkit.labs.models import Collective
        qs = Collective.objects.filter(active=True).order_by("display_order", "name")
        if not is_superuser:
            qs = qs.filter(invite_only=False)
        self.fields["collectives"].queryset = qs

    def clean_dir_share_name(self):
        value = self.cleaned_data.get("dir_share_name")
        if not value:
            return toolkit.members.models.Volunteer.DIR_SHARE_NONE
        return value

    def clean_collectives(self):
        selected = list(self.cleaned_data.get("collectives", []))
        # Non-superusers can't see invite-only collectives in the form, but if
        # they're already a member of one we must not silently drop it on save.
        if not self._is_superuser and self.instance.pk:
            existing_pks = {c.pk for c in selected}
            for c in self.instance.collectives.filter(invite_only=True):
                if c.pk not in existing_pks:
                    selected.append(c)
        return selected

    class Meta:
        model = toolkit.members.models.Volunteer
        fields = (
            "portrait", "notes", "roles", "status",
            "access_intro", "access_needs", "access_links",
            "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone",
            "dir_share_name", "dir_share_pronouns", "dir_share_email",
            "dir_share_phone", "dir_share_access_rider", "dir_share_collectives",
            "collectives",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"wrap": "soft", "rows": 4}),
            "roles": forms.CheckboxSelectMultiple(),
            "status": forms.RadioSelect(),
            "access_intro": forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
            "access_needs": forms.Textarea(attrs={"rows": 5}),
            "access_links": forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
            "collectives": forms.CheckboxSelectMultiple(),
        }

    def _parse_data_uri(self, image_data):
        prefix = "data:image/png;base64,"

        if not image_data.startswith(prefix):
            raise forms.ValidationError("Image data format not recognised")

        base64_data = image_data[len(prefix) :]

        try:
            data = binascii.a2b_base64(base64_data)
        except (binascii.Incomplete, binascii.Error):
            logger.exception("Invalid data")
            raise forms.ValidationError(
                "Image data could not be decoded " "(base64 data invalid)"
            )
        return data

    def clean(self):
        # Try to extract a photo from the image_data field. If successful, save
        # as the portrait. Note that the image will be used in preference to
        # any uploaded file, and will result in the 'clear' checkbox being
        # ignored. This is intentional, as the photo is harder to replace than
        # the uploaded image, if someone's managed to do both.

        cleaned_data = super().clean()

        image_data_uri = cleaned_data["image_data"]

        if image_data_uri:
            image_data = self._parse_data_uri(image_data_uri)
            image_file = SimpleUploadedFile(
                "webcam_photo.png", image_data, "image/png"
            )
            # Use portrait field to validate the uploaded data:
            cleaned_data["portrait"] = self.fields["portrait"].clean(
                image_file
            )

        return cleaned_data


class TrainingRecordForm(forms.ModelForm):
    class Meta:
        model = TrainingRecord
        fields = ("training_type", "role", "trainer", "training_date", "notes")


class GroupTrainingForm(forms.Form):
    type = forms.ChoiceField(
        choices=TrainingRecord.TRAINING_TYPE_CHOICES, required=True
    )
    role = forms.ModelChoiceField(
        queryset=toolkit.diary.models.Role.objects.all(), required=False
    )
    training_date = forms.DateField(required=True, initial=datetime.date.today)
    trainer = forms.CharField(min_length=2, max_length=128, required=True)
    volunteers = forms.ModelMultipleChoiceField(
        queryset=Member.objects.filter(volunteer__active=True).order_by(
            "name"
        ),
        widget=ChosenSelectMultiple(attrs={"size": "8"}),
        required=True,
    )
    notes = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text="(will be added to all selected volunteer's training "
        "records)",
    )

    def clean(self):
        super().clean()
        if (
            self.cleaned_data.get("type") == TrainingRecord.ROLE_TRAINING
            and self.cleaned_data.get("role") is None
        ):
            self.add_error("role", "This field is required.")
