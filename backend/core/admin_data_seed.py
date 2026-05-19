"""
admin_data_seed.py — Production-ready starter content for every admin section.

Idempotent: every record is upserted by a stable key, so this can run any
number of times (boot, manual trigger via POST /api/admin/seed/run) without
duplicating data.

Seeds the following collections:
  • experts                  → 8 authorised expert profiles
  • decision_templates       → 12 curated templates across 10 life-areas
  • customer_segments        → 6 production Target-Group profiles + INR pricing
  • decision_modes           → 6 default modes (also handled by collaboration.py)
  • solutions_store          → 6 pending public solutions (for approvals UI)
  • social_learning_templates→ 6 pending + 4 authorised templates
  • incidents                → 4 historical security incidents
  • audit_trail              → 25 historical audit events (last 30 days)
  • review_net.factors       → 6 default reusable rating factors

The author of every record is the platform "system" user; nothing leaks PII.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.database import db
from models.collaboration_data import DEFAULT_MODES
from models.customer_segment_models import PREDEFINED_FACTORS
from models.tier_models import CHAKRA_TIERS

logger = logging.getLogger(__name__)

SEED_VERSION = "2026-06-01-01"
SYSTEM_USER_ID = "system_seed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXPERTS  (collection: experts — used by notifications.py /experts route)
# ─────────────────────────────────────────────────────────────────────────────
EXPERTS_SEED: List[Dict[str, Any]] = [
    {
        "id": "exp_seed_career_01",
        "name": "Dr. Anjali Mehra",
        "email": "anjali.mehra@experts.viewdezider.com",
        "specialization": "Career Coaching & Leadership",
        "bio": "15+ years coaching engineers, founders, and mid-career professionals on career pivots, leadership, and high-stakes negotiations. Ex-McKinsey; PCC-certified.",
        "is_active": True,
    },
    {
        "id": "exp_seed_finance_01",
        "name": "Rohan Iyer, CFP",
        "email": "rohan.iyer@experts.viewdezider.com",
        "specialization": "Personal Finance & Wealth Planning",
        "bio": "SEBI-registered Investment Advisor. Specialises in goal-based financial planning, tax-optimised investing, and retirement strategies for Indian residents and NRIs.",
        "is_active": True,
    },
    {
        "id": "exp_seed_health_01",
        "name": "Dr. Priya Raghav, MBBS, MD",
        "email": "priya.raghav@experts.viewdezider.com",
        "specialization": "Preventive Health & Lifestyle Medicine",
        "bio": "Integrative medicine practitioner. Helps users design sustainable nutrition, sleep, and movement plans. Member, Indian Society of Lifestyle Medicine.",
        "is_active": True,
    },
    {
        "id": "exp_seed_relationships_01",
        "name": "Vikram Joshi, M.Phil",
        "email": "vikram.joshi@experts.viewdezider.com",
        "specialization": "Couples & Family Therapy",
        "bio": "Clinical psychologist with 12 years guiding couples through major life decisions — marriage, parenting, separation. Uses Gottman Method & Crucial Conversations.",
        "is_active": True,
    },
    {
        "id": "exp_seed_legal_01",
        "name": "Adv. Shruti Banerjee",
        "email": "shruti.banerjee@experts.viewdezider.com",
        "specialization": "Startup Law, Compliance & DPDP",
        "bio": "Corporate counsel, Bar Council of Delhi. Specialises in incorporation, employment contracts, IP, and DPDPA 2023 compliance for SaaS/marketplaces.",
        "is_active": True,
    },
    {
        "id": "exp_seed_education_01",
        "name": "Karthik Subramaniam, M.Ed",
        "email": "karthik.subramaniam@experts.viewdezider.com",
        "specialization": "Career Counselling for Students",
        "bio": "Helps Class 9–12 students and parents choose streams, evaluate study-abroad options, and decode entrance exams. Certified by NCERT & ASCA.",
        "is_active": True,
    },
    {
        "id": "exp_seed_entrepreneurship_01",
        "name": "Meera Krishnan",
        "email": "meera.krishnan@experts.viewdezider.com",
        "specialization": "Startup Strategy & Fundraising",
        "bio": "Founder x2, exited once. Advises early-stage founders on GTM, unit economics, pitch decks, and Seed/Series-A fundraising in India and SEA.",
        "is_active": True,
    },
    {
        "id": "exp_seed_wellness_01",
        "name": "Acharya Ananth",
        "email": "acharya.ananth@experts.viewdezider.com",
        "specialization": "Mindfulness, Meditation & Stress",
        "bio": "Trained at Isha & Vipassana traditions. Guides professionals on stress management, focus, and meditative decision-making practices.",
        "is_active": True,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. DECISION TEMPLATES  (collection: decision_templates)
# ─────────────────────────────────────────────────────────────────────────────
def _factor(name: str, category: str = "primary", rating: int = 7, order: int = 0,
            unit: str = "", expected_value: str = "", data_type: str = "text",
            operator: str = "=") -> Dict[str, Any]:
    return {
        "id": f"fct_{uuid.uuid4().hex[:10]}",
        "name": name,
        "category": category,
        "rating": rating,
        "order": order,
        "unit": unit,
        "expected_value": expected_value,
        "data_type": data_type,
        "operator": operator,
        "gap_multiplier": 1.0,
        "parent_id": None,
        "weight": None,
    }


DECISION_TEMPLATES_SEED: List[Dict[str, Any]] = [
    {
        "id": "tpl_seed_job_offer",
        "name": "Job Offer Evaluation",
        "life_area": "Career",
        "decision_type": "Job Offer",
        "description": "Evaluate a new job offer across compensation, growth, culture, and lifestyle impact.",
        "factors": [
            _factor("Total Compensation (CTC)", "financial", 9, 1, "₹", "Above current + 30%", "number", ">="),
            _factor("Role & Responsibility Fit", "growth", 9, 2),
            _factor("Learning & Growth Potential", "growth", 8, 3),
            _factor("Manager & Team Quality", "people", 8, 4),
            _factor("Company Stability & Trajectory", "risk", 7, 5),
            _factor("Work-Life Balance", "lifestyle", 7, 6, "hrs/week", "<= 45", "number", "<="),
            _factor("Commute / Location", "lifestyle", 6, 7, "minutes", "<= 45", "number", "<="),
            _factor("Brand & Resume Value", "growth", 6, 8),
        ],
    },
    {
        "id": "tpl_seed_buy_vs_rent",
        "name": "Buy vs. Rent a Home",
        "life_area": "Finance",
        "decision_type": "Real Estate",
        "description": "Compare buying vs. renting using EMI burden, opportunity cost, and life-stage flexibility.",
        "factors": [
            _factor("Monthly Cash Outflow (EMI vs Rent)", "financial", 9, 1, "₹/month", "", "number", "<="),
            _factor("Down Payment Available", "financial", 9, 2, "₹", "", "number", ">="),
            _factor("Years You'll Stay in this City", "lifestyle", 8, 3, "years", ">= 7", "number", ">="),
            _factor("Opportunity Cost vs Equity Returns", "financial", 8, 4),
            _factor("Job / Income Stability", "risk", 7, 5),
            _factor("Maintenance & Property Tax Load", "financial", 6, 6),
            _factor("Emotional / Lifestyle Anchor", "lifestyle", 6, 7),
            _factor("Resale & Liquidity", "risk", 5, 8),
        ],
    },
    {
        "id": "tpl_seed_start_business",
        "name": "Start a Business / Side-hustle",
        "life_area": "Career",
        "decision_type": "Entrepreneurship",
        "description": "Decide whether to start a new venture today, considering capital, market fit, and personal runway.",
        "factors": [
            _factor("Personal Financial Runway", "financial", 9, 1, "months", ">= 12", "number", ">="),
            _factor("Market Demand Validation", "market", 9, 2),
            _factor("Co-founder / Team Readiness", "people", 8, 3),
            _factor("Unique Skill / Unfair Advantage", "growth", 8, 4),
            _factor("Family / Spousal Support", "people", 7, 5),
            _factor("Opportunity Cost vs Job", "financial", 7, 6),
            _factor("Health & Energy Levels", "lifestyle", 6, 7),
            _factor("Legal / Regulatory Complexity", "risk", 5, 8),
        ],
    },
    {
        "id": "tpl_seed_higher_studies",
        "name": "Higher Studies / MBA Abroad",
        "life_area": "Education",
        "decision_type": "Education",
        "description": "Evaluate going for higher studies / MBA / Master's abroad vs. domestic vs. continuing work.",
        "factors": [
            _factor("Tuition + Living Cost", "financial", 9, 1, "₹ lakhs", "", "number", "<="),
            _factor("Funding Source (Savings + Loan)", "financial", 9, 2),
            _factor("Career ROI Post-Programme", "growth", 9, 3),
            _factor("Programme & School Tier", "growth", 8, 4),
            _factor("Geography & Visa Pathway", "lifestyle", 7, 5),
            _factor("Years of Work Experience Fit", "growth", 7, 6, "years", ">= 3", "number", ">="),
            _factor("Family Impact / Relocation Cost", "lifestyle", 6, 7),
        ],
    },
    {
        "id": "tpl_seed_marriage_decision",
        "name": "Marriage / Long-term Partner",
        "life_area": "Relationships",
        "decision_type": "Personal",
        "description": "Structured evaluation for long-term commitment beyond infatuation.",
        "factors": [
            _factor("Shared Core Values", "values", 10, 1),
            _factor("Communication & Conflict Style", "people", 9, 2),
            _factor("Financial Habits Alignment", "financial", 9, 3),
            _factor("Family / Social Circle Compatibility", "people", 8, 4),
            _factor("Lifestyle & Daily Habits Match", "lifestyle", 8, 5),
            _factor("Life Goals — Career, Kids, Location", "growth", 9, 6),
            _factor("Physical & Emotional Attraction", "people", 7, 7),
        ],
    },
    {
        "id": "tpl_seed_health_lifestyle",
        "name": "Major Lifestyle / Health Change",
        "life_area": "Health",
        "decision_type": "Lifestyle",
        "description": "Decide whether to adopt a new fitness, diet, or therapy regime.",
        "factors": [
            _factor("Evidence Base & Credibility", "risk", 9, 1),
            _factor("Sustainability in Daily Routine", "lifestyle", 9, 2),
            _factor("Cost — Money & Time", "financial", 8, 3, "₹/month", "", "number", "<="),
            _factor("Health Risk / Side Effects", "risk", 8, 4),
            _factor("Family / Social Support", "people", 6, 5),
            _factor("Measurable Outcomes", "growth", 7, 6),
        ],
    },
    {
        "id": "tpl_seed_car_purchase",
        "name": "Car / Big-Ticket Purchase",
        "life_area": "Finance",
        "decision_type": "Major Purchase",
        "description": "Evaluate a car, bike, or big-ticket purchase across financial and lifestyle factors.",
        "factors": [
            _factor("Total On-Road Cost", "financial", 9, 1, "₹", "", "number", "<="),
            _factor("EMI vs Monthly Cash-flow", "financial", 9, 2),
            _factor("Annual Running Cost (Fuel/EV+Insurance+Service)", "financial", 7, 3),
            _factor("Resale Value 5-yrs", "financial", 6, 4),
            _factor("Usage Frequency / Need", "lifestyle", 9, 5),
            _factor("Safety Ratings (NCAP)", "risk", 8, 6),
            _factor("Family Fit (Seats / Boot)", "lifestyle", 7, 7),
        ],
    },
    {
        "id": "tpl_seed_relocate_city",
        "name": "Relocate to Another City / Country",
        "life_area": "Lifestyle",
        "decision_type": "Relocation",
        "description": "Evaluate moving to a new city/country for work, family, or quality of life.",
        "factors": [
            _factor("Income Increase After Cost-of-Living", "financial", 9, 1),
            _factor("Career Trajectory in New Location", "growth", 9, 2),
            _factor("Cost of Living Delta", "financial", 8, 3),
            _factor("Family / Spouse Adjustment", "people", 9, 4),
            _factor("Education / Healthcare for Kids", "lifestyle", 8, 5),
            _factor("Visa, Tax & Legal Complexity", "risk", 7, 6),
            _factor("Cultural / Social Fit", "lifestyle", 6, 7),
            _factor("Reversibility", "risk", 6, 8),
        ],
    },
    {
        "id": "tpl_seed_invest_decision",
        "name": "Investment Allocation Decision",
        "life_area": "Finance",
        "decision_type": "Investment",
        "description": "Choose between equity, debt, real-estate, gold, or alt-assets for a chunk of capital.",
        "factors": [
            _factor("Expected CAGR Net of Tax", "financial", 9, 1, "%", ">= 10", "number", ">="),
            _factor("Volatility Tolerance", "risk", 9, 2),
            _factor("Liquidity Need Within 3 yrs", "financial", 8, 3),
            _factor("Time-Horizon", "growth", 8, 4, "years", ">= 5", "number", ">="),
            _factor("Asset-Class Diversification", "risk", 7, 5),
            _factor("Tax Treatment", "financial", 6, 6),
        ],
    },
    {
        "id": "tpl_seed_quit_job",
        "name": "Quit Current Job",
        "life_area": "Career",
        "decision_type": "Career Transition",
        "description": "Evaluate whether to quit your current job — with or without a next role lined up.",
        "factors": [
            _factor("Financial Runway (Without New Job)", "financial", 10, 1, "months", ">= 6", "number", ">="),
            _factor("Burnout / Mental Health Risk", "risk", 9, 2),
            _factor("Growth Stagnation Severity", "growth", 9, 3),
            _factor("Toxicity of Current Environment", "people", 8, 4),
            _factor("Market Demand for Your Skills", "market", 8, 5),
            _factor("Family Buy-In", "people", 7, 6),
            _factor("Reputation / Reference Risk", "risk", 6, 7),
        ],
    },
    {
        "id": "tpl_seed_new_product",
        "name": "Launch a New Product / Feature",
        "life_area": "Business",
        "decision_type": "Product Strategy",
        "description": "Whether to invest your team's quarter in building a new product or feature line.",
        "factors": [
            _factor("Customer Demand Evidence", "market", 10, 1),
            _factor("Revenue / TAM Potential", "financial", 9, 2),
            _factor("Strategic Fit with Vision", "growth", 9, 3),
            _factor("Team Capacity & Skills", "people", 8, 4),
            _factor("Build Cost vs Build Time", "financial", 8, 5),
            _factor("Competitive Differentiation", "market", 7, 6),
            _factor("Technical Debt / Risk", "risk", 7, 7),
        ],
    },
    {
        "id": "tpl_seed_charitable_giving",
        "name": "Charitable Giving / Donation Allocation",
        "life_area": "Social",
        "decision_type": "Philanthropy",
        "description": "Decide where to allocate a chunk of charitable giving for maximum impact.",
        "factors": [
            _factor("Cause Alignment with Your Values", "values", 9, 1),
            _factor("Impact per Rupee (Cost-Effectiveness)", "growth", 9, 2),
            _factor("Organisation Transparency & Audits", "risk", 9, 3),
            _factor("Tax Deductibility (80G etc.)", "financial", 6, 4),
            _factor("Geographic / Community Closeness", "lifestyle", 5, 5),
            _factor("Personal Involvement vs Hands-Off", "lifestyle", 5, 6),
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. CUSTOMER SEGMENTS  (collection: customer_segments)
# ─────────────────────────────────────────────────────────────────────────────
def _seg_factors(values: Dict[str, str]) -> List[Dict[str, Any]]:
    """Pre-populate a segment with the predefined factor catalog + research values."""
    out = []
    for f in PREDEFINED_FACTORS:
        out.append({
            **f,
            "value": values.get(f["key"], ""),
            "is_custom": False,
        })
    return out


def _tier_pricing(prices: Dict[str, int]) -> List[Dict[str, Any]]:
    """Build per-tier INR pricing rows. prices keyed by tier_key."""
    rows = []
    for t in CHAKRA_TIERS:
        monthly = prices.get(t["key"], int(t.get("monthly_price_inr") or 0))
        rows.append({
            "tier_key": t["key"],
            "country_code": "IN",
            "currency": "INR",
            "monthly_price": float(monthly),
            "annual_price": float(monthly * 10),  # 2 months free on annual
            "enabled": True,
        })
    return rows


CUSTOMER_SEGMENTS_SEED: List[Dict[str, Any]] = [
    {
        "segment_id": "cs_seed_tech_founder",
        "name": "Tech Startup Founder",
        "description": "Early-to-growth stage tech founder running a venture-backed or bootstrapped SaaS/marketplace.",
        "chakra_tier_link": "solar_plexus",
        "factors": _seg_factors({
            "age_range": "28–42",
            "gender": "All",
            "income_range": "₹25L–₹2Cr per annum",
            "education": "Engineering / MBA",
            "occupation": "Founder / CEO / CTO",
            "location": "Bengaluru, Mumbai, Delhi-NCR, Hyderabad, Pune",
            "family_status": "Single or married, 0–2 dependants",
            "urban_rural": "Tier-1 metros",
            "values": "Growth, autonomy, impact, mastery",
            "interests": "Tech, AI, productivity, fitness, indie hacking",
            "lifestyle": "Fast-paced, digital-first, remote-friendly",
            "personality": "Driven, analytical, optimistic, high-risk-tolerance",
            "attitudes": "AI-first, evidence-driven, contrarian-friendly",
            "motivations": "Build a meaningful company, financial freedom, scale impact",
            "pain_points": "Time scarcity, decision overload, fundraising stress, burnout",
            "buying_behaviour": "Researches deeply, peer-driven, subscription-friendly, trial-to-paid",
            "brand_loyalty": "Moderate — switches if value drops",
            "decision_drivers": "ROI, ease-of-use, social proof, integrations",
            "tech_savviness": "Very high",
            "company_size": "1–50 employees",
            "industry": "SaaS / FinTech / Marketplaces",
            "role": "Founder / CEO / CTO",
            "revenue_band": "₹0–₹50Cr ARR",
        }),
        "tier_pricings": _tier_pricing({}),
    },
    {
        "segment_id": "cs_seed_working_parent",
        "name": "Working Parent (Mid-Career)",
        "description": "Mid-career salaried professional juggling work, kids, parents, and personal goals.",
        "chakra_tier_link": "sacral",
        "factors": _seg_factors({
            "age_range": "32–48",
            "gender": "All",
            "income_range": "₹15L–₹60L per annum",
            "education": "Graduate / Post-graduate",
            "occupation": "Manager / Senior Individual Contributor",
            "location": "Tier-1 & Tier-2 Indian cities",
            "family_status": "Married, 1–2 children, possibly elderly parents",
            "urban_rural": "Urban",
            "values": "Family, stability, growth, balance",
            "interests": "Parenting, finance, fitness, travel, OTT",
            "lifestyle": "Time-pressed, multi-tasking, weekend warriors",
            "personality": "Conscientious, pragmatic, planner",
            "attitudes": "Risk-averse for family decisions, open to digital tools",
            "motivations": "Kids' future, retirement security, work-life balance",
            "pain_points": "Time scarcity, decision fatigue, juggling priorities",
            "buying_behaviour": "Comparison shoppers, peer recommendations, trust reviews",
            "brand_loyalty": "High when trust is built",
            "decision_drivers": "Trust, safety, ROI, simplicity",
            "tech_savviness": "Moderate-to-high",
        }),
        "tier_pricings": _tier_pricing({}),
    },
    {
        "segment_id": "cs_seed_solopreneur",
        "name": "Solopreneur / Freelance Consultant",
        "description": "Independent professional running a one-person business — coach, designer, consultant, content creator.",
        "chakra_tier_link": "sacral",
        "factors": _seg_factors({
            "age_range": "26–55",
            "gender": "All",
            "income_range": "₹8L–₹40L per annum",
            "education": "Graduate / Specialised certification",
            "occupation": "Consultant / Coach / Designer / Creator",
            "location": "Tier-1, Tier-2, also Tier-3",
            "family_status": "Varied",
            "urban_rural": "Urban-leaning",
            "values": "Autonomy, mastery, freedom, purpose",
            "interests": "Personal branding, productivity, mindfulness",
            "lifestyle": "Flexible, remote, calendar-driven",
            "personality": "Self-directed, creative, resilient",
            "motivations": "Independence, calmer income, doing what they love",
            "pain_points": "Inconsistent income, no team, isolation, decision-loneliness",
            "buying_behaviour": "Tries free first, community-driven, sensitive to monthly cost",
            "brand_loyalty": "Moderate",
            "decision_drivers": "Personal ROI, ease, community, support",
            "tech_savviness": "Moderate",
        }),
        "tier_pricings": _tier_pricing({}),
    },
    {
        "segment_id": "cs_seed_student_aspirant",
        "name": "Student / Career Aspirant (18–24)",
        "description": "College student or recent graduate planning education, first job, or higher studies.",
        "chakra_tier_link": "root",
        "factors": _seg_factors({
            "age_range": "18–24",
            "gender": "All",
            "income_range": "Parent-sponsored / Stipend ₹0–₹6L",
            "education": "In college / Recent graduate",
            "occupation": "Student / Intern / Junior Analyst",
            "location": "All India + abroad-aspirants",
            "family_status": "Dependent",
            "urban_rural": "Mixed",
            "values": "Ambition, identity, peer-validation, exploration",
            "interests": "Social media, gaming, sports, OTT, peer groups",
            "lifestyle": "High social, study-heavy",
            "personality": "Curious, identity-forming, ambitious-yet-unsure",
            "motivations": "Land good college / first job, prove themselves",
            "pain_points": "Information overload, parental pressure, FOMO, unclear path",
            "buying_behaviour": "Mobile-first, free-tier-heavy, peer-influenced, parent-paid",
            "brand_loyalty": "Low",
            "decision_drivers": "Social proof, ease, mobile UX, free tier",
            "tech_savviness": "High (mobile)",
        }),
        "tier_pricings": _tier_pricing({"root": 0, "sacral": 199}),
    },
    {
        "segment_id": "cs_seed_retiree",
        "name": "Pre-Retiree / Retiree (50+)",
        "description": "Late-career or retired Indian planning second-innings — investments, health, legacy.",
        "chakra_tier_link": "heart",
        "factors": _seg_factors({
            "age_range": "50–72",
            "gender": "All",
            "income_range": "₹10L–₹50L (pension + investments)",
            "education": "Graduate / Post-graduate",
            "occupation": "Senior professional / Retired",
            "location": "Tier-1 & Tier-2",
            "family_status": "Married, adult children, possibly grandchildren",
            "urban_rural": "Urban",
            "values": "Security, family, legacy, health, dignity",
            "interests": "Health, travel, spirituality, grandchildren, hobbies",
            "lifestyle": "Slower-paced, planned, routine-driven",
            "personality": "Reflective, cautious, generous",
            "motivations": "Financial security, health longevity, legacy planning",
            "pain_points": "Health uncertainty, technology gap, fear of dependency",
            "buying_behaviour": "Trust + reputation driven, prefers human support",
            "brand_loyalty": "Very high",
            "decision_drivers": "Trust, safety, simplicity, human assistance",
            "tech_savviness": "Moderate",
        }),
        "tier_pricings": _tier_pricing({}),
    },
    {
        "segment_id": "cs_seed_corp_decision_maker",
        "name": "Corporate Decision-Maker (Director+)",
        "description": "Director / VP-level decision-maker at mid-to-large enterprises driving strategy and team outcomes.",
        "chakra_tier_link": "throat",
        "factors": _seg_factors({
            "age_range": "35–55",
            "gender": "All",
            "income_range": "₹50L–₹5Cr per annum",
            "education": "MBA / Senior Postgrad",
            "occupation": "Director / VP / SVP / C-Suite",
            "location": "Tier-1 metros (India + global)",
            "family_status": "Married, 1–3 dependants",
            "urban_rural": "Urban",
            "values": "Impact, execution, integrity, growth",
            "interests": "Leadership, golf, travel, books, AI",
            "lifestyle": "Calendar-driven, jet-set, high-pressure",
            "personality": "Decisive, strategic, outcome-oriented",
            "motivations": "Career trajectory, team success, financial growth",
            "pain_points": "Decision quality at scale, talent retention, board pressure",
            "buying_behaviour": "Procurement-led, ROI memos, longer sales cycle, premium-friendly",
            "brand_loyalty": "Moderate",
            "decision_drivers": "ROI, credibility, peer-CXOs using it, audit-ability",
            "tech_savviness": "Moderate-to-high",
            "company_size": "200–10,000 employees",
            "industry": "BFSI / Manufacturing / Pharma / Tech / Retail",
            "role": "Director / VP / SVP / C-Suite",
            "revenue_band": "₹100Cr–₹10,000Cr",
        }),
        "tier_pricings": _tier_pricing({}),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 4. SOLUTIONS STORE — pending public solutions (Admin → Pending Approvals)
# ─────────────────────────────────────────────────────────────────────────────
SOLUTIONS_PENDING_SEED: List[Dict[str, Any]] = [
    {
        "solution_id": "sol_seed_pending_01",
        "type": "SERVICE",
        "name": "Notion Productivity Coaching (4-week)",
        "description": "Personalised 4-week 1:1 coaching to set up Notion for personal OKRs, weekly reviews, and second-brain workflows. Includes 4 calls + templates.",
        "provider": "Athena Productivity Studio",
        "country": "India", "state": "Karnataka", "city": "Bengaluru",
        "created_by_name": "Athena Studio",
        "quantitative_factors": [
            {"factor_name": "Duration", "value": "4", "unit": "weeks"},
            {"factor_name": "Price", "value": "12,000", "unit": "INR"},
        ],
    },
    {
        "solution_id": "sol_seed_pending_02",
        "type": "PRODUCT",
        "name": "Cure.fit ELEVATE Membership (Annual)",
        "description": "Bundle of gym + group classes + sleep + meditation. Suited for working professionals who want a single subscription for total wellness.",
        "provider": "Cult.fit",
        "country": "India", "state": "Karnataka", "city": "Bengaluru",
        "created_by_name": "Wellness Reviewer",
        "quantitative_factors": [
            {"factor_name": "Annual Cost", "value": "32,000", "unit": "INR"},
            {"factor_name": "Centres", "value": "300+", "unit": "across India"},
        ],
    },
    {
        "solution_id": "sol_seed_pending_03",
        "type": "EVENT",
        "name": "TiE Global Summit 2026 — Bengaluru",
        "description": "3-day in-person founder summit featuring 200+ investors, 50+ talks, and curated networking. Most relevant for Series-A/B founders.",
        "provider": "TiE Bangalore",
        "country": "India", "state": "Karnataka", "city": "Bengaluru",
        "created_by_name": "Community Curator",
        "quantitative_factors": [
            {"factor_name": "Ticket", "value": "25,000", "unit": "INR"},
            {"factor_name": "Days", "value": "3", "unit": "days"},
        ],
    },
    {
        "solution_id": "sol_seed_pending_04",
        "type": "PROJECT",
        "name": "Open-Source Personal Finance Tracker",
        "description": "Self-hosted GnuCash + Beancount setup with India tax categorisation. Bootstrap your own personal-finance data store without SaaS dependency.",
        "provider": "Community OSS",
        "country": "India", "state": "All India", "city": "Online",
        "created_by_name": "Indie Finance Hacker",
        "quantitative_factors": [
            {"factor_name": "Setup Time", "value": "4", "unit": "hours"},
            {"factor_name": "Cost", "value": "0", "unit": "INR"},
        ],
    },
    {
        "solution_id": "sol_seed_pending_05",
        "type": "PERSON_CONTACT",
        "name": "Dr. Karthik Iyer — Sports Physiotherapist",
        "description": "Specialist for runners and CrossFit athletes. Strong reviews for ACL recovery and shoulder mobility programmes.",
        "provider": "Sports Health Co.",
        "country": "India", "state": "Tamil Nadu", "city": "Chennai",
        "created_by_name": "Patient Reviewer",
        "quantitative_factors": [
            {"factor_name": "Consultation", "value": "1,500", "unit": "INR / 45-min"},
            {"factor_name": "Years of Practice", "value": "12", "unit": "years"},
        ],
    },
    {
        "solution_id": "sol_seed_pending_06",
        "type": "SERVICE",
        "name": "Zerodha Varsity Premium Mentorship",
        "description": "Live 8-week cohort with Zerodha Varsity mentors covering technical analysis, fundamentals, and portfolio construction.",
        "provider": "Zerodha Varsity",
        "country": "India", "state": "Karnataka", "city": "Bengaluru",
        "created_by_name": "Retail Investor",
        "quantitative_factors": [
            {"factor_name": "Cohort Fee", "value": "9,999", "unit": "INR"},
            {"factor_name": "Cohort Size", "value": "60", "unit": "learners"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 5. SOCIAL LEARNING TEMPLATES  (pending + authorized)
# ─────────────────────────────────────────────────────────────────────────────
SOCIAL_LEARNING_SEED: List[Dict[str, Any]] = [
    # Submitted (pending admin review) — show on /admin/social-learning-admin
    {
        "id": "sl_seed_submitted_01",
        "title": "Layoffs in Indian IT — How to Decision-Proof Your Career",
        "category": "problem",
        "detected_language": "english",
        "english_summary": "Indian IT majors announced 5,000+ layoffs in Q1 2026. Useful lessons for mid-career engineers on diversifying income, certifications, and personal brand.",
        "life_areas": ["career_profession", "finance_wealth"],
        "primary_life_area": "career_profession",
        "severity_score": 7,
        "factors": [{"name": "Job Stability", "category": "risk"}, {"name": "Skill Currency", "category": "growth"}],
        "concerns": [{"name": "Salary Loss"}, {"name": "Re-employment Time"}],
        "status": "submitted",
        "tier": 1,
    },
    {
        "id": "sl_seed_submitted_02",
        "title": "Bengaluru Water Crisis — Decision Framework for Apartment Buyers",
        "category": "need",
        "detected_language": "english",
        "english_summary": "Acute water shortage in Bengaluru should be a factor in any apartment-buying decision. Checklist: borewell yield, tanker access, society reserves, BWSSB pipeline.",
        "life_areas": ["finance_wealth", "environment_sustainability"],
        "primary_life_area": "finance_wealth",
        "severity_score": 6,
        "factors": [{"name": "Water Source"}, {"name": "Society Reserves"}],
        "concerns": [{"name": "Tanker Dependency"}],
        "status": "submitted",
        "tier": 1,
    },
    {
        "id": "sl_seed_submitted_03",
        "title": "GST 2.0 Rates — Implications for Solopreneurs",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "GST simplification reduces compliance overhead. Solopreneurs earning < ₹40L can stay GST-unregistered legally.",
        "life_areas": ["finance_wealth", "legal_governance"],
        "primary_life_area": "legal_governance",
        "severity_score": 4,
        "factors": [{"name": "Threshold"}, {"name": "Compliance"}],
        "concerns": [{"name": "Audit Risk"}],
        "status": "submitted",
        "tier": 1,
    },
    {
        "id": "sl_seed_submitted_04",
        "title": "Burnout in 30s — Early Warning Signals & Pre-Emption",
        "category": "problem",
        "detected_language": "english",
        "english_summary": "Pattern-recognition checklist of 12 early signals (sleep, irritability, headache, weekend dread). Pre-emptive solutions: micro-sabbaticals, therapy, manager talk.",
        "life_areas": ["health_wellness", "career_profession"],
        "primary_life_area": "health_wellness",
        "severity_score": 8,
        "factors": [{"name": "Sleep Quality"}, {"name": "Energy Levels"}],
        "concerns": [{"name": "Mental Health Decline"}],
        "status": "submitted",
        "tier": 1,
    },
    {
        "id": "sl_seed_submitted_05",
        "title": "Bharat Mobility Show 2026 — EV Buying Heuristics",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "EV launch wave at the Auto Expo. Heuristics: km/day-of-use, charging access, battery warranty, resale curve at year-5.",
        "life_areas": ["finance_wealth", "technology_innovation"],
        "primary_life_area": "finance_wealth",
        "severity_score": 5,
        "factors": [{"name": "Range"}, {"name": "Charging Access"}],
        "concerns": [{"name": "Resale Value"}],
        "status": "submitted",
        "tier": 1,
    },
    {
        "id": "sl_seed_submitted_06",
        "title": "AI Replacing Mid-Level White-Collar Roles in 2026",
        "category": "problem",
        "detected_language": "english",
        "english_summary": "Customer support, paralegal, junior analyst roles seeing 30-40% reduction. Mid-career professionals need to add AI-leverage skills.",
        "life_areas": ["career_profession", "education_learning"],
        "primary_life_area": "career_profession",
        "severity_score": 9,
        "factors": [{"name": "Role at Risk"}, {"name": "AI-Augment Skills"}],
        "concerns": [{"name": "Career Stagnation"}],
        "status": "submitted",
        "tier": 1,
    },
    # Authorized (tier 2) — show in user-facing social-learning library
    {
        "id": "sl_seed_authorized_01",
        "title": "Marriage in late-30s — Decision factors validated by data",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "Decision framework synthesised from 200+ couples on values alignment, financial parity, and conflict-resolution maturity.",
        "life_areas": ["relationships_family"],
        "primary_life_area": "relationships_family",
        "severity_score": 5,
        "factors": [{"name": "Values Alignment"}, {"name": "Conflict Style"}],
        "concerns": [{"name": "Mismatched Goals"}],
        "status": "authorized",
        "tier": 2,
    },
    {
        "id": "sl_seed_authorized_02",
        "title": "SIP vs Lump-sum — When data says lump-sum wins",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "30-year Nifty backtest: lump-sum beats SIP 67% of the time on absolute returns. SIP still better behaviourally for most.",
        "life_areas": ["finance_wealth"],
        "primary_life_area": "finance_wealth",
        "severity_score": 4,
        "factors": [{"name": "Investment Horizon"}, {"name": "Behavioural Discipline"}],
        "concerns": [{"name": "Volatility Tolerance"}],
        "status": "authorized",
        "tier": 2,
    },
    {
        "id": "sl_seed_authorized_03",
        "title": "Remote-first vs Hybrid — Engineering team productivity findings",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "Survey of 50 Indian engineering teams: hybrid (2-3 days office) wins on collaboration but remote-first wins on retention.",
        "life_areas": ["career_profession"],
        "primary_life_area": "career_profession",
        "severity_score": 4,
        "factors": [{"name": "Collaboration"}, {"name": "Retention"}],
        "concerns": [{"name": "Productivity Drop"}],
        "status": "authorized",
        "tier": 2,
    },
    {
        "id": "sl_seed_authorized_04",
        "title": "Caring for ageing parents — Decision matrix",
        "category": "solution",
        "detected_language": "english",
        "english_summary": "Move-in vs assisted-living vs home-care: 6-factor matrix covering medical needs, finances, sibling load, and parent preferences.",
        "life_areas": ["relationships_family", "health_wellness"],
        "primary_life_area": "relationships_family",
        "severity_score": 7,
        "factors": [{"name": "Medical Need Level"}, {"name": "Financial Capacity"}],
        "concerns": [{"name": "Sibling Conflict"}],
        "status": "authorized",
        "tier": 2,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 6. INCIDENTS  (4 historical security incidents)
# ─────────────────────────────────────────────────────────────────────────────
def _build_incidents() -> List[Dict[str, Any]]:
    base = _now()
    rows = [
        {
            "id": "INC-SEED-001",
            "title": "Suspicious admin login attempts from new geography",
            "incident_type": "unauthorized_access",
            "severity": "medium",
            "description": "Multiple failed admin login attempts (12 in 4 minutes) from an IP in a geography we don't typically serve. Account lockout triggered. Investigated user account; no compromise detected. IP added to deny-list.",
            "affected_systems": ["Admin Portal", "Auth Service"],
            "affected_user_count": 0,
            "kyc_data_involved": False,
            "initial_actions_taken": "Account locked, IP banned at NGINX layer, JWT rotation forced.",
            "status": "resolved",
            "created_at_offset_days": 35,
            "certin_notified": False,
            "resolution_notes": "Brute-force attempt by automated bot. Rate-limiter + lockout worked as designed.",
        },
        {
            "id": "INC-SEED-002",
            "title": "Outdated dependency CVE-2025-3198 (httpx pre-1.0)",
            "incident_type": "api_compromise",
            "severity": "low",
            "description": "Vulnerability scanner flagged httpx==0.25.x as having a request smuggling CVE. No exploit evidence; pre-emptive patch.",
            "affected_systems": ["Backend Container"],
            "affected_user_count": 0,
            "kyc_data_involved": False,
            "initial_actions_taken": "Upgraded httpx to 0.28.x. Re-built container. Smoke tests passed.",
            "status": "resolved",
            "created_at_offset_days": 21,
            "certin_notified": False,
            "resolution_notes": "Pre-emptive dependency upgrade. No customer impact.",
        },
        {
            "id": "INC-SEED-003",
            "title": "DigiLocker callback rate-limit spike — possible scraping",
            "incident_type": "ddos_attack",
            "severity": "medium",
            "description": "DigiLocker callback endpoint received 850 rpm sustained for 6 minutes from rotating IPs in same /24 block. Rate-limiter contained the spike. Investigating intent.",
            "affected_systems": ["Auth Service", "DigiLocker Adapter"],
            "affected_user_count": 0,
            "kyc_data_involved": True,
            "initial_actions_taken": "Stricter rate-limit on /api/digilocker/callback (5/min/IP). Audit-trail review showed zero successful KYC reads.",
            "status": "contained",
            "created_at_offset_days": 9,
            "certin_notified": False,
        },
        {
            "id": "INC-SEED-004",
            "title": "Accidental disclosure of test admin email in seed dump",
            "incident_type": "credential_leak",
            "severity": "low",
            "description": "A test admin email was visible in a GitHub repo file as part of a seed README. No password or token exposed. Repo is private; access limited to founders.",
            "affected_systems": ["GitHub Repo"],
            "affected_user_count": 1,
            "kyc_data_involved": False,
            "initial_actions_taken": "Email scrubbed via BFG repo-cleaner. Force-push completed. README rewritten with generic samples.",
            "status": "resolved",
            "created_at_offset_days": 3,
            "certin_notified": False,
            "resolution_notes": "Low-severity hygiene issue. No real PII exposed.",
        },
    ]
    out = []
    for r in rows:
        offset = r.pop("created_at_offset_days")
        ts = base - timedelta(days=offset)
        doc = {
            **r,
            "created_by": SYSTEM_USER_ID,
            "created_by_name": "System (Seed)",
            "detected_at": _iso(ts),
            "created_at": _iso(ts),
            "updated_at": _iso(ts + timedelta(hours=2)),
            "certin_notified_at": None,
            "users_notified": False,
            "users_notified_at": None,
            "users_notified_count": 0,
            "resolved_at": _iso(ts + timedelta(hours=6)) if r["status"] == "resolved" else None,
            "root_cause": "",
            "remediation_steps": "",
            "resolution_notes": r.get("resolution_notes", ""),
            "timeline": [
                {"timestamp": _iso(ts), "status": "detected", "note": "Incident detected and logged", "by": SYSTEM_USER_ID},
                {"timestamp": _iso(ts + timedelta(minutes=30)), "status": "investigating", "note": "Incident under investigation", "by": SYSTEM_USER_ID},
            ] + ([{
                "timestamp": _iso(ts + timedelta(hours=6)),
                "status": "resolved",
                "note": r.get("resolution_notes", "Resolved."),
                "by": SYSTEM_USER_ID,
            }] if r["status"] == "resolved" else []),
            "notification_log": [],
        }
        out.append(doc)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 7. AUDIT TRAIL  (25 historical events spread across last 30 days)
# ─────────────────────────────────────────────────────────────────────────────
def _build_audit_trail() -> List[Dict[str, Any]]:
    base = _now()
    actions = [
        ("digilocker_status_check", "digilocker", False, []),
        ("biometric_verified", "biometric", True, ["biometric_template"]),
        ("totp_verified", "totp", True, ["totp_secret"]),
        ("incident_created", "incident", False, []),
        ("audit_purge", "audit", False, []),
        ("digilocker_initiate", "digilocker", True, ["aadhaar_session"]),
        ("biometric_verify_failed", "biometric", True, []),
        ("certin_notified", "incident", False, []),
        ("users_notified", "incident", False, []),
        ("totp_verify_failed", "totp", True, []),
    ]
    out: List[Dict[str, Any]] = []
    for i in range(25):
        a, e, sens, fields = actions[i % len(actions)]
        ts = base - timedelta(days=29 - i, hours=(i * 7) % 24, minutes=(i * 13) % 60)
        out.append({
            "id": f"AUD-SEED-{i:04d}",
            "action": a,
            "entity_type": e,
            "entity_id": f"{e}_demo_{i:03d}",
            "user_id": SYSTEM_USER_ID,
            "details": f"Seed event #{i} — {a.replace('_', ' ')} on demo entity.",
            "ip_address": f"10.0.{(i * 7) % 256}.{(i * 13) % 256}",
            "sensitive_data_accessed": sens,
            "data_fields_accessed": fields,
            "timestamp": _iso(ts),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 8. REVIEW-NET FACTORS  (6 reusable rating factors)
# ─────────────────────────────────────────────────────────────────────────────
REVIEW_NET_FACTORS_SEED: List[Dict[str, Any]] = [
    {
        "id": "rnf_seed_value_for_money",
        "name": "Value for Money",
        "description": "Does the price match the outcome delivered?",
        "applies_to": ["PRODUCT", "SERVICE", "EVENT", "PROJECT"],
        "data_type": "rating",
        "min_value": 1, "max_value": 5,
        "is_required": True,
        "order": 1,
    },
    {
        "id": "rnf_seed_quality",
        "name": "Quality",
        "description": "Overall craftsmanship / delivery quality.",
        "applies_to": ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"],
        "data_type": "rating",
        "min_value": 1, "max_value": 5,
        "is_required": True,
        "order": 2,
    },
    {
        "id": "rnf_seed_responsiveness",
        "name": "Responsiveness",
        "description": "Speed of communication and support.",
        "applies_to": ["SERVICE", "PERSON_CONTACT"],
        "data_type": "rating",
        "min_value": 1, "max_value": 5,
        "is_required": False,
        "order": 3,
    },
    {
        "id": "rnf_seed_outcome",
        "name": "Outcome / Result Delivered",
        "description": "Did it actually solve the problem you bought it for?",
        "applies_to": ["PRODUCT", "SERVICE", "EVENT", "PROJECT"],
        "data_type": "rating",
        "min_value": 1, "max_value": 5,
        "is_required": True,
        "order": 4,
    },
    {
        "id": "rnf_seed_ease_of_use",
        "name": "Ease of Use / Adoption",
        "description": "How easy was it to start and continue using?",
        "applies_to": ["PRODUCT", "SERVICE"],
        "data_type": "rating",
        "min_value": 1, "max_value": 5,
        "is_required": False,
        "order": 5,
    },
    {
        "id": "rnf_seed_recommend",
        "name": "Would Recommend",
        "description": "Would you recommend this to a friend?",
        "applies_to": ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"],
        "data_type": "boolean",
        "is_required": True,
        "order": 6,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────────────────────────────────────
async def seed_admin_data(force: bool = False) -> Dict[str, Any]:
    """Idempotently seed all admin sections with production-grade starter data.

    Records are upserted by their stable id/key. Run any number of times.
    Returns a summary dict suitable for API responses or logs.
    """
    summary: Dict[str, int] = {}
    now = _now()

    # ── 1) Experts (collection used by notif route uses field `id`) ──────────
    # Note: collection also has a unique index on `expert_id` from expert_net.py;
    # set expert_id = id to avoid null-collision under that unique index.
    n = 0
    for e in EXPERTS_SEED:
        doc = {**e, "expert_id": e["id"], "created_by": SYSTEM_USER_ID, "created_at": now}
        res = await db.experts.update_one({"id": e["id"]}, {"$setOnInsert": doc}, upsert=True)
        if res.upserted_id or res.modified_count:
            n += 1
    summary["experts"] = n

    # ── 2) Decision Templates ────────────────────────────────────────────────
    n = 0
    for t in DECISION_TEMPLATES_SEED:
        doc = {
            **t,
            "is_approved": True,
            "is_official": True,
            "created_by": SYSTEM_USER_ID,
            "submitted_by": SYSTEM_USER_ID,
            "submitted_by_name": "View Dezider Editorial",
            "created_at": now,
        }
        res = await db.decision_templates.update_one(
            {"id": t["id"]}, {"$setOnInsert": doc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["decision_templates"] = n

    # ── 3) Customer Segments ─────────────────────────────────────────────────
    n = 0
    for s in CUSTOMER_SEGMENTS_SEED:
        doc = {
            **s,
            "market_research_module_ids": [],
            "created_at": now,
            "updated_at": now,
            "created_by": SYSTEM_USER_ID,
        }
        res = await db.customer_segments.update_one(
            {"segment_id": s["segment_id"]}, {"$setOnInsert": doc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["customer_segments"] = n

    # ── 4) Decision Modes (6 defaults) ───────────────────────────────────────
    n = 0
    for m in DEFAULT_MODES:
        await db.decision_modes.update_one({"id": m["id"]}, {"$set": m}, upsert=True)
        n += 1
    summary["decision_modes"] = n

    # ── 5) Pending solutions (for Pending Approvals) ─────────────────────────
    n = 0
    for s in SOLUTIONS_PENDING_SEED:
        doc = {
            **s,
            "approval_status": "pending",
            "status": "active",
            "is_authorized": False,
            "created_by": SYSTEM_USER_ID,
            "created_at": _iso(now - timedelta(hours=24)),
            "updated_at": _iso(now - timedelta(hours=24)),
        }
        res = await db.solutions_store.update_one(
            {"solution_id": s["solution_id"]}, {"$setOnInsert": doc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["pending_solutions"] = n

    # ── 6) Social Learning Templates ─────────────────────────────────────────
    n = 0
    for t in SOCIAL_LEARNING_SEED:
        doc = {
            **t,
            "created_by": SYSTEM_USER_ID,
            "created_at": _iso(now - timedelta(days=2)),
            "updated_at": _iso(now - timedelta(days=2)),
            "geo_level": "national",
            "region_hierarchy": {"level": "national", "country": "India"},
            "life_area_mapping": {"primary_life_area_id": t.get("primary_life_area", "")},
            "scenario_mapping": {},
            "learnings_mydezider": {"factors": t.get("factors", []), "summary": ""},
            "learnings_solution_finder": {"risks": [], "summary": ""},
            "root_causes": [],
            "lessons_learned": [],
            "tags": [],
            "admin_notes": "",
        }
        if t.get("status") == "authorized":
            doc["authorized_at"] = _iso(now - timedelta(days=1))
            doc["authorized_by"] = SYSTEM_USER_ID
        res = await db.social_learning_templates.update_one(
            {"id": t["id"]}, {"$setOnInsert": doc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["social_learning_templates"] = n

    # ── 7) Incidents ─────────────────────────────────────────────────────────
    n = 0
    for inc in _build_incidents():
        res = await db.incidents.update_one(
            {"id": inc["id"]}, {"$setOnInsert": inc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["incidents"] = n

    # ── 8) Audit Trail ───────────────────────────────────────────────────────
    n = 0
    for evt in _build_audit_trail():
        res = await db.audit_trail.update_one(
            {"id": evt["id"]}, {"$setOnInsert": evt}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["audit_trail_events"] = n

    # ── 9) ReviewNet rating factors ──────────────────────────────────────────
    n = 0
    for f in REVIEW_NET_FACTORS_SEED:
        doc = {
            **f,
            "is_default": True,
            "created_by": SYSTEM_USER_ID,
            "created_at": _iso(now),
        }
        res = await db.review_net_factors.update_one(
            {"id": f["id"]}, {"$setOnInsert": doc}, upsert=True,
        )
        if res.upserted_id or res.modified_count:
            n += 1
    summary["review_net_factors"] = n

    # ── Persist seed marker ──────────────────────────────────────────────────
    await db.app_config.update_one(
        {"key": "admin_data_seed"},
        {"$set": {
            "key": "admin_data_seed",
            "value": {"seed_version": SEED_VERSION, "last_run": _iso(now), "summary": summary},
        }},
        upsert=True,
    )

    logger.info(f"Admin data seed complete (version {SEED_VERSION}): {summary}")
    return {"ok": True, "seed_version": SEED_VERSION, "summary": summary}


async def ensure_admin_data_seeded_on_boot() -> None:
    """Boot-time hook. Runs the seed unless the current version is already
    persisted (guards against repeated upserts on every restart)."""
    try:
        marker = await db.app_config.find_one({"key": "admin_data_seed"}, {"_id": 0})
        if marker and marker.get("value", {}).get("seed_version") == SEED_VERSION:
            logger.info(f"Admin data seed v{SEED_VERSION} already present — skipping.")
            return
        await seed_admin_data()
    except Exception as e:
        logger.error(f"Admin data seed at boot failed: {e}", exc_info=True)
