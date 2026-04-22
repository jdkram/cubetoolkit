from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Event, EventTermsRevision

_AUDITED_FIELDS = ("terms", "outside_hire", "private")


@receiver(pre_save, sender=Event)
def snapshot_financial_fields_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return  # new record — nothing to snapshot
    try:
        prior = Event.objects.get(pk=instance.pk)
    except Event.DoesNotExist:
        return
    if any(getattr(prior, f) != getattr(instance, f) for f in _AUDITED_FIELDS):
        EventTermsRevision.objects.create(
            event=instance,
            saved_by=getattr(instance, "_saved_by", None),
            terms_text=prior.terms or "",
            outside_hire=prior.outside_hire,
            private=prior.private,
        )
