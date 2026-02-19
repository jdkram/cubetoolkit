# Seed Data Reference

This file documents the sample data produced by `manage.py seed_dev_data`.

**Command location:** `toolkit/util/management/commands/seed_dev_data.py`

---


The `seed_dev_data` management command should produce a realistic working
state that lets developers exercise the full application without needing a
copy of the live database. The data below was derived from live HTML pages
captured from the S&S site (`sample_html_from_current_site/`) on 18 Feb 2026.
Real volunteer names have been replaced with fictional ones.

**Command location:** `toolkit/util/management/commands/seed_dev_data.py`

**Storage approach:** Embed the data directly in the Python command file
(using Python dictionaries/lists). For large datasets, a `toolkit/util/
fixtures/seed_data/` directory containing JSON files loaded by the command
is cleaner and more version-control-friendly. Either approach is fine;
keep the seed data as plain text (not a database dump) so it diffs cleanly
in git and stays small.

#### Roles (from live rota HTML)

| Role name | standard | Notes |
|---|---|---|
| Keyholder | True | |
| Programmer | True | |
| Projectionist - DCP | True | |
| Projectionist - MP4 | False | |
| Projectionist - Video/DVD | False | |
| Projectionist (trained shadowing) | False | Shadow slot |
| Bar Staff - Shift 1 | True | |
| Bar Staff - Shift 2 | False | |
| Bar Shadow | False | Shadow slot |
| Box Office - Admission Tickets | True | |
| Box Office - Greeter | False | |
| Box Office - Memberships and Merch | False | |
| Usher - Fire Trained | True | |
| Facilitator | True | |
| Facilitator Shadow | False | Shadow slot |
| Minute taker | False | |
| Inductor - 1 (trained) | False | |
| Inductor - 2 (shadowing) | False | Shadow slot |
| Trainee (inducted) | False | |
| Audio Visual Technician | False | |
| Sound Technician level 1 | False | |
| Sound Technician level 2 | False | |
| Sound Technician level 3 | False | |
| Cafe (Level 1) | False | |
| Cafe (Level 2) | False | |
| Cafe Shadowing | False | Shadow slot |
| Cleaner | False | |
| Extra Hands (no training needed) | False | |
| Line Cleaner | False | |
| Tech (Shadowing) | False | Shadow slot |

#### Event tags (from live programme)

`film`, `music`, `workshop`, `exhibition`, `performance`, `meeting`,
`induction`, `volunteer`, `party`, `training-for-volunteers`, `cafe`,
`online`, `subtitles`, `closed-captions`, `free`, `outside-hire`

#### Fictional volunteer names

The following names are inspired by characters and performers from the kinds
of films S&S screens — arthouse, world cinema, documentary, experimental.
All are fictional; none correspond to real people.

| Fictional name | Inspired by |
|---|---|
| Cleo Marchetti | *Cléo de 5 à 7* (Varda) |
| Elia Silveira | *Call Me by Your Name* (Guadagnino) |
| Marta Voss | Fassbinder ensemble |
| Rex Hollis | British kitchen-sink tradition |
| Phoebe Lund | Generic British |
| Kalani Horita | Japanese-British |
| Vera Deschamps | French New Wave |
| Remy Okafor | West African heritage |
| Jules Travers | Gender-neutral, British |
| Lena Barrow | Nordic-British |
| Sasha Pryce | Eastern European-British |
| Tomás Ferreira | Portuguese |
| Nell Arundel | Northern English |
| Ivan Solis | Latin American |
| Ana Fonseca | Portuguese/Spanish |

#### Events to seed (drawn from live programme, adapted)

Create these events spread across a 6-week window centred on `now + 2
weeks`. Each event should have 1–2 showings. Tags and roles follow from
the event type.

| Event | Tags | Notes |
|---|---|---|
| Community Kitchen Special: Shared Recipes | `cafe`, `workshop` | Rota note: "Opening the venue for all volunteers to use as they will. Workshop, print room..." |
| Volunteer Hangout | `volunteer`, `party` | Rota note: "A chill get together for all volunteers, perfect if you are new or experienced." |
| Volunteer Induction | `induction`, `volunteer` | Rota note: "Please feel free to join us all and share your experiences of volunteering..." |
| Keyholder Training | `training-for-volunteers` | Rota note: "Keyholder Training for those who have been proposed and agreed as Keyholders." |
| Seeking a Friend for the End of the World | `film` | Comedy drama; full cinema setup |
| Friday Cleaning Club and Brunch Social | `volunteer`, `cafe` | Rota note: "Cleaning from 10am, brunch from noon." |
| Art Club | `workshop`, `exhibition` | Open workshop, no training needed |
| Family Film Club | `film`, `free` | Child-friendly; earlier start time |
| Starcade | `music`, `performance` | Gig night with multiple acts; bar shifts, sound tech, box office |
| Creative Writing | `workshop`, `meeting` | Small group; meeting room; facilitator + shadow |
| Programme Development Meeting | `meeting` | Internal; facilitator + minute taker |
| It's Such a Beautiful Day + ME | `film` | Hertzfeldt double bill |

#### Rota notes to use verbatim (lightly adapted from live site)

These characterful notes reflect the real S&S voice and should be used
as-is in the seed data:

- *"Opening the venue for all volunteers to use as they will. Workshop, print room, cinema. Come along and have a go at whatever takes your fancy."*
- *"A chill get together for all volunteers, perfect if you are new or experienced."*
- *"Please feel free to join us all and share your experiences of volunteering at the Star and Shadow."*
- *"Keyholder Training for those who have been proposed and agreed as Keyholders but have not yet had training. (Or if any existing keyholder wants a refresh then that is good too!)"*
- *"Doors 5:30pm. Bar shift 1: 5:30pm–8pm. Bar shift 2: 8pm–10pm. Bar closes at 10pm."*
- *"Cafe open to public: 10:00–1:30pm"*


