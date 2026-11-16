"""
Load the content that is currently hardcoded in the React app, so the admin
starts populated instead of empty. Safe to re-run: existing rows are left alone.

    python manage.py seed_content
    python manage.py seed_content --frontend ../HerWell-Website   # also attach the PDFs
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.files import File
from django.core.management.base import BaseCommand

from content.models import Event, Resource, Video
from core.models import SiteSettings

NAIROBI = ZoneInfo("Africa/Nairobi")

RESOURCES = [
    ("employer", 1, "checklist", "Workplace Inclusivity Checklist", "Free PDF · Self-assessment",
     "Score how well your organisation supports menstrual, perimenopausal and menopausal health at work, "
     "then see exactly where the gaps are.",
     "public/resources/employer/workplace-inclusivity-checklist.pdf"),
    ("employer", 2, "template", "Menstrual Health Policy Template", "Free PDF · Editable template",
     "A ready-to-adapt policy document for organisations, drafted by clinicians, written for African workplaces.",
     "public/resources/employer/menstrual-health-policy-template.pdf"),
    ("individual", 1, "guide", "Perimenopause & Menopause Guide", "Free ebook",
     "The full guide: what changes, when it starts, which symptoms are worth investigating, and what actually helps.",
     "public/resources/women/perimenopause-and-menopause-guide.pdf"),
    ("individual", 2, "conversation", "Menopause Myths, Answered", "Free PDF",
     "“It only starts after 50.” “It’s an old woman’s problem.” We take the most common myths apart, one at a time.",
     "public/resources/women/menopause-myths-answered.pdf"),
    ("individual", 3, "tracker", "A Workplace Guide to Perimenopause & Menopause", "Free PDF",
     "What you are entitled to ask for at work, how to raise it, and what a supportive employer should "
     "already have in place.",
     "public/resources/women/workplace-guide-to-perimenopause-and-menopause.pdf"),
]

KAMBUA = ("https://www.youtube.com/watch?v=ZRs2SRSvNT0",
          "Being KAMBUA | Daktari Wetu | Dr Achieng Aling, The Menstrual Doctor", "52:51")
HEY_MAMA = ("https://www.youtube.com/watch?v=bbwOmDdXxDU",
            "Dr. Achieng' Aling: Seeking health is like dating, it's ok to seek a second opinion", "45:21")

VIDEOS = [
    ("home", KAMBUA, "A word from our founder", "Why HerWell exists",
     "After years of watching African women be told their pain was normal, Dr. Achieng' built the service "
     "she kept wishing she could refer them to, clinically rigorous, unhurried, and designed around how "
     "women actually live and work on this continent."),
    ("employer", KAMBUA, "A word from our founder · For employers",
     "Why women's health belongs on the executive agenda",
     "What untreated menstrual, maternal and menopause conditions actually cost an organisation, in absence, "
     "in attrition, and in the women who quietly stop putting themselves forward, and what changes when you "
     "take them seriously."),
    ("individual", HEY_MAMA, "A word from our founder · For you", "Why this was built for women like you",
     "What it means to finally be taken seriously by someone who understands both the medicine and the life "
     "you are living, and why our founder built HerWell for the women she kept wishing she could refer "
     "somewhere better."),
]

# The placeholder events currently on the Community page. Unpublished, so the
# client reviews them before anything shows from the API.
EVENTS = [
    ("2026-07-15", "webinar", "Understanding Perimenopause: What No One Tells You", "Dr. Amara Osei"),
    ("2026-07-22", "qa", "Painful Periods: Causes, Myths, and Real Solutions", "Dr. Fatima Bello"),
    ("2026-08-05", "workshop", "Menopause & Mental Health in the Workplace", "Dr. Ngozi Williams"),
    ("2026-06-18", "webinar", "Breaking the Silence on Menstrual Health at Work", "Dr. Kefilwe Dlamini"),
    ("2026-05-30", "qa", "Everything You Wanted to Ask About Fibroids", "Dr. Adaeze Okafor"),
]


class Command(BaseCommand):
    help = "Seed the admin with the content currently hardcoded in the frontend."

    def add_arguments(self, parser):
        parser.add_argument("--frontend", type=Path, help="Path to the HerWell-Website repo, to attach the PDFs.")

    def handle(self, *args, frontend: Path | None = None, **options):
        site = SiteSettings.load()
        if not site.substack_url:
            site.substack_url = "https://herwell.substack.com"  # the feed the site already reads
            site.save()
        self.stdout.write("Site settings: ready")

        for audience, order, icon, title, badge, description, pdf in RESOURCES:
            resource, created = Resource.objects.get_or_create(
                title=title,
                defaults=dict(audience=audience, sort_order=order, icon=icon, badge=badge, description=description),
            )
            pdf_path = frontend / pdf if frontend else None
            if pdf_path and pdf_path.exists() and not resource.file:
                with pdf_path.open("rb") as fh:
                    resource.file.save(pdf_path.name, File(fh), save=True)
            self.stdout.write(f"Resource: {title} ({'created' if created else 'exists'}{', PDF attached' if resource.file else ''})")

        for placement, (url, title, duration), eyebrow, heading, blurb in VIDEOS:
            _, created = Video.objects.get_or_create(
                placement=placement,
                defaults=dict(youtube_url=url, title=title, duration=duration, eyebrow=eyebrow,
                              heading=heading, blurb=blurb),
            )
            self.stdout.write(f"Video: {placement} ({'created' if created else 'exists'})")

        for day, kind, title, speaker in EVENTS:
            starts = datetime.fromisoformat(f"{day}T18:00").replace(tzinfo=NAIROBI)
            _, created = Event.objects.get_or_create(
                title=title,
                defaults=dict(event_type=kind, starts_at=starts, speaker=speaker, is_published=False),
            )
            self.stdout.write(f"Event: {title} ({'created, unpublished' if created else 'exists'})")

        self.stdout.write(self.style.SUCCESS("Done."))
