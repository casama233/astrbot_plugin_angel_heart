from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# P2 source-debt baselines captured from canonical master on 2026-08-31.
# Generated WebUI assets are intentionally not covered here: the Cary release
# gate already rebuilds them from lockfile and verifies reproducibility.
SHRINK_ONLY_MAX_BYTES = {
    "roles/front_desk.py": 85_577,
    "core/conversation_ledger.py": 65_445,
}


def test_large_orchestration_modules_are_shrink_only() -> None:
    over_budget: list[str] = []
    for relative_path, maximum in SHRINK_ONLY_MAX_BYTES.items():
        path = ROOT / relative_path
        actual = path.stat().st_size
        if actual > maximum:
            over_budget.append(
                f"{relative_path}: {actual:,} > {maximum:,} bytes"
            )

    assert not over_budget, (
        "Angel Heart large orchestration modules exceeded their P2 "
        "shrink-only architecture budget:\n- "
        + "\n- ".join(over_budget)
        + "\nExtract new isolated behavior into focused core/roles helpers with "
        "regression coverage. When an extraction makes a guarded module "
        "smaller, lower its ceiling in this test instead of raising it."
    )
