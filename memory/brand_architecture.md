# Brand & Product Architecture — Source of Truth

**Status:** LOCKED · 5 May 2026
**Owner:** Founder / Super Admin
**Audience:** every future dev / design / marketing / legal session

---

## 1 · Layer stack (top-down)

| Layer | Name | Surface |
|-------|------|---------|
| **Legal entity** | **VEALES Vedic Decisions Private Limited** | T&Cs, privacy policy, invoices, MCA, GST, employment, bank, trademark applicant, domain WHOIS registrant, App-Store/Play-Console legal entity |
| **Internal codename** | **View Dezider** | GitHub repo, Jira, infra, `carry_forward.md`, internal Slack — *never customer-facing* |
| **Master / Roof brand** | **Earth Dezider** | Splash footer, /about, app-store *publisher* name, social parent handle (`@earthdezider`), `earthdezider.com` (1-pager + waitlist), investor-deck cover, "by Earth Dezider" imprint on every product |
| **Product line 1 (live)** | **JELCOS AI** | `jelcos.ai`, JELCOS marketing site, app-store product, biz-org whitelabel parent |
| **Product line 2 (next)** | **GeoDezider AI** | `geodezider.ai`, govt marketing site, govt-org whitelabel parent |
| **Consumer edition (future, ~year 3)** | **Earth Dezider** | The master brand *becomes* the consumer app — identical naming (the Apple pattern) |

---

## 2 · Naming canon

### JELCOS AI — full expansion (single source of truth)
> ***Joyful Executive's Life Choices Operating System powered by Artificial Intelligence***

| Letter | Word |
|---|---|
| J | Joyful |
| E | Executive's |
| L | Life |
| C | Choices |
| O | Operating |
| S | System |
| A | Artificial |
| I | Intelligence |

- Audience identity it creates: **The Joyful Executive**
- Tagline: *"The AI Decision OS for the Joyful Executive's life."*
- Buyer segments (all 5): Solopreneurs · Startup Founders · MSME Founders · CXOs · Corporate Managers

### GeoDezider AI
- Audience: government departments, civic decisions
- Tagline (placeholder, to refine before launch): *"The AI Decision OS for civic governance."*

### Earth Dezider
- Audience: every human (eventual consumer edition)
- Strategic frame: *"The Decision OS for People."*
- Reason: **People are the common substrate across all segments.** A JELCOS executive is also a citizen on GeoDezider AI and a consumer on Earth Dezider. One human, multiple editions.

---

## 3 · Org / role hierarchy

```
🌍 EARTH DEZIDER — Master brand (consumer-facing identity)
│   ▲
│   └─ legally owned by: VEALES Vedic Decisions Private Limited
│
├─── 🏢 JELCOS AI (Business Leaders edition)
│       └── Biz-org whitelabels (on their own domains)
│
├─── 🏛 GEO DEZIDER AI (Govt Departments edition)
│       └── Govt-org whitelabels (on their own domains)
│
└─── 👤 Earth Dezider (Consumer edition — future)


🔐 Role hierarchy (people-first; one person can span editions)

Super Admin (Earth Dezider — central)
│
├── JELCOS AI Product-Line Admin
│     ├── Whitelabel Biz-org Admins (per domain)
│     │     └── Biz-org Members (executives)
│     └── JELCOS Customer Success
│
├── GeoDezider AI Product-Line Admin
│     ├── Whitelabel Govt-org Admins (per domain)
│     │     └── Govt-org Members / Citizens
│     └── GeoDezider Customer Success
│
└── Consumer Admin (future)
      └── Consumers
```

A single `person_id` may simultaneously hold roles across multiple editions.

---

## 4 · Brand-imprint rules (Day-1)

**Rule:** *"VEALES Vedic Decisions Private Limited" never appears in consumer-facing marketing copy. It appears only in legal/compliance surfaces.*

| Surface | Show this |
|---------|-----------|
| App splash / login | JELCOS AI wordmark · small "by Earth Dezider" beneath |
| Footer of every screen | "An Earth Dezider product" |
| /about page | "JELCOS AI is one of several product lines from Earth Dezider — the Decision OS for People." |
| App-Store product name | "JELCOS AI" |
| App-Store publisher | "Earth Dezider" |
| App-Store legal entity | "VEALES Vedic Decisions Private Limited" |
| Email from-name | "JELCOS AI · Earth Dezider" |
| Invoice header | Earth Dezider logo |
| Invoice footer fine-print | "Billed by VEALES Vedic Decisions Private Limited · GSTIN: XXXXX · CIN: XXXXX" |
| Investor deck slide 1 | Earth Dezider roof + product editions chart |
| Social bio | "@jelcosai · an @earthdezider product" |

---

## 5 · Domains, handles, trademarks (lock this week)

### Domains (buy + lock as redirects)
- ✅ `earthdezider.com` — primary roof / 1-pager
- ✅ `earthdezider.ai` — defensive
- ✅ `jelcos.ai` — JELCOS AI primary
- ✅ `jelcos.com`, `jelcosai.com`, `getjelcos.com` — defensive
- ✅ `jelkos.ai`, `gelcos.ai` — mis-spell defensive
- ✅ `geodezider.ai` — GeoDezider AI primary
- ✅ `geodezider.com`, `geodeziderai.com` — defensive

### Social handles
- `@earthdezider` — X · LinkedIn · Instagram · YouTube
- `@jelcosai` — same set
- `@geodezider` — same set

### Trademarks (file via TM agent, IP India + later USPTO/EUIPO)
**Applicant:** VEALES Vedic Decisions Private Limited
**Word marks** (Classes 9 + 42):
1. **Earth Dezider**
2. **JELCOS AI**
3. **GeoDezider AI**

Logos / device marks: file once final logos exist.

---

## 6 · Codebase abstraction (implemented in this session)

Single codebase, edition-aware via:

| Layer | What it does |
|---|---|
| `backend/.env` → `PRODUCT_EDITION` | One env var per deployment: `jelcos`, `geodezider`, `consumer`. |
| `backend/core/branding.py` | Resolves the active edition's brand config (display name, tagline, primary_color, logo, supported feature mask). |
| `GET /api/branding/current` | Returns the active edition config for the frontend to hydrate. |
| `GET /api/branding/editions` | Super-admin only — lists all editions for switching. |
| `users.product_edition` field | Each user belongs to one home edition (defaults to active edition on signup). |
| ACM feature gating | Already supports per-edition flags; gate features by edition + role. |
| `frontend/src/store/brandingStore.ts` | Hydrates the brand on app boot; drives splash, footer, /about, theme color. |

This means **one codebase deploys as JELCOS AI today, GeoDezider AI tomorrow, Earth Dezider Consumer in year 3** by flipping a single env var (and applying edition-specific theming).

---

## 7 · Day-1 launch order (locked)

1. **JELCOS AI** (now) — first hot-leads rollout, business-leader segment
2. **GeoDezider AI** (next) — govt-dept rollout once JELCOS AI has traction
3. **Whitelabels** (parallel to 1 & 2) — per biz-org / govt-org on their own domains
4. **Earth Dezider Consumer** (year 3) — consolidates user base from all editions; master-brand becomes the consumer app

---

## 8 · Don'ts (avoid these mistakes)

- ❌ Don't say "VEALES Vedic Decisions Private Limited" anywhere in consumer marketing.
- ❌ Don't put `Artificial Intelligence` or `AI` *inside* the JELCOS expansion as a redundant suffix — the `AI` in "JELCOS AI" + the `.ai` TLD already carry that signal; the acronym's `AI` letters resolve to *Artificial Intelligence* via the "powered by" connector phrase.
- ❌ Don't launch a standalone Earth Dezider consumer app before JELCOS AI has paying customers — split focus is the most common cause of multi-product startup failure.
- ❌ Don't fork the codebase per edition. One codebase, env-flag editions.
- ❌ Don't build separate auth systems per edition. One `person_id`, multiple edition memberships.
- ❌ Don't drop the "by Earth Dezider" footer to "save space" on JELCOS AI surfaces — that footer is the only thing building Earth Dezider equity until consumer launch.
