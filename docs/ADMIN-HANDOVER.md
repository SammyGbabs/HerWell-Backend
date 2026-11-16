# HerWell Admin — Handover

**Scope:** Admin v1 — the seven-module dashboard behind herwellafrica.com
**Repos:** `HerWell-Backend` (new) · `HerWell-Website` (frontend, updated to read from it)
**Status:** Built and tested locally. Not yet deployed. Nothing committed.

This document covers what was built, how to put it live on free hosting, how the client uses it day to day, and what is still open.

---

## Contents

1. [What was built](#1-what-was-built)
2. [How it fits together](#2-how-it-fits-together)
3. [Going live](#3-going-live)
4. [Using the admin](#4-using-the-admin)
5. [Free-tier limits and when to pay](#5-free-tier-limits-and-when-to-pay)
6. [Security](#6-security)
7. [Testing and verification](#7-testing-and-verification)
8. [Open items](#8-open-items)
9. [File reference](#9-file-reference)

---

## 1. What was built

### The seven modules

| # | Module | What the client can do |
|---|---|---|
| 1 | **Resources & downloads** | Add a resource with title, badge, description, icon, PDF and audience (Employer or For You). Every download still goes through the lead form. |
| 2 | **Blog** | Keep writing on Substack (Option A). New posts appear automatically once a day, or immediately with **Refresh blog now**. |
| 3 | **Videos** | One founder video per page (Home, Employer, For You): YouTube link, title, label, heading, blurb. |
| 4 | **Events & webinars** | Date, type (Webinar, Q&A, Workshop), title, speaker, registration link, optional recording link. Upcoming vs past sorts itself by date. |
| 5 | **Form submissions** | Every form on the site in one inbox: contact messages, demo requests, resource downloads, newsletter sign-ups. Filters, date range, status, staff notes, CSV export. |
| 6 | **Payments & pricing** | Pricing tiers for checkout, read-only transaction records, and a **Test gateway connection** button. Paystack hosted checkout. |
| 7 | **Site settings** | Contact email, WhatsApp community link, social links, Substack URL, Mailchimp audience ID. Previously hardcoded across several files. |

### Stack

| Piece | Choice | Why |
|---|---|---|
| Admin and API | Django 5.2 LTS, Django REST Framework | Django admin covers most of the seven modules with very little code, which is what makes the budget work. |
| Admin look | Unfold theme, HerWell plum as primary colour | Reads as a modern dashboard rather than default Django. |
| Database | Supabase Postgres (free) | Managed Postgres; used purely as a database, Django owns the schema. |
| File storage | Supabase Storage via its S3 API | Same account; public bucket for resource PDFs. |
| Hosting | Render web service (free) | Python support, deploys from GitHub, blueprint in `render.yaml`. |
| Payments | Paystack | Founder is Kenya-based; Paystack covers cards and M-Pesa. See [open items](#8-open-items). |
| Newsletter | Mailchimp | Newsletter sign-ups are pushed to the audience set in Site settings. |

### Frontend changes (HerWell-Website)

Every section the admin manages now reads from the API, **with the existing hardcoded content kept as a fallback**. If the API is not configured, asleep or down, the site renders exactly as it did before.

| Area | Files |
|---|---|
| Shared fetch layer and fallback hook | `src/lib/api.ts` (new) |
| Site settings hook | `src/lib/siteSettings.ts` (new) |
| Resources | `src/components/sections/FreeResourcesSection.tsx` |
| Videos | `src/lib/founderVideo.ts`, `VideoSection.tsx`, `ExpertsSection.tsx` |
| Events | `src/components/sections/CommEventsSection.tsx` |
| Contact email, WhatsApp, socials | `ContactSection.tsx`, `Footer.tsx`, `CommFinalCTA.tsx`, `Community.tsx`, `SolutionSystems.tsx`, `SolutionWorkplaces.tsx` |
| Forms | `LeadForm.tsx` (spam honeypot), `leads.ts`; `CommNewsletterSection.tsx` and `CommResourcesSection.tsx` were only logging to the console and now submit for real |
| Blog feed | `scripts/fetch-blog.mjs` reads the Substack URL from the admin at build time |

Two bugs were fixed along the way:

- **PDF downloads would have navigated away from the site** once files were on Supabase, because browsers ignore the `download` attribute on another origin. The API now adds Supabase's `?download` flag so the file is sent as an attachment.
- **The Community download cards said "Check your inbox"** when nothing emails the file. They now say the team will email it, which matches what actually happens.

---

## 2. How it fits together

```
 Visitor ──► herwellafrica.com (React, Vercel)
                 │  GET  /api/settings, /resources, /videos, /events
                 │  POST /api/leads, /api/checkout
                 ▼
            HerWell-Backend (Django, Render) ◄── Client edits content in /admin
                 │            │          │
                 ▼            ▼          ▼
          Supabase       Supabase    Paystack ──► webhook back to Django
          Postgres       Storage     Mailchimp
                         (PDFs)

 GitHub Actions (backend repo)
   daily   ─► Vercel deploy hook  (rebuild = pull new Substack posts)
   weekly  ─► pg_dump of Supabase (private artifact, 90 days)

 UptimeRobot ─► /healthz every 5 min (keeps Render awake, keeps Supabase active)
```

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Uptime check; runs one DB query |
| GET | `/api/settings/` | Contact email, WhatsApp, Substack URL, filled-in social links |
| GET | `/api/resources/?audience=employer\|individual` | Published resources; `fileUrl` is null until a PDF is uploaded |
| GET | `/api/videos/` | `{ home, employer, individual }` |
| GET | `/api/events/` | `{ upcoming: [...], past: [...] }` |
| POST | `/api/leads/` | Any site form; same payload the frontend already sent. 10 per hour per IP |
| GET | `/api/pricing/?audience=` | Active pricing tiers |
| POST | `/api/checkout/` | `{ tier, email, fullName? }` → Paystack checkout URL |
| GET | `/api/checkout/status/?reference=` | For a "payment complete" page |
| POST | `/api/payments/paystack/webhook/` | Paystack only |

---

## 3. Going live

Roughly an hour, in this order. Every value mentioned is described in `.env.example`.

### Step 1 — Supabase

1. Create a project in the region closest to users (e.g. Frankfurt, `eu-central-1`).
2. **Connect → Session pooler** → copy the URI. This is `DATABASE_URL`.
   Do **not** use "Direct connection": it is IPv6-only and Render cannot reach it.
3. **Storage → New bucket** named `resources`, set to **Public**.
4. **Storage → S3 Connection** → note the region and create an access key pair.

### Step 2 — Render

1. Push `HerWell-Backend` to GitHub.
2. Render → **New → Blueprint** → select the repo. `render.yaml` creates the service.
3. Fill in the values it asks for: allowed host, CORS origins (`https://herwellafrica.com,https://www.herwellafrica.com`), the Supabase values, the first admin's username, email and password.
4. Deploy. The build runs migrations and creates the admin account.
5. Load the site's current content into the production database, from your machine:

   ```bash
   cd HerWell-Backend
   # with DATABASE_URL and the SUPABASE_* values from Render in your .env
   python manage.py seed_content --frontend ../HerWell-Website
   ```

   This adds the 5 resources with their PDFs, the 3 founder videos, the Substack URL, and the 5 placeholder events (left unpublished for the client to review).

### Step 3 — Keep it awake

Create a free UptimeRobot HTTP monitor on `https://<service>.onrender.com/healthz`, every 5 minutes.

### Step 4 — Vercel (frontend)

1. Add `VITE_API_BASE_URL=https://<service>.onrender.com` to the project's environment variables.
2. **Settings → Git → Deploy Hooks** → create one on `main`. Copy its URL.
3. Redeploy.

### Step 5 — Wire the deploy hook

- Render: set `VERCEL_DEPLOY_HOOK_URL` (powers **Refresh blog now**).
- GitHub, backend repo → **Settings → Secrets → Actions**: add `VERCEL_DEPLOY_HOOK_URL` (daily blog sync) and `DATABASE_URL` (weekly backup).
- Run both workflows once by hand from the **Actions** tab to confirm they pass.

### Step 6 — Optional integrations

| Integration | Where | Value |
|---|---|---|
| Mailchimp | Render env | `MAILCHIMP_API_KEY` |
| Mailchimp | Admin → Site settings | Audience ID |
| Paystack | Render env | `PAYSTACK_SECRET_KEY` (start with `sk_test_`), `PAYSTACK_CALLBACK_URL` |
| Paystack | Paystack dashboard → Webhooks | `https://<service>.onrender.com/api/payments/paystack/webhook/` |

### Go-live check

- [ ] `https://<service>.onrender.com/healthz` returns `{"ok": true}`
- [ ] Admin login works at `/admin/`
- [ ] Site footer, contact page and Community page show the admin's values
- [ ] A test lead from the contact form appears under **Form submissions**
- [ ] A resource download from the Employer page downloads the PDF without leaving the page
- [ ] **Refresh blog now** shows a success message and Vercel starts a deploy
- [ ] **Test gateway connection** reports Paystack in TEST mode
- [ ] Backup workflow produced an artifact

---

## 4. Using the admin

A guide the client can follow. Sign in at `https://<service>.onrender.com/admin/`.

### Add a free resource
**Website content → Resources & downloads → Add.** Fill in title, badge (e.g. "Free PDF · 12 pages"), description, which page it belongs on, an icon, and upload the PDF. Leave the PDF empty to show the card and collect requests before the file is ready. Use **Order** to arrange cards; untick **Show on site** to hide one.

### Change a video
**Website content → Videos** → open the page's video → paste the new YouTube link and update the text. Untick **Show on site** and that page shows "Publishing shortly" instead.

### Add an event
**Website content → Events & webinars → Add.** Set the date and time (Nairobi time), type, title, speaker and registration link. It shows under Upcoming until the time passes, then moves to Past on its own. Add a recording link afterwards to give past events a "Watch recording" button.

### Work through form submissions
**Inbox → Form submissions.** New items arrive with status **New**. Filter by type (download, demo, contact, newsletter), audience, status or date. Change the status from the list as you handle each one, and add notes inside. To export: tick rows (or "select all"), choose **Export selected to CSV** from the actions menu.

Download requests from the Community page collect an email only, so the team sends the file by hand.

### Publish a new blog post now
Publish on Substack as usual. New posts appear on the site within a day automatically. For immediately: **Settings → Site settings & blog → Refresh blog now** (top right). The site updates about two minutes later.

### Update contact details or social links
**Settings → Site settings & blog.** Empty a social field to remove that link from the footer. Changes reach the site within five minutes.

### Pricing and payments
**Payments → Pricing tiers** to set plans shown at checkout. For monthly or yearly plans, create the plan in the Paystack dashboard first and paste its `PLN_…` code. **Payments → Transactions & gateway** lists every payment; records cannot be edited, because Paystack is the source of truth. Use **Test gateway connection** if payments seem to fail.

### Staff accounts
**Settings → Staff users.** Give each person their own login. Untick **Superuser status** for anyone who only needs content and inbox access, and grant permissions through a group.

---

## 5. Free-tier limits and when to pay

| Service | Free limit | Risk | Fix |
|---|---|---|---|
| Render | Sleeps after 15 min idle; 750 hours/month | First request after sleep takes 30–60 s | UptimeRobot ping (included above). One always-on service fits in 750 hours. |
| Supabase | 500 MB DB, 1 GB storage; pauses after 7 days idle; **no backups** | Paused project; data loss | `/healthz` touches the DB; weekly `backup.yml` dump |
| GitHub Actions | Generous on public and private repos | None at this volume | — |
| Mailchimp | 500 contacts (free plan) | Sign-ups stop syncing past the cap | Upgrade Mailchimp when needed |

**Move Render to the paid Starter plan (about USD 7/month) before taking real money.** Checkout should never be served by a sleeping instance. This is a client cost and belongs in the quote.

If the database outgrows the free tier or the client wants point-in-time recovery, Supabase Pro is about USD 25/month.

---

## 6. Security

- **Secrets live only in environment variables** (Paystack, Mailchimp, deploy hook, storage keys). The admin shows gateway *status*, never keys.
- **No card data is held.** Paystack's hosted page takes the card; the backend stores only brand and last four digits. Paystack's reusable authorization code is stripped before anything is saved.
- **Webhooks:** HMAC-SHA512 signature required; each event recorded once so retries are harmless; every charge re-verified with Paystack; paid amount and currency must match what was quoted at checkout, or the transaction is marked failed.
- **Forms:** rate-limited per IP; hidden honeypot field drops bots silently; CSV export neutralises spreadsheet formulas typed into forms.
- **Admin:** HTTPS enforced, secure cookies, HSTS, 8-hour staff sessions, password minimum 10 characters.
- **CORS:** only the listed site origins may call `/api/`.

Not yet done, and worth adding before the platform holds health data: two-factor login for staff (`django-otp`) and an audit log. Both are in `BACKEND-PROPOSAL.md`, phase 8.

---

## 7. Testing and verification

| Check | Result |
|---|---|
| Backend test suite (`python manage.py test`) | 19 passed |
| Django deploy check (`check --deploy`) | Clean apart from two HSTS subdomain/preload warnings, left off on purpose until the client's subdomains are known to be HTTPS-only |
| Frontend `tsc -b` and `eslint .` | Clean |
| Frontend production build | Passes |
| Live run: backend server + real requests from the site's origin | CORS and preflight allowed; settings, resources, videos, events returned; contact and newsletter payloads saved; PDF served as `application/pdf` |
| Blog script reading the Substack URL from the admin | Works; falls back to the default feed if the API is unreachable |

**Not tested against the real services:** Supabase Storage uploads, Paystack and Mailchimp. Their calls are covered by tests with mocked responses; the first real run is part of the go-live check.

---

## 8. Open items

| Item | Owner | Notes |
|---|---|---|
| **Legal entity country** | Client | Confirms Paystack vs Stripe/Flutterwave. Swapping provider means one replacement for `payments/paystack.py`; nothing else changes. |
| **Real social profile URLs** | Client | Until entered, the footer's Social column is hidden. The old links pointed at the LinkedIn/YouTube/Instagram home pages. |
| **Review and publish events** | Client | The seeded events are the site's old placeholders and are unpublished. Until real events are published, the Community page shows "New sessions are being planned." |
| **Substack posts** | Client | The HerWell Substack feed currently has no posts, so the blog stays empty until the first one is published. |
| **Pricing page / checkout UI** | Developer | The API supports checkout; no frontend page calls it yet. Wire it once the provider is confirmed. |
| **Automatic emailing of downloads** | Optional | Today the PDF downloads in the browser; Community requests are sent by the team by hand. An email step (e.g. Resend or Brevo) is a small add-on. |
| **Leftover hardcoded email** | Developer | Three placeholder messages in `src/pages/ComingSoon.tsx` still contain `info@herwellafrica.com`. |
| **Staff 2FA and audit log** | Developer | Recommended before any health data is stored. |
| **Commit and push** | Developer | Both repos have uncommitted changes. `build.sh` is invoked as `bash build.sh`, so no executable bit is needed. |

---

## 9. File reference

### Backend (`HerWell-Backend`)

```
config/settings.py          All configuration, read from environment variables
config/urls.py              Admin, /healthz and /api/ routes
core/                       Site settings, health check, blog refresh button
  management/commands/
    seed_content.py         Loads the site's current content (+ PDFs)
    ensure_superuser.py     Creates the first admin on deploy
  tests.py                  The full test suite
content/                    Resources, videos, events
leads/                      Form submissions, CSV export, Mailchimp sync
payments/                   Pricing tiers, transactions, Paystack adapter and webhook
static/admin/herwell.css    Small admin style touches
build.sh                    Render build: install, collectstatic, migrate, admin
render.yaml                 Render blueprint
.env.example                Every environment variable, explained
.github/workflows/
  blog-sync.yml             Daily site rebuild for new Substack posts
  backup.yml                Weekly database dump
README.md                   Developer quick start
```

### Run locally

```bash
cd HerWell-Backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env                     # DJANGO_DEBUG=true is enough
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_content --frontend ../HerWell-Website
python manage.py runserver               # admin at http://localhost:8000/admin/

# in HerWell-Website/.env
VITE_API_BASE_URL=http://localhost:8000
```
