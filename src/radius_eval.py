"""
radius_eval.py — 244곳 전체: 평가(집계) 반경 2·3·5km 에서 순위가 유지되는가 (계획 B).

시뮬레이션은 반경과 무관하다. 후보마다 기본 설정으로 한 번 돌린 로그를 반경만
바꿔 집계한다. 3km 값은 placement_eval.csv 의 같은 시드 값과 정확히 같아야 한다(배선 점검).

    DATA_DIR=. PYTHONPATH=src python src/radius_eval.py --seed 42   # 이어서 실행(시간 예산 BUDGET_S)
    PYTHONPATH=src python src/radius_eval.py --check                  # 배선 점검
결과: outputs/radius_eval.csv (새 파일). 기존 파일은 건드리지 않는다.
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
import numpy as np, pandas as pd
import evaluate as E

RADII = (2.0, 3.0, 5.0)
OUT = E.OUT_DIR / "radius_eval.csv"
COLS = ["seed", "radius_km", "cand_id", "cand_name", "gu", "n_dong_scope",
        "n_calls_scope", "before", "after", "delta", "rate_pct", "elapsed_s"]


def done_set():
    if not OUT.exists():
        return set()
    d = pd.read_csv(OUT, encoding="utf-8-sig")
    g = d.groupby(["seed", "cand_id"])["radius_km"].nunique()
    return set(g[g == len(RADII)].index)


def run(seed: int, budget: float):
    import load, simulator as S, travel_time as T
    t_start = time.perf_counter()
    cands = E.candidate_table()
    done = done_set()
    todo = [r for r in cands.itertuples() if (seed, int(r.cand_id)) not in done]
    print(f"seed {seed}: 완료 {len(cands)-len(todo)}/{len(cands)}", flush=True)
    if not todo:
        return 0
    calls = load.load_calls()
    depots = load.load_depots()
    reservation = load.load_reservation_occupancy()
    mx = S.TravelMatrix(T.TravelTime.build(),
                        set(calls["origin_dong_canon"].astype(str))
                        | set(calls["dest_dong_canon"].astype(str)))
    sub = S.slice_period(calls, start=S.REPRESENTATIVE_START, days=S.REPRESENTATIVE_DAYS)
    dong_xy = E.dong_coords()
    bpath = Path(os.path.expanduser(f"~/radius_base_seed{seed}.pkl"))
    if bpath.exists():
        base_log = pd.read_pickle(bpath)
    else:
        base_log = S.run_placement(None, sub, depots, mx, reservation=reservation, seed=seed)
        base_log.to_pickle(bpath)
    print(f"  준비 {time.perf_counter()-t_start:.0f}s", flush=True)
    n = 0
    for r in todo:
        if time.perf_counter() - t_start > budget:
            break
        t0 = time.perf_counter()
        log = S.run_placement(int(r.cand_id), sub, depots, mx, reservation=reservation, seed=seed)
        el = time.perf_counter() - t0
        rows = []
        for rad in RADII:
            m = E.scope_members(r.lat, r.lon, dong_xy, radius_km=rad)
            b, nc = E.scope_pickup(base_log, m)
            a, _ = E.scope_pickup(log, m)
            rows.append(dict(seed=seed, radius_km=rad, cand_id=int(r.cand_id),
                             cand_name=r.cand_name, gu=r.gu, n_dong_scope=len(m),
                             n_calls_scope=nc, before=b, after=a, delta=a - b,
                             rate_pct=(a - b) / b * 100 if b else np.nan, elapsed_s=el))
        pd.DataFrame(rows, columns=COLS).to_csv(OUT, mode="a", header=not OUT.exists(),
                                                index=False, encoding="utf-8-sig")
        n += 1
        print(f"  [seed {seed}] {len(cands)-len(todo)+n}/{len(cands)}  {int(r.cand_id)}  {el:.0f}s", flush=True)
    left = len(todo) - n
    print(f"  이번 {n}곳 · 남은 {left}곳 · {time.perf_counter()-t_start:.0f}s", flush=True)
    return left


def check():
    d = pd.read_csv(OUT, encoding="utf-8-sig")
    d = d[d.radius_km == 3.0]
    ev = E.load_results()
    m = d.merge(ev[["seed", "cand_id", "rate_pct", "n_calls_scope"]],
                on=["seed", "cand_id"], suffixes=("", "_ev"))
    dif = (m.rate_pct - m.rate_pct_ev).abs()
    print(f"배선 점검: {len(m)}행 대조, 최대차 {dif.max():.3e}%p, "
          f"콜수 불일치 {(m.n_calls_scope != m.n_calls_scope_ev).sum()}건 → "
          f"{'일치' if dif.max() < 1e-9 else '**어긋남**'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check()
    else:
        left = run(a.seed, float(os.environ.get("BUDGET_S", "140")))
        print("LEFT", left)
