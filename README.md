# Sozibot — KI Social Media Automation

AI-powered social media management platform. Generates, schedules, approves and publishes content across Instagram, Facebook, LinkedIn, Twitter and TikTok — all from one dashboard.

---

## Features

- **Content Calendar** — 4-week forward view with 3-level drill-down (Week → Day → Post)
- **AI Content Generation** — Claude-powered posts tailored to your brand voice
- **Inline Approval Workflow** — Approve/reject posts directly in the calendar
- **Variant System** — Generate multiple AI variants per post, pick the best
- **Multi-Platform** — Instagram, Facebook, LinkedIn, Twitter/X, TikTok
- **Brand Settings** — Upload PDFs, set tone of voice, visual style
- **Media Manager** — Asset library with AI image analysis
- **Analytics** — Post performance and engagement tracking
- **Billing** — Stripe-based subscription plans with usage limits

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, Flask |
| AI | Anthropic Claude API |
| Scheduling | APScheduler |
| Payments | Stripe |
| Frontend | Vanilla JS, Jinja2 templates |
| Design | Catppuccin Mocha dark theme |

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/Hansweier/social-media-saas.git
cd social-media-saas
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env` — minimum required:

```env
CLAUDE_API_KEY=sk-ant-...        # https://console.anthropic.com
```

All other keys are optional and only needed for the respective platforms.

### 3. Run

```bash
python main.py
```

Dashboard opens at `http://localhost:5000`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CLAUDE_API_KEY` | ✅ | Anthropic API key for AI generation |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram | Instagram Graph API token |
| `INSTAGRAM_ACCOUNT_ID` | Instagram | Numeric Instagram Business ID |
| `FACEBOOK_ACCESS_TOKEN` | Facebook | Facebook Page Access Token |
| `FACEBOOK_PAGE_ID` | Facebook | Facebook Page ID |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn | LinkedIn OAuth2 token |
| `LINKEDIN_PERSON_ID` | LinkedIn | `urn:li:person:XXXXX` |
| `TWITTER_API_KEY` | Twitter | Twitter Developer API key |
| `TWITTER_API_SECRET` | Twitter | Twitter Developer API secret |
| `TWITTER_ACCESS_TOKEN` | Twitter | Twitter Access Token |
| `TWITTER_ACCESS_TOKEN_SECRET` | Twitter | Twitter Access Token Secret |
| `TIKTOK_ACCESS_TOKEN` | TikTok | TikTok Content Posting API token |
| `STRIPE_SECRET_KEY` | Billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Billing | Stripe webhook signing secret |
| `STRIPE_PRICE_STARTER` | Billing | Stripe Price ID for Starter plan |
| `STRIPE_PRICE_PRO` | Billing | Stripe Price ID for Pro plan |
| `STRIPE_PRICE_AGENCY` | Billing | Stripe Price ID for Agency plan |
| `ADMIN_SECRET` | Billing | Admin secret for license key generation |
| `APP_BASE_URL` | Billing | Public URL e.g. `https://yourdomain.com` |

---

## Meta Developer Setup (Instagram & Facebook)

1. Go to [developers.facebook.com](https://developers.facebook.com) → Create App → **Business** type
2. Add product: **Instagram Graph API**
3. Your Instagram account must be a **Business or Creator** account linked to a Facebook Page
4. Generate tokens in Graph API Explorer with scopes:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
5. For production posting → submit App Review to Meta (takes 1–5 business days)

---

## Stripe Setup

1. Create products & prices in [Stripe Dashboard](https://dashboard.stripe.com)
2. Copy Price IDs (`price_xxx`) into `.env`
3. Set webhook endpoint: `https://yourdomain.com/billing/webhook`
4. Events to listen for:
   - `checkout.session.completed`
   - `invoice.paid`
   - `invoice.payment_failed`
   - `customer.subscription.deleted`

---

## Plans

| Plan | Posts/month | Platforms | Price |
|------|-------------|-----------|-------|
| Trial | 30 | 3 | Free |
| Starter | 150 | 3 | €79/mo |
| Pro | Unlimited | 5 | €149/mo |
| Agency | Unlimited | 5 | €349/mo |

---

## Project Structure

```
├── bot/                    # Core bot logic
│   ├── ai_generator.py     # Claude content generation
│   ├── content_calendar.py # Calendar data management
│   ├── poster.py           # Post execution
│   └── scheduler.py        # APScheduler jobs
├── brand/                  # Brand defaults
├── dashboard/
│   ├── routes/             # Flask blueprints
│   │   ├── calendar.py     # 4-week calendar + archive
│   │   ├── approval.py     # Post approval workflow
│   │   ├── billing.py      # Stripe billing
│   │   └── ...
│   ├── services/
│   │   ├── plan_service.py # Plan limits & license keys
│   │   ├── variant_service.py
│   │   └── ai_vision.py    # Claude vision analysis
│   └── templates/          # Jinja2 HTML templates
├── platforms/              # Platform-specific API wrappers
│   ├── instagram/
│   ├── facebook/
│   ├── linkedin/
│   ├── twitter/
│   └── tiktok/
├── .env.example
├── requirements.txt
└── main.py
```

---

## License

Private — all rights reserved.
