-- 36_add_drhp_columns.sql
-- -------------------------------------------------------------------
-- Adds columns to `ipo_assessments` to hold the structured content
-- extracted from a company's DRHP (Draft Red Herring Prospectus) PDF
-- by 37_parse_drhp.py.
--
-- Design note: DRHPs from different companies/merchant bankers use
-- slightly different section wording and page layouts, so the parser
-- reads each document's own Table of Contents rather than assuming a
-- fixed page number -- see 37_parse_drhp.py's docstring for the full
-- explanation. These columns hold whatever it manages to extract;
-- any column can legitimately be null if that section wasn't found
-- in a particular document (the frontend already knows how to show
-- an honest "not available" state -- same principle as gmp/gmp-less
-- rows in the ipos table).
--
-- Safe to run once. Running it a second time is harmless -- every
-- column uses "add column if not exists".
-- -------------------------------------------------------------------

alter table ipo_assessments
  add column if not exists business_summary text,
  add column if not exists industry_summary text,
  add column if not exists objects_of_offer text,
  add column if not exists key_risks jsonb,
  add column if not exists financial_summary jsonb,
  add column if not exists source_pdf_filename text,
  add column if not exists parsed_at timestamptz;
