from django.db import migrations

_NEXTCLOUD_GUIDE_URL = "/nextcloud/Film%20%26%20Television%20Programming%20Guide.pdf"

_TICKETSOURCE_GUIDANCE = (
    "<p>Log in to <a href=\"https://www.ticketsource.co.uk\" target=\"_blank\" rel=\"noopener noreferrer\">TicketSource</a>."
    " Username: <strong>REDACTED</strong>. Password: ask a member of the film programming group &mdash; it changes regularly.</p>"
    "<p>See also: <a href=\"{nextcloud_url}\" target=\"_blank\" rel=\"noopener noreferrer\">Film &amp; Television Programming Guide (Nextcloud)</a>"
    " for full guidance on TicketSource, pricing, and promotional material.</p>"
    "<ol>"
    "<li>Hover over the <strong>Events</strong> tab and click <strong>New event</strong>. Enter the same title, date, and details as in Toolkit. Click <strong>Save changes</strong>.</li>"
    "<li>Click <strong>Add venue</strong> and type <em>Star and Shadow</em> into the venue name field. Select the first option from the dropdown &mdash; this autocompletes the venue details. Click <strong>Save changes</strong>.</li>"
    "<li>Click <strong>Add date</strong>. Enter the date and start time. You do not need to specify a doors open time or ending time."
    " Set <strong>Stop ticket sales</strong> to <em>1 hour before start time</em>. Click <strong>Save changes</strong>.</li>"
    "<li>Click <strong>Add ticket allocation</strong> and select <em>Tickets are allocated on a seating plan</em>."
    " From the dropdown choose <strong>2025 Seating Plan</strong>."
    " Uncheck the box labelled <em>Enable orphan seat rule on internet bookings</em>. Click <strong>Save changes</strong>.</li>"
    "<li>Click <strong>Pricing category</strong> and add four pricing options:"
    "<ul>"
    "<li><strong>Full price</strong> &mdash; standard: <strong>&pound;6.50</strong>; cheap night: <strong>&pound;3.50</strong></li>"
    "<li><strong>Concessions</strong> &mdash; standard: <strong>&pound;5</strong>; cheap night: <strong>&pound;3</strong></li>"
    "<li><strong>Further concessions</strong> &mdash; for those who need it; set your own price</li>"
    "<li><strong>Gratis / Free</strong> &mdash; for comps. In <em>Advanced settings</em>, check <em>Individual ticket</em>"
    " and set <em>Maximum selection of</em> to <strong>1 ticket</strong>.</li>"
    "</ul>"
    "For free events, set all ticket prices to &pound;0.</li>"
    "<li>Click <strong>Activate event</strong> to make the listing live.</li>"
    "<li>Click <strong>Publicise event</strong> and copy the <strong>Ticket shop URL</strong>."
    " Paste it into the <em>Ticket link</em> field above in Toolkit.</li>"
    "<li>You can also download a QR code from TicketSource to use in print promotion.</li>"
    "</ol>"
).format(nextcloud_url=_NEXTCLOUD_GUIDE_URL)


def update_guidance(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    SiteConfiguration.objects.update(ticket_link_guidance_html=_TICKETSOURCE_GUIDANCE)


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0080_siteconfiguration_tmdb_api_key"),
    ]

    operations = [
        migrations.RunPython(update_guidance, migrations.RunPython.noop),
    ]
