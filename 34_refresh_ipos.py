"""
34_refresh_ipos.py
-------------------------------------------------------------------
Fills the `ipos` table (PRD.md H1 / Wireframes.md "IPO Tracker") --
this table existed since 01_create_tables.sql but had zero rows and
no ingestion script until now, same situation shareholding_pattern
was in before 25_shareholding_refresh.py.

Data source: the `nse` PyPI package (already used for
shareholding_pattern -- see 25_shareholding_refresh.py), which exposes
3 real IPO-listing endpoints, confirmed by 31_check_nse_ipo_api.py
before this script was written (never guessed at an API that might
not exist):
    nse.listUpcomingIPO()  -- IPOs that haven't opened yet
    nse.listCurrentIPO()   -- IPOs currently open for subscription
                              (includes a subscription multiplier,
                              per bidder category -- this script keeps
                              only the "Total" row per IPO)
    nse.listPastIPO()      -- recently closed/listed IPOs

SME exclusion (added after Avdhoot's explicit instruction: "make sure
you dont include SME IPOs into this"): NSE lists SME-platform IPOs
(NSE Emerge) alongside mainboard IPOs on the same 3 endpoints. Each
row carries a `series` (current/upcoming IPOs) or `securityType`
(past IPOs) field -- confirmed via 35_list_live_ipos.py's real output
that mainboard IPOs show "EQ" (or occasionally "BE") while SME-platform
IPOs show "SME" (or an "SM"-prefixed code among past listings). This
script now reads that field and skips any row carrying it, rather than
guessing at the distinction.

What this deliberately does NOT fill in, and why:
  - `gmp` (Grey Market Premium): NSE has no official GMP data --it's
    unofficial, scraped-from-forums data with no reliable free source.
    Left null rather than guessing/fabricating a number for something
    literally named after being off-the-record.
  - `sector_id`: NSE's IPO endpoints don't return a sector. Once a
    stock lists and appears in `assets` (this project's own Nifty 500
    universe) with a real sector, this script looks it up by matching
    the IPO's symbol against `assets.ticker` and fills sector_id in --
    but a brand-new IPO not yet in `assets` (most of them, especially
    upcoming ones) stays null, honestly, until that happens.
  - `post_listing_performance`: needs actual post-listing trading data
    over time, which is a separate ongoing job, not a one-time fetch --
    left as null here; a future script can build this out once daily
    prices for newly-listed stocks are flowing through 05_daily_price_refresh.py.

Matching runs to existing rows: `ipos.symbol` (see
32_add_ipo_symbol_column.sql) is the stable key -- this script never
creates a duplicate row for an IPO it's already seen, and never wipes
an existing field to null just because a later NSE endpoint (e.g.
listPastIPO once the IPO closes) doesn't repeat that field -- same
"never overwrite existing data with less information" principle every
other ingestion script here follows.

Setup: nothing new -- `nse` is already a project dependency.

Run manually:
    python 34_refresh_ipos.py
-------------------------------------------------------------------
"""
import tempfile
from datetime import datetime

from db_client import get_client
from ingestion_log import start_run, finish_run

SME_MARKERS = ("SME",)  # matches "SME" exactly and "SM"-prefixed codes below


def _is_sme(series_or_type: str | None) -> bool:
    if not series_or_type:
        return False
    v = series_or_type.strip().upper()
    return v in SME_MARKERS or v.startswith("SM")


def _parse_nse_date(s):
    """NSE dates come as 'DD-Mon-YYYY' (e.g. '07-Sep-2026'), or the
    literal string '-' when a date isn't set yet. Returns an ISO
    'YYYY-MM-DD' string, or None."""
    if not s or s == "-":
        return None
    try:
        return datetime.strptime(s.strip(), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return None


def _clean_text(s):
    """NSE uses the literal string '-' for "not available yet" in some
    text fields (e.g. priceRange on a very fresh past-IPO row) -- treat
    that the same as missing, not as a real value to display."""
    if not s or s == "-":
        return None
    return s.strip()


def build_records(nse):
    """Fetches all 3 NSE IPO endpoints and merges them into one record
    per symbol, skipping SME-platform IPOs entirely. Returns
    ({symbol: {field: value, ...}}, {sme_symbols_seen})."""
    records = {}
    sme_symbols = set()

    def merge(symbol, is_sme=False, **fields):
        if not symbol:
            return
        symbol = symbol.strip().upper()
        if is_sme:
            sme_symbols.add(symbol)
            records.pop(symbol, None)  # never keep a partial SME row
            return
        if symbol in sme_symbols:
            return  # already confirmed SME by another endpoint -- stay excluded
        existing = records.setdefault(symbol, {"symbol": symbol})
        for key, value in fields.items():
            if value is not None:
                existing[key] = value

    for row in nse.listUpcomingIPO() or []:
        merge(
            row.get("symbol"),
            is_sme=_is_sme(row.get("series")),
            company_name=_clean_text(row.get("companyName")),
            open_date=_parse_nse_date(row.get("issueStartDate")),
            close_date=_parse_nse_date(row.get("issueEndDate")),
            price_band=_clean_text(row.get("issuePrice")),
        )

    for row in nse.listCurrentIPO() or []:
        fields = dict(
            company_name=_clean_text(row.get("companyName")),
            open_date=_parse_nse_date(row.get("issueStartDate")),
            close_date=_parse_nse_date(row.get("issueEndDate")),
            price_band=_clean_text(row.get("issuePrice")),
        )
        # The "Total" category row is the overall subscription figure
        # across all bidder types (QIB/NII/RII/Total) -- the other rows
        # for the same symbol are per-category breakdowns we don't need
        # for this simple tracker.
        if row.get("category") == "Total" and row.get("noOfTime") is not None:
            try:
                times = float(row["noOfTime"])
                fields["subscription_status"] = f"{times:.2f}x subscribed"
            except (TypeError, ValueError):
                pass
        merge(row.get("symbol"), is_sme=_is_sme(row.get("series")), **fields)

    for row in nse.listPastIPO() or []:
        merge(
            row.get("symbol"),
            is_sme=_is_sme(row.get("securityType")),
            company_name=_clean_text(row.get("company")),
            open_date=_parse_nse_date(row.get("ipoStartDate")),
            close_date=_parse_nse_date(row.get("ipoEndDate")),
            price_band=_clean_text(row.get("priceRange")),
        )

    return records, sme_symbols


def main():
    supabase = get_client()
    run_id = start_run("ipo_refresh")

    with tempfile.TemporaryDirectory() as tmp_dir:
        from nse import NSE

        with NSE(download_folder=tmp_dir) as nse:
            records, sme_symbols = build_records(nse)

    print(f"Found {len(records)} distinct mainboard IPOs across upcoming/current/past NSE listings.")
    if sme_symbols:
        print(f"Excluded {len(sme_symbols)} SME-platform IPO(s): {sorted(sme_symbols)}")

        # One-time cleanup: an earlier run (before this SME filter existed)
        # may have already inserted these as real rows. Remove them now so
        # the ipos table doesn't keep showing SME IPOs from that run.
        deleted = supabase.table("ipos").delete().in_("symbol", sorted(sme_symbols)).execute()
        if deleted.data:
            print(f"Removed {len(deleted.data)} previously-inserted SME row(s) from the ipos table.")

    ok_count = 0
    failed_symbols = []

    for symbol, new_fields in records.items():
        try:
            existing_res = supabase.table("ipos").select("*").eq("symbol", symbol).maybe_single().execute()
            existing = existing_res.data if existing_res else None

            # Merge onto the existing row rather than overwrite it --
            # e.g. once an IPO closes, listPastIPO() may not repeat the
            # subscription_status listCurrentIPO() gave us earlier, and
            # a merge (not a plain upsert of only today's fields) keeps
            # that earlier value instead of silently wiping it to null.
            merged = {**(existing or {}), **new_fields}
            merged.pop("ipo_id", None)  # let Postgres manage the primary key

            # Once this company has actually listed and appears in our
            # own Nifty 500 universe (`assets`), pick up its real
            # sector -- honest best-effort, not required for the row
            # to be usable without it.
            if not merged.get("sector_id"):
                asset_res = supabase.table("assets").select("sector_id").eq("ticker", symbol).maybe_single().execute()
                if asset_res and asset_res.data and asset_res.data.get("sector_id"):
                    merged["sector_id"] = asset_res.data["sector_id"]

            supabase.table("ipos").upsert(merged, on_conflict="symbol").execute()
            ok_count += 1
        except Exception as e:
            print(f"  ! {symbol}: {e}")
            failed_symbols.append(symbol)

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(records)} ok. Failed: {failed_symbols if failed_symbols else 'none'}")


if __name__ == "__main__":
    main()
