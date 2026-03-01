"""
seed_dev_data - populate the database with realistic anonymised sample data.

Data is drawn from live S&S site HTML captured 18 Feb 2026.
Real volunteer names have been replaced with fictional ones.

Usage:
    manage.py seed_dev_data              # idempotent, safe to run repeatedly
    manage.py seed_dev_data --wipe       # clear diary/member data first
"""

import datetime
import io
import os
import random
import re
import urllib.request

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from toolkit.diary.models import Event, EventTag, EventTemplate, MediaItem, Role, RotaEntry, Room, Showing
from toolkit.index.models import IndexCategory, IndexLink
from toolkit.members.models import Member, Volunteer

try:
    from wagtail.models import Page, Site
    from toolkit.content.models import BasicArticlePage, SectionRootWithLinks
    WAGTAIL_AVAILABLE = True
except ImportError:
    WAGTAIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

ROLES = [
    {"name": "Keyholder", "standard": True},
    {"name": "Programmer", "standard": True},
    {"name": "Projectionist - DCP", "standard": True},
    {"name": "Projectionist - MP4", "standard": False},
    {"name": "Projectionist - Video/DVD", "standard": False},
    {"name": "Projectionist (trained shadowing)", "standard": False},
    {"name": "Bar Staff - Shift 1", "standard": True},
    {"name": "Bar Staff - Shift 2", "standard": False},
    {"name": "Bar Shadow", "standard": False},
    {"name": "Box Office - Admission Tickets", "standard": True},
    {"name": "Box Office - Greeter", "standard": False},
    {"name": "Box Office - Memberships and Merch", "standard": False},
    {"name": "Usher - Fire Trained", "standard": True},
    {"name": "Facilitator", "standard": True},
    {"name": "Facilitator Shadow", "standard": False},
    {"name": "Minute taker", "standard": False},
    {"name": "Inductor - 1 (trained)", "standard": False},
    {"name": "Inductor - 2 (shadowing)", "standard": False},
    {"name": "Trainee (inducted)", "standard": False},
    {"name": "Audio Visual Technician", "standard": False},
    {"name": "Sound Technician level 1", "standard": False},
    {"name": "Sound Technician level 2", "standard": False},
    {"name": "Cafe (Level 1)", "standard": False},
    {"name": "Cafe (Level 2)", "standard": False},
    {"name": "Cafe Shadowing", "standard": False},
    {"name": "Cleaner", "standard": False},
    {"name": "Extra Hands (no training needed)", "standard": False},
    {"name": "Line Cleaner", "standard": False},
    {"name": "Tech (Shadowing)", "standard": False},
]

ROOMS = [
    # Primary rooms: vivid triadic hues (red/blue/yellow ~120° apart), white text.
    # Café is bright yellow - _is_light_colour() in edit_views auto-applies black text.
    # Secondary rooms: clearly pastel so they recede visually; black text auto-detected.
    {"name": "Cinema",      "colour": "#CC2200", "is_primary": True},   # vivid vermilion
    {"name": "Venue Space", "colour": "#0057B8", "is_primary": True},   # royal blue
    {"name": "Café",        "colour": "#FFD700", "is_primary": True},   # bright yellow (→ black text)
    {"name": "External",    "colour": "#E0F5CC", "is_primary": False},  # faint lime green
    {"name": "Meeting",     "colour": "#EDE0FF", "is_primary": False},  # faint lavender
    {"name": "Dark Room",   "colour": "#E8E8E8", "is_primary": False},  # faint grey
    {"name": "Print Room",  "colour": "#D0EDFA", "is_primary": False},  # faint sky blue
    {"name": "workshop",    "colour": "#F5EABB", "is_primary": False},  # faint cream/tan
    {"name": "Green room",  "colour": "#CCEEDF", "is_primary": False},  # faint mint
]

# Which room each seed event belongs to.
EVENT_ROOMS = {
    # --- original events ---
    "Community Kitchen Special: Shared Recipes":                       "Café",
    "Volunteer Hangout":                                                "Venue Space",
    "Volunteer Induction":                                              "Meeting",
    "Keyholder Training":                                               "Meeting",
    "Seeking a Friend for the End of the World":                       "Cinema",
    "Friday Cleaning Club and Brunch Social":                           "Venue Space",
    "Art Club":                                                         "Print Room",
    "Family Film Club":                                                 "Cinema",
    "Starcade":                                                         "Venue Space",
    "Creative Writing":                                                 "Meeting",
    "Programme Development Meeting":                                    "Meeting",
    "Cafe Induction":                                                   "Café",
    "It's Such a Beautiful Day + ME":                                   "Cinema",
    "The Annual Ritual Sacrifice of Pens: A Volunteer Ceremony":       "Venue Space",
    "Four Hours of a Man Juggling Jelly While Weeping":                "Cinema",
    "The Badger Orchestra: An Evening of Striped Symphonies":          "Venue Space",
    "The Impossible Film-Athon: 10 Simultaneous Cinema Screenings":    "Cinema",
    "The Great Inventory Crisis: Volunteer Spirits Appreciation Night": "Venue Space",
    "The Freezer Expedition: A Journey Into the Unknown":              "Café",
    "The Loft Haunting: Negotiation & Possibly Exorcism":              "Venue Space",
    # --- extended events ---
    "Knitting Circle":                                                  "Meeting",
    "Darkroom Induction":                                               "Dark Room",
    "Life Drawing Drop-In":                                             "Venue Space",
    "Repair Café":                                                      "Venue Space",
    "Open Mic Night":                                                   "Venue Space",
    "Printmaking Workshop":                                             "Print Room",
    "Free Film Friday: Spirited Away":                                  "Cinema",
    "Gig: Spectral Harm + support":                                     "Venue Space",
    "Documentary Night: The Painters":                                  "Cinema",
    "Sound Bath & Meditation":                                          "Venue Space",
    "Bike Maintenance Workshop":                                        "Workshop",
    "Volunteer Meeting - All Hands":                                    "Venue Space",
    "Late Night Horror: The Wailing":                                   "Cinema",
    "Zine Fair":                                                        "Venue Space",
    "Letterpress Taster Session":                                       "Print Room",
    "Gig: Pale Teeth + Grotmoor":                                       "Venue Space",
    "Short Film Night":                                                  "Cinema",
    "Fermenting & Pickling Workshop":                                   "Café",
    "Yoga & Movement":                                                  "Venue Space",
    "Film: Perfect Days":                                               "Cinema",
    "Board Game Social":                                                "Venue Space",
    "Podcast Recording Workshop":                                       "Meeting",
    "Volunteer Hangout (April)":                                        "Venue Space",
    "Film: 20,000 Species of Bees":                                     "Cinema",
    "Darkroom Open Session":                                            "Dark Room",
    "Gig: Glass Maze + Tender Echo":                                    "Venue Space",
    "Screen Printing Masterclass":                                      "Print Room",
    "Community Meal":                                                   "Café",
    "Film: All of Us Strangers":                                        "Cinema",
    "Writing Group":                                                    "Meeting",
    # --- busy day 1 (offset +35: all six of these share one date) ---
    "BD1: Cinema - Past Lives":                                         "Cinema",
    "BD1: Venue - Accordion Workshop":                                  "Venue Space",
    "BD1: Café - Sunday Brunch":                                        "Café",
    "BD1: Print Room - Risograph Demo":                                 "Print Room",
    "BD1: Meeting - Programme Pitch Session":                           "Meeting",
    "BD1: Dark Room - Portfolio Review":                                "Dark Room",
    "BD1: Workshop - Seed Swap":                                        "Workshop",
    # --- busy day 2 (offset +70: festival weekend day 1) ---
    "BD2: Cinema - Moonlight":                                          "Cinema",
    "BD2: Venue - Drone & Bass Spectacular":                            "Venue Space",
    "BD2: Café - Pop-Up Market":                                        "Café",
    "BD2: Print Room - Open Press Day":                                 "Print Room",
    "BD2: Meeting - Funders Briefing":                                  "Meeting",
    "BD2: Dark Room - Group Shoot":                                     "Dark Room",
    "BD2: Green Room - Artist Residency Open Studio":                   "Green room",
    # --- busy day 3 (offset +105: autumn programme launch) ---
    "BD3: Cinema - Autumn Launch Screening: The Zone of Interest":      "Cinema",
    "BD3: Venue - Launch Party":                                        "Venue Space",
    "BD3: Café - Cake Sale & Bake-Off":                                 "Café",
    "BD3: Print Room - Poster Making":                                  "Print Room",
    "BD3: Meeting - AGM":                                               "Meeting",
    "BD3: Workshop - Intro to Screen Printing":                         "Workshop",
    # --- flag-test events ---
    "Film: Certified Copy (CANCELLED)":                                 "Cinema",
    "Outside Hire: Private Party":                                      "Venue Space",
    "Film: Portrait of a Lady on Fire (Unconfirmed)":                   "Cinema",
    "Film: Toni Erdmann (Discounted Preview)":                          "Cinema",
    "Private: Safeguarding Training":                                   "Meeting",
}

TAGS = [
    "film",
    "music",
    "workshop",
    "exhibition",
    "performance",
    "meeting",
    "induction",
    "volunteer",
    "party",
    "training-for-volunteers",
    "cafe",
    "online",
    "subtitles",
    "closed-captions",
    "free",
    "outside-hire",
]

# Fictional volunteer names - not real people.
# Inspired by characters/performers from arthouse & world cinema.
VOLUNTEERS = [
    {"name": "Cleo Marchetti", "email": "cleo.marchetti@example.com"},
    {"name": "Elia Silveira", "email": "elia.silveira@example.com"},
    {"name": "Marta Voss", "email": "marta.voss@example.com"},
    {"name": "Rex Hollis", "email": "rex.hollis@example.com"},
    {"name": "Phoebe Lund", "email": "phoebe.lund@example.com"},
    {"name": "Kalani Horita", "email": "kalani.horita@example.com"},
    {"name": "Vera Deschamps", "email": "vera.deschamps@example.com"},
    {"name": "Remy Okafor", "email": "remy.okafor@example.com"},
    {"name": "Jules Travers", "email": "jules.travers@example.com"},
    {"name": "Lena Barrow", "email": "lena.barrow@example.com"},
    {"name": "Sasha Pryce", "email": "sasha.pryce@example.com"},
    {"name": "Tomás Ferreira", "email": "tomas.ferreira@example.com"},
    {"name": "Nell Arundel", "email": "nell.arundel@example.com"},
    {"name": "Ivan Solis", "email": "ivan.solis@example.com"},
    {"name": "Ana Fonseca", "email": "ana.fonseca@example.com"},
    # Single-name volunteers - added to verify the system handles names without surnames.
    {"name": "Beef", "email": "beef@example.com"},
    {"name": "Sparks", "email": "sparks@example.com"},
    {"name": "Cheddar", "email": "cheddar@example.com"},
    {"name": "Moth", "email": "moth@example.com"},
    {"name": "Fig", "email": "fig@example.com"},
]

# Background colours for generated test images, keyed by primary tag.
# Chosen to be visually distinct and cinema-appropriate.
TAG_COLOURS = {
    "film":        (20, 20, 60),    # dark navy
    "music":       (60, 10, 60),    # deep purple
    "performance": (60, 10, 40),    # dark crimson
    "workshop":    (10, 50, 30),    # dark forest green
    "exhibition":  (40, 30, 10),    # dark ochre
    "cafe":        (60, 30, 10),    # dark burnt orange
    "volunteer":   (20, 40, 50),    # dark teal
    "meeting":     (30, 30, 30),    # charcoal
    "induction":   (20, 40, 50),    # dark teal
    "party":       (50, 20, 50),    # dark magenta
    "default":     (25, 25, 40),    # neutral dark blue
}

EVENTS = [
    {
        "name": "Community Kitchen Special: Shared Recipes",
        "copy_summary": "Opening the venue for all volunteers to use as they will. "
        "Workshop, print room, cinema - come along and have a go at whatever takes your fancy.",
        "copy": "An open afternoon for S&S volunteers. The kitchen is yours, the print "
        "room is yours, the cinema is yours. Bring something to share, bring your ideas, "
        "bring yourself. No agenda, no structure - just the building and us.",
        "tags": ["cafe", "workshop"],
        "private": False,
        "rota_notes": "bring your lovely selves and recipes and let's eat stuff from the freezer that's been in there too long\n _____________________\n< I like mooooooovies >\n ---------------------\n        \\   ^__^\n         \\  (oo)\\_______\n            (__)\       )\\/\\\n                ||----w |\n                ||     ||",

        "roles": ["Keyholder", "Cafe (Level 1)", "Extra Hands (no training needed)"],
        "day_offset": 3,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/1267320/pexels-photo-1267320.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Volunteer Hangout",
        "copy_summary": "A chill get together for all volunteers, perfect if you are new or experienced.",
        "copy": "No agenda, no tasks, just volunteers getting to know each other over "
        "a drink. New volunteers especially welcome - this is a great way to meet people "
        "and find out what's going on.",
        "tags": ["volunteer", "party"],
        "private": False,
        "rota_notes": "A chill get together for all volunteers, perfect if you are new or experienced.",
        "roles": ["Keyholder", "Bar Staff - Shift 1"],
        "day_offset": 5,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/3171837/pexels-photo-3171837.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Volunteer Induction",
        "copy_summary": "New to S&S? Come along to our volunteer induction.",
        "copy": "Our regular volunteer induction - a friendly introduction to the Star "
        "and Shadow, how we run things, what roles are available, and how to get started. "
        "Everyone who wants to volunteer should come to one of these first.",
        "tags": ["induction", "volunteer"],
        "private": False,
        "rota_notes": "Please feel free to join us all and share your experiences of "
        "volunteering at the Star and Shadow.",
        "roles": [
            "Inductor - 1 (trained)",
            "Inductor - 2 (shadowing)",
        ],
        "day_offset": 7,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Keyholder Training",
        "copy_summary": "Training for proposed and agreed keyholders.",
        "copy": "Keyholder training for those who have been proposed and agreed as "
        "keyholders but have not yet had training. Existing keyholders welcome if you "
        "want a refresh.",
        "tags": ["training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Keyholder Training for those who have been proposed and agreed "
        "as Keyholders but have not yet had training. (Or if any existing keyholder "
        "wants a refresh then that is good too!)",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 10,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/279810/pexels-photo-279810.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Seeking a Friend for the End of the World",
        "copy_summary": "2012 comedy-drama. Dodge embarks on a road trip as an asteroid "
        "threatens Earth. Dir. Lorene Scafaria. 101 min.",
        "copy": "As a massive asteroid nears Earth, a man finds himself alone after his "
        "wife leaves him. He and his neighbour take a road trip across America to find "
        "his high school sweetheart. Funny, sweet, and oddly comforting.",
        "film_information": "Dir. Lorene Scafaria, USA 2012, 101 min, 15",
        "tags": ["film"],
        "private": False,
        "rota_notes": "Doors 6:30pm. Film 7pm. Projectionist set up by 6pm. The apostrophe thing's fixed-that's genuinely nice.",

        "roles": [
            "Keyholder",
            "Projectionist - DCP",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "day_offset": 12,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/7991579/pexels-photo-7991579.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Friday Cleaning Club and Brunch Social",
        "copy_summary": "Monthly cleaning morning followed by brunch for all volunteers.",
        "copy": "The building doesn't clean itself. Join us from 10am for a cleaning "
        "session, then stay for brunch from noon. A great way to give back and meet "
        "people at the same time.",
        "tags": ["volunteer", "cafe"],
        "private": False,
        "rota_notes": "Cleaning 10am, brunch noon. Cafe open 10:00 til 1:30pm. \nWowee I sure love these apostrophes '''''''''''''''''",

        "roles": ["Keyholder", "Cleaner", "Cafe (Level 1)", "Cafe Shadowing"],
        "day_offset": 14,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/4239091/pexels-photo-4239091.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Art Club",
        "copy_summary": "Open workshop in the art room. All welcome, no experience needed.",
        "copy": "Drop in, pick up some materials, make something. Art Club meets weekly "
        "and is open to everyone - members, volunteers, and the curious.",
        "tags": ["workshop", "exhibition"],
        "private": False,
        "rota_notes": "Art Club meets weekly. Drop in, make something. Yes, apostrophes work now, thanks for asking.",

        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 16,
        "hour": 15,
        "image_url": "https://images.pexels.com/photos/102127/pexels-photo-102127.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Family Film Club",
        "copy_summary": "A free film screening suitable for families and children.",
        "copy": "Our monthly family film club - free, child-friendly, and always "
        "something worth watching. Popcorn available.",
        "pricing": "Free",
        "tags": ["film", "free"],
        "private": False,
        "rota_notes": "Doors 5:30pm. Bar 5:308pm shift 1, 8pm10pm shift 2. Closes 10pm. Apostrophes are working. Not saying I'm shocked.",

        "roles": [
            "Keyholder",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
        ],
        "day_offset": 19,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/33129/popcorn-movie-party-entertainment.jpg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Starcade",
        "copy_summary": "An evening of live music and performance.",
        "copy": "Three acts, two bars, one night. Starcade is S&S's irregular gig night "
        "- always something different, always worth coming to.",
        "tags": ["music", "performance"],
        "private": False,
        "rota_notes": "Doors 7pm. First act 8pm. Sound check 5pm-tech arrives 4:30pm. Apostrophes work. Moving on.",

        "roles": [
            "Keyholder",
            "Sound Technician level 1",
            "Sound Technician level 2",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Box Office - Admission Tickets",
            "Usher - Fire Trained",
        ],
        "day_offset": 21,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/1763075/pexels-photo-1763075.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Creative Writing",
        "copy_summary": "A small group workshop for writers at all levels.",
        "copy": "Weekly creative writing workshop. Exercises, sharing, feedback. "
        "All welcome - from first-timers to experienced writers.",
        "tags": ["workshop", "meeting"],
        "private": False,
        "rota_notes": "Weekly creative writing workshop. Exercises, feedback, sharing. We looooooove writing \" and \' the most, so it's great that apostrophes work now. We can finally write about writing without wanting to scream.",

        "roles": ["Facilitator", "Facilitator Shadow"],
        "day_offset": 23,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/733856/pexels-photo-733856.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Programme Development Meeting",
        "copy_summary": "Meeting to discuss upcoming programme proposals. Open to all.",
        "copy": "Monthly meeting open to all volunteers and members of the public interested in programming. "
        "Bring proposals, costings, and ideas.",
        "tags": ["meeting"],
        "private": False,
        "rota_notes": "Agenda circulated Friday. Please review proposals beforehand.",

        "roles": ["Facilitator", "Minute taker"],
        "day_offset": 25,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Cafe Induction",
        "copy_summary": "Training on how to use the coffee machine and run the cafe.",
        "copy": "Essential training for anyone wanting to volunteer in the cafe. Covers "
        "food hygiene, coffee machine operation, and till use.",
        "tags": ["induction", "cafe", "training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Please read the cafe handbook before attending.",
        "roles": [
            "Inductor - 1 (trained)", 
            "Trainee (inducted)", 
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
            "Trainee (inducted)",
        ],
        "day_offset": 26,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/1307698/pexels-photo-1307698.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "It's Such a Beautiful Day + ME",
        "copy_summary": "Don Hertzfeldt double bill. Strange, beautiful, and genuinely moving.",
        "copy": "A rare chance to see Don Hertzfeldt's animated features on the big screen. "
        "It's Such a Beautiful Day (2012) and ME (2022). Warning: may cause existential "
        "feelings in a good way.",
        "film_information": "Dir. Don Hertzfeldt, USA 2012/2022",
        "tags": ["film"],
        "private": False,
        "rota_notes": "Two films, short break between. Projectionist: check format carefully - "
        "the ME print is DCP, Beautiful Day is MP4.",
        "roles": [
            "Keyholder",
            "Projectionist - DCP",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "day_offset": 28,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/269140/pexels-photo-269140.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Annual Ritual Sacrifice of Pens: A Volunteer Ceremony",
        "copy_summary": "Where do all our pens go? Let's investigate through interpretive ritual & ancient summoning.",
        "copy": "For years, S&S volunteers have wondered: where do the pens disappear to? Tonight, we gather to perform the ancient & sacred Ritual Sacrifice-a solemn ceremony combining scavenger hunt, interpretive dance, & mysterious incantations to either return our missing pens or appease the pen-stealing spirits. Participants must bring one treasured pen to offer. No writing utensils will survive the evening. ",
        "pricing": "Free / your dignity",
        "tags": ["volunteer", "performance", "meeting"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Volunteer-only ritual ceremony. We can't overstate how important it is that volunteers bring a pen they're willing to lose forever.",
        "roles": ["Keyholder", "Sound Technician level 1", "Facilitator"],
        "day_offset": 5,
        "hour": 20,
        "image_url": "https://images.pexels.com/photos/1181690/pexels-photo-1181690.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Four Hours of a Man Juggling Jelly While Weeping",
        "copy_summary": "Wordless. Jiggling. Haunting.",
        "copy": "A visionary work by reclusive avant-garde artist Klaus Gelatino. For four uninterrupted hours, a solitary figure stands centre frame juggling cubes of translucent jelly, made all the more perilous by the growing pool of tears accumulating around him. No plot, no dialogue, just the relentless geometry of sorrow and gelatine.",
        "film_information": "Dir. Klaus Gelatino, Switzerland 2024, 240 min, no cert",
        "tags": ["film", "exhibition"],
        "private": False,
        "rota_notes": "Doors 4pm. Film 4:308:30pm. Toilet breaks discouraged but reluctantly permitted. Box office should be prepared to discuss refund policy (spoiler: no). \nhey - anyone mind if i bring ingredients for jelly shots? \n we're in the process of negotiating a Q&A with the director, provided he eats his way out of the custard tomb that is his current art piece in time. Please watch this space",
        "roles": [
            "Keyholder",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Usher - Fire Trained",
        ],
        "day_offset": 10,
        "hour": 16,
        "image_url": "https://images.pexels.com/photos/3761679/pexels-photo-3761679.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Badger Orchestra: An Evening of Striped Symphonies",
        "copy_summary": "Five badgers. Seventeen instruments. Zero rehearsal. Infinite chaos.",
        "copy": "Fresh from their sold-out European tour, The Badger Orchestra brings their unique blend of aggressive territorial behavior & accidental musicality to S&S. The sounds have been variously described as 'haunting,' 'feral,' 'somehow melancholic,' & 'are you sure those are badgers?'",
        "pricing": "£8/£5",
        "tags": ["music", "performance", "party"],
        "private": False,
        "rota_notes": "Badger gig, so can't stress enough how important it is that we keep door access secure. Badgers are excellent at escaping & also smell quite strong. sound tech might be a challenging setup.",
        "roles": [
            "Keyholder",
            "Sound Technician level 1",
            "Sound Technician level 2",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Box Office - Admission Tickets",
            "Usher - Fire Trained",
        ],
        "day_offset": 15,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/3807517/pexels-photo-3807517.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Impossible Film-Athon: 10 Simultaneous Cinema Screenings",
        "copy_summary": "Ten films. One screen. Eyes wedged open. Narrative coherence shmoherence.",
        "copy": "Inspired by the fragmented postmodern consciousness of modern life, our programmers have attempted the impossible: a ten-film parallel marathon. All films play simultaneously on a single screen via split-diopter lens technology and pure spite. You will see: a kung-fu film, a French New Wave piece, Found Footage horror, documentary realism, experimental animation, a period drama, a heist thriller, Nordic noir, a Bollywood spectacular, & something our programmers refuse to categorize that involves a lot of thin ham. Bring neck support, your own eyelid props, and your willingness to question why cinema exists.",
        "film_information": "A collaborative fever dream, 8 hours, no coherent rating system",
        "tags": ["film", "exhibition", "workshop"],
        "private": False,
        "rota_notes": "Simultaneous film convergence! Doors at noon, screenings 1pm9pm. Projectionist: you're a hero & we can't thank you enough. Some attendees may experience mild synesthesia, probs a good idea to have a first aider to hand here",
        "roles": [
            "Keyholder",
            "Projectionist - DCP",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Usher - Fire Trained",
            "Audio Visual Technician",
        ],
        "day_offset": 20,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/7974/pexels-photo.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Great Inventory Crisis: Volunteer Spirits Appreciation Night",
        "copy_summary": "We have too much stock. You have a liver. Let's introduce them.",
        "copy": "S&S's bar inventory has reached critical levels. Someone ordered seventeen bottles of absinthe in 2019 & we've learned it doesn't expire, and may be gaining sentience. Join us for an evening devoted to the singular mission of reducing our stock to manageable levels. Volunteers only as we can't have the public witness our desperation & strategic dedication to cocktails nobody wants. Features: mystery spirit roulette, experimental mixing, & the moral satisfaction of preventing waste",
        "pricing": "Free (until the next day)",
        "tags": ["volunteer", "party"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "currently plumbed in kegs off limits - please do a stock take before the event and put things aside, no point doing it after as you'll all be hammered - Jerome \n\n and please drink responsibly, but also lots -- fulgencio",
        "roles": ["Keyholder", "Bar Staff - Shift 1", "Bar Staff - Shift 2"],
        "day_offset": 6,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3407814/pexels-photo-3407814.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Freezer Expedition: A Journey Into the Unknown",
        "copy_summary": "What's in the back? We don't know, but we're going to find out.",
        "copy": "The back of our catering freezer hasn't been catalogued since approximately 2015. Behind the labelled containers of ice lollies and what is statistically likely to be daal, something waits. Is it treasure? Is it 2kg of coriander that won't have survived being frozen? Tonight, a selected group of brave volunteers will undertake an archaeological expedition into the depths of our freezer unit to discover what culinary relics remain",
        "pricing": "Free (frostbite treatment not covered)",
        "tags": ["volunteer", "workshop"],
        "private": True,
        "hide_in_programme": True,
        "rota_notes": "Freezer archaeology expedition! Bring thick gloves & emotional resilience. Put the hot water on for a cuppa _before_ you start as your hands will be too numb after.",
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 8,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/5850537/pexels-photo-5850537.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "The Loft Haunting: Negotiation & Possibly Exorcism",
        "copy_summary": "We have a ghost. It's inconvenient. Come help us either evict it or reach detente.",
        "copy": "For months now, S&S vols have reported strange phenomena in the loft: inexplicable drafts, items rearranged, the sound of something that might be sobbing, rats, or the ventiliation system playing up. After careful consideration, we've concluded the most likely explanation is a poltergeist. Rather than immediately attempting violent supernatural removal, we're trying a more collaborative approach: come join us in a negotiation of reasonable cohabition terms, and when that fails, a good ol' fashioned exorcism. Come armed with: sage, skepticism, & a willingness to communicate with the unknown.",
        "pricing": "£5/£3 (proceeds go toward better heating)",
        "tags": ["workshop", "performance", "meeting"],
        "private": False,
        "rota_notes": "For months now, S&S vols have reported strange phenomena in the loft: inexplicable drafts, items rearranged, the sound of something that might be sobbing, rats, or the ventiliation system playing up. After careful consideration, we've concluded the most likely explanation is a poltergeist. Rather than immediately attempting violent supernatural removal, we're trying a more collaborative approach: come join us in a negotiation of reasonable cohabition terms, and when that fails, a good ol' fashioned exorcism. Come armed with: sage, skepticism, & a willingness to communicate with the unknown.",
        "roles": [
            "Keyholder",
            "Facilitator",
            "Audio Visual Technician",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "day_offset": 11,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/1303081/pexels-photo-1303081.jpeg?auto=compress&cs=tinysrgb&w=800",
    },

    # ── Extended programme: spread over ~4 months ──────────────────────────

    {
        "name": "Knitting Circle",
        "copy_summary": "Weekly knitting and crafts drop-in. All levels welcome.",
        "copy": "Bring your needles, bring your wool, bring your half-finished scarf from 2019. "
                "No agenda, just knitting, chat, and tea.",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 18,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/4614227/pexels-photo-4614227.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Darkroom Induction",
        "copy_summary": "Introduction to the darkroom: chemicals, equipment, safety.",
        "copy": "Everything you need to start using the darkroom yourself. "
                "Covers safety, chemistry, enlargers, and printing basics.",
        "tags": ["workshop", "induction", "training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "roles": ["Inductor - 1 (trained)", "Trainee (inducted)", "Trainee (inducted)", "Trainee (inducted)"],
        "day_offset": 20,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/262271/pexels-photo-262271.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Life Drawing Drop-In",
        "copy_summary": "Weekly life drawing with a rotating cast of models.",
        "copy": "Two-hour life drawing session with a professional model. "
                "All media welcome. No booking needed - just turn up.",
        "pricing": "£5/£3",
        "tags": ["workshop", "exhibition"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 22,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/374710/pexels-photo-374710.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Repair Café",
        "copy_summary": "Bring your broken things. Our volunteers will help you fix them.",
        "copy": "Broken lamp? Wobbly chair? Jacket that needs a new zip? "
                "Bring it along and our skilled volunteers will help you repair it. Free.",
        "pricing": "Free (donations welcome)",
        "tags": ["workshop", "free"],
        "private": False,
        "roles": ["Keyholder", "Extra Hands (no training needed)", "Extra Hands (no training needed)"],
        "day_offset": 25,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/4492126/pexels-photo-4492126.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Open Mic Night",
        "copy_summary": "Five minutes, anything goes. Music, poetry, comedy, confessions.",
        "copy": "Sign up on the door for a five-minute slot. "
                "We've had folk songs, stand-up, experimental theremin pieces, and one "
                "very long piece of spoken-word about a supermarket car park. All welcome.",
        "pricing": "Free",
        "tags": ["music", "performance"],
        "private": False,
        "roles": ["Keyholder", "Sound Technician level 1", "Bar Staff - Shift 1", "Box Office - Admission Tickets"],
        "day_offset": 30,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/167636/pexels-photo-167636.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Printmaking Workshop",
        "copy_summary": "Hands-on introduction to linocut and screen printing.",
        "copy": "Learn the basics of two printmaking techniques in one afternoon. "
                "Materials provided. No experience needed.",
        "pricing": "£12/£8",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder", "Facilitator", "Facilitator Shadow"],
        "day_offset": 33,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/1647976/pexels-photo-1647976.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Free Film Friday: Spirited Away",
        "copy_summary": "Miyazaki's masterpiece on the big screen. Free.",
        "copy": "Spirited Away (2001). A ten-year-old girl wanders into a world ruled by gods, "
                "witches, and spirits, and her parents have been turned into pigs. "
                "Dir. Hayao Miyazaki, Japan, 125 min, PG.",
        "film_information": "Dir. Hayao Miyazaki, Japan 2001, 125 min, PG",
        "pricing": "Free",
        "tags": ["film", "free"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 36,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/7991452/pexels-photo-7991452.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Gig: Spectral Harm + support",
        "copy_summary": "Post-punk three-piece with an opening set from local act Molar.",
        "copy": "Spectral Harm play damaged post-punk somewhere between Wire and Shellac. "
                "Support from Newcastle's own Molar, who play one long continuous note "
                "that is somehow also a song.",
        "pricing": "£8/£5",
        "tags": ["music", "performance"],
        "private": False,
        "roles": ["Keyholder", "Sound Technician level 1", "Sound Technician level 2",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2",
                  "Box Office - Admission Tickets", "Usher - Fire Trained"],
        "day_offset": 40,
        "hour": 20,
        "image_url": "https://images.pexels.com/photos/1105666/pexels-photo-1105666.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Documentary Night: The Painters",
        "copy_summary": "Portrait of a collective of painters working in post-industrial Gateshead.",
        "copy": "A quietly devastating document of what it means to make art in difficult "
                "economic conditions. Q&A with the director after the screening.",
        "film_information": "Dir. Ama Kwei, UK 2024, 82 min, 12A",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - MP4", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 44,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/3094218/pexels-photo-3094218.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Sound Bath & Meditation",
        "copy_summary": "90 minutes of gongs, singing bowls, and deep rest.",
        "copy": "Lie down, close your eyes, and let the sound wash over you. "
                "Mats and blankets provided. Recommended for insomniacs, the stressed, "
                "and the merely curious.",
        "pricing": "£7/£5",
        "tags": ["workshop", "performance"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 47,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3822864/pexels-photo-3822864.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Bike Maintenance Workshop",
        "copy_summary": "Learn to fix your own bike. Tools and expertise provided.",
        "copy": "Punctures, brakes, gears, chains. A practical hands-on session for "
                "anyone who wants to be less dependent on the bike shop.",
        "pricing": "Free (donations welcome)",
        "tags": ["workshop", "free"],
        "private": False,
        "roles": ["Keyholder", "Facilitator", "Extra Hands (no training needed)"],
        "day_offset": 51,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/100582/pexels-photo-100582.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Volunteer Meeting - All Hands",
        "copy_summary": "Monthly all-volunteer meeting. Agenda circulated beforehand.",
        "copy": "Open to all volunteers. The place where we make collective decisions "
                "about the cinema. Agenda sent by email the Thursday before.",
        "pricing": "Free",
        "tags": ["meeting", "volunteer"],
        "private": False,
        "roles": ["Facilitator", "Minute taker", "Keyholder"],
        "day_offset": 54,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Late Night Horror: The Wailing",
        "copy_summary": "Korean horror masterpiece. Not for the faint-hearted.",
        "copy": "A detective investigates a series of bizarre deaths in a small village "
                "following the arrival of a mysterious stranger. Dir. Na Hong-jin, "
                "Korea 2016, 156 min, 18. Late licence until 1am.",
        "film_information": "Dir. Na Hong-jin, South Korea 2016, 156 min, 18",
        "pricing": "£6/£4",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2", "Usher - Fire Trained"],
        "day_offset": 58,
        "hour": 22,
        "image_url": "https://images.pexels.com/photos/247314/pexels-photo-247314.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Zine Fair",
        "copy_summary": "Independent publishers, infoshops, and zine makers from across the region.",
        "copy": "Tables of self-published work: comics, poetry, politics, "
                "personal essays, and things that don't fit any category. Free entry, "
                "everything for sale at zine prices.",
        "pricing": "Free entry",
        "tags": ["exhibition", "workshop"],
        "private": False,
        "roles": ["Keyholder", "Extra Hands (no training needed)", "Extra Hands (no training needed)",
                  "Bar Staff - Shift 1"],
        "day_offset": 61,
        "hour": 12,
        "image_url": "https://images.pexels.com/photos/4226896/pexels-photo-4226896.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Letterpress Taster Session",
        "copy_summary": "Try the letterpress for 90 minutes. No experience needed.",
        "copy": "Get hands-on with our Adana press. Print a small card to take home. "
                "Maximum 6 participants - book in advance.",
        "pricing": "£10",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 65,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/1591060/pexels-photo-1591060.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Gig: Pale Teeth + Grotmoor",
        "copy_summary": "Two bands, one night, no particular genre.",
        "copy": "Pale Teeth play expansive post-rock with electronics. "
                "Grotmoor play something shorter and angrier. Both are excellent.",
        "pricing": "£6/£4",
        "tags": ["music", "performance"],
        "private": False,
        "roles": ["Keyholder", "Sound Technician level 1", "Sound Technician level 2",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2",
                  "Box Office - Admission Tickets", "Usher - Fire Trained"],
        "day_offset": 68,
        "hour": 20,
        "image_url": "https://images.pexels.com/photos/995301/pexels-photo-995301.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Short Film Night",
        "copy_summary": "An evening of short films from local filmmakers.",
        "copy": "Programme TBC. Submissions open until two weeks before. "
                "All genres, maximum 15 minutes per film.",
        "pricing": "£5/£3",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - MP4", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 72,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/66134/pexels-photo-66134.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Fermenting & Pickling Workshop",
        "copy_summary": "Make your own kimchi, sauerkraut, or pickles. Take them home.",
        "copy": "A practical afternoon learning the basics of lacto-fermentation. "
                "Materials provided. You'll leave with at least one jar of something.",
        "pricing": "£15/£10 (materials included)",
        "tags": ["workshop", "cafe"],
        "private": False,
        "roles": ["Keyholder", "Facilitator", "Cafe (Level 1)"],
        "day_offset": 75,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/5945641/pexels-photo-5945641.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Yoga & Movement",
        "copy_summary": "Weekly yoga class in the venue space. All levels.",
        "copy": "An accessible, non-competitive yoga class. Mats available. "
                "Donations-based - pay what you can.",
        "pricing": "Donations",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder"],
        "day_offset": 79,
        "hour": 9,
        "image_url": "https://images.pexels.com/photos/4498152/pexels-photo-4498152.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Film: Perfect Days",
        "copy_summary": "Wim Wenders' quietly beautiful film about a Tokyo toilet cleaner.",
        "copy": "Hirayama (Kōji Yakusho) lives a life of small pleasures and careful routine. "
                "Cassette tapes, old paperbacks, and the light through trees. "
                "Dir. Wim Wenders, Japan/Germany 2023, 123 min, PG.",
        "film_information": "Dir. Wim Wenders, Japan/Germany 2023, 123 min, PG",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 82,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/1659438/pexels-photo-1659438.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Board Game Social",
        "copy_summary": "Bring a game, play a game. Bar open.",
        "copy": "Monthly board game night. We have a small library but bring your favourites. "
                "Cooperative games especially welcomed - it's nicer when we all win or all lose together.",
        "pricing": "Free",
        "tags": ["party", "volunteer"],
        "private": False,
        "roles": ["Keyholder", "Bar Staff - Shift 1"],
        "day_offset": 86,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/4291/food-kitchen-cutting-board-cooking.jpg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Podcast Recording Workshop",
        "copy_summary": "Practical intro to recording and editing a podcast.",
        "copy": "Covers microphone technique, basic recording software, editing "
                "for narrative flow, and how to publish. Bring a story you want to tell.",
        "pricing": "£8/£5",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Facilitator", "Audio Visual Technician", "Keyholder"],
        "day_offset": 89,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/3784221/pexels-photo-3784221.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Volunteer Hangout (April)",
        "copy_summary": "Monthly volunteer social. New faces especially welcome.",
        "copy": "No agenda. Just the bar, us, and whoever turns up. "
                "If you've been meaning to come along for ages, this is the night.",
        "tags": ["volunteer", "party"],
        "private": False,
        "roles": ["Keyholder", "Bar Staff - Shift 1"],
        "day_offset": 92,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/3171837/pexels-photo-3171837.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Film: 20,000 Species of Bees",
        "copy_summary": "Tender Spanish film about an 8-year-old navigating gender identity.",
        "copy": "Cocó spends a summer in the Basque Country with her family while her "
                "parents' relationship unravels. A genuinely compassionate film. "
                "Dir. Estibaliz Urresola Solaguren, Spain 2023, 125 min, 12A.",
        "film_information": "Dir. Estibaliz Urresola Solaguren, Spain 2023, 125 min, 12A",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 96,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/1002703/pexels-photo-1002703.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Darkroom Open Session",
        "copy_summary": "Drop-in printing session for trained darkroom members.",
        "copy": "Open access for volunteers who've completed the darkroom induction. "
                "Enlargers and chemicals in good order. Sign up on the sheet.",
        "tags": ["workshop"],
        "private": True,
        "hide_in_programme": True,
        "roles": ["Keyholder"],
        "day_offset": 100,
        "hour": 12,
        "image_url": "https://images.pexels.com/photos/262271/pexels-photo-262271.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Gig: Glass Maze + Tender Echo",
        "copy_summary": "Ambient sounds collide with anxious electronics.",
        "copy": "Glass Maze make long slow pieces full of texture and patience. "
                "Tender Echo are shorter and more agitated. Both are from Newcastle.",
        "pricing": "£7/£5",
        "tags": ["music", "performance"],
        "private": False,
        "roles": ["Keyholder", "Sound Technician level 1", "Sound Technician level 2",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2",
                  "Box Office - Admission Tickets", "Usher - Fire Trained"],
        "day_offset": 103,
        "hour": 20,
        "image_url": "https://images.pexels.com/photos/196644/pexels-photo-196644.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Screen Printing Masterclass",
        "copy_summary": "Full-day screen printing intensive. Advanced techniques.",
        "copy": "For those who've done the taster. Work through a full professional "
                "print run from artwork separation to final print. Maximum 4 participants.",
        "pricing": "£40 (materials included)",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 107,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/8107222/pexels-photo-8107222.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Community Meal",
        "copy_summary": "Cook together, eat together. Ingredients provided.",
        "copy": "The monthly community meal. We shop, we cook, we eat. "
                "No dietary preferences turned away if you let us know in advance.",
        "pricing": "Free (donations welcome)",
        "tags": ["cafe", "volunteer"],
        "private": False,
        "roles": ["Keyholder", "Cafe (Level 1)", "Cafe (Level 1)", "Extra Hands (no training needed)"],
        "day_offset": 111,
        "hour": 17,
        "image_url": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Film: All of Us Strangers",
        "copy_summary": "Andrew Haigh's devastating film about ghosts, grief, and love.",
        "copy": "A lonely screenwriter strikes up a relationship with a neighbour, "
                "then finds himself visiting his childhood home - and his long-dead parents. "
                "Dir. Andrew Haigh, UK 2023, 105 min, 15.",
        "film_information": "Dir. Andrew Haigh, UK 2023, 105 min, 15",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 115,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/1918290/pexels-photo-1918290.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Writing Group",
        "copy_summary": "Fortnightly writing group. Bring something you're working on.",
        "copy": "Small group, honest feedback, strong tea. Bring up to 1,500 words "
                "of something - fiction, non-fiction, script, poetry, whatever you're stuck on.",
        "tags": ["workshop", "meeting"],
        "private": False,
        "roles": ["Facilitator"],
        "day_offset": 118,
        "hour": 18,
        "image_url": "https://images.pexels.com/photos/733856/pexels-photo-733856.jpeg?auto=compress&cs=tinysrgb&w=800",
    },

    # ── Busy Day 1 (offset +35): 7 things happening simultaneously ─────────
    # A typical full Sunday: film + workshop + café brunch + print room + meeting + darkroom + workshop

    {
        "name": "BD1: Cinema - Past Lives",
        "copy_summary": "Celine Song's debut feature. A love story across two continents and twenty years.",
        "copy": "Nora and Hae Sung, childhood sweethearts in Seoul, reconnect as adults. "
                "One of the best films of 2023.",
        "film_information": "Dir. Celine Song, USA/South Korea 2023, 105 min, 12A",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 35,
        "hour": 15,
        "image_url": "https://images.pexels.com/photos/1659438/pexels-photo-1659438.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Venue - Accordion Workshop",
        "copy_summary": "Two-hour introduction to the diatonic button accordion.",
        "copy": "Absolute beginners welcome. Accordions provided. "
                "You will leave able to play at least one tune, probably.",
        "pricing": "£12/£8",
        "tags": ["workshop", "music"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 35,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/164853/pexels-photo-164853.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Café - Sunday Brunch",
        "copy_summary": "Weekly Sunday brunch. Full veggie fry-up and excellent coffee.",
        "copy": "The café is open from 10am. Full veggie breakfast, "
                "eggs various ways, excellent filter coffee, "
                "and the weekend papers if someone's brought them.",
        "pricing": "Pay what you can",
        "tags": ["cafe"],
        "private": False,
        "roles": ["Keyholder", "Cafe (Level 1)", "Cafe (Level 2)", "Cafe Shadowing"],
        "day_offset": 35,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/376464/pexels-photo-376464.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Print Room - Risograph Demo",
        "copy_summary": "See the Riso in action. Learn what it can (and can't) do.",
        "copy": "A 45-minute demo of the risograph printer, followed by open questions. "
                "Essential viewing if you're planning to use it for a project.",
        "pricing": "Free",
        "tags": ["workshop", "free"],
        "private": False,
        "roles": ["Facilitator"],
        "day_offset": 35,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/1591060/pexels-photo-1591060.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Meeting - Programme Pitch Session",
        "copy_summary": "Monthly open pitch session. Bring your event idea.",
        "copy": "Five minutes per proposal. Feedback from the room. "
                "No idea too small or too strange.",
        "tags": ["meeting"],
        "private": False,
        "roles": ["Facilitator", "Minute taker"],
        "day_offset": 35,
        "hour": 16,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Dark Room - Portfolio Review",
        "copy_summary": "Bring your prints. Get honest feedback.",
        "copy": "Informal group review of recent work. The darkroom will be available "
                "for printing before the session from 11am.",
        "tags": ["workshop", "exhibition"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 35,
        "hour": 17,
        "image_url": "https://images.pexels.com/photos/262271/pexels-photo-262271.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD1: Workshop - Seed Swap",
        "copy_summary": "Bring seeds to swap. Leave with something new to grow.",
        "copy": "Annual seed swap. Bring packets, envelopes, or just seeds in "
                "a bit of folded paper. Label them if you can.",
        "pricing": "Free",
        "tags": ["workshop", "free"],
        "private": False,
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "day_offset": 35,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/1002703/pexels-photo-1002703.jpeg?auto=compress&cs=tinysrgb&w=800",
    },

    # ── Busy Day 2 (offset +70): 7 things - notional festival weekend ──────

    {
        "name": "BD2: Cinema - Moonlight",
        "copy_summary": "Barry Jenkins' Moonlight. Oscar-winning, essential.",
        "copy": "Three chapters in the life of a young Black man growing up in Miami. "
                "Dir. Barry Jenkins, USA 2016, 111 min, 15.",
        "film_information": "Dir. Barry Jenkins, USA 2016, 111 min, 15",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 70,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/7991579/pexels-photo-7991579.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Venue - Drone & Bass Spectacular",
        "copy_summary": "Four acts, eight hours, every shade of drone.",
        "copy": "Festival day. Four acts across the afternoon and evening: "
                "ambient, noise, bass-heavy electronics, and something labelled simply 'ritual'. "
                "Bar open all day.",
        "pricing": "£10/£7 day pass",
        "tags": ["music", "performance"],
        "private": False,
        "roles": ["Keyholder", "Sound Technician level 1", "Sound Technician level 2",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2",
                  "Box Office - Admission Tickets", "Usher - Fire Trained"],
        "day_offset": 70,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/1105666/pexels-photo-1105666.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Café - Pop-Up Market",
        "copy_summary": "Local makers, bakers, and sellers. Free entry.",
        "copy": "Around fifteen stalls in and around the café. "
                "Ceramics, preserves, clothing, plants, and at least one table "
                "selling things that defy categorisation.",
        "pricing": "Free entry",
        "tags": ["exhibition", "cafe"],
        "private": False,
        "roles": ["Keyholder", "Cafe (Level 1)", "Cafe (Level 2)",
                  "Extra Hands (no training needed)", "Extra Hands (no training needed)"],
        "day_offset": 70,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/1267320/pexels-photo-1267320.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Print Room - Open Press Day",
        "copy_summary": "All the presses running all day. Come and make something.",
        "copy": "The print room is running all day with a skeleton crew. "
                "Turn up, get a brief intro, make a print. Materials provided.",
        "pricing": "£5 materials contribution",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Facilitator", "Facilitator Shadow"],
        "day_offset": 70,
        "hour": 12,
        "image_url": "https://images.pexels.com/photos/8107222/pexels-photo-8107222.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Meeting - Funders Briefing",
        "copy_summary": "Private briefing for grant-funded projects. Volunteers involved only.",
        "copy": "Closed briefing on current Arts Council-funded projects. "
                "Agenda and papers circulated in advance.",
        "tags": ["meeting"],
        "private": True,
        "hide_in_programme": True,
        "roles": ["Facilitator", "Minute taker"],
        "day_offset": 70,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Dark Room - Group Shoot",
        "copy_summary": "Collaborative darkroom session for the photography collective.",
        "copy": "Members of the photography collective working on a joint "
                "project around the building. Darkroom in use all day.",
        "tags": ["workshop", "exhibition"],
        "private": False,
        "roles": ["Keyholder"],
        "day_offset": 70,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/262271/pexels-photo-262271.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD2: Green Room - Artist Residency Open Studio",
        "copy_summary": "Visit the current resident artist. Work in progress.",
        "copy": "The green room has been occupied for six weeks by artist-in-residence "
                "Marisol Vento. Today she opens her studio to anyone who wants to "
                "see what's been happening.",
        "pricing": "Free",
        "tags": ["exhibition"],
        "private": False,
        "roles": ["Keyholder"],
        "day_offset": 70,
        "hour": 15,
        "image_url": "https://images.pexels.com/photos/3094218/pexels-photo-3094218.jpeg?auto=compress&cs=tinysrgb&w=800",
    },

    # ── Busy Day 3 (offset +105): autumn programme launch ──────────────────

    {
        "name": "BD3: Cinema - Autumn Launch Screening: The Zone of Interest",
        "copy_summary": "Opening night of the autumn programme. Jonathan Glazer's devastating film.",
        "copy": "The commandant of Auschwitz lives an ordinary domestic life with his family "
                "in a house beside the camp wall. Harrowing, extraordinary, necessary. "
                "Dir. Jonathan Glazer, UK/Poland 2023, 105 min, 12A.",
        "film_information": "Dir. Jonathan Glazer, UK/Poland 2023, 105 min, 12A",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Bar Staff - Shift 2", "Usher - Fire Trained"],
        "day_offset": 105,
        "hour": 19,
        "image_url": "https://images.pexels.com/photos/7991452/pexels-photo-7991452.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD3: Venue - Launch Party",
        "copy_summary": "Autumn programme launch. Free bar for the first hour.",
        "copy": "Come celebrate the new programme. Programme booklets available. "
                "Free bar for the first hour courtesy of a donation we'd rather not name.",
        "pricing": "Free",
        "tags": ["party", "volunteer"],
        "private": False,
        "roles": ["Keyholder", "Bar Staff - Shift 1", "Bar Staff - Shift 2",
                  "Usher - Fire Trained", "Extra Hands (no training needed)"],
        "day_offset": 105,
        "hour": 21,
        "image_url": "https://images.pexels.com/photos/3171837/pexels-photo-3171837.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD3: Café - Cake Sale & Bake-Off",
        "copy_summary": "Volunteers bake. Everyone eats. Judging is extremely informal.",
        "copy": "Annual bake-off. Bring a bake by 3pm, judging at 5pm, "
                "everything consumed by 6pm. No theme. All skill levels welcome. "
                "Last year someone brought shop-bought cake with a handwritten label. "
                "They did not win.",
        "pricing": "Free",
        "tags": ["cafe", "volunteer"],
        "private": False,
        "roles": ["Keyholder", "Cafe (Level 1)", "Cafe Shadowing"],
        "day_offset": 105,
        "hour": 14,
        "image_url": "https://images.pexels.com/photos/1024359/pexels-photo-1024359.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD3: Print Room - Poster Making",
        "copy_summary": "Design and print a poster for the autumn programme.",
        "copy": "Open session to make posters for the new programme. "
                "Artwork provided, you operate the press. Two-colour risograph.",
        "pricing": "Free",
        "tags": ["workshop", "free"],
        "private": False,
        "roles": ["Facilitator", "Facilitator Shadow"],
        "day_offset": 105,
        "hour": 11,
        "image_url": "https://images.pexels.com/photos/1647976/pexels-photo-1647976.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD3: Meeting - AGM",
        "copy_summary": "Annual General Meeting. All active volunteers should attend.",
        "copy": "Full AGM with elections, finance report, and major policy votes. "
                "Papers circulated two weeks in advance. Childcare available on request.",
        "tags": ["meeting", "volunteer"],
        "private": False,
        "roles": ["Facilitator", "Minute taker", "Keyholder"],
        "day_offset": 105,
        "hour": 13,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "BD3: Workshop - Intro to Screen Printing",
        "copy_summary": "Beginners welcome. Make one print to take home.",
        "copy": "A two-hour taster covering screen preparation, ink mixing, "
                "and basic squeegee technique. You'll print one A4 image. "
                "Materials included in the ticket price.",
        "pricing": "£12/£8",
        "tags": ["workshop"],
        "private": False,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 105,
        "hour": 10,
        "image_url": "https://images.pexels.com/photos/8107222/pexels-photo-8107222.jpeg?auto=compress&cs=tinysrgb&w=800",
    },

    # ── Flag test events ────────────────────────────────────────────────────
    # One of each: cancelled, outside hire, unconfirmed, discounted, private

    {
        "name": "Film: Certified Copy (CANCELLED)",
        "copy_summary": "Abbas Kiarostami's knotty romantic puzzle. Screening cancelled.",
        "copy": "A writer and a woman spend the day together in Tuscany. "
                "Kiarostami gives nothing away. "
                "Dir. Abbas Kiarostami, France/Italy 2010, 106 min, PG.",
        "film_information": "Dir. Abbas Kiarostami, France/Italy 2010, 106 min, PG",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 42,
        "hour": 19,
        "cancelled": True,
        "confirmed": True,
        "image_url": "https://images.pexels.com/photos/1659438/pexels-photo-1659438.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Outside Hire: Private Party",
        "copy_summary": "Venue Space hired for a private event.",
        "copy": "Venue Space booked for a private birthday party. Not open to the public.",
        "pricing": "",
        "tags": ["outside-hire"],
        "private": False,
        "outside_hire": True,
        "booked_by": "External Booker",
        "roles": ["Keyholder"],
        "day_offset": 55,
        "hour": 18,
        "confirmed": True,
        "image_url": "https://images.pexels.com/photos/3171837/pexels-photo-3171837.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Film: Portrait of a Lady on Fire (Unconfirmed)",
        "copy_summary": "Céline Sciamma's exquisite 18th-century love story. Date pencilled in.",
        "copy": "A painter is commissioned to produce a wedding portrait of a young woman "
                "who refuses to pose. Dir. Céline Sciamma, France 2019, 122 min, 15.",
        "film_information": "Dir. Céline Sciamma, France 2019, 122 min, 15",
        "pricing": "£7/£5",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 63,
        "hour": 19,
        "confirmed": False,
        "image_url": "https://images.pexels.com/photos/269140/pexels-photo-269140.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Film: Toni Erdmann (Discounted Preview)",
        "copy_summary": "Maren Ade's three-hour comedy about a father who won't stop.",
        "copy": "A German father, concerned about his estranged daughter, follows her "
                "to Bucharest and inserts himself into her corporate life. "
                "Dir. Maren Ade, Germany 2016, 162 min, 15.",
        "film_information": "Dir. Maren Ade, Germany 2016, 162 min, 15",
        "pricing": "£5 preview price",
        "tags": ["film"],
        "private": False,
        "roles": ["Keyholder", "Projectionist - DCP", "Box Office - Admission Tickets",
                  "Bar Staff - Shift 1", "Usher - Fire Trained"],
        "day_offset": 77,
        "hour": 18,
        "confirmed": True,
        "discounted": True,
        "image_url": "https://images.pexels.com/photos/7991579/pexels-photo-7991579.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
    {
        "name": "Private: Safeguarding Training",
        "copy_summary": "Internal safeguarding training for keyholders and facilitators.",
        "copy": "Mandatory training for anyone taking on keyholder or facilitator roles. "
                "Led by the safeguarding officer. Not open to the public.",
        "tags": ["training-for-volunteers"],
        "private": True,
        "hide_in_programme": True,
        "roles": ["Keyholder", "Facilitator"],
        "day_offset": 90,
        "hour": 10,
        "confirmed": True,
        "image_url": "https://images.pexels.com/photos/3183150/pexels-photo-3183150.jpeg?auto=compress&cs=tinysrgb&w=800",
    },
]

# Event templates - pre-defined event types selectable when creating a new event.
# (The "add event" UI form requires an EventTemplate to be chosen.)
# Roles and tags reference names defined in ROLES and TAGS above.
EVENT_TEMPLATES = [
    {
        "name": "Film (DCP)",
        "pricing": "£7/£5",
        "roles": [
            "Keyholder",
            "Programmer",
            "Projectionist - DCP",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "tags": ["film"],
    },
    {
        "name": "Film (MP4/DVD)",
        "pricing": "£7/£5",
        "roles": [
            "Keyholder",
            "Programmer",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
            "Usher - Fire Trained",
        ],
        "tags": ["film"],
    },
    {
        "name": "Family Film Club",
        "pricing": "Free",
        "roles": [
            "Keyholder",
            "Projectionist - MP4",
            "Box Office - Admission Tickets",
            "Bar Staff - Shift 1",
        ],
        "tags": ["film", "free"],
    },
    {
        "name": "Gig",
        "pricing": "",
        "roles": [
            "Keyholder",
            "Sound Technician level 1",
            "Sound Technician level 2",
            "Bar Staff - Shift 1",
            "Bar Staff - Shift 2",
            "Box Office - Admission Tickets",
            "Usher - Fire Trained",
        ],
        "tags": ["music", "performance"],
    },
    {
        "name": "Volunteer Induction",
        "pricing": "Free",
        "roles": [
            "Inductor - 1 (trained)",
            "Inductor - 2 (shadowing)",
            "Trainee (inducted)",
        ],
        "tags": ["induction", "volunteer"],
    },
    {
        "name": "Meeting",
        "pricing": "Free",
        "roles": ["Facilitator", "Minute taker"],
        "tags": ["meeting"],
    },
    {
        "name": "Workshop",
        "pricing": "",
        "roles": ["Keyholder", "Facilitator", "Facilitator Shadow"],
        "tags": ["workshop"],
    },
    {
        "name": "Cleaning Session",
        "pricing": "Free",
        "roles": ["Keyholder", "Cleaner", "Extra Hands (no training needed)"],
        "tags": ["volunteer"],
    },
    {
        "name": "Keyholder Training",
        "pricing": "Free",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "tags": ["training-for-volunteers"],
    },
    {
        "name": "Community Kitchen",
        "pricing": "Free",
        "roles": ["Keyholder", "Cafe (Level 1)", "Extra Hands (no training needed)"],
        "tags": ["cafe", "workshop"],
    },
    {
        "name": "Party",
        "pricing": "",
        "roles": ["Keyholder", "Bar Staff - Shift 1", "Bar Shadow"],
        "tags": ["volunteer", "party"],
    },
    {
        "name": "Exhibition",
        "pricing": "",
        "roles": ["Keyholder", "Extra Hands (no training needed)"],
        "tags": ["exhibition"],
    },
    {
        "name": "Outside Hire",
        "pricing": "",
        "roles": ["Keyholder"],
        "tags": ["outside-hire"],
    },
    {
        "name": "Training",
        "pricing": "Free",
        "roles": ["Keyholder", "Trainee (inducted)"],
        "tags": ["training-for-volunteers"],
    },
]

# Safer Spaces page content (based on the live S&S website).
# Used for CMS seed data.
SAFER_SPACES_BODY = """
<h2>Safer Spaces Statement</h2>
<p>The Star and Shadow is committed to being a welcoming space for everyone.
We take all concerns around safety, abuse, and wellbeing seriously - whether
they affect our volunteers, audience members, or anyone in our community.
All volunteers read our Safer Spaces Statement at induction.</p>
<p>If you experience or witness something that concerns you, please come forward.
We have procedures in place to support confidential communication and to take
action where needed.</p>

<h2>Conflict and Breaches of Safer Spaces</h2>
<p>We acknowledge that conflict is inevitable in collective spaces, and that
most issues are resolved through direct conversation. When additional support
is needed, our Mediation Collective is available to help.</p>
<p>Current Mediation Collective members: Dawn Felicia Knox, Amanda McBride, and
Steve Watson. You can reach the team at
<a href="mailto:mediation@starandshadow.org.uk">mediation@starandshadow.org.uk</a>.</p>

<h2>Safeguarding</h2>
<p>Safeguarding is a legal responsibility we take seriously. Our current
Safeguarding Officer is Josephine Walker.</p>
<p>You can submit safeguarding concerns (in confidence) to
<a href="mailto:safeguarding@starandshadow.org.uk">safeguarding@starandshadow.org.uk</a>.</p>
<p>All disclosures to the safeguarding team are treated as confidential.</p>

<h2>Further Resources</h2>
<ul>
<li>Rape Crisis Newcastle upon Tyne - 0800 035 2794</li>
<li>National Male Survivors Helpline - 0808 800 5005</li>
<li>Childline - 0800 1111</li>
<li>LGBT+ Switchboard</li>
<li>GALOP (LGBTQ+ domestic violence support)</li>
</ul>
"""

WHO_ARE_WE_BODY = """
<h2>About the Star and Shadow</h2>
<p>The Star and Shadow Cinema is a volunteer-run community cinema based in
Newcastle upon Tyne. We're not just a cinema - we're a workspace, a meeting
space, an arts space, and a community hub.</p>
<p>Everything we do is run by volunteers. There are no permanent paid staff.
The building is collectively managed, programmed, and cared for by a community
of around 200 active volunteers.</p>
<p>We show independent and world cinema, host live music and performance, run
workshops, and welcome groups who want to use the space. If you've never been,
come along - the bar's open, the welcome's warm, and the programming is always
interesting.</p>
<h2>How We Work</h2>
<p>Decisions are made collectively. There's no boss. The cinema is governed by
a combination of regular volunteer meetings, working groups, and a co-operative
structure that gives every active volunteer a say in how the place is run.</p>
<p>We believe that cinema - and culture more broadly - should be accessible to
everyone, regardless of income, background, or how much they already know about
film. Our pricing reflects that: we keep tickets cheap and our bar is not a
markup machine.</p>
"""

HOW_TO_VOLUNTEER_BODY = """
<h2>How to Get Involved</h2>
<p>The Star and Shadow is run entirely by volunteers. Whether you want to work
behind the bar, operate the projector, help with events, or get involved in
programming - there's a role for you.</p>
<h2>First Steps</h2>
<p>Attend a <strong>Volunteer Induction</strong> - these run regularly and are
the starting point for all new volunteers. You'll meet people, learn how the
building works, and find out what opportunities are available.</p>
<p>Induction dates are listed on the <a href="/">programme page</a>.</p>
<h2>What Happens Next</h2>
<p>After induction you'll be added to the volunteer mailing list and can start
signing up for roles on the rota. Training for most roles (bar, box office,
projection) is hands-on and arranged through the rota.</p>
<h2>Roles Available</h2>
<ul>
<li><strong>Keyholder</strong> - opens and closes the venue</li>
<li><strong>Bar</strong> - bar staff, shadowing, and bar management</li>
<li><strong>Box Office</strong> - tickets, memberships, and greeting</li>
<li><strong>Projectionist</strong> - DCP, MP4/DVD, and shadowing</li>
<li><strong>Facilitator</strong> - facilitating meetings and events</li>
<li><strong>Programmer</strong> - proposing and booking events</li>
<li><strong>Cleaner</strong> - keeping the building clean and welcoming</li>
</ul>
"""

PRIVACY_POLICY_BODY = """
<h2>Privacy Policy</h2>
<p>The Star and Shadow Cinema takes your privacy seriously. We collect only the
data we need to run the cinema and keep our volunteer community informed.</p>
<h2>What We Collect</h2>
<ul>
<li>Your name and email address if you join our mailing list or volunteer</li>
<li>Booking information if you purchase tickets through our box office</li>
</ul>
<h2>How We Use It</h2>
<p>We use your data to send programme information (with your consent), manage
volunteering, and administer the cinema. We never sell your data or share it
with third parties for marketing purposes.</p>
<h2>Your Rights</h2>
<p>You have the right to access, correct, or request deletion of your personal
data at any time. To unsubscribe from our mailing list, follow the link at the
bottom of any email we send you.</p>
<h2>Contact</h2>
<p>If you have any questions about how we handle your data, contact us at
<a href="mailto:info@starandshadow.org.uk">info@starandshadow.org.uk</a>.</p>
"""


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Populate the database with anonymised sample data for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all existing diary/member data before seeding.",
        )
        parser.add_argument(
            "--bulk-volunteers",
            type=int,
            default=2000,
            metavar="N",
            help="Create N numbered test volunteers (voltest_NNNN) for performance testing. Default: 2000.",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self.stdout.write("Wiping existing data...")
            RotaEntry.objects.all().delete()
            Showing.objects.all().delete()
            Event.objects.all().delete()
            EventTemplate.objects.all().delete()
            Room.objects.all().delete()  # wipe all, including any stray rooms not in ROOMS
            EventTag.objects.filter(read_only=False).delete()
            # Delete seed-generated media items (and their files)
            for mi in MediaItem.objects.filter(credit="seed_dev_data"):
                if mi.media_file:
                    mi.media_file.delete(save=False)
                mi.delete()
            Volunteer.objects.all().delete()
            Member.objects.all().delete()
            User.objects.filter(username__contains=".").delete()
            User.objects.filter(username__startswith="voltest_").delete()
            IndexLink.objects.all().delete()
            IndexCategory.objects.all().delete()
            if WAGTAIL_AVAILABLE:
                # Delete seeded section roots and their children.
                # Use page.delete() (not queryset delete) so treebeard
                # properly repairs numchild counts on ancestor pages.
                for slug in ("about", "get-involved", "important-info"):
                    for page in Page.objects.filter(slug=slug):
                        page.delete()
                # Also remove any old-style standalone article pages that
                # might have been seeded before the section structure existed.
                for page in Page.objects.filter(slug="safer-spaces"):
                    page.delete()
            self.stdout.write("  Done.")

        counts = {
            "roles": 0,
            "tags": 0,
            "event_templates": 0,
            "volunteers": 0,
            "events": 0,
            "showings": 0,
            "rota_entries": 0,
            "images": 0,
            "cms_pages": 0,
            "index_links": 0,
        }

        # Roles
        for role_data in ROLES:
            _, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"standard": role_data["standard"]},
            )
            if created:
                counts["roles"] += 1

        # Tags
        for tag_name in TAGS:
            tag, created = EventTag.objects.get_or_create(name=tag_name)
            if created:
                tag.clean()  # generates slug
                tag.save()
                counts["tags"] += 1

        # Event templates
        for tmpl_data in EVENT_TEMPLATES:
            tmpl, created = EventTemplate.objects.get_or_create(
                name=tmpl_data["name"],
                defaults={"pricing": tmpl_data.get("pricing", "")},
            )
            if created:
                counts["event_templates"] += 1
                for role_name in tmpl_data.get("roles", []):
                    try:
                        tmpl.roles.add(Role.objects.get(name=role_name))
                    except Role.DoesNotExist:
                        pass
                for tag_name in tmpl_data.get("tags", []):
                    try:
                        tmpl.tags.add(EventTag.objects.get(name=tag_name))
                    except EventTag.DoesNotExist:
                        pass

        # Pre-compute induction batch dates for the seed volunteers.
        # Walk forward from 2 years ago in random 10–60 day steps so each
        # "batch" of inductees shares the same date, as in real life.
        _today = timezone.now().date()
        _batch_date_pool = []
        _d = _today - datetime.timedelta(days=365 * 2)
        while _d < _today - datetime.timedelta(days=30):
            _batch_date_pool.append(_d)
            _d += datetime.timedelta(days=random.randint(10, 60))

        _vol_induction_dates = []
        _vi = 0
        _pool_idx = 0
        while _vi < len(VOLUNTEERS):
            _bs = random.randint(2, 5)
            _bd = _batch_date_pool[_pool_idx % len(_batch_date_pool)]
            _entries = min(_bs, len(VOLUNTEERS) - _vi)
            _vol_induction_dates.extend([_bd] * _entries)
            _vi += _entries
            _pool_idx += 1

        # Members and Volunteers
        volunteer_objects = {}
        for idx, vol_data in enumerate(VOLUNTEERS):
            member, created = Member.objects.get_or_create(
                email=vol_data["email"],
                defaults={"name": vol_data["name"]},
            )
            if created:
                counts["volunteers"] += 1

            # Create or get Django user
            username = vol_data["email"].split("@")[0]
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": vol_data["email"],
                    "first_name": vol_data["name"].split()[0],
                    "last_name": " ".join(vol_data["name"].split()[1:]),
                },
            )

            volunteer, _ = Volunteer.objects.get_or_create(
                member=member, defaults={"user": user}
            )
            volunteer_objects[vol_data["name"]] = volunteer

            # Back-date the induction date to the pre-computed batch date.
            # We use queryset .update() to bypass auto_now_add.
            induction_date = _vol_induction_dates[idx]
            induction_dt = timezone.make_aware(
                datetime.datetime.combine(induction_date, datetime.time(18, 0))
            )
            Volunteer.objects.filter(pk=volunteer.pk).update(created_at=induction_dt)

            # Give most volunteers a plausible last-login date.
            if random.random() < 0.75:
                user.last_login = timezone.now() - datetime.timedelta(
                    days=random.randint(0, 500)
                )
                user.save(update_fields=["last_login"])

        vol_list = list(volunteer_objects.values())

        # Assign roles to seed volunteers so the summary table shows a mix.
        # First volunteer → superuser; second and third → programmer.
        programmers_group, _ = Group.objects.get_or_create(name="Programmers")
        seed_users = [v.user for v in vol_list if v.user]
        if seed_users:
            u = seed_users[0]
            u.is_superuser = True
            u.is_staff = True
            u.save(update_fields=["is_superuser", "is_staff"])
        for u in seed_users[1:3]:
            programmers_group.user_set.add(u)

        # Rooms - create/update all 9 S&S spaces.
        # update_or_create ensures is_primary is set correctly on re-runs.
        rooms_dict = {}
        for room_data in ROOMS:
            room_obj, _ = Room.objects.update_or_create(
                name=room_data["name"],
                defaults={
                    "colour": room_data["colour"],
                    "is_primary": room_data.get("is_primary", False),
                },
            )
            rooms_dict[room_data["name"]] = room_obj
        default_room = rooms_dict["Venue Space"]

        # Events and Showings
        now = timezone.now()
        anchor = now + datetime.timedelta(days=14)  # centre window 2 weeks out

        for event_data in EVENTS:
            # Derive duration: explicit integer minutes > film_information parse > N(90, 20) clamped 30-240 min
            if "duration" in event_data:
                dur_minutes = event_data["duration"]
            else:
                fi = event_data.get("film_information", "")
                fi_match = re.search(r'(\d+)\s*min', fi) if fi else None
                if fi_match:
                    dur_minutes = int(fi_match.group(1))
                else:
                    dur_minutes = int(max(30, min(240, round(random.gauss(90, 20)))))
            dur_time = datetime.time(dur_minutes // 60, dur_minutes % 60)

            # Derive terms: explicit > copy text (always >= 4 words for every seed event)
            terms_text = event_data.get("terms") or event_data.get("copy", "")

            event, created = Event.objects.get_or_create(
                name=event_data["name"],
                defaults={
                    "copy_summary": event_data.get("copy_summary", ""),
                    "copy": event_data.get("copy", ""),
                    "film_information": event_data.get("film_information", ""),
                    "pricing": event_data.get("pricing", ""),
                    "private": event_data.get("private", False),
                    "outside_hire": event_data.get("outside_hire", False),
                    "terms": terms_text,
                    "duration": dur_time,
                },
            )

            if created:
                counts["events"] += 1
                for tag_name in event_data.get("tags", []):
                    try:
                        tag = EventTag.objects.get(name=tag_name)
                        event.tags.add(tag)
                    except EventTag.DoesNotExist:
                        pass

            # Showing
            showing_start = anchor.replace(
                hour=event_data["hour"],
                minute=0,
                second=0,
                microsecond=0,
            ) + datetime.timedelta(days=event_data["day_offset"] - 14)

            event_room = rooms_dict.get(
                EVENT_ROOMS.get(event_data["name"], "Venue Space"),
                default_room,
            )
            showing, s_created = Showing.objects.get_or_create(
                event=event,
                start=showing_start,
                defaults={
                    "room": event_room,
                    "booked_by": event_data.get("booked_by", "seed_dev_data"),
                    "confirmed": event_data.get("confirmed", True),
                    "cancelled": event_data.get("cancelled", False),
                    "discounted": event_data.get("discounted", False),
                    "hide_in_programme": event_data.get("hide_in_programme", False),
                    "rota_notes": event_data.get("rota_notes", ""),
                },
            )
            if s_created:
                counts["showings"] += 1

            # Rota entries
            available_vols = vol_list[:]
            random.shuffle(available_vols)
            vol_iter = iter(available_vols)

            roles_list = event_data.get("roles", [])
            num_roles = len(roles_list)

            # Calculate how many slots should be empty based on how far in the future the event is.
            # Events closer to now: fewer empty slots. Events further out: more empty slots.
            # max day_offset is 28, so normalize to a 0-1 scale for empty fill rate.
            day_offset = event_data.get("day_offset", 14)
            normalized_distance = min(day_offset / 28.0, 1.0)
            # For close events (0.1 distance), fill 70-80%. For far events (1.0 distance), fill 30-40%.
            fill_rate = 0.8 - (normalized_distance * 0.45)  # ranges ~0.35 to 0.8

            # For each role, create 1-2 additional "backup" slots.
            expanded_roles = []
            for role_name in roles_list:
                expanded_roles.append(role_name)
                if random.random() < 0.7:  # 70% of roles get a backup slot
                    expanded_roles.append(role_name)

            num_expanded = len(expanded_roles)
            num_to_fill = max(1, int(num_expanded * fill_rate))
            unfilled_indices = set(random.sample(range(num_expanded), num_expanded - num_to_fill))

            for i, role_name in enumerate(expanded_roles):
                try:
                    role = Role.objects.get(name=role_name)
                except Role.DoesNotExist:
                    continue

                if i in unfilled_indices:
                    name = ""
                else:
                    try:
                        name = next(vol_iter).member.name
                    except StopIteration:
                        name = ""

                _, re_created = RotaEntry.objects.get_or_create(
                    showing=showing,
                    role=role,
                    rank=1 if i < num_roles else 2,  # backup slots have rank 2
                    defaults={
                        "required": (i < num_roles),  # only first N slots are required
                        "name": name,
                    },
                )
                if re_created:
                    counts["rota_entries"] += 1

            # Generate a test image for this event (for layout testing)
            if not event.media.exists():
                primary_tag = (event_data.get("tags") or ["default"])[0]
                colour = TAG_COLOURS.get(primary_tag, TAG_COLOURS["default"])
                if self._make_event_image(event, colour, event_data.get("image_url")):
                    counts["images"] += 1

        # CMS pages
        if WAGTAIL_AVAILABLE:
            counts["cms_pages"] += self._seed_cms_pages()

        # Toolkit index links
        counts["index_links"] = self._seed_index_links()

        # Bulk test volunteers (performance testing only)
        if options["bulk_volunteers"]:
            counts["volunteers"] += self._seed_bulk_volunteers(options["bulk_volunteers"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeed data created:\n"
                f"  Roles:           {counts['roles']} new\n"
                f"  Tags:            {counts['tags']} new\n"
                f"  Event templates: {counts['event_templates']} new\n"
                f"  Volunteers:      {counts['volunteers']} new\n"
                f"  Events:          {counts['events']} new\n"
                f"  Showings:        {counts['showings']} new\n"
                f"  Rota entries:    {counts['rota_entries']} new\n"
                f"  Images:          {counts['images']} new\n"
                f"  CMS pages:       {counts['cms_pages']} new\n"
                f"  Index links:     {counts['index_links']} new"
            )
        )

    def _seed_index_links(self):
        """Seed the toolkit homepage with a sample link category and links.

        Uses silly placeholder sites to demonstrate the description field,
        which is designed for credentials and notes that admins want to
        copy-paste rather than embed in the link text.
        """
        created = 0

        category, cat_created = IndexCategory.objects.get_or_create(
            name="Useful Resources"
        )
        if cat_created:
            created += 1

        links = [
            {
                "text": "Eel Slap",
                "link": "http://eelslap.com",
                "description": "login: eel   pass: slap",
            },
            {
                "text": "Pointer Pointer",
                "link": "http://pointerpointer.com",
                "description": "login: pointer   pass: point",
            },
            {
                "text": "The Useless Web",
                "link": "http://www.theuselessweb.com",
                "description": "login: useless   pass: web",
            },
            {
                "text": "Windows 93",
                "link": "http://www.windows93.net",
                "description": "",
            },
        ]

        for link_data in links:
            _, link_created = IndexLink.objects.get_or_create(
                link=link_data["link"],
                category=category,
                defaults={
                    "text": link_data["text"],
                    "description": link_data["description"],
                },
            )
            if link_created:
                created += 1

        return created

    def _seed_bulk_volunteers(self, count):
        """Bulk-create N numbered test volunteers for performance testing.

        Uses username pattern voltest_NNNN to avoid clashing with real seed
        volunteers. Idempotent: skips indices that already exist.
        Returns count of volunteers created.
        """
        existing = set(
            int(u[8:])
            for u in User.objects.filter(username__startswith="voltest_")
            .values_list("username", flat=True)
            if u[8:].isdigit()
        )
        to_create = [i for i in range(1, count + 1) if i not in existing]
        if not to_create:
            return 0

        self.stdout.write(f"  Creating {len(to_create)} bulk test volunteers...")

        # Members
        Member.objects.bulk_create(
            [
                Member(
                    name=f"Volunteer {i:04d}",
                    email=f"voltest_{i:04d}@example.test",
                )
                for i in to_create
            ]
        )
        members_by_email = {
            m.email: m
            for m in Member.objects.filter(
                email__in=[f"voltest_{i:04d}@example.test" for i in to_create]
            )
        }

        # Users (no password needed - these accounts are never logged into)
        new_users = []
        for i in to_create:
            u = User(
                username=f"voltest_{i:04d}",
                email=f"voltest_{i:04d}@example.test",
            )
            u.set_unusable_password()
            new_users.append(u)
        User.objects.bulk_create(new_users)
        users_by_username = {
            u.username: u
            for u in User.objects.filter(
                username__in=[f"voltest_{i:04d}" for i in to_create]
            )
        }

        # Volunteers
        Volunteer.objects.bulk_create(
            [
                Volunteer(
                    member=members_by_email[f"voltest_{i:04d}@example.test"],
                    user=users_by_username[f"voltest_{i:04d}"],
                )
                for i in to_create
                if f"voltest_{i:04d}@example.test" in members_by_email
                and f"voltest_{i:04d}" in users_by_username
            ]
        )

        # Back-date induction dates in batches (same logic as seed volunteers).
        # Walk from 5 years ago so 2000 volunteers span a realistic range.
        today = timezone.now().date()
        batch_date_pool = []
        d = today - datetime.timedelta(days=365 * 5)
        while d < today - datetime.timedelta(days=30):
            batch_date_pool.append(d)
            d += datetime.timedelta(days=random.randint(10, 60))

        vol_pks = list(
            Volunteer.objects.filter(
                member__email__in=[
                    f"voltest_{i:04d}@example.test" for i in to_create
                ]
            ).values_list("pk", flat=True).order_by("pk")
        )
        vi = 0
        bi = 0
        while vi < len(vol_pks):
            bs = random.randint(3, 8)
            bd = batch_date_pool[bi % len(batch_date_pool)]
            bdt = timezone.make_aware(
                datetime.datetime.combine(bd, datetime.time(18, 0))
            )
            Volunteer.objects.filter(pk__in=vol_pks[vi:vi + bs]).update(created_at=bdt)
            vi += bs
            bi += 1

        # Random last_login for 60% of bulk volunteers.
        now = timezone.now()
        users_to_update = []
        for u in users_by_username.values():
            if random.random() < 0.6:
                u.last_login = now - datetime.timedelta(days=random.randint(0, 700))
                users_to_update.append(u)
        if users_to_update:
            User.objects.bulk_update(users_to_update, ["last_login"], batch_size=500)

        # 2% panopticon (superuser), 4% programmer.
        all_new_users = list(users_by_username.values())
        n = len(all_new_users)
        if n:
            programmers_group, _ = Group.objects.get_or_create(name="Programmers")
            n_super = max(1, int(0.02 * n))
            superusers = random.sample(all_new_users, min(n_super, n))
            superuser_pks = {u.pk for u in superusers}
            User.objects.filter(pk__in=superuser_pks).update(is_superuser=True, is_staff=True)
            n_prog = max(1, int(0.04 * n))
            eligible = [u for u in all_new_users if u.pk not in superuser_pks]
            programmers = random.sample(eligible, min(n_prog, len(eligible)))
            programmers_group.user_set.add(*programmers)

        return len(to_create)

    def _make_event_image(self, event, bg_colour, image_url=None):
        """Generate or download an 800×450 JPEG test image and attach it to the event."""
        try:
            img = None
            if image_url:
                try:
                    # Download image
                    req = urllib.request.Request(
                        image_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        img_data = response.read()

                    img = Image.open(io.BytesIO(img_data))
                    if img.mode != "RGB":
                        img = img.convert("RGB")

                    # Resize and center-crop to 800x450
                    target_w, target_h = 800, 450
                    img_ratio = img.width / img.height
                    target_ratio = target_w / target_h

                    if img_ratio > target_ratio:
                        # Image is wider than target
                        new_h = target_h
                        new_w = int(new_h * img_ratio)
                    else:
                        # Image is taller than target
                        new_w = target_w
                        new_h = int(new_w / img_ratio)

                    # Use LANCZOS if available (Pillow 9+), else fallback to default
                    resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
                    img = img.resize((new_w, new_h), resample=resample)

                    left = (new_w - target_w) / 2
                    top = (new_h - target_h) / 2
                    right = (new_w + target_w) / 2
                    bottom = (new_h + target_h) / 2
                    img = img.crop((left, top, right, bottom))

                except Exception as exc:
                    self.stdout.write(
                        f"  Warning: could not download image for '{event.name}': {exc}"
                    )
                    img = None

            if img is None:
                # Fallback to generated placeholder
                img = Image.new("RGB", (800, 450), color=bg_colour)
                draw = ImageDraw.Draw(img)

                # Draw a subtle lighter panel in the lower third
                panel_y = 300
                draw.rectangle(
                    [0, panel_y, 800, 450],
                    fill=tuple(max(0, c + 20) for c in bg_colour),
                )

                # Title text - wrap at ~40 chars
                title = event.name
                if len(title) > 40:
                    # Simple word-wrap
                    words = title.split()
                    lines, current = [], []
                    for word in words:
                        if (
                            sum(len(w) for w in current) + len(current) + len(word)
                            > 38
                        ):
                            lines.append(" ".join(current))
                            current = [word]
                        else:
                            current.append(word)
                    if current:
                        lines.append(" ".join(current))
                else:
                    lines = [title]

                y = panel_y + 20
                for line in lines:
                    draw.text((30, y), line, fill=(240, 240, 240))
                    y += 28

                # "SEED IMAGE" watermark in top-right corner
                draw.text((670, 12), "SEED IMAGE", fill=(180, 180, 180))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            jpeg_bytes = buf.getvalue()

            # Write to MEDIA_ROOT
            safe_name = "".join(c if c.isalnum() else "_" for c in event.name[:30])
            filename = f"seed_{event.pk}_{safe_name}.jpg"
            media_dir = os.path.join(settings.MEDIA_ROOT, "diary")
            os.makedirs(media_dir, exist_ok=True)
            file_path = os.path.join(media_dir, filename)
            with open(file_path, "wb") as f:
                f.write(jpeg_bytes)

            # Create MediaItem record pointing to the file
            media_item = MediaItem(
                media_file=f"diary/{filename}",
                credit="seed_dev_data",
                caption=event.name,
            )
            media_item.save()
            event.media.add(media_item)
            return True

        except Exception as exc:
            self.stdout.write(f"  Warning: image generation failed for '{event.name}': {exc}")
            return False

    def _seed_cms_pages(self):
        """Create sample Wagtail CMS pages matching the live S&S nav structure.

        Creates three section roots (About, Get Involved, Important Info) with
        article pages underneath, so the nav menu has the same shape as the
        live starandshadow.org.uk site.  Returns count of pages created.
        """
        try:
            site = Site.objects.filter(is_default_site=True).first()
            if not site:
                self.stdout.write("  No Wagtail site configured - skipping CMS pages.")
                return 0
            root_page = site.root_page
        except Exception as exc:
            self.stdout.write(f"  Warning: could not get Wagtail site: {exc}")
            return 0

        created = 0

        def get_or_create_section(slug, title):
            nonlocal created
            existing = root_page.get_descendants().filter(slug=slug).first()
            if existing:
                return existing.specific
            try:
                section = SectionRootWithLinks(
                    title=title,
                    slug=slug,
                    show_in_menus=True,
                    live=True,
                )
                root_page.add_child(instance=section)
                created += 1
                return section
            except Exception as exc:
                self.stdout.write(f"  Warning: could not create section '{title}': {exc}")
                return None

        def get_or_create_article(parent, slug, title, body, show_on_programme_page=False):
            nonlocal created
            if parent is None:
                return
            existing = parent.get_descendants().filter(slug=slug).first()
            if existing:
                return existing.specific
            try:
                page = BasicArticlePage(
                    title=title,
                    slug=slug,
                    body=body,
                    show_on_programme_page=show_on_programme_page,
                    live=True,
                    show_in_menus=True,
                )
                parent.add_child(instance=page)
                created += 1
            except Exception as exc:
                self.stdout.write(f"  Warning: could not create page '{title}': {exc}")

        # --- About ---
        about = get_or_create_section("about", "About")
        get_or_create_article(about, "who-are-we", "Who Are We", WHO_ARE_WE_BODY.strip())

        # --- Get Involved ---
        get_involved = get_or_create_section("get-involved", "Get Involved")
        get_or_create_article(
            get_involved, "how-to-volunteer", "How to Volunteer", HOW_TO_VOLUNTEER_BODY.strip()
        )

        # --- Important Info ---
        important_info = get_or_create_section("important-info", "Important Info")
        get_or_create_article(
            important_info,
            "safer-spaces",
            "Safer Spaces",
            SAFER_SPACES_BODY.strip(),
            show_on_programme_page=True,
        )
        get_or_create_article(
            important_info, "privacy-policy", "Privacy Policy", PRIVACY_POLICY_BODY.strip()
        )

        # Extra top-level pages - added to reproduce Bug I (sidebar nav overflow).
        # On the live site there are enough sections that the volunteer login link
        # is pushed below the visible area on small/laptop screens because the
        # sidebar has no scroll mechanism.  These pages keep that condition visible
        # in the dev environment so the fix can be verified.
        for slug, title in [
            ("support-us", "Support Us"),
            ("bar-collective", "Bar Collective"),
            ("tech-and-av", "Tech and AV"),
            ("cafe-collective", "Cafe Collective"),
            ("film-nights", "Film Nights"),
            ("community-events", "Community Events"),
        ]:
            get_or_create_article(root_page, slug, title, "<p>Placeholder.</p>")

        return created
