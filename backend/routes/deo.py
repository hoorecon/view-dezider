"""
DEO (Decision Engine Optimization) Router
Phase A: Inbound — Import solutions from external URLs (AI + Manual scraping)
Phase B: Outbound — Expose decision engine via API keys, Widget, SDK
"""
import os
import uuid
import json
import hashlib
import secrets
import re
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

from core.database import db
from core.auth import get_current_user

router = APIRouter()


# ================================================================
# PHASE A: DEO INBOUND — IMPORT SOLUTIONS FROM EXTERNAL URLS
# ================================================================

async def ai_extract_product_data(html_text: str, url: str, context: str = "") -> dict:
    """Use LLM to intelligently extract product/service data from HTML."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Truncate HTML to fit in context
    clean_html = html_text[:12000]

    prompt = f"""Analyze this webpage HTML and extract ALL products/services listed. 
URL: {url}
Context: {context or 'General product/service page'}

For EACH product/service found, extract:
1. name: Product/service name
2. description: Brief description (1-2 sentences)
3. type: One of PRODUCT, SERVICE, EVENT, PROJECT, PERSON_CONTACT
4. provider: Company/brand name
5. price_range: Price or price range as string (e.g., "₹5,000 - ₹10,000")
6. currency: Currency code (e.g., INR, USD)
7. url: Direct link to the product if found
8. image_url: Product image URL if found
9. quantitative_factors: Array of measurable attributes, each with:
   - factor_name: Name of the metric (e.g., "Price", "Rating", "Duration")
   - value: Numeric value
   - unit: Unit of measurement (e.g., "INR", "stars", "months", "km")
10. qualitative_factors: Array of review/quality attributes, each with:
    - factor_name: Quality aspect (e.g., "Customer Service", "Build Quality", "Value for Money")
    - rating: Score from 1-10
    - summary: Brief text about this quality aspect
11. tags: Array of relevant category tags

Return ONLY valid JSON array. If no products found, return empty array [].
Example format:
[{{
  "name": "Example Product",
  "description": "A great product",
  "type": "PRODUCT",
  "provider": "Brand X",
  "price_range": "₹5,000",
  "currency": "INR",
  "url": "https://example.com/product",
  "image_url": "https://example.com/img.jpg",
  "quantitative_factors": [{{"factor_name": "Price", "value": 5000, "unit": "INR"}}, {{"factor_name": "Rating", "value": 4.5, "unit": "stars"}}],
  "qualitative_factors": [{{"factor_name": "Build Quality", "rating": 8, "summary": "Well built and durable"}}],
  "tags": ["electronics", "gadgets"]
}}]

HTML content:
{clean_html}"""

    try:
        chat = LlmChat(
            api_key=api_key,
            model="openai/gpt-4.1-mini",
        )
        response = await chat.send_message_async(UserMessage(content=prompt))
        text = response.text.strip()

        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # Try to find array in response
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        if start_idx >= 0 and end_idx > start_idx:
            text = text[start_idx:end_idx]

        products = json.loads(text)
        return {"products": products, "source": "ai", "count": len(products)}
    except json.JSONDecodeError:
        return {"products": [], "source": "ai", "error": "Failed to parse AI response", "raw": text[:500]}
    except Exception as e:
        return {"products": [], "source": "ai", "error": str(e)}


async def manual_extract_product_data(html_text: str, selectors: dict) -> dict:
    """Extract product data using CSS selectors (manual mapping)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "html.parser")
    products = []

    # Find product containers
    container_sel = selectors.get("container", ".product, .item, article")
    containers = soup.select(container_sel)

    if not containers:
        # Try the whole page as a single product
        containers = [soup]

    for container in containers[:50]:  # Limit to 50 products
        product = {}

        for field, sel in selectors.items():
            if field == "container":
                continue
            el = container.select_one(sel) if sel else None
            if el:
                if field in ["image_url", "url"]:
                    product[field] = el.get("src") or el.get("href") or el.get_text(strip=True)
                elif field == "price":
                    price_text = el.get_text(strip=True)
                    # Extract numeric value
                    nums = re.findall(r'[\d,]+\.?\d*', price_text.replace(",", ""))
                    product["price_range"] = price_text
                    if nums:
                        product.setdefault("quantitative_factors", []).append({
                            "factor_name": "Price",
                            "value": float(nums[0]),
                            "unit": selectors.get("currency", "INR"),
                        })
                elif field == "rating":
                    rating_text = el.get_text(strip=True)
                    nums = re.findall(r'[\d.]+', rating_text)
                    if nums:
                        product.setdefault("quantitative_factors", []).append({
                            "factor_name": "Rating",
                            "value": float(nums[0]),
                            "unit": "stars",
                        })
                else:
                    product[field] = el.get_text(strip=True)

        if product.get("name"):
            product.setdefault("type", "PRODUCT")
            product.setdefault("quantitative_factors", [])
            product.setdefault("qualitative_factors", [])
            product.setdefault("tags", [])
            products.append(product)

    return {"products": products, "source": "manual", "count": len(products)}


@router.post("/deo/scrape-url")
async def scrape_url(request: Request, user: dict = Depends(get_current_user)):
    """Scrape a URL and extract product/service data using AI."""
    import requests as http_req
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    mode = body.get("mode", "ai")  # "ai" or "manual"
    context = body.get("context", "")  # Additional context for AI
    selectors = body.get("selectors", {})  # CSS selectors for manual mode
    life_area_id = body.get("life_area_id", "")

    # Fetch the page
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = http_req.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html_text = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")

    # Extract based on mode
    if mode == "manual" and selectors:
        result = await manual_extract_product_data(html_text, selectors)
    else:
        result = await ai_extract_product_data(html_text, url, context)

    # Add metadata
    result["url"] = url
    result["life_area_id"] = life_area_id
    result["scraped_at"] = datetime.now(timezone.utc).isoformat()

    # Log the scrape
    await db.deo_scrape_logs.insert_one({
        "scrape_id": str(uuid.uuid4()),
        "url": url,
        "mode": mode,
        "user_id": user["user_id"],
        "product_count": result.get("count", 0),
        "life_area_id": life_area_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return result


@router.post("/deo/import")
async def import_scraped_solutions(request: Request, user: dict = Depends(get_current_user)):
    """Import scraped product data into Solutions Store + ReviewNet."""
    body = await request.json()
    products = body.get("products", [])
    life_area_id = body.get("life_area_id", "")
    sub_area_id = body.get("sub_area_id", "")
    category_id = body.get("category_id", "")
    source_url = body.get("source_url", "")
    country = body.get("country", "IN")
    language = body.get("language", "en")
    visibility = body.get("visibility", "PRIVATE")

    if not products:
        raise HTTPException(status_code=400, detail="No products to import")

    user_role = user.get("role", "")
    org_role = user.get("org_role", "")
    is_admin = user_role in ["super_admin", "co_admin", "admin"] or org_role in ["org_super_admin", "org_co_admin"]

    imported = []
    for p in products:
        name = p.get("name", "").strip()
        if not name:
            continue

        sol_type = p.get("type", "PRODUCT").upper()
        if sol_type not in ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"]:
            sol_type = "PRODUCT"

        # Determine approval status
        approval_status = "approved"
        is_authorized = False
        if visibility == "PUBLIC":
            if is_admin:
                is_authorized = True
            else:
                approval_status = "pending"

        solution_id = str(uuid.uuid4())

        solution = {
            "solution_id": solution_id,
            "type": sol_type,
            "name": name,
            "description": p.get("description", ""),
            "life_area_id": life_area_id,
            "sub_area_id": sub_area_id,
            "category_id": category_id,
            "visibility": visibility,
            "approval_status": approval_status,
            "created_by": user["user_id"],
            "created_by_name": user.get("name", ""),
            "org_id": user.get("org_id"),
            "is_authorized": is_authorized,
            "country": country,
            "language": language,
            "provider": p.get("provider", ""),
            "url": p.get("url", source_url),
            "image_url": p.get("image_url", ""),
            "tags": p.get("tags", []),
            "price_range": p.get("price_range", ""),
            "currency": p.get("currency", "INR"),
            "type_specific": {},
            "quantitative_factors": p.get("quantitative_factors", []),
            "deo_source": {
                "url": source_url,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "mode": body.get("mode", "ai"),
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.solutions_store.insert_one(solution)

        # Import qualitative factors as ReviewNet reviews
        qual_factors = p.get("qualitative_factors", [])
        if qual_factors:
            factor_ratings = {}
            for qf in qual_factors:
                factor_ratings[qf.get("factor_name", "")] = qf.get("rating", 5)

            review = {
                "review_id": str(uuid.uuid4()),
                "solution_id": solution_id,
                "user_id": user["user_id"],
                "user_name": user.get("name", "DEO Import"),
                "text": f"Auto-imported from {source_url}",
                "pros": "; ".join(qf.get("summary", "") for qf in qual_factors if qf.get("rating", 0) >= 7),
                "cons": "; ".join(qf.get("summary", "") for qf in qual_factors if qf.get("rating", 0) < 5),
                "factor_ratings": factor_ratings,
                "is_deo_import": True,
                "source_url": source_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.solution_reviews.insert_one(review)

        solution.pop("_id", None)
        imported.append({"solution_id": solution_id, "name": name, "type": sol_type})

    return {
        "message": f"Imported {len(imported)} solutions",
        "imported": imported,
        "total": len(imported),
    }


# DEO Domain Mappings (Admin)
@router.get("/deo/mappings")
async def list_deo_mappings(user: dict = Depends(get_current_user)):
    """List configured DEO domain mappings."""
    mappings = await db.deo_mappings.find(
        {"status": "active"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"mappings": mappings, "total": len(mappings)}


@router.post("/deo/mappings")
async def create_deo_mapping(request: Request, user: dict = Depends(get_current_user)):
    """Create a domain → life_area mapping for DEO scraping."""
    user_role = user.get("role", "")
    org_role = user.get("org_role", "")
    if user_role not in ["super_admin", "co_admin", "admin"] and org_role not in ["org_super_admin", "org_co_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    mapping = {
        "mapping_id": str(uuid.uuid4()),
        "domain": body.get("domain", "").strip(),
        "life_area_id": body.get("life_area_id", ""),
        "default_type": body.get("default_type", "PRODUCT"),
        "selectors": body.get("selectors", {}),
        "description": body.get("description", ""),
        "created_by": user["user_id"],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.deo_mappings.insert_one(mapping)
    mapping.pop("_id", None)
    return mapping


@router.get("/deo/scrape-logs")
async def list_scrape_logs(user: dict = Depends(get_current_user)):
    """List recent scrape logs."""
    logs = await db.deo_scrape_logs.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"logs": logs, "total": len(logs)}


# ================================================================
# PHASE B: DEO OUTBOUND — API KEYS, PUBLIC API, WIDGET, SDK
# ================================================================

# --- API Key Management ---

@router.post("/deo/api-keys")
async def generate_api_key(request: Request, user: dict = Depends(get_current_user)):
    """Generate a new DEO API key for external integration."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="API key name is required")

    # Generate a secure API key
    raw_key = f"deo_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    permissions = body.get("permissions", ["full_flow", "values_api", "logic_api"])
    allowed_origins = body.get("allowed_origins", ["*"])

    api_key_doc = {
        "key_id": str(uuid.uuid4()),
        "name": name,
        "key_hash": key_hash,
        "key_prefix": raw_key[:12],  # For display
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "permissions": permissions,
        "allowed_origins": allowed_origins,
        "rate_limit": body.get("rate_limit", 1000),  # requests per day
        "usage_count": 0,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": None,
    }

    await db.deo_api_keys.insert_one(api_key_doc)

    return {
        "message": "API key generated",
        "key_id": api_key_doc["key_id"],
        "api_key": raw_key,  # Only returned ONCE at creation
        "name": name,
        "permissions": permissions,
        "note": "Save this key securely. It won't be shown again.",
    }


@router.get("/deo/api-keys")
async def list_api_keys(user: dict = Depends(get_current_user)):
    """List user's DEO API keys."""
    keys = await db.deo_api_keys.find(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0, "key_hash": 0}
    ).sort("created_at", -1).to_list(50)
    return {"keys": keys, "total": len(keys)}


@router.delete("/deo/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: dict = Depends(get_current_user)):
    """Revoke a DEO API key."""
    result = await db.deo_api_keys.update_one(
        {"key_id": key_id, "user_id": user["user_id"]},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key revoked"}


# --- DEO API Key Authentication Helper ---

async def verify_deo_api_key(request: Request) -> dict:
    """Verify DEO API key from header or query param."""
    api_key = request.headers.get("X-DEO-API-Key") or request.query_params.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="DEO API key required. Pass via X-DEO-API-Key header or api_key query param.")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_doc = await db.deo_api_keys.find_one({"key_hash": key_hash, "status": "active"})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Check rate limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage_key = f"deo_usage_{key_doc['key_id']}_{today}"
    usage = await db.deo_usage.find_one({"usage_key": usage_key})
    count = usage.get("count", 0) if usage else 0
    if count >= key_doc.get("rate_limit", 1000):
        raise HTTPException(status_code=429, detail="Daily rate limit exceeded")

    # Increment usage
    await db.deo_usage.update_one(
        {"usage_key": usage_key},
        {"$inc": {"count": 1}, "$set": {"date": today}},
        upsert=True
    )
    await db.deo_api_keys.update_one(
        {"key_id": key_doc["key_id"]},
        {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"usage_count": 1}}
    )

    return key_doc


# --- PUBLIC API ENDPOINTS (API Key Auth) ---

# Tier 1: Option-Values API — Fetch factor-option data
@router.get("/deo/public/solutions")
async def public_get_solutions(
    request: Request,
    life_area_id: Optional[str] = None,
    type: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """[Public API] Get solutions with their factor values. Requires DEO API key."""
    key_doc = await verify_deo_api_key(request)
    if "values_api" not in key_doc.get("permissions", []):
        raise HTTPException(status_code=403, detail="This API key doesn't have 'values_api' permission")

    query = {"status": "active", "is_authorized": True}
    if life_area_id:
        query["life_area_id"] = life_area_id
    if type:
        query["type"] = type.upper()
    if country:
        query["country"] = country
    if language:
        query["language"] = language

    solutions = await db.solutions_store.find(
        query, {"_id": 0}
    ).limit(limit).to_list(limit)

    # Enrich with ReviewNet data
    for sol in solutions:
        reviews = await db.solution_reviews.find(
            {"solution_id": sol["solution_id"]}, {"_id": 0}
        ).to_list(100)
        if reviews:
            all_ratings = {}
            for r in reviews:
                for fname, fval in r.get("factor_ratings", {}).items():
                    all_ratings.setdefault(fname, []).append(fval)
            sol["qualitative_factors"] = [
                {"factor_name": k, "avg_rating": round(sum(v) / len(v), 1), "review_count": len(v)}
                for k, v in all_ratings.items()
            ]
            sol["total_reviews"] = len(reviews)
        else:
            sol["qualitative_factors"] = []
            sol["total_reviews"] = 0

    return {
        "solutions": solutions,
        "total": len(solutions),
        "api": "deo_values_api",
    }


# Tier 2: Full Decision Flow — Predefined options/factors, user provides assessment %
@router.post("/deo/public/decision-flow")
async def public_decision_flow(request: Request):
    """[Public API] Full decision flow with predefined options & factors.
    User provides assessment percentages for each option-factor combination.
    Returns computed scores and recommendations."""
    key_doc = await verify_deo_api_key(request)
    if "full_flow" not in key_doc.get("permissions", []):
        raise HTTPException(status_code=403, detail="This API key doesn't have 'full_flow' permission")

    body = await request.json()
    decision_context_id = body.get("decision_context_id")  # Use a pre-configured decision template
    solution_ids = body.get("solution_ids", [])  # Solutions to use as options
    assessments = body.get("assessments", {})  # {option_id: {factor_id: percentage}}

    if not solution_ids:
        raise HTTPException(status_code=400, detail="solution_ids required — provide solution IDs from the Solutions Store")

    # Fetch solutions
    solutions = []
    for sid in solution_ids:
        sol = await db.solutions_store.find_one({"solution_id": sid, "status": "active"}, {"_id": 0})
        if sol:
            solutions.append(sol)

    if len(solutions) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid solutions required")

    # Collect all factors from solutions
    all_factors = {}
    for sol in solutions:
        for qf in sol.get("quantitative_factors", []):
            fname = qf.get("factor_name", "")
            if fname and fname not in all_factors:
                all_factors[fname] = {"name": fname, "type": "quantitative", "weight": 1}
        # Get qualitative factors from reviews
        reviews = await db.solution_reviews.find(
            {"solution_id": sol["solution_id"]}, {"_id": 0}
        ).to_list(50)
        for r in reviews:
            for fname in r.get("factor_ratings", {}):
                if fname not in all_factors:
                    all_factors[fname] = {"name": fname, "type": "qualitative", "weight": 1}

    factors = list(all_factors.values())

    # If user provides custom factor weights
    factor_weights = body.get("factor_weights", {})
    for f in factors:
        if f["name"] in factor_weights:
            f["weight"] = factor_weights[f["name"]]

    total_weight = sum(f["weight"] for f in factors) or 1

    # Compute scores for each option
    results = []
    for sol in solutions:
        option_score = 0
        factor_scores = []

        for f in factors:
            fname = f["name"]
            weight_normalized = f["weight"] / total_weight

            # Check if user provided assessment
            user_pct = None
            if sol["solution_id"] in assessments and fname in assessments[sol["solution_id"]]:
                user_pct = assessments[sol["solution_id"]][fname]

            # Auto-populate from store data if user didn't provide
            if user_pct is None:
                # Try quantitative
                for qf in sol.get("quantitative_factors", []):
                    if qf.get("factor_name") == fname:
                        user_pct = min(100, max(0, float(qf.get("value", 50))))
                        break

                # Try qualitative (convert 1-10 to percentage)
                if user_pct is None:
                    reviews = await db.solution_reviews.find(
                        {"solution_id": sol["solution_id"]}, {"_id": 0}
                    ).to_list(50)
                    ratings = []
                    for r in reviews:
                        if fname in r.get("factor_ratings", {}):
                            ratings.append(r["factor_ratings"][fname])
                    if ratings:
                        user_pct = round((sum(ratings) / len(ratings)) * 10, 1)

            if user_pct is None:
                user_pct = 50  # Default

            weighted_score = user_pct * weight_normalized
            option_score += weighted_score
            factor_scores.append({
                "factor": fname,
                "percentage": user_pct,
                "weight": f["weight"],
                "weighted_score": round(weighted_score, 2),
                "source": "user" if sol["solution_id"] in assessments and fname in assessments.get(sol["solution_id"], {}) else "auto",
            })

        results.append({
            "solution_id": sol["solution_id"],
            "name": sol["name"],
            "type": sol["type"],
            "total_score": round(option_score, 2),
            "factor_scores": factor_scores,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["total_score"], reverse=True)

    # Add rank
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return {
        "decision_result": {
            "factors": factors,
            "options": results,
            "recommendation": results[0]["name"] if results else None,
            "recommendation_score": results[0]["total_score"] if results else 0,
        },
        "api": "deo_full_flow",
    }


# Tier 3: Decision Logic API — Custom factors/options, our scoring
@router.post("/deo/public/decision-logic")
async def public_decision_logic(request: Request):
    """[Public API] Apply our decision scoring logic to custom options & factors.
    Client provides their own options, factors, and assessment percentages.
    Returns computed worth scores, rankings, and analysis."""
    key_doc = await verify_deo_api_key(request)
    if "logic_api" not in key_doc.get("permissions", []):
        raise HTTPException(status_code=403, detail="This API key doesn't have 'logic_api' permission")

    body = await request.json()
    options = body.get("options", [])
    factors = body.get("factors", [])

    if len(options) < 2:
        raise HTTPException(status_code=400, detail="At least 2 options required")
    if not factors:
        raise HTTPException(status_code=400, detail="At least 1 factor required")

    # Validate input structure
    for opt in options:
        if not opt.get("name"):
            raise HTTPException(status_code=400, detail="Each option must have a 'name'")
        if not opt.get("assessments"):
            raise HTTPException(status_code=400, detail=f"Option '{opt['name']}' must have 'assessments' (factor_name → percentage map)")

    for f in factors:
        if not f.get("name"):
            raise HTTPException(status_code=400, detail="Each factor must have a 'name'")
        f.setdefault("weight", 1)
        f.setdefault("importance", 50)

    total_weight = sum(f["weight"] for f in factors) or 1

    # Compute scores using PRR-style scoring
    results = []
    for opt in options:
        total_score = 0
        factor_details = []

        for f in factors:
            fname = f["name"]
            pct = opt["assessments"].get(fname, 50)
            weight_norm = f["weight"] / total_weight

            # Apply importance weighting
            importance = f.get("importance", 50) / 100
            effective_weight = weight_norm * (0.5 + importance * 0.5)

            weighted_score = pct * effective_weight
            total_score += weighted_score

            factor_details.append({
                "factor": fname,
                "assessment_pct": pct,
                "weight": f["weight"],
                "importance": f.get("importance", 50),
                "weighted_score": round(weighted_score, 2),
            })

        results.append({
            "option": opt["name"],
            "total_score": round(total_score, 2),
            "worth_percentage": round(total_score, 1),
            "factor_details": factor_details,
            "metadata": opt.get("metadata", {}),
        })

    results.sort(key=lambda x: x["total_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    # Compute gap analysis
    if len(results) >= 2:
        gap = round(results[0]["total_score"] - results[1]["total_score"], 2)
        confidence = "high" if gap > 15 else "medium" if gap > 5 else "low"
    else:
        gap = 0
        confidence = "low"

    return {
        "decision_analysis": {
            "options": results,
            "factors_used": len(factors),
            "recommendation": results[0]["option"],
            "recommendation_score": results[0]["total_score"],
            "runner_up": results[1]["option"] if len(results) > 1 else None,
            "score_gap": gap,
            "confidence": confidence,
        },
        "api": "deo_logic_api",
    }


# --- EMBEDDABLE WIDGET ---

@router.get("/deo/public/widget")
async def get_widget(
    request: Request,
    life_area_id: Optional[str] = None,
    theme: str = Query(default="dark", regex="^(dark|light)$"),
):
    """[Public API] Get embeddable decision widget HTML. Requires DEO API key."""
    key_doc = await verify_deo_api_key(request)
    if "full_flow" not in key_doc.get("permissions", []):
        raise HTTPException(status_code=403, detail="Widget requires 'full_flow' permission")

    api_key = request.headers.get("X-DEO-API-Key") or request.query_params.get("api_key")

    # Determine base URL
    forwarded_host = request.headers.get("x-forwarded-host", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    else:
        base_url = str(request.base_url).rstrip("/")

    bg = "#0F172A" if theme == "dark" else "#FFFFFF"
    text_color = "#F8FAFC" if theme == "dark" else "#1E293B"
    surface = "#1E293B" if theme == "dark" else "#F1F5F9"
    primary = "#3B82F6"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>View Dezider - Decision Widget</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: {bg}; color: {text_color}; padding: 16px; }}
.widget-header {{ text-align: center; margin-bottom: 20px; }}
.widget-title {{ font-size: 18px; font-weight: 700; }}
.widget-sub {{ font-size: 12px; color: #94A3B8; margin-top: 4px; }}
.solutions-grid {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }}
.sol-card {{ background: {surface}; border-radius: 12px; padding: 14px; cursor: pointer; border: 2px solid transparent; transition: border-color 0.2s; }}
.sol-card:hover {{ border-color: {primary}; }}
.sol-card.selected {{ border-color: {primary}; background: {primary}22; }}
.sol-name {{ font-size: 15px; font-weight: 600; }}
.sol-desc {{ font-size: 12px; color: #94A3B8; margin-top: 4px; }}
.sol-factors {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }}
.factor-chip {{ background: {primary}15; color: {primary}; font-size: 10px; padding: 2px 8px; border-radius: 6px; }}
.compare-btn {{ width: 100%; padding: 14px; background: {primary}; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 700; cursor: pointer; }}
.compare-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.results {{ margin-top: 20px; }}
.result-card {{ background: {surface}; border-radius: 12px; padding: 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }}
.rank-badge {{ width: 28px; height: 28px; border-radius: 14px; background: {primary}; color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }}
.score {{ font-size: 20px; font-weight: 700; color: {primary}; }}
.powered {{ text-align: center; margin-top: 16px; font-size: 10px; color: #64748B; }}
.powered a {{ color: {primary}; text-decoration: none; }}
#loading {{ text-align: center; padding: 40px; color: #94A3B8; }}
</style>
</head>
<body>
<div class="widget-header">
  <div class="widget-title">Compare & Decide</div>
  <div class="widget-sub">Select 2+ options to compare with AI-powered analysis</div>
</div>
<div id="loading">Loading solutions...</div>
<div id="solutions" class="solutions-grid" style="display:none;"></div>
<button id="compareBtn" class="compare-btn" disabled onclick="compare()">Compare Selected (0)</button>
<div id="results" class="results" style="display:none;"></div>
<div class="powered">Powered by <a href="#" target="_blank">View Dezider DEO</a></div>

<script>
const API_BASE = "{base_url}/api";
const API_KEY = "{api_key}";
let solutions = [];
let selected = new Set();

async function loadSolutions() {{
  try {{
    const params = new URLSearchParams({{ api_key: API_KEY, limit: "20" }});
    {"if ('" + (life_area_id or "") + "') params.set('life_area_id', '" + (life_area_id or "") + "');" if life_area_id else ""}
    const resp = await fetch(API_BASE + "/deo/public/solutions?" + params);
    const data = await resp.json();
    solutions = data.solutions || [];
    renderSolutions();
  }} catch(e) {{ document.getElementById('loading').textContent = 'Failed to load'; }}
}}

function renderSolutions() {{
  document.getElementById('loading').style.display = 'none';
  const grid = document.getElementById('solutions');
  grid.style.display = 'flex';
  grid.innerHTML = solutions.map(s => `
    <div class="sol-card ${{selected.has(s.solution_id) ? 'selected' : ''}}" onclick="toggle('${{s.solution_id}}')">
      <div class="sol-name">${{s.name}}</div>
      <div class="sol-desc">${{s.description || ''}}</div>
      <div class="sol-factors">
        ${{(s.quantitative_factors || []).slice(0,3).map(f => `<span class="factor-chip">${{f.factor_name}}: ${{f.value}} ${{f.unit || ''}}</span>`).join('')}}
      </div>
    </div>
  `).join('');
}}

function toggle(id) {{
  if (selected.has(id)) selected.delete(id); else selected.add(id);
  renderSolutions();
  const btn = document.getElementById('compareBtn');
  btn.textContent = `Compare Selected (${{selected.size}})`;
  btn.disabled = selected.size < 2;
}}

async function compare() {{
  const btn = document.getElementById('compareBtn');
  btn.textContent = 'Analyzing...';
  btn.disabled = true;
  try {{
    const resp = await fetch(API_BASE + "/deo/public/decision-flow", {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json', 'X-DEO-API-Key': API_KEY }},
      body: JSON.stringify({{ solution_ids: [...selected] }})
    }});
    const data = await resp.json();
    const results = data.decision_result?.options || [];
    const div = document.getElementById('results');
    div.style.display = 'block';
    div.innerHTML = '<div style="font-size:14px;font-weight:600;margin-bottom:10px;">Results</div>' +
      results.map(r => `
        <div class="result-card">
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="rank-badge">#${{r.rank}}</div>
            <div><div style="font-weight:600;">${{r.name}}</div><div style="font-size:11px;color:#94A3B8;">${{r.type}}</div></div>
          </div>
          <div class="score">${{r.total_score.toFixed(1)}}%</div>
        </div>
      `).join('');
  }} catch(e) {{
    alert('Analysis failed');
  }}
  btn.textContent = `Compare Selected (${{selected.size}})`;
  btn.disabled = false;
}}

loadSolutions();
</script>
</body>
</html>"""

    return HTMLResponse(content=html)


# --- SDK Info / Documentation ---

@router.get("/deo/public/sdk-info")
async def get_sdk_info(request: Request):
    """[Public API] Get SDK/API integration documentation."""
    key_doc = await verify_deo_api_key(request)

    forwarded_host = request.headers.get("x-forwarded-host", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    else:
        base_url = str(request.base_url).rstrip("/")

    return {
        "name": "View Dezider DEO SDK",
        "version": "1.0.0",
        "base_url": f"{base_url}/api",
        "authentication": {
            "type": "API Key",
            "header": "X-DEO-API-Key",
            "query_param": "api_key",
        },
        "endpoints": {
            "values_api": {
                "url": f"{base_url}/api/deo/public/solutions",
                "method": "GET",
                "description": "Get solutions with quantitative & qualitative factor values",
                "params": ["life_area_id", "type", "country", "language", "limit"],
                "permission": "values_api",
            },
            "full_flow": {
                "url": f"{base_url}/api/deo/public/decision-flow",
                "method": "POST",
                "description": "Full decision flow with predefined options from Solutions Store. Provide assessment percentages per option-factor.",
                "body": {
                    "solution_ids": ["id1", "id2"],
                    "assessments": {"id1": {"Price": 80, "Quality": 90}},
                    "factor_weights": {"Price": 2, "Quality": 1},
                },
                "permission": "full_flow",
            },
            "logic_api": {
                "url": f"{base_url}/api/deo/public/decision-logic",
                "method": "POST",
                "description": "Use our scoring logic with YOUR custom options & factors",
                "body": {
                    "options": [
                        {"name": "Option A", "assessments": {"Cost": 70, "Quality": 85}},
                        {"name": "Option B", "assessments": {"Cost": 90, "Quality": 60}},
                    ],
                    "factors": [
                        {"name": "Cost", "weight": 2, "importance": 80},
                        {"name": "Quality", "weight": 1, "importance": 60},
                    ],
                },
                "permission": "logic_api",
            },
            "widget": {
                "url": f"{base_url}/api/deo/public/widget",
                "method": "GET",
                "description": "Embeddable comparison widget (HTML). Add to your site with iframe.",
                "params": ["api_key", "life_area_id", "theme"],
                "embed": f'<iframe src="{base_url}/api/deo/public/widget?api_key=YOUR_KEY&theme=dark" width="400" height="600" frameborder="0"></iframe>',
                "permission": "full_flow",
            },
        },
        "rate_limit": "1000 requests/day per API key",
        "support": "Contact admin for higher limits",
    }
