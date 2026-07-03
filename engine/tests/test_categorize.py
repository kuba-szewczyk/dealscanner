"""Tests for the deterministic category classifier."""
from dealscanner_engine.categorize import derive_category


def test_hvac_is_construction():
    assert derive_category("Charlotte Commercial HVAC Contractor") == "Construction & Trades"


def test_auto_repair_is_auto():
    assert derive_category("Established automotive repair shop in Marietta") == "Auto & Transport"


def test_accounting_practice_is_professional_services():
    # 'practice' must NOT route to Healthcare; accounting wins.
    assert derive_category("Northwest Metro Detroit Accounting, Audit & Tax Practice") == "Professional Services"


def test_dental_is_healthcare():
    assert derive_category("Profitable Dental Practice for Sale") == "Healthcare"


def test_optometry_is_healthcare():
    assert derive_category("Optometry practice, established 30 years") == "Healthcare"


def test_self_storage_is_real_estate():
    assert derive_category("North Georgia Self Storage - 3 locations") == "Real Estate & Property"


def test_montessori_is_education():
    assert derive_category("Montessori School", "Montessori school in Alexandria, VA") == "Education & Childcare"


def test_distributor_is_distribution():
    assert derive_category("Tenured, Profitable Southeastern Metal Distributor") == "Distribution & Wholesale"


def test_restaurant_is_food():
    assert derive_category("Joe's Pizzeria & Tavern") == "Restaurant & Food"


def test_unmatched_is_other():
    assert derive_category("Mysterious holding company with no detail") == "Other"


def test_combines_multiple_text_fields():
    assert derive_category("Acme Corp", None, "manufacturer of luxury products") == "Manufacturing"
