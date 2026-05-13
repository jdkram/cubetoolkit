# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
from django import template

register = template.Library()


@register.filter
def role_label(rota_entry, showing):
    """Return the display label for a rota entry role.

    Singletons show just the role name ("Keyholder"). When a role appears
    more than once in the same showing, all entries get a rank suffix
    ("Keyholder-1", "Keyholder-2"). Uses the prefetched rotaentry_set so
    no extra queries are made.
    """
    count = sum(
        1 for e in showing.rotaentry_set.all()
        if e.role_id == rota_entry.role_id
    )
    if count > 1:
        return f"{rota_entry.role.name}-{rota_entry.rank}"
    return rota_entry.role.name
