# HerWell Backend

Django admin and JSON API for the HerWell website ([HerWell-Website](https://github.com/SammyGbabs/HerWell-Website)).
The React site stays on Vercel. This service gives the client a dashboard to run the site's content, read form submissions and see payments.

**Stack:** Django 5.2 LTS · Django REST Framework · Unfold admin theme · Supabase (Postgres + Storage) · Render · Paystack

**Full handover (go-live steps, client admin guide, open items):** [docs/ADMIN-HANDOVER.md](docs/ADMIN-HANDOVER.md)

## Admin modules

| # | Module | Where in the admin | What the client does |
|---|---|---|---|
| 1 | Resources & downloads | Website content → Resources | Title, badge, description, PDF, Employer/For You. Downloads stay behind the lead form. |
| 2 | Blog | Settings → Site settings & blog | Writes on Substack. **Refresh blog now** button + automatic daily sync. |
| 3 | Videos | Website content → Videos | YouTube link, title, label, heading, blurb, which page. |
| 4 | Events & webinars | Website content → Events | Date, type, title, speaker, registration link. Upcoming/past sorts itself by date. |
| 5 | Form submissions | Inbox → Form submissions | Contact, demo, downloads, newsletter. Filters, status, notes, CSV export. |
| 6 | Payments & pricing | Payments | Pricing tiers; read-only transactions; **Test gateway connection** button. |
| 7 | Site settings | Settings → Site settings | Contact email, WhatsApp link, socials, Substack URL, Mailchimp list ID. |

## API

All public, read-only except the two `POST`s. JSON keys are camelCase to match the React code.

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | Uptime check. Also touches the DB so Supabase never pauses. |
| GET | `/api/settings/` | Contact email, WhatsApp, Substack, `social` (only filled links). |
| GET | `/api/resources/?audience=employer\|individual` | `fileUrl` is `null` until a PDF is uploaded. |
| GET | `/api/videos/` | `{ home, employer, individual }`, each with `youtubeId`. |
| GET | `/api/events/` | `{ upcoming: [...], past: [...] }` |
| POST | `/api/leads/` | Exactly the `LeadPayload` in `src/lib/leads.ts`. Returns `201 { id }`. 10/hour/IP. |
| GET | `/api/pricing/?audience=` | Active tiers. |
| POST | `/api/checkout/` | `{ tier, email, fullName? }` → `{ url, reference }`. Redirect the buyer to `url`. |
| GET | `/api/checkout/status/?reference=` | For the "payment complete" page. |
| POST | `/api/payments/paystack/webhook/` | Paystack only. Signature-checked, idempotent, re-verified with Paystack. |

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # DJANGO_DEBUG=true is enough to start
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_content --frontend ../HerWell-Website   # loads today's site content + PDFs
python manage.py runserver
python manage.py test
```

Admin at http://localhost:8000/admin/. In the frontend's `.env`, set `VITE_API_BASE_URL=http://localhost:8000`.

## Deploy (free tier)

### 1. Supabase
1. Create a project in the region closest to users (e.g. `eu-central-1`).
2. **Connect → Session pooler** → copy the URI → this is `DATABASE_URL`. *Don't* use "Direct connection": it's IPv6-only and Render can't reach it.
3. **Storage → New bucket** `resources`, set to **Public**.
4. **Storage → S3 Connection** → note the region, create an access key pair.

### 2. Render
1. **New → Blueprint** → pick this repo. `render.yaml` defines everything.
2. Fill in the secret values it asks for (see `.env.example` for what each one is).
3. First deploy runs migrations and creates the admin account from `DJANGO_SUPERUSER_*`.
4. Load the current content once, from your machine against the production DB:
   `DATABASE_URL=<supabase uri> SUPABASE_...=<...> python manage.py seed_content --frontend ../HerWell-Website`

### 3. Keep it awake
Render's free instance sleeps after 15 min idle (first request then takes ~30–60 s, and a lead form would hang).
Add a free [UptimeRobot](https://uptimerobot.com) HTTP monitor on `https://<service>.onrender.com/healthz` every 5 minutes.
One always-on service fits inside Render's 750 free hours/month.

### 4. GitHub secrets (this repo)
- `DATABASE_URL`: the weekly `backup.yml` workflow dumps the DB to a private artifact (Supabase free has no backups).
- `VERCEL_DEPLOY_HOOK_URL`: the daily `blog-sync.yml` rebuilds the site so new Substack posts appear.

### 5. Paystack
- Dashboard → Settings → API Keys & Webhooks → webhook URL: `https://<service>.onrender.com/api/payments/paystack/webhook/`
- Start with `sk_test_` keys. For monthly/yearly tiers, create a Plan in Paystack and paste its `PLN_…` code on the tier.
- **Before taking real money, move Render to the paid Starter plan** (~$7/mo) so checkout is never served by a sleeping instance.

### 6. Frontend
Set `VITE_API_BASE_URL=https://<service>.onrender.com` in Vercel and redeploy. Every form posts here, and resources, videos,
events, contact email, WhatsApp link, social links and the Substack feed all come from the admin.
Each section keeps its built-in content as a fallback (`src/lib/api.ts`), so if this service is asleep or down the site
still renders exactly as it did before the backend existed.

## Security notes
- Gateway and API keys live only in environment variables, never in the admin.
- No card data is stored: hosted checkout, last 4 digits and brand only; Paystack's reusable authorization code is stripped.
- Webhooks: HMAC-SHA512 signature required, one row per event (retries are no-ops), charge re-verified via Paystack, amount and currency must match the checkout.
- CSV export neutralises spreadsheet formulas typed into forms.
- Lead and checkout endpoints are rate-limited; a honeypot field (`website`) silently drops bots.

## Layout

```
config/     settings, urls
core/       site settings singleton, health check, blog refresh, seed + superuser commands, tests
content/    resources, videos, events
leads/      form submissions, Mailchimp sync
payments/   pricing tiers, transactions, Paystack adapter + webhook
```
