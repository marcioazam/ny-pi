"""Model B of bench/tools/gate_sim.py (calibrated on the real sequential gates, RUNBOOK 2026-11-18)."""

import json
import random
from pathlib import Path

from bench import stats
from bench.tools import gate_sim as gs

PRM = (stats.ALPHA1, stats.COST1, stats.TURNS1)
# shape of docs/bench/baseline-main: most tasks 12/12, a few mixed, a few k1 cases
SHAPE = (
    [(12, 12)] * 31 + [(8, 12)] * 2 + [(1, 12)] + [(4, 4)] * 2 + [(1, 1)] * 3 + [(0, 1)]
)


def base_file(tmp: Path) -> Path:
    rows = [
        {"suite": "s4", "task_id": f"t{i}", "rep": r, "passed": r < s, "cost_usd": 1.0, "wall_s": 1.0,
         "security": False, "turns": 5, "error": None}
        for i, (s, n) in enumerate(SHAPE) for r in range(n)
    ]  # fmt: skip
    f = tmp / "runs.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return f


def test_prior_makes_an_all_pass_task_nearly_deterministic() -> None:
    a, b = gs.fit_prior(SHAPE)
    fail_12_12 = (b) / (a + b + 12)  # posterior predictive failure of a 12/12 task
    assert fail_12_12 < 0.01 < 1 / 26  # the legacy shrunk rate (0.5 / 13) is 4%


def test_fixed_base_is_the_observed_round_in_every_iteration(tmp_path: Path) -> None:
    m = gs.load_model(base_file(tmp_path))
    obs = [r["passed"] for t in m for r in t.pool]
    for i in range(3):
        d = gs.draw(m, "a", random.Random(i), fixed=True)
        assert [r["passed"] for r in d.base] == obs


def test_model_b_approves_an_unchanged_pr_most_of_the_time(tmp_path: Path) -> None:
    m = gs.load_model(base_file(tmp_path))
    by = gs.simulate(m, 40, 200, [PRM[0]], [PRM], PRM, 1, ("a",))
    s = gs.summarize(by, PRM, real=True)["a"]
    legacy = gs.summarize(
        gs.simulate(m, 40, 200, [PRM[0]], [PRM], PRM, 1, ("a",), fixed=False),
        PRM,
        real=True,
    )["a"]
    assert s["new"] > legacy["new"] and s["new"] >= 0.8


def test_worker_init_carries_the_cost_override() -> None:
    old = dict(gs.EST)
    try:
        gs._init([], 1, est={"s1": 0.015})
        assert gs.EST["s1"] == 0.015
    finally:
        gs.EST.update(old)
        gs._init([], 2000)
