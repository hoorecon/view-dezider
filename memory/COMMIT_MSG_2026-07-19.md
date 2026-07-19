feat(frame): Sponsored Solutions (AdMaker) + publisher widgets (AdTaker) + 10M-option Option-Bank Finder + full KT doc refresh

BUILD_VERSION=2026.07.19.004 · BUILD_TAG=v3.111-frame-adprograms-optionbank-kt
Scope: Iter 193–194 (everything since v3.108-decider-store-subfactors / 2026.07.18.004)
Tests: 27/27 backend pytest (iter193: 13, iter194: 14) + 11 testing-agent UI flows PASS, zero regressions.

════════════════════════════════════════════════════════════════════
FUNCTIONAL KT — for Product Managers & End Users
════════════════════════════════════════════════════════════════════

1. SPONSORED SOLUTIONS (AdMaker Program) — the AdWords of Decider Apps
   • When a user runs a Decider App, the organic Top-N stays 100% quality-ranked
     (money can NEVER reorder it). Up to N clearly-labelled "Sponsored Solutions ·
     AD" cards render BELOW the organic list.
   • Trust dial: only options that match the user at/above a Min Cutoff % can be
     sponsored. Cutoff % + slot count are configured globally and per
     LifeArea/SubArea/Scenario in the Central Catalog Manager — a value set high
     up applies to every leaf below it unless a deeper node overrides (Admin →
     AdMaker & AdTaker → Cutoffs & Slots).
   • Auction: among eligible bids, rank = bid × match-quality; winners pay the
     fair second price, charged per click; budgets auto-pause when exhausted.
     Bids target a region ('global' or a country) and a time slot (calendar
     window + daily hours in the advertiser's timezone) — AdWords-style dayparting.
   • AdMaker Studio (/admaker-studio): advertisers self-serve on their NORMAL
     user login. Premium (Pro/Enterprise/Trial) plans or an Org "Advertiser"
     role unlock it (ACM feature `admaker_program`); free users see an upgrade
     CTA. Guard-rail: users can only promote options linked to THEIR OWN
     Solution-Store listings. Dashboard: impressions, clicks, CTR, spend, avg CPC.

2. EMBEDDABLE DECIDER APPS (AdTaker Program) — the AdSense of Decider Apps
   • Any Decider App embeds on third-party sites with ONE script tag carrying a
     tracker ID (DZ-PUB-XXXXXXXX). Impressions, clicks and attributed installs
     ("conversions", via ?ref= on clone) are measured per tracker; publishers
     earn a revenue share (default 68%).
   • Publisher identity — two rails, both live:
     (a) API Key (dzk_…) + Secret (dzs_…): minted at creation, secret shown
         EXACTLY ONCE (hash-only storage), admin-rotatable; self-serve stats/
         snippet API without any login.
     (b) Publisher Portal (/adtaker-portal): Organizations linked to a publisher
         see tracker, keys, snippet builder and 30-day earnings on their OrgLogin.
   • Admin console /admin/ad-programs (Monetization group): Bids · Publishers ·
     Cutoffs & Slots, with one-time-secret modals and key rotation.

3. FINDER AT SCALE (Option Bank) — best pick out of millions in seconds
   • Decider Apps can now search an "Option Bank" instead of only their embedded
     options. Runs become background jobs with a live progress bar (% + stage
     labels) and loader music (new 'finder' slot, admin-uploadable) — same UX
     contract as Deep-Import. Measured: 200,000 options scored in 2.65s after
     index pruning (~10s worst-case full scan); ≤60s SLA holds at scale.
   • The bank fills from 3 rails (all admin-triggered, idempotent):
     internal (template options + bridged Solution Store & ReviewNet data),
     external partner APIs (URL + field mapping), and Deep-Import/bulk rows.
     Admin → Decider Store → "Bank" action per template.
   • Store templates also gained a "Catalog" action (map to the CCM Scenario
     that drives cutoff/slot inheritance).

4. DASHBOARD & DOCS
   • Storefront hero (signed-in) links to AdMaker Studio + Publisher Portal.
   • Full KT refresh to v3.23.1: SRS (FRAME spec + scale architecture +
     benchmarks), API_REFERENCE (all new endpoint tables), SYSTEM_KT §10
     (block diagram + cheat-sheet), ADMIN_USER_GUIDE ("Ad Programs" how-tos),
     PRD appendix, ACM matrix, INDEX changelog.
   • Postman collection FULLY regenerated from live OpenAPI — 126 folders /
     1,316 requests / 100% endpoint coverage (was 58 folders / 1,021 requests
     with ~300 newer endpoints missing + a 419-request "Other" bucket). New
     one-command regen script keeps it in lock-step with the code forever.

════════════════════════════════════════════════════════════════════
TECHNICAL KT — for Devs maintaining the codebase
════════════════════════════════════════════════════════════════════

BACKEND — new modules
  core/ad_auction.py        AdMaker core. Pure fns: bid_is_live (status/budget/
                            region/calendar/daily-hours w/ IANA tz + overnight
                            wrap), score_bids (AdRank = bid_paise × QS(worth/100,
                            floor .05); one slot per option; GSP price =
                            next_AdRank ÷ own_QS + 1p clamped [1, own bid]).
                            Async: resolve_ad_config (precedence template.finder_
                            settings → catalog_nodes.finder_ad_config walked up
                            ≤8 ancestors, per-key nearest-wins → ai_wallet
                            globals), run_auction, record_impressions.
  core/finder_bank.py       Option-Bank pipeline (S0–S4). build_leaf_specs maps
                            cloned factors → bank vals keys via NEW
                            Factor.source_sub_id (name-norm fallback for legacy
                            clones). compile_prefilter → native Mongo clauses
                            (num ranges / txt regex; non-compilable ops become
                            residual in-stream Python checks; match_rule any/all
                            semantics preserved). run_bank_job: count → S1 prune
                            (adaptive funnel: relaxed_all / mandatory+optional)
                            → S2 motor cursor + projection + heapq Top-K (O(K)
                            mem, asyncio yield per 1K docs, progress per batch)
                            → S3 cutoff + auction (bid targets scored via
                            name_norm lookup even outside the heap) → persists
                            finder_jobs.result + decisions.finder_sponsored_ids.
                            bank_upsert: idempotent bulk upsert on (template_id,
                            name_norm), values normalized ONCE at ingest.
  routes/admaker.py         /admaker: bids CRUD (admin) + POST /track (CPC:
                            charges last GSP price, $inc clicks/spent, auto-
                            exhausted) + GET /resolve-config + Studio my/*
                            (_require_admaker: platform admin ∥ org_role in
                            {org_admin, advertiser} ∥ ACM check_feature_access
                            'admaker_program'; _owned_options: template
                            options[].linked_solution_id ∪ bank store_bridge
                            source_ref × solutions_store.created_by incl.
                            same-org users; my/dashboard aggregates CTR/avg CPC).
  routes/adtaker.py         /adtaker: publisher CRUD (mints tracker DZ-PUB-hex8
                            + dzk_/dzs_ keys, sha256 hash-only storage, secret
                            in create/rotate response ONLY), rotate-keys, stats
                            (shared _stats_payload: daily $substrBytes buckets,
                            CTR, earnings = conversions × bounty × share%),
                            self/* (X-Adtaker-Key/-Secret header auth), portal/me
                            (session user.org_id match), public widget.js
                            (script-src-derived root), embed HTML (frame-
                            ancestors *, server-side impression log, sendBeacon
                            click + deep-link ?ref=), track beacon. Exposes
                            log_conversion() consumed by decider_store.clone.
  routes/option_bank.py     /decider-store/{tid}/bank*: stats, sync-template,
                            ingest/solutions (bridged quantitative_factors keyed
                            by sub-factor id + ReviewNet baseline_profile),
                            ingest/partner (httpx fetch + items_path dig +
                            value_map), ingest/bulk (≤50K), DELETE ?source=.
  scripts/seed_finder_bank_synthetic.py  seeder (10K-batch insert_many) +
                            end-to-end benchmark harness (prints S1/S2 numbers).

BACKEND — modified
  routes/finder.py          run: sponsored auction after ranking (region =
                            body.region → user.country → 'global'), user-safe
                            sponsored cards (NO bid/price exposure), ad_config +
                            eligible_above_cutoff; config exposes bank_options;
                            NEW POST /decisions/{id}/finder/jobs (spec_hash
                            cache <10min, asyncio.create_task) + GET
                            /finder/jobs/{job_id} (owner-scoped).
  routes/decider_store.py   _clean_finder_settings += min_cutoff_pct/sponsored_n;
                            template catalog_node_id (create/update/_card);
                            clone: ?ref → adtaker.log_conversion; cloned factors
                            persist source_sub_id (real + implicit-single subs).
  routes/catalog.py + models/catalog_models.py  CatalogNodeUpdate +=
                            finder_min_cutoff_pct/finder_sponsored_n (-1 clears)
                            → node.finder_ad_config.
  models/decisions_models.py Factor.source_sub_id (survives PUT /decisions
                            factor saves — do NOT strip it).
  core/ai_wallet.py         DEFAULTS/validation += finder_min_cutoff_pct(60),
                            finder_sponsored_n(3), adtaker_default_share_pct(68),
                            adtaker_conversion_bounty_paise(500).
  data/acm_seed_data.py     module ad_programs / feature admaker_program
                            (ga_paid); ACM_SEED_VERSION=2026-07-19-01.
  routes/app_appearance.py  LOADER_SLOTS += 'finder'.
  core/db_indices.py        decider_option_bank ((template_id,name_norm) unique,
                            (template_id,source), vals.$** wildcard), finder_jobs,
                            admaker_bids/admaker_events, adtaker_publishers
                            (tracker_id & publisher_id unique), adtaker_events.
  server.py                 include admaker/adtaker/option_bank routers.

FRONTEND
  app/finder/[id].tsx       auto job-mode when bank_options>0: start job → poll
                            1.2s → progress bar + % + LoaderMusicChip('finder');
                            Sponsored Solutions amber card BELOW organic (AD
                            badge, "Promoted by", one-shot click beacon →
                            /admaker/track); Step-7 link hidden in bank mode.
  app/admaker-studio.tsx    NEW advertiser dashboard (metrics row, own-bid list,
                            create modal w/ eligible-option chips, ACM locked
                            state w/ upgrade CTA).
  app/adtaker-portal.tsx    NEW org publisher portal (tracker/api_key copy,
                            snippet builder, 30-day stats, org-gate empty state).
  app/admin/ad-programs.tsx NEW 3-tab console: Bids CRUD (option suggestions,
                            dayparting fields, GSP/spend counters) · Publishers
                            (api_key row, Rotate keys, ONE-TIME secret modal,
                            Linked-Org field, snippet+stats) · Cutoffs & Slots
                            (globals via ai-wallet config + per-node override
                            editor showing effective value + source).
  app/admin/decider-store.tsx  Catalog mapping modal (search CCM nodes, clear),
                            Bank modal (counts by source, sync/ingest/clear),
                            Sponsored globals in Finder & Landing settings.
  app/decider-store/[id].tsx  forwards ?ref into clone body (conversion attribution).
  app/decider-store/index.tsx hero pills → /admaker-studio + /adtaker-portal.
  app/admin/index.tsx       'ad-programs' tool registered (Monetization group).
  src/hooks/useLoaderMusic.ts LoaderSlot += 'finder'.

TESTS & DOCS
  backend/tests/test_iter193_admaker_adtaker.py   13 tests (GSP math, targeting,
      CCM inheritance + -1 clear, bid CRUD/validation, finder-run sponsored E2E
      + organic-immutability, CPC charge, widget/embed/track/conversion/stats).
  backend/tests/test_iter194_bank_studio_keys.py  14 tests (leaf mapping/prefilter/
      score rollup, ingest rails idempotency, async job <60s SLA + S1-prune
      assertion + cache + bank-sponsored auction, Studio ownership 403 + free-
      user ACM 403, key auth valid/invalid/rotate, org-portal gate).
  docs/ SRS v3.22+v3.23, API_REFERENCE v3.23.1, POSTMAN v3.23.1, SYSTEM_KT §10,
      ADMIN_USER_GUIDE "Ad Programs", PRD appendix, ACM, INDEX changelog.

POSTMAN / DOC TOOLING (kept in lock-step with code from now on)
  docs/Postman_Collection.json  FULL regeneration from live OpenAPI: 126 folders,
      1,316 requests, 0 uncategorized (was 58 folders / 1,021 requests — ~300
      endpoints added after 2026-06-12 were missing and 419 requests sat in a
      generic "Other" folder). AdTaker self/* requests auto-carry
      X-Adtaker-Key/-Secret headers; collection vars incl. adtakerKey/Secret,
      trackerId, templateId, decisionId, finderJobId.
  backend/scripts/generate_postman_collection.py  NEW one-command regenerator
      (prints counts, warns if any route falls into "Other").
  backend/core/openapi_helpers.py  build_postman_collection() extracted — single
      code path shared by the script and GET /admin/docs/postman-collection.
  backend/prompts/admin_docs_taxonomy.py  CATEGORY_MAP overhauled: ALL ~130 route
      prefixes named (admin sub-areas split out: Recon, Notification Engine,
      Import Analytics, PII Lookup, Quota, Payouts, Regression Runner, Loader
      Music); SUBPATH_CATEGORY_RULES for /decider-store/*/bank, /decisions/*/finder,
      /decisions/*/deep-import; channel tags for partner-facing surfaces
      (adtaker/embed/webhooks/public-pulse). Also improves /admin/docs/api-catalog.

OPS / MIGRATION NOTES
  • ACM auto-reseeds on restart (seed 2026-07-19-01). Mongo indexes auto-install
    via ensure_indexes at boot (wildcard index vals.$** included).
  • BMP (bmp-55-patterns) carries a 200K SYNTHETIC Option Bank from the
    benchmark — prod should NOT ingest it; if the seeder is ever run on prod,
    clear with Admin → Decider Store → Bank → Clear bank (source=synthetic).
  • No .env changes. No breaking API changes; finder/run response is additive.

DEPLOY
  EXPECT_BUILD=2026.07.19.004 ./deploy/sync.sh emergent-v3
