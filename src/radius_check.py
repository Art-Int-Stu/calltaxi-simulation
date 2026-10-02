"""
radius_check.py — 평가(집계) 반경 2·3·5km 에서 후보 순위가 유지되는지.

시뮬레이션은 반경과 무관하다. 후보 9곳(sensitivity.select_candidates)을 기본 설정·
seed 42 로 한 번씩 돌려 로그를 얻고, 같은 로그를 반경만 바꿔 집계한다.
결과: outputs/radius_check.csv (새 파일). 기존 파일은 건드리지 않는다.
"""
from __future__ import annotations
import sys, time
import numpy as np, pandas as pd
from scipy import stats
import evaluate as E, load, simulator as S, travel_time as T
import sensitivity as SE

RADII = (2.0, 3.0, 5.0)
OUT = E.OUT_DIR / "radius_check.csv"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    calls = load.load_calls()
    depots = load.load_depots()
    reservation = load.load_reservation_occupancy()
    mx = S.TravelMatrix(T.TravelTime.build(),
                        set(calls["origin_dong_canon"].astype(str))
                        | set(calls["dest_dong_canon"].astype(str)))
    sub = S.slice_period(calls, start=S.REPRESENTATIVE_START, days=S.REPRESENTATIVE_DAYS)
    dong_xy = E.dong_coords()
    sel = SE.select_candidates()
    print(f"콜 {len(sub):,} · 후보 {len(sel)}곳", flush=True)
    import os, pickle
    BUDGET = float(os.environ.get("BUDGET_S", "110"))
    T_START = time.perf_counter()
    cache_base = os.path.expanduser("~/radius_base_log.pkl")
    if os.path.exists(cache_base):
        base_log = pd.read_pickle(cache_base)
    else:
        t0 = time.perf_counter()
        base_log = S.run_placement(None, sub, depots, mx, reservation=reservation, seed=S.SEED)
        base_log.to_pickle(cache_base)
        print(f"before {time.perf_counter()-t0:.0f}s", flush=True)
    rows = pd.read_csv(OUT).to_dict("records") if OUT.exists() else []
    done = {r["cand_id"] for r in rows}
    for r in sel.itertuples():
        if int(r.cand_id) in done:
            continue
        if time.perf_counter() - T_START > BUDGET:
            print("PARTIAL: 시간 예산 소진, 다시 실행하면 이어서 진행", len(done), "/ 9", flush=True)
            return
        t0 = time.perf_counter()
        log = S.run_placement(int(r.cand_id), sub, depots, mx, reservation=reservation, seed=S.SEED)
        for rad in RADII:
            m = E.scope_members(r.lat, r.lon, dong_xy, radius_km=rad)
            b, n = E.scope_pickup(base_log, m)
            a, _ = E.scope_pickup(log, m)
            rows.append(dict(radius_km=rad, cand_id=int(r.cand_id), cand_name=r.cand_name,
                             gu=r.gu, band=r.band, n_dong_scope=len(m), n_calls_scope=n,
                             before=b, after=a, delta=a-b,
                             rate_pct=(a-b)/b*100 if b else np.nan))
        done.add(int(r.cand_id))
        pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
        print(f"  {r.cand_id} {r.cand_name[:14]} {time.perf_counter()-t0:.0f}s", flush=True)
    res = pd.DataFrame(rows)
    p = res.pivot_table(index=["cand_id", "cand_name", "band"], columns="radius_km",
                        values="rate_pct").reset_index()
    p = p.sort_values(3.0)
    print("\n개선율(%) — 음수=개선"); print(p.round(2).to_string(index=False))
    print("\n집계 콜 수"); print(res.pivot_table(index="cand_id", columns="radius_km",
                                               values="n_calls_scope").to_string())
    for rad in (2.0, 5.0):
        rho, _ = stats.spearmanr(p[3.0], p[rad])
        top3 = set(p.nsmallest(3, 3.0)["cand_id"]) == set(p.nsmallest(3, rad)["cand_id"])
        print(f"3km vs {rad:g}km  Spearman {rho:.3f}  상위3 동일 {top3}")
    # 배선 점검: 3km 가 기존 sensitivity base 와 일치해야 함
    old = SE.load_results()
    old = old[old["config"] == "base"].set_index("cand_id")["rate_pct"]
    new = res[res.radius_km == 3.0].set_index("cand_id")["rate_pct"]
    print("3km vs 기존 sensitivity base 최대차:", float((new - old.reindex(new.index)).abs().max()))
    print("저장:", OUT)

if __name__ == "__main__":
    main()
