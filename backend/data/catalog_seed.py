"""
Central Catalog Management — initial seed.

Levels 0 and 1 are auto-projected from `data.hos_seed_data.LIFE_AREAS` and
SUB_AREAS so we have a stable backbone. Levels 2 and 3 are seeded here as
opinionated defaults that admins can extend at runtime.

Layout:
  L0 = life_area      (e.g. Finance)
  L1 = sub_area       (e.g. Savings)            ← already in HOS_SEED
  L2 = category       (e.g. FD)                 ← seeded here
  L3 = subcategory    (e.g. Senior-Citizen FD)  ← seeded here

Naming convention for node_id:
  cn_{life_area_short}_{slug_path_joined_by_underscore}
"""
from __future__ import annotations

from typing import Dict, List

# Each entry is a Level-2 node; `children` are Level-3.
# The dict key is the **L1 sub_area_id** the L2 node hangs under.

CCM_LEVEL2_BY_SUBAREA: Dict[str, List[dict]] = {

    # ----------------------------- FINANCE -----------------------------
    "sa_fin_savings": [
        {"slug": "fd", "name": "Fixed Deposit", "icon": "wallet", "children": [
            {"slug": "senior_citizen", "name": "Senior Citizen FD"},
            {"slug": "tax_saver", "name": "Tax-Saver FD"},
            {"slug": "regular", "name": "Regular FD"},
            {"slug": "corporate", "name": "Corporate FD"},
        ]},
        {"slug": "rd", "name": "Recurring Deposit"},
        {"slug": "chit_funds", "name": "Chit Funds"},
        {"slug": "savings_account", "name": "Savings Account"},
        {"slug": "ppf", "name": "Public Provident Fund (PPF)"},
        {"slug": "ssy", "name": "Sukanya Samriddhi (Girl child)"},
        {"slug": "post_office", "name": "Post Office Schemes"},
    ],
    "sa_fin_investments": [
        {"slug": "mutual_funds", "name": "Mutual Funds", "icon": "trending-up", "children": [
            {"slug": "elss", "name": "ELSS (Tax-Saver)"},
            {"slug": "index_funds", "name": "Index Funds"},
            {"slug": "midcap", "name": "Mid-cap"},
            {"slug": "smallcap", "name": "Small-cap"},
            {"slug": "debt", "name": "Debt Funds"},
            {"slug": "hybrid", "name": "Hybrid / Balanced"},
        ]},
        {"slug": "stocks", "name": "Direct Stocks"},
        {"slug": "etf", "name": "ETFs"},
        {"slug": "gold", "name": "Gold (SGB / Digital / Physical)"},
        {"slug": "bonds", "name": "Bonds (Govt / Corporate)"},
        {"slug": "nps", "name": "NPS (Retirement)"},
        {"slug": "crypto", "name": "Crypto"},
        {"slug": "alternative", "name": "Alternative (REIT / InvIT)"},
    ],
    "sa_fin_risk": [
        {"slug": "term_life", "name": "Term Life", "icon": "shield-checkmark"},
        {"slug": "endowment", "name": "Endowment / Money-back"},
        {"slug": "ulip", "name": "ULIP"},
        {"slug": "health_insurance", "name": "Health Insurance", "children": [
            {"slug": "individual", "name": "Individual"},
            {"slug": "family_floater", "name": "Family Floater"},
            {"slug": "senior_citizen", "name": "Senior Citizen"},
            {"slug": "critical_illness", "name": "Critical Illness"},
        ]},
        {"slug": "vehicle_insurance", "name": "Vehicle Insurance"},
        {"slug": "home_insurance", "name": "Home / Property Insurance"},
        {"slug": "travel_insurance", "name": "Travel Insurance"},
    ],
    "sa_fin_debt": [
        {"slug": "home_loan", "name": "Home Loan", "icon": "home"},
        {"slug": "personal_loan", "name": "Personal Loan"},
        {"slug": "vehicle_loan", "name": "Vehicle Loan"},
        {"slug": "education_loan", "name": "Education Loan"},
        {"slug": "credit_card", "name": "Credit Cards"},
        {"slug": "msme_loan", "name": "MSME / Business Loan"},
        {"slug": "loan_against_securities", "name": "Loan Against Securities"},
    ],
    "sa_fin_planning": [
        {"slug": "tax_filing", "name": "Tax Filing & Advisory", "icon": "document-text", "children": [
            {"slug": "itr_personal", "name": "Personal ITR Filing"},
            {"slug": "gst_filing", "name": "GST Filing"},
            {"slug": "tds", "name": "TDS Compliance"},
            {"slug": "ca_advisory", "name": "CA Advisory"},
        ]},
        {"slug": "estate_planning", "name": "Estate Planning / Wills"},
        {"slug": "retirement_planning", "name": "Retirement Planning"},
        {"slug": "child_education_planning", "name": "Child Education Planning"},
        {"slug": "wealth_advisory", "name": "Wealth Advisory"},
    ],

    # ------------------------------ CAREER -----------------------------
    "sa_car_job": [
        {"slug": "entry_level", "name": "Entry-level Jobs", "icon": "briefcase"},
        {"slug": "mid_career", "name": "Mid-career Jobs"},
        {"slug": "senior_leadership", "name": "Senior Leadership / C-suite"},
        {"slug": "remote", "name": "Remote / Distributed"},
        {"slug": "contract_freelance", "name": "Contract / Freelance"},
        {"slug": "internship", "name": "Internships"},
        {"slug": "government_jobs", "name": "Government Jobs"},
    ],
    "sa_car_business": [
        {"slug": "startups", "name": "Startups", "icon": "rocket"},
        {"slug": "msme", "name": "MSME / Small Business"},
        {"slug": "corporates", "name": "Corporates / Enterprise"},
        {"slug": "social_enterprise", "name": "Social Enterprise / NGO"},
        {"slug": "family_business", "name": "Family Business"},
        {"slug": "co_op", "name": "Co-operative Society"},
    ],
    "sa_car_fundraise": [
        {"slug": "angel", "name": "Angel Investors", "icon": "trending-up"},
        {"slug": "vc", "name": "Venture Capital"},
        {"slug": "pe", "name": "Private Equity"},
        {"slug": "family_office", "name": "Family Offices"},
        {"slug": "stock_traders", "name": "Stock Market Traders"},
        {"slug": "crowdfunding", "name": "Crowdfunding Platforms"},
        {"slug": "grants", "name": "Govt Grants / Schemes"},
    ],
    "sa_car_growth": [
        {"slug": "career_mentor", "name": "Career Mentors", "icon": "people"},
        {"slug": "executive_coach", "name": "Executive Coaching"},
        {"slug": "subject_expert", "name": "Subject Matter Experts"},
        {"slug": "industry_advisor", "name": "Industry Advisors"},
    ],

    # ---------------------------- KNOWLEDGE ----------------------------
    "sa_kno_education": [
        {"slug": "k12", "name": "K-12 School", "icon": "school"},
        {"slug": "ug", "name": "Undergraduate"},
        {"slug": "pg", "name": "Postgraduate"},
        {"slug": "phd", "name": "PhD / Research"},
        {"slug": "online_programs", "name": "Online Programs / MOOCs"},
        {"slug": "vocational", "name": "Vocational / ITI"},
        {"slug": "tutors", "name": "Tutors"},
    ],
    "sa_kno_skills": [
        {"slug": "tech_skills", "name": "Tech Skills (Coding/Cloud/AI)", "icon": "ribbon", "children": [
            {"slug": "programming", "name": "Programming"},
            {"slug": "cloud", "name": "Cloud / DevOps"},
            {"slug": "data_ai", "name": "Data & AI"},
            {"slug": "cybersecurity", "name": "Cybersecurity"},
        ]},
        {"slug": "soft_skills", "name": "Soft Skills"},
        {"slug": "creative_skills", "name": "Creative (Design/Music/Arts)"},
        {"slug": "language", "name": "Language Proficiency"},
    ],

    # ------------------------------ HEALTH -----------------------------
    "sa_hlt_preventive": [
        {"slug": "health_check", "name": "Health Checkups", "icon": "medkit", "children": [
            {"slug": "master_check", "name": "Master Health Checkup"},
            {"slug": "cardiac", "name": "Cardiac / Heart Screening"},
            {"slug": "diabetes", "name": "Diabetes Screening"},
            {"slug": "cancer", "name": "Cancer Screening"},
        ]},
        {"slug": "imaging", "name": "Imaging (MRI / CT / Ultrasound)"},
        {"slug": "blood_tests", "name": "Blood Tests / Pathology"},
        {"slug": "vaccination", "name": "Vaccination"},
    ],
    "sa_hlt_lifestyle": [
        {"slug": "yoga", "name": "Yoga", "icon": "leaf"},
        {"slug": "meditation", "name": "Meditation"},
        {"slug": "ayurveda", "name": "Ayurveda"},
        {"slug": "nutrition", "name": "Nutrition / Diet"},
        {"slug": "fitness", "name": "Fitness / Gym"},
        {"slug": "sleep_health", "name": "Sleep Health"},
    ],
    "sa_hlt_physical": [
        {"slug": "general_practitioner", "name": "General Practitioners"},
        {"slug": "specialist_doctors", "name": "Specialist Doctors", "children": [
            {"slug": "cardiologist", "name": "Cardiologist"},
            {"slug": "endocrinologist", "name": "Endocrinologist"},
            {"slug": "orthopedic", "name": "Orthopedic"},
            {"slug": "neurologist", "name": "Neurologist"},
            {"slug": "gynecologist", "name": "Gynecologist"},
        ]},
        {"slug": "dental", "name": "Dental"},
        {"slug": "physiotherapy", "name": "Physiotherapy"},
        {"slug": "ophthalmology", "name": "Ophthalmology"},
        {"slug": "dermatology", "name": "Dermatology"},
    ],
    "sa_hlt_mental": [
        {"slug": "psychologist", "name": "Clinical Psychologist", "icon": "happy"},
        {"slug": "psychiatrist", "name": "Psychiatrist"},
        {"slug": "therapist_counselor", "name": "Therapist / Counsellor"},
        {"slug": "wellness_coach", "name": "Mental Wellness Coach"},
    ],

    # ----------------------------- ASSETS ------------------------------
    "sa_ast_real_estate": [
        {"slug": "apartment", "name": "Apartment / Flat", "icon": "home", "children": [
            {"slug": "1bhk", "name": "1BHK"},
            {"slug": "2bhk", "name": "2BHK"},
            {"slug": "3bhk", "name": "3BHK"},
            {"slug": "4plus_bhk", "name": "4+BHK / Penthouse"},
        ]},
        {"slug": "villa", "name": "Villa / Independent House"},
        {"slug": "plot", "name": "Plot / Land"},
        {"slug": "commercial", "name": "Commercial Property"},
        {"slug": "rental", "name": "Rental Listings"},
        {"slug": "co_living", "name": "Co-living / PG"},
    ],
    "sa_ast_home": [
        {"slug": "cleaning", "name": "Home Cleaning", "icon": "construct"},
        {"slug": "laundry", "name": "Laundry"},
        {"slug": "interior", "name": "Interior Design"},
        {"slug": "repair_maintenance", "name": "Repair / Maintenance"},
        {"slug": "home_security", "name": "Home Security"},
        {"slug": "appliances", "name": "Home Appliances"},
        {"slug": "furniture", "name": "Furniture"},
    ],
    "sa_ast_vehicles": [
        {"slug": "two_wheeler", "name": "Two-wheelers", "icon": "car"},
        {"slug": "car", "name": "Cars", "children": [
            {"slug": "hatchback", "name": "Hatchback"},
            {"slug": "sedan", "name": "Sedan"},
            {"slug": "suv", "name": "SUV"},
            {"slug": "luxury", "name": "Luxury"},
        ]},
        {"slug": "ev", "name": "Electric Vehicles"},
        {"slug": "commercial_vehicle", "name": "Commercial Vehicles"},
        {"slug": "chauffeur", "name": "Chauffeur / Driver Service"},
        {"slug": "service_repair", "name": "Vehicle Service / Repair"},
    ],
    "sa_ast_valuables": [
        {"slug": "gold_jewellery", "name": "Gold Jewellery"},
        {"slug": "diamond", "name": "Diamond / Gemstones"},
        {"slug": "watches", "name": "Luxury Watches"},
        {"slug": "art_collectibles", "name": "Art / Collectibles"},
    ],
    "sa_ast_digital": [
        {"slug": "domain_brand", "name": "Domains / Brand IP"},
        {"slug": "patents", "name": "Patents"},
        {"slug": "trademarks", "name": "Trademarks"},
        {"slug": "copyrights", "name": "Copyrights"},
    ],

    # -------------------------- RELATIONSHIPS --------------------------
    "sa_rel_marriage": [
        {"slug": "matrimony", "name": "Matrimony", "icon": "heart", "children": [
            {"slug": "brides", "name": "Brides (Profiles)"},
            {"slug": "grooms", "name": "Grooms (Profiles)"},
            {"slug": "second_marriage", "name": "Second Marriage"},
            {"slug": "intercaste", "name": "Inter-caste / Inter-faith"},
        ]},
        {"slug": "wedding_planning", "name": "Wedding Planning"},
        {"slug": "marriage_counseling", "name": "Marriage Counselling"},
    ],
    "sa_rel_parenting": [
        {"slug": "child_psychology", "name": "Child Psychology"},
        {"slug": "parenting_coach", "name": "Parenting Coach"},
        {"slug": "school_counsellor", "name": "School Counsellor"},
    ],
    "sa_rel_family": [
        {"slug": "elder_care", "name": "Elder Care Services", "icon": "people"},
        {"slug": "estate_legal", "name": "Family Legal & Estate"},
        {"slug": "family_therapy", "name": "Family Therapy"},
    ],
}
