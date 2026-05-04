"""
Starter templates for Solution Matrix — one per OrgType.

Exposed to the frontend via GET /api/tools/solution-matrix/templates.
Users can preview a template, then seed their own entry with it.

Each template is a *partial* payload matching the shape that
`create_solution_matrix` expects. It omits user/org identifiers and
timestamps; those are injected server-side at copy time.
"""
from typing import Dict, List


def _cell(time="", energy="", people="", finance="", infrastructure="",
          summary="", knowledge_skills="", influences=None) -> Dict:
    return {
        "summary": summary,
        "knowledge_skills": knowledge_skills,
        "capacity": energy,          # legacy mirror
        "energy": energy,            # canonical TEPFI-E
        "time": time,
        "people": people,
        "finance": finance,
        "infrastructure": infrastructure,
        "influences": influences or {},
    }


def _empty_slot() -> Dict:
    return _cell()


def _layer(aggregate=None, individual=None, org=None, govt=None, nature=None) -> Dict:
    return {
        "aggregate": aggregate or _empty_slot(),
        "individual": individual or _empty_slot(),
        "org": org or _empty_slot(),
        "govt": govt or _empty_slot(),
        "nature": nature or _empty_slot(),
    }


SOLUTION_MATRIX_TEMPLATES: List[Dict] = [
    # ──────────────────────────────────────────────────────
    # 1) INDIVIDUAL — Home Renovation
    # ──────────────────────────────────────────────────────
    {
        "template_id": "individual_home_renovation",
        "org_type": "individual",
        "matrix_mode": "standard",
        "title": "Home Renovation (Individual)",
        "subtitle": "A 3-month apartment refresh example",
        "icon": "home",
        "color": "#2563EB",
        "payload": {
            "area_of_life": "assets",
            "smart_goal": "Complete a 3-month interior refresh of my 2BHK apartment within a 4 lakh INR budget by end of the next quarter.",
            "milestones": [
                {"description": "Finalise design, contractor quotes and budget", "timeline": "Week 1-2"},
                {"description": "Demolition, painting and electrical rework", "timeline": "Week 3-6"},
                {"description": "Furniture, lighting, final cleanup", "timeline": "Week 9-12"},
            ],
            "q1_all_concerns": "Running over budget. Contractor delays. Dust and noise during work. Living arrangements mid-project.",
            "q2_priority_concerns": "Budget overrun and living arrangement during demolition weeks.",
            "simpler_solutions": "DIY painting of 1 bedroom. Negotiate bulk price with single contractor instead of per-room.",
            "simpler_capabilities": "Basic DIY tools, design sense, negotiation skills.",
            "simpler_resources": "Existing furniture (70% reusable), family support for weekend supervision.",
            "simpler_help_aspect": "Structural advice + plumbing",
            "simpler_help_level": "Consulting",
            "simpler_help_from": "Civil engineer friend + licensed plumber",
            "matrix_mode": "standard",
            "matrix_self": _layer(
                aggregate=_cell(
                    time="10-12 hrs/week for supervision & decisions.",
                    energy="Moderate — reserved weekends; weekday evenings for calls.",
                    people="Myself as decision maker + spouse for approvals.",
                    finance="Self-funded from savings; tracking with a weekly burn sheet.",
                    infrastructure="Current apartment as worksite; temporary stay at parents' for 2 weeks.",
                    summary="My personal bandwidth and budget discipline are the primary levers.",
                ),
            ),
            "matrix_micro": _layer(
                aggregate=_cell(
                    time="Contractor crew working 6 days/week for 8-10 hrs/day.",
                    energy="Crew energy high early, tapers — need motivation checkpoints.",
                    people="1 site engineer, 4 masons, 2 painters, 1 electrician, 1 plumber.",
                    finance="Material advances phased weekly; retention 10% till handover.",
                    infrastructure="On-site storage, power backup for drilling, water line.",
                    summary="Tight crew coordination is the make-or-break.",
                ),
            ),
            "matrix_macro": _layer(
                aggregate=_cell(
                    time="Society NOC 7-10 working days; civic permits 3-4 weeks.",
                    energy="External approvals drain attention — delegate to a PMC if budget permits.",
                    people="Society secretary, RWA committee, municipal inspector.",
                    finance="Budget parking approvals + GST on materials adds ~12% overhead.",
                    infrastructure="Service lift slot, garbage disposal contract, water tanker bookings.",
                    summary="Macro touchpoints are mostly regulatory and community-driven.",
                ),
            ),
        },
    },

    # ──────────────────────────────────────────────────────
    # 2) ORG — SaaS Startup Q2 Growth
    # ──────────────────────────────────────────────────────
    {
        "template_id": "org_saas_q2_growth",
        "org_type": "org",
        "matrix_mode": "accurate",
        "title": "SaaS Q2 Growth Plan (Org)",
        "subtitle": "Scale a B2B SaaS from 500 to 2000 MAUs",
        "icon": "business",
        "color": "#7C3AED",
        "payload": {
            "area_of_life": "career",
            "smart_goal": "Grow monthly active users from 500 to 2000 and ARR from 1.2Cr to 2.4Cr within Q2 through product-led growth and targeted sales.",
            "milestones": [
                {"description": "Launch self-serve onboarding + free tier", "timeline": "Month 1"},
                {"description": "Hire 2 BDRs + 1 Solution Engineer", "timeline": "Month 1-2"},
                {"description": "Ship usage-based billing + 3 integrations", "timeline": "Month 2-3"},
            ],
            "q1_all_concerns": "Runway tight — 9 months. Support load will spike. Integration scope creep. Founder bandwidth.",
            "q2_priority_concerns": "Runway + founder bandwidth are the two binding constraints.",
            "simpler_solutions": "Bundle 3 integrations instead of 6; defer enterprise SSO to Q3; lean on community-led support.",
            "simpler_capabilities": "Strong product team, 2 senior engineers, founder with enterprise sales experience.",
            "simpler_resources": "Remaining seed capital 4.8Cr, cloud credits 30L, design partner NPS 62.",
            "simpler_help_aspect": "Go-to-market positioning + pricing psychology",
            "simpler_help_level": "Coaching",
            "simpler_help_from": "Fractional CMO + 2 advisor founders from portfolio",
            "matrix_mode": "accurate",
            "matrix_self": _layer(
                individual=_cell(
                    time="Founders: 55 hrs/week, CTO 50 hrs/week.",
                    energy="High but depletes Q-end; protect 1 day/week deep work.",
                    people="2 founders, 1 CTO, 1 Head of Design.",
                    finance="Founder compensation restrained; deferred bonuses.",
                    infrastructure="Personal laptops, home offices, shared note-taking OS.",
                ),
                org=_cell(
                    time="Team of 14 — avg 42 productive hrs/week.",
                    energy="Product pod high, GTM pod re-org this quarter.",
                    people="7 engineers, 3 product/design, 4 GTM/ops.",
                    finance="Payroll ~ 70L/month, AWS ~ 12L/month.",
                    infrastructure="Shared Mumbai office 2 days/week, rest WFH.",
                ),
            ),
            "matrix_micro": _layer(
                individual=_cell(
                    time="Users invest 3-5 min/session, 4 sessions/week.",
                    energy="Low-friction onboarding critical; drop-off at step 3.",
                    people="Ops managers (primary buyer) + analysts (daily user).",
                    finance="Willingness-to-pay ~ 1500/seat/mo for mid-market.",
                    infrastructure="Webapp primary; mobile view only for approvals.",
                ),
                org=_cell(
                    time="Customer procurement cycle 4-8 weeks.",
                    energy="Security & legal review absorbs half of deal cycle.",
                    people="Design partners 18; expansion-ready accounts 6.",
                    finance="Avg ACV 1.8L; expansion target 40% NDR.",
                    infrastructure="Integrations with Slack, Jira, HubSpot are table-stakes.",
                ),
            ),
            "matrix_macro": _layer(
                individual=_cell(
                    time="Prospects respond to cohorts & content on 2 week cadence.",
                    energy="Decision maker fatigue; personalise first-touch heavily.",
                    people="Mid-market ICP across India + SEA.",
                    finance="Post-seed funding climate cool; prove CAC payback < 14 mo.",
                    infrastructure="LinkedIn + community + SEO; minimal paid ads.",
                ),
                org=_cell(
                    time="Industry conferences clustered Mar & Jun.",
                    energy="Partner ecosystem is underutilised — activate 2 resellers.",
                    people="VC advisors, design partner CEOs, community leads.",
                    finance="Bridge note optional if runway < 6 months.",
                    infrastructure="Partner marketplaces (HubSpot, Slack) for discoverability.",
                ),
                govt=_cell(
                    time="Govt buyer cycles span fiscal year boundaries.",
                    energy="Selective only — if product is core enough to justify compliance load.",
                    people="IT secretary / DIGIT teams in 2-3 states.",
                    finance="Empanelment via GeM for PSU opportunities.",
                    infrastructure="ISO 27001 + data-residency compliance needed.",
                ),
            ),
        },
    },

    # ──────────────────────────────────────────────────────
    # 3) GOVT — Swachh Bharat Drive (District-level)
    # ──────────────────────────────────────────────────────
    {
        "template_id": "govt_swachh_bharat_drive",
        "org_type": "govt",
        "matrix_mode": "accurate",
        "title": "Swachh Bharat — District Drive (Govt)",
        "subtitle": "Lift a district from 62% to 95% door-to-door segregation in one year",
        "icon": "shield-checkmark",
        "color": "#F59E0B",
        "payload": {
            "area_of_life": "social_contributions",
            "smart_goal": "Take door-to-door waste segregation coverage from 62% to 95% across all 14 urban local bodies in the district within 12 months, tracked monthly via ODF+ metrics.",
            "milestones": [
                {"description": "Baseline audit + ward-level action plans", "timeline": "Month 1-2"},
                {"description": "Swachhata SBM-U 2.0 dashboards operationalised; 3000 safai-mitras trained", "timeline": "Month 3-6"},
                {"description": "Composting units + MRFs commissioned in 10 ULBs", "timeline": "Month 7-10"},
                {"description": "Independent verification achieves ODF+ / Star Rating", "timeline": "Month 11-12"},
            ],
            "q1_all_concerns": "Citizen behavior change slow. Contractor payment delays. Political transitions mid-year. Landfill saturation.",
            "q2_priority_concerns": "Citizen behavior change + consistent contractor performance.",
            "simpler_solutions": "Leverage existing SHG networks for IEC; piggyback on PM-AJAY funds; partner with 2 reputed NGOs for training.",
            "simpler_capabilities": "District admin machinery, SBM-U funds, ULB ward structures, municipal engineers.",
            "simpler_resources": "SBM-U 2.0 outlay 12Cr, 15th Finance Commission grants 7Cr, 3000 existing safai-mitras.",
            "simpler_help_aspect": "Behaviour-change communication + MRF engineering design",
            "simpler_help_level": "Problem Solving",
            "simpler_help_from": "CSE Delhi, GIZ India, local NGOs (Hasiru Dala model)",
            "matrix_mode": "accurate",
            "matrix_self": _layer(
                govt=_cell(
                    time="DC/Collector reviews monthly; ULB CEOs weekly.",
                    energy="Leadership commitment strong in yr-1; risk of dilution in election year.",
                    people="DC office team of 6 + 14 ULB CEOs.",
                    finance="Admin expenses ~ 3% of programme outlay.",
                    infrastructure="District command centre with GIS dashboards.",
                ),
            ),
            "matrix_micro": _layer(
                individual=_cell(
                    time="Citizens need 2 extra minutes/day to segregate.",
                    energy="Behaviour fatigue in month 3; reinforce via RWAs.",
                    people="Households (~ 2.4 lakh) + street vendors.",
                    finance="User fees kept token (Rs 40/month) for willingness.",
                    infrastructure="3-bin household kits + QR-tagged collection.",
                ),
                org=_cell(
                    time="Bulk generators (hotels, apartments) respond to weekly audits.",
                    energy="Enforce via show-cause + spot fines when nudges fail.",
                    people="Housekeeping heads, RWA secretaries, market associations.",
                    finance="Graded penalty slab; penalties feed a ward maintenance fund.",
                    infrastructure="On-site composters subsidised 50% for > 100 kg/day generators.",
                ),
                govt=_cell(
                    time="ULB sanitation inspectors daily rounds; ward sabhas fortnightly.",
                    energy="Inspector workload needs rationalisation — beat redesign.",
                    people="ULB CEOs, sanitary inspectors, ward supervisors.",
                    finance="Performance grants via 15th FC tied to segregation KPIs.",
                    infrastructure="GPS-tracked vehicles, transfer stations, MRFs.",
                ),
                nature=_cell(
                    time="Monsoon months Jun-Sep slow collection; plan buffer.",
                    energy="Landfill methane + leachate load; plan bioremediation.",
                    people="River/lake protection volunteers; school eco-clubs.",
                    finance="Earmark 5% for legacy waste bioremediation.",
                    infrastructure="Scientific landfill capping + 2 FSTPs.",
                ),
            ),
            "matrix_macro": _layer(
                govt=_cell(
                    time="MoHUA quarterly Swachh Survekshan rounds.",
                    energy="Inter-dept coordination (Revenue, Health, Water) is the gating factor.",
                    people="State Urban Development Dept, MoHUA liaison.",
                    finance="Central assistance 60:40 sharing; performance grants on audit.",
                    infrastructure="Integrated dashboards across 14 ULBs.",
                ),
            ),
        },
    },

    # ──────────────────────────────────────────────────────
    # 4) NATURE — Urban Tree Plantation Drive
    # ──────────────────────────────────────────────────────
    {
        "template_id": "nature_urban_plantation",
        "org_type": "nature",
        "matrix_mode": "accurate",
        "title": "Urban Tree Plantation Drive (Nature)",
        "subtitle": "Plant 50,000 trees across 10 wards with 80% 3-year survival",
        "icon": "leaf",
        "color": "#10B981",
        "payload": {
            "area_of_life": "social_contributions",
            "smart_goal": "Plant 50,000 native-species trees across 10 wards within 18 months with a guaranteed 80% 3-year survival rate through geo-tagged aftercare.",
            "milestones": [
                {"description": "Species mix finalised + 50 planting sites GIS-mapped", "timeline": "Month 1-3"},
                {"description": "Monsoon planting window: 30,000 saplings in ground", "timeline": "Month 4-6"},
                {"description": "Aftercare round 1: 90-day survival audit", "timeline": "Month 7-9"},
                {"description": "Aftercare + gap-filling to reach 80% 3-yr survival", "timeline": "Month 10-18"},
            ],
            "q1_all_concerns": "Climate change impacting survival. Land ownership disputes. Monsoon variability. Sustained volunteer engagement.",
            "q2_priority_concerns": "Long-term aftercare funding + sustained volunteer engagement.",
            "simpler_solutions": "Adopt-a-tree crowdfunding model; integrate with school curriculum; geo-tag with QR for citizen audits.",
            "simpler_capabilities": "NGO network, botanists, GIS volunteers, CSR contacts.",
            "simpler_resources": "3 native-species nurseries, 500 active volunteers, CSR pipeline 80L.",
            "simpler_help_aspect": "Species ecology + aftercare IoT sensors",
            "simpler_help_level": "Consulting",
            "simpler_help_from": "ATREE Bengaluru, local arboretum, IISc Bio-div group",
            "matrix_mode": "accurate",
            "matrix_self": _layer(
                individual=_cell(
                    time="Programme lead 25 hrs/week; volunteer coordinators 15 hrs/week.",
                    energy="High during planting weekends; needs quarterly retreats to sustain.",
                    people="Lead + 4 coordinators + 500 active volunteers.",
                    finance="Small operational reserve (~ 4L/month).",
                    infrastructure="Google Drive + WhatsApp groups; switching to dedicated CRM.",
                ),
                nature=_cell(
                    time="Pre-monsoon site prep (Apr-May) is critical.",
                    energy="Saplings fragile first 12 weeks; heatwave risk high.",
                    people="Arborists, ecologists, amateur naturalists.",
                    finance="Sapling cost Rs 45 + aftercare Rs 120 over 3 years.",
                    infrastructure="Nursery beds, drip irrigation pilot on 5 sites.",
                ),
            ),
            "matrix_micro": _layer(
                individual=_cell(
                    time="Volunteers 3-4 hours every weekend during planting.",
                    energy="Novel experience — onboarding day keeps retention high.",
                    people="College clubs, RWA members, corporate volunteer teams.",
                    finance="Covered via CSR or sponsor-a-tree crowdfunding.",
                    infrastructure="Site-level tool kits (spades, mulch, saplings).",
                ),
                org=_cell(
                    time="Corporate CSR teams respond to quarterly reports.",
                    energy="Pair CSR with employee-engagement weekends for stickiness.",
                    people="2 tech parks, 1 bank, 1 hotel chain confirmed.",
                    finance="Sponsor-a-tree Rs 500; adopt-a-grove Rs 50,000.",
                    infrastructure="Branded signage, CSR impact dashboards.",
                ),
                nature=_cell(
                    time="3-year survival window; critical checkpoints at 90/365/1095 days.",
                    energy="Pests + grazing are top 2 loss drivers.",
                    people="Urban ecologists + local naturalists.",
                    finance="Aftercare = 60% of lifetime cost per tree.",
                    infrastructure="Tree guards, drip lines, IoT moisture sensors (pilot).",
                ),
            ),
            "matrix_macro": _layer(
                govt=_cell(
                    time="Forest Dept / ULB permits 30-45 days per site.",
                    energy="Departmental coordination with ULB horticulture wing.",
                    people="DFO, ULB commissioner, ward corporator.",
                    finance="Leverage CAMPA funds + state greening mission grants.",
                    infrastructure="Use forest-dept nurseries; publish data on open-data portal.",
                ),
                nature=_cell(
                    time="Climate patterns shifting — plan native-drought-resistant species.",
                    energy="Urban heat island reduction is the macro co-benefit.",
                    people="Civic ecology networks, bird atlas volunteers.",
                    finance="Biodiversity credits + carbon pre-selling experimental.",
                    infrastructure="Ward-level biodiversity registers updated annually.",
                ),
            ),
        },
    },
]


def list_templates() -> List[Dict]:
    """Return lightweight metadata list for the picker UI."""
    return [
        {
            "template_id": t["template_id"],
            "org_type": t["org_type"],
            "matrix_mode": t["matrix_mode"],
            "title": t["title"],
            "subtitle": t["subtitle"],
            "icon": t["icon"],
            "color": t["color"],
        }
        for t in SOLUTION_MATRIX_TEMPLATES
    ]


def get_template(template_id: str) -> Dict:
    """Return a single template payload by id, or None."""
    for t in SOLUTION_MATRIX_TEMPLATES:
        if t["template_id"] == template_id:
            return t
    return None
