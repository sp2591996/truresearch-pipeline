"""
203_refresh_bank_annual_financials.py
-------------------------------------------------------------------
Fills `bank_annual_financials` (202_create_bank_annual_financials.sql --
run that SQL file in Supabase first) with each listed Indian bank's
full-year figures, the bank on its own (standalone), as filed with NSE.

Where the numbers come from:
  Every listed bank files its results with NSE in XBRL, a standard
  machine-readable format. The March-quarter filing carries the full
  fiscal year (income statement) and the year-end balance sheet.
  - FY25 onwards: NSE's "Integrated Filing - Financials" list
    (nse.iter_financial_results_with_xbrl), the system SEBI moved
    results to in 2025.
  - Up to FY24: NSE's older results list (nse.financial_results).
  Both use the same XBRL labels (InterestEarned, Deposits, ...).
  Uses the `nse` package (version 5 or later) already used by this
  project for shareholding, IPOs and quarterly results.

Which banks: every active Indian stock in the Private Sector Banks and
Public Sector Banks industries, so a newly listed bank is picked up
without editing this file.

Safe to re-run any time:
  - A filing already saved (same file link) is not downloaded again,
    so a weekly run usually only checks the lists and finishes quickly.
  - Every year goes through sanity checks before it is saved (deposits
    and net worth above zero, interest earned above interest paid, bad
    loans under 40%, and no tenfold jump from the year before). A year
    that fails is NOT saved and is listed at the end for a person to
    look at.

Run:
    python 203_refresh_bank_annual_financials.py            # preview only, saves nothing
    python 203_refresh_bank_annual_financials.py --write    # save to the database
    python 203_refresh_bank_annual_financials.py --write --only SBIN HDFCBANK
-------------------------------------------------------------------
"""
import argparse
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

from nse import NSE

from db_client import get_client
from ingestion_log import finish_run, start_run

MARKET = "india"
BANK_INDUSTRIES = ["Private Sector Banks", "Public Sector Banks"]
YEARS_BACK = 4  # FY23-FY26 today, the four years the page shows
REQUEST_DELAY_SECONDS = 1.0
RETRY_DELAY_SECONDS = 5
CRORE = 1e7

XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"

# XBRL label -> (column, kind). "flow" = full-year amount, "stock" = year-end
# amount, "ratio" = a fraction filed as 0.0149 for 1.49%.
FIELDS = {
    "InterestEarned": ("interest_earned_cr", "flow"),
    "InterestExpended": ("interest_expended_cr", "flow"),
    "OtherIncome": ("other_income_cr", "flow"),
    "OperatingExpenses": ("operating_expenses_cr", "flow"),
    "ProvisionsOtherThanTaxAndContingencies": ("provisions_cr", "flow"),
    "ProfitLossFromOrdinaryActivitiesBeforeTax": ("profit_before_tax_cr", "flow"),
    "ProfitLossForThePeriod": ("net_profit_cr", "flow"),
    "BasicEarningsPerShareAfterExtraordinaryItems": ("eps", "per_share"),
    "Deposits": ("deposits_cr", "stock"),
    "Borrowings": ("borrowings_cr", "stock"),
    "Advances": ("advances_cr", "stock"),
    "Investments": ("investments_cr", "stock"),
    "Capital": ("_capital", "stock"),
    "ReservesAndSurplus": ("_reserves", "stock"),
    "Assets": ("total_assets_cr", "stock"),
    "PercentageOfGrossNpa": ("gross_npa_pct", "ratio"),
    "PercentageOfNpa": ("net_npa_pct", "ratio"),
    "ReturnOnAssets": ("return_on_assets_pct", "ratio"),
    "CET1Ratio": ("cet1_pct", "ratio"),
    "GrossNonPerformingAssets": ("_gnpa_amt", "flow"),  # amounts, to check the filed ratios
    "NonPerformingAssets": ("_nnpa_amt", "flow"),
}
# Used only when the main label is missing from a filing: column -> (label, kind).
FALLBACKS = {
    "net_profit_cr": ("ProfitLossFromOrdinaryActivitiesAfterTax", "flow"),
    "eps": ("BasicEarningsPerShareBeforeExtraordinaryItems", "per_share"),
}


# ---------------------------------------------------------------------------
# Reading one XBRL filing
# ---------------------------------------------------------------------------

def _d(text):
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()


def parse_filing(path: Path, fy_end: date) -> dict:
    """Return {column: value} for the fiscal year ending fy_end."""
    root = ET.parse(path).getroot()
    contexts = {}
    for c in root.iter(f"{XBRLI}context"):
        has_dims = any(True for _ in c.iter(f"{XBRLDI}explicitMember")) or any(True for _ in c.iter(f"{XBRLDI}typedMember"))
        p = c.find(f"{XBRLI}period")
        inst = p.find(f"{XBRLI}instant")
        if inst is not None:
            contexts[c.get("id")] = {"instant": _d(inst.text), "dims": has_dims}
        else:
            contexts[c.get("id")] = {"start": _d(p.find(f"{XBRLI}startDate").text), "end": _d(p.find(f"{XBRLI}endDate").text), "dims": has_dims}

    # The full-year context. NSE filings name it "FourD"; older filings
    # sometimes date it like the quarter by mistake, so the name wins.
    # Otherwise: the longest undimensioned period ending at the year end.
    durations = [(cid, c) for cid, c in contexts.items() if not c["dims"] and "end" in c and c["end"] == fy_end]
    year_ctx = "FourD" if "FourD" in contexts and not contexts["FourD"]["dims"] else None
    if year_ctx is None and durations:
        year_ctx = max(durations, key=lambda x: (x[1]["end"] - x[1]["start"]).days)[0]
        if (contexts[year_ctx]["end"] - contexts[year_ctx]["start"]).days < 300:
            year_ctx = None  # only a quarter available; don't pass it off as a year
    instant_ctxs = {cid for cid, c in contexts.items() if not c["dims"] and c.get("instant") == fy_end}
    # Some FY23-and-earlier filings use "FourD" / "OneI" without ever defining
    # them. NSE's naming is consistent, so fall back to the names.
    if year_ctx is None and "FourD" not in contexts:
        year_ctx = "FourD"
    if not instant_ctxs:
        instant_ctxs = {cid for cid in ("FourI", "OneI") if cid not in contexts}

    facts = {}
    for el in root:
        label = el.tag.split("}")[-1]
        cref = el.get("contextRef")
        if cref is None or el.text is None:
            continue
        facts.setdefault(label, {})[cref] = el.text.strip()

    def value(label, kind):
        found = facts.get(label, {})
        if kind == "stock":
            raw = next((found[c] for c in instant_ctxs if c in found), None)
        else:
            raw = found.get(year_ctx) if year_ctx else None
        if raw in (None, ""):
            return None
        try:
            v = float(raw)
        except ValueError:
            return None
        if kind in ("flow", "stock"):
            return round(v / CRORE, 2)
        if kind == "ratio":
            return round(v * 100, 4) if abs(v) < 1 else round(v, 4)  # 0.0149 -> 1.49; tolerate filers who send 1.49
        return v

    out = {}
    for label, (col, kind) in FIELDS.items():
        out[col] = value(label, kind)
    for col, (label, kind) in FALLBACKS.items():
        if out.get(col) is None:
            out[col] = value(label, kind)
    cap, res = out.pop("_capital"), out.pop("_reserves")
    out["net_worth_cr"] = round(cap + res, 2) if cap is not None and res is not None else None

    # Bad-loan ratios: some banks file them in the wrong scale (Yes Bank FY24
    # filed 0.0002 for 2%). Where the amounts and the loan book are filed,
    # work the ratios out and use those if the filed ones disagree.
    gnpa_amt, nnpa_amt, adv = out.pop("_gnpa_amt"), out.pop("_nnpa_amt"), out.get("advances_cr")
    out["_notes"] = []
    if gnpa_amt and nnpa_amt is not None and adv:
        gross_book = adv + gnpa_amt - nnpa_amt
        calc = {"gross_npa_pct": gnpa_amt / gross_book * 100, "net_npa_pct": nnpa_amt / adv * 100}
        for col, v in calc.items():
            filed = out.get(col)
            if filed is None or abs(filed - v) > max(0.25, 0.3 * v):
                out["_notes"].append(f"{col} filed as {filed}, worked out as {v:.2f} from the amounts; using {v:.2f}")
                out[col] = round(v, 4)
    else:
        for col in ("gross_npa_pct", "net_npa_pct"):
            if out.get(col) is not None and out[col] < 0.1:
                out["_notes"].append(f"{col} filed as {out[col]}, too low to be right and no amounts to check it; left blank")
                out[col] = None
    nature = facts.get("NatureOfReportStandaloneConsolidated", {})
    out["_nature"] = next(iter(nature.values()), "")
    return out


# ---------------------------------------------------------------------------
# Checks before saving
# ---------------------------------------------------------------------------

def problems(row: dict, previous: dict | None, db_group_profit: float | None) -> list[str]:
    p = []
    # Against our database: `fundamentals` holds group profit, which runs up to
    # about 35% above the bank's own (Kotak). Far outside that means the
    # filing itself is mis-tagged (IOB's FY23 XBRL says 4,957 Cr; the bank
    # reported 2,099 Cr).
    if db_group_profit and row.get("net_profit_cr") and db_group_profit > 0:
        ratio = row["net_profit_cr"] / db_group_profit
        if ratio < 0.6 or ratio > 1.6:
            p.append(f"net profit {row['net_profit_cr']:,.0f} Cr is {ratio:.1f}x the database's group profit {db_group_profit:,.0f} Cr")
    # Income lines must be there. Older filings (FY23 and before) carry no
    # balance sheet; those years are saved with income lines only and the
    # balance-sheet checks below simply don't apply.
    need = ["interest_earned_cr", "interest_expended_cr", "net_profit_cr"]
    missing = [k for k in need if row.get(k) is None]
    if missing:
        p.append(f"missing {', '.join(missing)}")
        return p
    bs = [row.get(k) for k in ("deposits_cr", "net_worth_cr", "total_assets_cr")]
    if any(v is not None for v in bs) and None in bs:
        p.append("balance sheet only partly filed")
    if all(v is not None for v in bs) and min(bs) <= 0:
        p.append("deposits, net worth or total assets not above zero")
    if not (0 < row["interest_expended_cr"] < row["interest_earned_cr"]):
        p.append("interest paid not between zero and interest earned")
    if row["net_profit_cr"] > row["interest_earned_cr"] + (row.get("other_income_cr") or 0):
        p.append("net profit larger than total income")
    if row.get("deposits_cr") and row.get("total_assets_cr") and row["deposits_cr"] > row["total_assets_cr"]:
        p.append("deposits larger than total assets")
    for k in ("gross_npa_pct", "net_npa_pct"):
        if row.get(k) is not None and not (0 <= row[k] < 40):
            p.append(f"{k} outside 0-40%")
    if previous:
        for k in ("interest_earned_cr", "deposits_cr", "total_assets_cr"):
            a, b = row.get(k), previous.get(k)
            if a and b and (a / b > 10 or b / a > 10):
                p.append(f"{k} moved more than tenfold from the year before")
    return p


# ---------------------------------------------------------------------------
# Finding the filings
# ---------------------------------------------------------------------------

def call(fn, *args, **kwargs):
    try:
        out = fn(*args, **kwargs)
    except Exception:
        time.sleep(RETRY_DELAY_SECONDS)
        out = fn(*args, **kwargs)  # a second failure raises normally
    time.sleep(REQUEST_DELAY_SECONDS)
    return out


def _when(text):
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime((text or "").strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def find_filings(nse, symbol: str, years: list[date], need_old: bool) -> dict:
    """{fiscal_year_end: (xbrl_url, filed_at)} for the standalone March filing of each year."""
    found = {}
    # FY25 onwards: integrated filing
    for r in call(lambda: list(nse.iter_financial_results_with_xbrl(symbol=symbol))):
        if str(r.get("consolidated", "")).lower() != "standalone" or not r.get("xbrl"):
            continue
        qe = _when(r.get("qe_Date", "").title()).date()
        if qe not in years:
            continue
        when = max(_when(r.get("revised_Date")), _when(r.get("creation_Date")), _when(r.get("broadcast_Date")))
        if qe not in found or when > found[qe][1]:
            found[qe] = (r["xbrl"], when)
    # Up to FY24: the older results list (annual first, Q4 quarterly as a fallback)
    if need_old:
        for period in ("annual", "quarterly"):
            for r in call(nse.financial_results, period=period, symbol=symbol) or []:
                if "non" not in str(r.get("consolidated", "")).lower() or not r.get("xbrl"):
                    continue
                if str(r.get("audited", "")).lower().startswith("un"):
                    continue
                qe = _when(r.get("toDate")).date()
                if qe not in years or (qe in found and found[qe][0].find("INTEGRATED") >= 0):
                    continue
                when = max(_when(r.get("filingDate")), _when(r.get("broadCastDate")))
                if qe not in found or when > found[qe][1]:
                    found[qe] = (r["xbrl"], when)
    return found


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="save to the database (default: preview only)")
    ap.add_argument("--only", nargs="*", help="limit to these tickers")
    args = ap.parse_args()

    sb = get_client()
    industries = sb.table("industries").select("industry_id, name").in_("name", BANK_INDUSTRIES).execute().data
    ind_ids = [i["industry_id"] for i in industries]
    banks = (
        sb.table("assets").select("asset_id, ticker").eq("market", MARKET).eq("asset_type", "equity").eq("is_active", True)
        .in_("industry_id", ind_ids).order("ticker").execute().data
    )
    if args.only:
        wanted = {t.upper() for t in args.only}
        banks = [b for b in banks if b["ticker"] in wanted]
    today = date.today()
    last_fy = today.year if today.month >= 4 else today.year - 1  # FY ending 31 Mar of this year once April starts
    years = [date(last_fy - i, 3, 31) for i in range(YEARS_BACK)]
    print(f"{'PREVIEW (nothing saved)' if not args.write else 'WRITING'}: {len(banks)} banks, fiscal years {years[-1].year}-{years[0].year}\n")

    saved = {}
    if banks:
        try:
            for r in sb.table("bank_annual_financials").select("*").in_("asset_id", [b["asset_id"] for b in banks]).eq("basis", "standalone").execute().data:
                saved[(r["asset_id"], r["fiscal_year_end"])] = r
        except Exception as e:
            if args.write:
                raise SystemExit(f"Can't read bank_annual_financials ({e}). Run 202_create_bank_annual_financials.sql in Supabase first.")
            print("(Table bank_annual_financials not there yet -- fine for a preview. Run 202_create_bank_annual_financials.sql before --write.)\n")

    # The database's own (group) profit per bank per year, for the cross-check.
    group_profit = {}
    if banks:
        for f in sb.table("fundamentals").select("asset_id, fiscal_year_end_date, net_income").in_("asset_id", [b["asset_id"] for b in banks]).execute().data:
            if f["net_income"] is not None:
                group_profit[(f["asset_id"], f["fiscal_year_end_date"])] = f["net_income"] / CRORE

    run_id = start_run("bank_annual_financials") if args.write else None
    ok, failed, flagged, written = [], [], [], 0

    with tempfile.TemporaryDirectory() as tmp, NSE(download_folder=tmp) as nse:
        for n, b in enumerate(banks, 1):
            t, aid = b["ticker"], b["asset_id"]
            print(f"[{n}/{len(banks)}] {t}")
            old_years_missing = any((aid, y.isoformat()) not in saved for y in years if y < date(2025, 3, 31))
            try:
                filings = find_filings(nse, t, years, need_old=old_years_missing)
            except Exception as e:
                print(f"   couldn't list filings: {e}")
                failed.append(t)
                continue
            rows = {}
            for fy in sorted(filings):
                url, filed = filings[fy]
                have = saved.get((aid, fy.isoformat()))
                if have and have.get("source_url") == url:
                    rows[fy] = have
                    continue
                try:
                    path = call(nse.download_document, url, folder=tmp)
                    data = parse_filing(Path(path), fy)
                except Exception as e:
                    print(f"   FY{str(fy.year)[2:]}: couldn't read the filing ({e})")
                    flagged.append(f"{t} FY{str(fy.year)[2:]}: unreadable filing {url}")
                    continue
                nature = data.pop("_nature")
                if nature and "standalone" not in nature.lower():
                    flagged.append(f"{t} FY{str(fy.year)[2:]}: filing says '{nature}', expected Standalone")
                    continue
                prev = rows.get(date(fy.year - 1, 3, 31)) or saved.get((aid, date(fy.year - 1, 3, 31).isoformat()))
                issues = problems(data, prev, group_profit.get((aid, fy.isoformat())))
                label = f"FY{str(fy.year)[2:]}"
                for note in data.pop("_notes"):
                    print(f"   {label}: note, {note}")
                    flagged.append(f"{t} {label} (saved): {note}")
                if issues:
                    print(f"   {label}: NOT saved, {'; '.join(issues)}")
                    flagged.append(f"{t} {label}: {'; '.join(issues)}")
                    continue
                record = {
                    "asset_id": aid,
                    "fiscal_year_end": fy.isoformat(),
                    "basis": "standalone",
                    **data,
                    "source": "nse",
                    "source_url": url,
                    "filed_at": filed.replace(tzinfo=timezone.utc).isoformat() if filed != datetime.min else None,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                rows[fy] = record
                fmt = lambda v: "-" if v is None else f"{v:,.0f}"  # noqa: E731
                print(
                    f"   {label}: interest earned {fmt(data['interest_earned_cr'])} | net profit {fmt(data['net_profit_cr'])} | "
                    f"deposits {fmt(data.get('deposits_cr'))} | net worth {fmt(data.get('net_worth_cr'))} | GNPA {data.get('gross_npa_pct')}"
                    + ("" if args.write else "  (preview)")
                )
                if args.write:
                    sb.table("bank_annual_financials").upsert(record, on_conflict="asset_id,fiscal_year_end,basis").execute()
                    written += 1
            missing = [f"FY{str(y.year)[2:]}" for y in years if y not in filings]
            if missing:
                print(f"   no filing found for {', '.join(missing)}")
            ok.append(t)

    if run_id is not None:
        finish_run(run_id, ok_count=len(ok), failed_symbols=failed)
    print(f"\nDone. {len(ok)}/{len(banks)} banks checked, {written} year-rows saved{'' if args.write else ' (preview: run with --write to save)'}.")
    if failed:
        print(f"Couldn't reach NSE for: {', '.join(failed)}")
    if flagged:
        print(f"\n{len(flagged)} year(s) held back for a person to look at:")
        for f in flagged:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
