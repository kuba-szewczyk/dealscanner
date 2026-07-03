"""Deterministic category classifier — recovers a real industry from listing text.

The v1 import left ~2,700 listings tagged 'Other'. This re-derives a meaningful
category from name + take + full_text using an ordered keyword taxonomy (first match
wins, so specific trades beat generic 'shop'/'store'). Pure + free; run at ingest and
as a one-off backfill. Returns 'Other' only when nothing matches.
"""
from __future__ import annotations

# Ordered: earlier categories win. Specific industries before generic retail/services.
TAXONOMY: list[tuple[str, list[str]]] = [
    ("Healthcare", ["dental", "dentist", "orthodon", "optometr", "optical", "vision care",
                    "medical", "physician", "clinic", "pharmac", "veterinar", " vet ",
                    "chiropract", "physical therapy", "home health", "hospice", "nursing",
                    "urgent care", "healthcare", "health care", "dermatolog", "audiolog",
                    "behavioral health", "medspa", "med spa", "imaging", "cardiolog"]),
    ("Education & Childcare", ["montessori", "school", "academy", "daycare", "day care",
                              "childcare", "child care", "preschool", "tutoring", "learning center",
                              "education"]),
    ("Restaurant & Food", ["restaurant", "pizz", "cafe", "café", "bakery", " deli", "catering",
                           "brewery", "taqueria", "diner", "bistro", "bar & grill", "bar and grill",
                           " grill", "coffee", "food truck", "ice cream", "juice bar", "donut",
                           "doughnut", "sandwich", "eatery", "tavern", "nightclub", "food & beverage"]),
    ("Construction & Trades", ["construction", "contractor", "hvac", "plumb", "electrical",
                               "electrician", "roofing", "concrete", "excavat", "landscap",
                               "remodel", "builder", "mechanical", "paving", "masonry", "fencing",
                               "drywall", "glazing", "millwork", "insulation", "demolition",
                               "septic", "grading", "utility", "infrastructure"]),
    ("Manufacturing", ["manufactur", "fabricat", "machine shop", "foundry", "plastics", "molding",
                       "injection", "tooling", "machining", "metal fab", "production facility",
                       "assembly", "extrusion", "cnc"]),
    ("Auto & Transport", ["automotive", "auto repair", "auto body", "car wash", "carwash", "towing",
                          "dealership", " tire", "collision", "body shop", "transmission",
                          "auto service", "lube", "fleet"]),
    ("Distribution & Wholesale", ["distribut", "wholesale", "supplier", "logistics", "freight",
                                  "trucking", "transportation", "warehous", "supply company",
                                  "supply co"]),
    ("Personal Care & Fitness", ["salon", " spa", "barber", "fitness", "gym", "yoga", "massage",
                                 "tanning", "tattoo", " nails", "nail ", "wellness", "grooming",
                                 "pet ", "laundr", "dry clean"]),
    ("Cleaning & Facilities", ["cleaning", "janitorial", "restoration", "pest control",
                               "landscaping maintenance", "facility services", "disaster restoration"]),
    ("Real Estate & Property", ["real estate", "property management", "self storage", "self-storage",
                                "storage", "rental propert", "mobile home", "rv park", "apartment",
                                "commercial property"]),
    ("Hospitality & Lodging", ["hotel", "motel", "lodging", " inn", "bed & breakfast",
                               "bed and breakfast", "campground", "resort"]),
    ("Professional Services", ["accounting", " cpa", "bookkeep", "insurance", "marketing",
                               "advertising", "consulting", "staffing", "recruiting", "engineering",
                               "architect", "legal", "law firm", "financial", " tax ", "agency",
                               "it services", "managed services", "saas", "software"]),
    ("Retail & E-commerce", ["retail", " store", "boutique", "ecommerce", "e-commerce", "online store",
                             "amazon", "shopify", " shop", "dealer", "convenience", "liquor",
                             "smoke shop", "dispensary", "gas station"]),
]


def derive_category(*texts: str | None) -> str:
    """Return the first matching category for the combined text, else 'Other'."""
    t = " ".join(x for x in texts if x).lower()
    for label, kws in TAXONOMY:
        if any(kw in t for kw in kws):
            return label
    return "Other"


# The final, consolidated display buckets (everything maps into one of these; each ends up 10+).
CANONICAL = {label for label, _ in TAXONOMY} | {"Other"}

# Raw/legacy category strings -> a canonical bucket (folds the long tail so nothing is < ~10).
ALIASES = {
    # Restaurant & Food (bars, fast food, food service)
    "bar": "Restaurant & Food", "bar/taproom": "Restaurant & Food", "fast food": "Restaurant & Food",
    "fast casual": "Restaurant & Food", "food service": "Restaurant & Food",
    "culinary - cooking classes": "Restaurant & Food",
    # Auto & Transport (salvage)
    "auto salvage": "Auto & Transport", "auto recycling": "Auto & Transport",
    "truck salvage": "Auto & Transport",
    # Professional Services (generic services, rental, office, tech, printing, B2B, events)
    "services": "Professional Services", "service": "Professional Services",
    "service businesses": "Professional Services", "office services": "Professional Services",
    "repair services": "Professional Services", "industrial services": "Professional Services",
    "rental": "Professional Services", "equipment rental": "Professional Services",
    "event rental services": "Professional Services", "event services": "Professional Services",
    "printing": "Professional Services", "b2b sales": "Professional Services",
    "trade show displays & exhibits": "Professional Services", "information": "Professional Services",
    "online and technology": "Professional Services",
    # Healthcare (specialties, senior care)
    "ophthalmology": "Healthcare", "nephrology": "Healthcare", "assisted living": "Healthcare",
    # Personal Care & Fitness (beauty)
    "beauty services": "Personal Care & Fitness", "beauty & personal care": "Personal Care & Fitness",
    # Retail & E-commerce
    "cannabis": "Retail & E-commerce", "consumer products": "Retail & E-commerce",
    # Manufacturing
    "solar/energy": "Manufacturing", "personal protective equipment": "Manufacturing",
    "scrap metal": "Manufacturing",
    # Distribution & Wholesale (logistics/shipping)
    "moving and shipping": "Distribution & Wholesale",
    # Construction & Trades (home improvement)
    "kitchen renovation": "Construction & Trades", "home improvement": "Construction & Trades",
    "garage door installation and service": "Construction & Trades",
    # Education & Childcare
    "franchise - children's services": "Education & Childcare",
    # Hospitality & Lodging (recreation, entertainment, events, marinas, accommodation)
    "marina": "Hospitality & Lodging", "entertainment": "Hospitality & Lodging",
    "entertainment/bar": "Hospitality & Lodging", "recreation & tourism": "Hospitality & Lodging",
    "event venue": "Hospitality & Lodging", "accommodation and food services": "Hospitality & Lodging",
    # Other (agriculture is too small to stand alone)
    "agriculture": "Other", "agriculture - vineyards and wineries": "Other",
    "agriculture - greenhouse produce": "Other", "tree farms & orchards": "Other",
}


def canonical_category(raw: str | None, *texts: str | None) -> str:
    """Map any (possibly raw broker-supplied) category to one of CANONICAL.
    Already-canonical kept · known aliases folded · else derive from text · else 'Other'.
    Keeps the display buckets to ~14 and stops new tiny categories from appearing."""
    r = (raw or "").strip()
    if r in CANONICAL:
        return r
    if r.lower() in ALIASES:
        return ALIASES[r.lower()]
    return derive_category(r, *texts)
