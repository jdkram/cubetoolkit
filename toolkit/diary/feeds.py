import datetime

from django.contrib.syndication.views import Feed
from django.urls import reverse
import django.utils.timezone as timezone
from django.conf import settings

from toolkit.diary.models import Showing


class BasicWhatsOnFeed(Feed):
    DAYS_AHEAD = 60
    title = f"{settings.VENUE['name']} — forthcoming events"
    description = f"Upcoming public events at {settings.VENUE['name']}."
    link = "/programme"

    def items(self):
        startdate = timezone.now()
        enddate = startdate + datetime.timedelta(days=self.DAYS_AHEAD)
        return (
            Showing.objects.public()
            .start_in_range(startdate, enddate)
            .order_by("start")
            .select_related("event")
        )

    def item_title(self, showing):
        return f"{showing.event.name} — {showing.start.strftime('%-d %B %Y, %H:%M')}"

    def item_description(self, showing):
        summary = showing.event.copy_summary.strip()
        if summary:
            return summary
        return showing.event.copy_html

    def item_link(self, showing):
        return reverse("single-event-view", kwargs={"event_id": showing.event_id})

    def item_pubdate(self, showing):
        # Feed readers use pubdate to decide what's "new".
        ts = showing.created_at or showing.event.created_at
        if ts and not timezone.is_aware(ts):
            ts = timezone.make_aware(ts)
        return ts
