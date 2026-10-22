"""Transaction monitoring project: synthetic data -> rules -> tuning -> dashboard.
Run: python aml_monitoring.py   (needs pandas, numpy, matplotlib)
To use real data (e.g. IBM AML on Kaggle), replace build_data() with a loader that
returns columns: acct, day, type, amount, country."""
import sqlite3
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rng = np.random.default_rng(42)
DAYS, N = 90, 3000
HR = ["IR", "KP", "SY", "MM"]                      # high-risk jurisdictions
OK = ["US", "GB", "CA", "MX", "IN", "AE"]
IN_T, OUT_T = {"ach_in", "cash_in", "wire_in"}, {"ach_out", "cash_out", "wire_out", "card"}
TRUTH = {"structuring": set(range(100, 125)), "passthrough": set(range(125, 145)),
         "hr_wire": set(range(145, 160))}


def build_data():
    rows = []
    add = lambda a, d, t, x, c="US": rows.append((a, int(d), t, round(float(x), 2), c))
    types = ["card", "ach_out", "ach_in", "cash_in", "cash_out", "wire_in", "wire_out"]
    p = [.40, .10, .12, .12, .10, .08, .08]
    for a in range(N):                              # normal behaviour
        for _ in range(rng.poisson(25)):
            t = rng.choice(types, p=p)
            wire = t.startswith("wire")
            c = rng.choice(HR) if wire and rng.random() < .02 else rng.choice(OK)
            add(a, rng.integers(DAYS), t, rng.lognormal(7 if wire else 5, .9), c)
    for a in range(0, 40):                          # legit cash businesses (false positives)
        d = rng.integers(0, DAYS - 3)
        for k in range(2):
            add(a, d + k, "cash_in", rng.uniform(8200, 9800))
    for a in range(40, 60):                         # legit escrow/payroll pass-through
        d, x = rng.integers(DAYS), rng.uniform(12000, 18000)
        add(a, d, "wire_in", x); add(a, d, "wire_out", x * .95)
    for a in TRUTH["structuring"]:                  # injected typologies
        for _ in range(rng.integers(1, 3)):
            d = rng.integers(0, DAYS - 3)
            for k in range(rng.integers(3, 6)):
                add(a, d + rng.integers(0, 3), "cash_in", rng.uniform(8500, 9950))
    for a in TRUTH["passthrough"]:
        for _ in range(rng.integers(2, 4)):
            d, x = rng.integers(DAYS), rng.uniform(20000, 50000)
            add(a, d, "wire_in", x, rng.choice(OK)); add(a, d, "wire_out", x * rng.uniform(.9, .98), rng.choice(OK))
    for a in TRUTH["hr_wire"]:
        for _ in range(rng.integers(2, 5)):
            add(a, rng.integers(DAYS), rng.choice(["wire_in", "wire_out"]), rng.uniform(8000, 40000), rng.choice(HR))
    return pd.DataFrame(rows, columns=["acct", "day", "type", "amount", "country"])


# ---- rules: each returns the set of alerted accounts -------------------------
def structuring(df, lo=8000, n=3):
    c = df[(df.type == "cash_in") & df.amount.between(lo, 9999.99)]
    m = c.groupby(["acct", "day"]).size().unstack(fill_value=0).reindex(columns=range(DAYS), fill_value=0)
    return set(m.index[m.T.rolling(3, min_periods=1).sum().T.max(axis=1) >= n])

def passthrough(df, amt=10000, ratio=.9):
    g = lambda s: df[df.type.isin(s)].groupby(["acct", "day"]).amount.sum()
    m = pd.concat([g(IN_T).rename("i"), g(OUT_T - {"card"}).rename("o")], axis=1).dropna()
    return set(m[(m.i >= amt) & (m.o >= ratio * m.i)].reset_index().acct)

def hr_wire(df, t=5000):
    return set(df[df.type.str.startswith("wire") & df.country.isin(HR) & (df.amount >= t)].acct)

RULES = {"structuring": (structuring, {"lo": [7000, 8000, 9000], "n": [2, 3, 4]}, {"lo": 7000, "n": 2}),
         "passthrough": (passthrough, {"amt": list(range(2500, 50001, 2500))}, {"amt": 5000}),
         "hr_wire": (hr_wire, {"t": [1000, 2000, 5000, 10000]}, {"t": 1000})}


def score(alerts, truth):
    tp = len(alerts & truth); fp = len(alerts - truth)
    pr = tp / max(len(alerts), 1); rc = tp / len(truth)
    return dict(alerts=len(alerts), tp=tp, fp=fp, precision=round(pr, 3), recall=round(rc, 3),
                f1=round(2 * pr * rc / max(pr + rc, 1e-9), 3))


def grid(d):
    keys = list(d); out = [{}]
    for k in keys:
        out = [{**o, k: v} for o in out for v in d[k]]
    return out


if __name__ == "__main__":
    df = build_data()
    con = sqlite3.connect("aml.db"); df.rename(columns={"acct": "acct"}).to_sql("tx", con, if_exists="replace", index=False)
    sql_hits = {r[0] for r in con.execute(open("queries.sql").read().split(";")[0])}
    print(f"{len(df):,} transactions, {df.acct.nunique():,} accounts | SQL structuring check matches Python: "
          f"{sql_hits == structuring(df, 8000, 3)}")

    sweep, best, base = [], {}, {}
    for name, (fn, space, default) in RULES.items():
        truth = TRUTH[name]
        for prm in grid(space):
            sweep.append({"rule": name, **prm, **score(fn(df, **prm), truth)})
        s = pd.DataFrame([r for r in sweep if r["rule"] == name]).sort_values(["f1", "alerts"], ascending=[False, True])
        best[name] = {k: s.iloc[0][k] for k in space}
        base[name] = score(fn(df, **default), truth)
        best[name] = {k: (int(v) if float(v).is_integer() else v) for k, v in best[name].items()}
    pd.DataFrame(sweep).to_csv("tuning_results.csv", index=False)

    summary = []
    for name, (fn, _, default) in RULES.items():
        t = score(fn(df, **best[name]), TRUTH[name])
        summary.append({"rule": name, "params_before": default, "before_alerts": base[name]["alerts"],
                        "before_precision": base[name]["precision"], "before_recall": base[name]["recall"],
                        "params_after": best[name], "after_alerts": t["alerts"],
                        "after_precision": t["precision"], "after_recall": t["recall"], "_fp_b": base[name]["fp"],
                        "_tp_b": base[name]["tp"], "_fp_a": t["fp"], "_tp_a": t["tp"]})
    S = pd.DataFrame(summary)
    S.drop(columns=[c for c in S if c.startswith("_")]).to_csv("tuning_summary.csv", index=False)
    print(S.drop(columns=[c for c in S if c.startswith("_")]).to_string(index=False))

    # ---- dashboard ----
    fig, ax = plt.subplots(2, 2, figsize=(14, 9)); fig.suptitle("Transaction Monitoring Dashboard (synthetic data)", fontsize=16, weight="bold")
    x = np.arange(len(S)); w = .35
    for off, tag, lab in [(-w / 2, "b", "Before tuning"), (w / 2, "a", "After tuning")]:
        a = ax[0, 0]
        a.bar(x + off, S[f"_tp_{tag}"], w, color="#2a9d8f", label=f"{lab}: true positives")
        a.bar(x + off, S[f"_fp_{tag}"], w, bottom=S[f"_tp_{tag}"], color="#e76f51", alpha=.55 if tag == "b" else 1, label=f"{lab}: false positives")
    ax[0, 0].set_xticks(x, S.rule); ax[0, 0].set_title("Alerts by rule: before vs after tuning"); ax[0, 0].legend(fontsize=7)
    sw = pd.DataFrame(sweep); pt = sw[sw.rule == "passthrough"]
    ax[0, 1].plot(pt.amt, pt.precision, marker="o", label="Precision"); ax[0, 1].plot(pt.amt, pt.recall, marker="s", label="Recall")
    ax[0, 1].plot(pt.amt, pt.f1, "--", label="F1"); ax[0, 1].set_title("Pass-through rule: threshold tuning"); ax[0, 1].set_xlabel("Min inflow ($)"); ax[0, 1].legend()
    ci = df[(df.type == "cash_in") & (df.amount < 15000)].amount
    ax[1, 0].hist(ci, bins=60, color="#264653"); ax[1, 0].axvline(10000, color="red", ls="--"); ax[1, 0].set_yscale("log")
    ax[1, 0].set_title("Cash deposits: spike just under the $10k reporting line"); ax[1, 0].set_xlabel("Deposit amount ($)")
    ax[1, 1].axis("off")
    T = S[["rule", "before_alerts", "before_precision", "before_recall", "after_alerts", "after_precision", "after_recall"]]
    tb = ax[1, 1].table(cellText=T.values, colLabels=["Rule", "Alerts\nbefore", "Prec\nbefore", "Recall\nbefore", "Alerts\nafter", "Prec\nafter", "Recall\nafter"], loc="center")
    tb.auto_set_font_size(False); tb.set_fontsize(9); tb.scale(1, 2.2); ax[1, 1].set_title("Tuning summary")
    plt.tight_layout(); plt.savefig("dashboard.png", dpi=130)
    print("saved dashboard.png")
