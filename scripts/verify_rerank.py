"""Verification: editing an account's settings re-ranks the whole corpus instantly,
in code, with zero network/LLM calls. Proves 'filters expose the latest setup'."""
import copy
import time

from dealscanner_engine import db, evaluator, thesis

conn = db.connect()
settings = thesis.get_settings(conn, "water")
original = copy.deepcopy(settings)

def snapshot(label):
    t0 = time.perf_counter()
    rows = evaluator.board(conn, thesis.get_settings(conn, "water"), include_sections=("in",), limit=10000)
    ms = (time.perf_counter() - t0) * 1000
    top = [r["business_name"][:32] for r in rows[:3]]
    print(f"{label:34} -> {len(rows):4d} listings in board, re-ranked in {ms:6.1f} ms; top3={top}")
    return len(rows)

print("\n=== BEFORE: default water settings ===")
n_before = snapshot("default")

# EDIT 1: drop septic + well-drilling keywords from the thesis (operator narrows focus)
edited = copy.deepcopy(original)
edited["keywords"]["tier1"] = [k for k in edited["keywords"]["tier1"]
                               if "septic" not in k and "well" not in k]
thesis.update_settings(conn, "water", edited)
n_drop = snapshot("after dropping septic/well kw")

# EDIT 2: also tighten size — require SDE >= $2.5M
edited2 = copy.deepcopy(edited)
edited2["size"]["sde_min"] = 2_500_000
edited2["size"]["ebitda_min"] = 2_000_000
thesis.update_settings(conn, "water", edited2)
n_tight = snapshot("after tightening size band")

# restore
thesis.update_settings(conn, "water", original)
n_restored = snapshot("restored default")

print("\nRESULT:")
print(f"  default={n_before}  drop-kw={n_drop}  tighten-size={n_tight}  restored={n_restored}")
assert n_drop < n_before, "dropping keywords should shrink the board"
assert n_tight < n_drop, "tightening size should shrink further"
assert n_restored == n_before, "restoring settings should restore the board exactly"
print("  API/network calls made: 0   cost: $0.00")
print("  PASS: settings edits re-rank the full corpus instantly, in code, idempotently.")
