from django.db import migrations, models

_TICKETSOURCE_GUIDANCE = (
    "<ol>"
    "<li>Go to <a href=\"https://www.ticketsource.co.uk\" target=\"_blank\" rel=\"noopener noreferrer\">TicketSource</a>"
    " and create a new event with the same title and date.</li>"
    "<li>Set the pricing tier: standard (<strong>£6.50 / £5 concession</strong>) or free."
    " Cheap night: <strong>£3.50 / £3</strong>.</li>"
    "<li>Select the correct seating plan (Cinema layout for film screenings).</li>"
    "<li>Use the exact event title from the toolkit so box office reports match.</li>"
    "<li>Copy the ticket URL and paste it into the <em>Ticket link</em> field above.</li>"
    "</ol>"
)


def seed_ticketsource_guidance(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    SiteConfiguration.objects.filter(ticket_link_guidance_html="").update(
        ticket_link_guidance_html=_TICKETSOURCE_GUIDANCE
    )


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0070_siteconfiguration_age_rating_choices_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="ticket_link_guidance_html",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Ticket link setup guidance",
                help_text=(
                    "HTML shown in a collapsible panel directly below the ticket link field on the "
                    "event edit form. Use this to guide programmers through setting up tickets on "
                    "your chosen platform. Leave blank to hide the panel entirely."
                ),
            ),
        ),
        migrations.RunPython(seed_ticketsource_guidance, migrations.RunPython.noop),
    ]
