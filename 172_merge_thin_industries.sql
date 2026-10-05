-- =====================================================================
-- 172_merge_thin_industries.sql
--
-- Follow-up to 169/170/171: those cleaned up stale SECTOR/industry rows
-- and added a sector-level grouping layer. This script does the same
-- "no category left too thin to have a real index/KPIs" fix one level
-- down, at the INDUSTRY level -- every industry with 1-2 stocks gets
-- merged into the closest related industry within the SAME sector
-- (never across sectors). Where no good existing sibling exists, a
-- small number of new umbrella industries are created instead (12
-- total, e.g. "General Retail", "Diversified Financials").
--
-- This is a REAL data change (stocks move to a different industry_id,
-- old thin industries get deleted) -- not just cosmetic, same as
-- 169/170. Run the two PREVIEW selects at the very end first if you
-- want to sanity check before running the next session's work on top
-- of this.
--
-- Order of operations:
--   1) Create the 12 new umbrella industries.
--   2) Move every thin industry's stocks into its target industry.
--   3) Clean up industry_scores for the industries about to be retired
--      (same FK lesson as 170 -- this table is purely derived, safe to
--      delete for a dying industry).
--   4) Delete the now-empty (retired) industries.
--   5) Verify.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) New umbrella industries (12 total)
-- ---------------------------------------------------------------------
insert into industries (name, sector_id, market) values
  ('General Retail', (select sector_id from sectors where name = 'Consumer Services' and market = 'india'), 'india'),
  ('Diversified Consumer Services', (select sector_id from sectors where name = 'Consumer Services' and market = 'india'), 'india'),
  ('Diversified Financials', (select sector_id from sectors where name = 'Financial Services' and market = 'india'), 'india'),
  ('Aviation', (select sector_id from sectors where name = 'Transportation & Logistics' and market = 'india'), 'india'),
  ('Publishing & Advertising', (select sector_id from sectors where name = 'Communication Services' and market = 'usa'), 'usa'),
  ('Telecommunication Services', (select sector_id from sectors where name = 'Communication Services' and market = 'usa'), 'usa'),
  ('Electronics & Distribution', (select sector_id from sectors where name = 'Consumer Discretionary' and market = 'usa'), 'usa'),
  ('General Retail', (select sector_id from sectors where name = 'Consumer Discretionary' and market = 'usa'), 'usa'),
  ('Tobacco & Alcoholic Beverages', (select sector_id from sectors where name = 'Consumer Staples' and market = 'usa'), 'usa'),
  ('Business & Professional Services', (select sector_id from sectors where name = 'Industrials' and market = 'usa'), 'usa'),
  ('Metals & Mining', (select sector_id from sectors where name = 'Materials' and market = 'usa'), 'usa'),
  ('Specialty & Industrial REITs', (select sector_id from sectors where name = 'Real Estate' and market = 'usa'), 'usa'),
  ('Office REITs & Real Estate Services', (select sector_id from sectors where name = 'Real Estate' and market = 'usa'), 'usa'),
  ('Self-Storage & Data Center REITs', (select sector_id from sectors where name = 'Real Estate' and market = 'usa'), 'usa');

-- ---------------------------------------------------------------------
-- 2) Move stocks -- grouped by TARGET industry. industry_id values are
--    taken directly from your own audit export, so these are exact.
-- ---------------------------------------------------------------------

-- ===== INDIA =====

-- Automobile and Auto Components
update assets set industry_id = 14 where industry_id in (16, 90, 59);              -- -> Auto Parts
update assets set industry_id = 21 where industry_id in (114);                     -- -> Auto Manufacturers

-- Capital Goods
update assets set industry_id = 48 where industry_id in (276);                     -- -> Conglomerates
update assets set industry_id = 79 where industry_id in (88);                      -- -> Solar
update assets set industry_id = 15 where industry_id in (123, 115, 110);           -- -> Specialty Industrial Machinery
update assets set industry_id = 22 where industry_id in (111);                     -- -> Electrical Equipment & Parts

-- Chemicals
update assets set industry_id = 42 where industry_id in (293, 87);                 -- -> Chemicals

-- Construction
update assets set industry_id = 19 where industry_id in (119, 259);                -- -> Engineering & Construction

-- Construction Materials
update assets set industry_id = 5 where industry_id in (256);                      -- -> Building Materials

-- Consumer Durables
update assets set industry_id = 65 where industry_id in (68, 32);                  -- -> Consumer Electronics
update assets set industry_id = 74 where industry_id in (125);                     -- -> Luxury Goods
update assets set industry_id = 45 where industry_id in (24);                      -- -> Furnishings, Fixtures & Appliances

-- Consumer Services
update assets set industry_id = 83 where industry_id in (82);                      -- -> Apparel Retail
update assets set industry_id = 93 where industry_id in (27, 72);                  -- -> Specialty Business Services
update assets set industry_id = 25 where industry_id in (122);                     -- -> Lodging
update assets set industry_id = (select industry_id from industries where name = 'General Retail' and market = 'india')
  where industry_id in (287, 57, 92);
update assets set industry_id = (select industry_id from industries where name = 'Diversified Consumer Services' and market = 'india')
  where industry_id in (95, 107);

-- Fast Moving Consumer Goods
update assets set industry_id = 277 where industry_id in (91);                     -- -> Beverages - Alcoholic
update assets set industry_id = 4 where industry_id in (33);                       -- -> Packaged Foods
update assets set industry_id = 26 where industry_id in (98, 67, 255);             -- -> Household & Personal Products

-- Financial Services
update assets set industry_id = 316 where industry_id in (318);                    -- -> Private Sector Banks
update assets set industry_id = 71 where industry_id in (40, 103, 104);            -- -> Insurance - Diversified
update assets set industry_id = 58 where industry_id in (77);                      -- -> Financial Data & Stock Exchanges
update assets set industry_id = (select industry_id from industries where name = 'Diversified Financials' and market = 'india')
  where industry_id in (53, 258);

-- Healthcare
update assets set industry_id = 100 where industry_id in (117);                    -- -> Diagnostics & Research
update assets set industry_id = 31 where industry_id in (36);                      -- -> Drug Manufacturers - Specialty & Generic

-- Information Technology
update assets set industry_id = 13 where industry_id in (97, 39);                  -- -> Software - Infrastructure
update assets set industry_id = 44 where industry_id in (112, 86);                 -- -> Information Technology Services

-- Media Entertainment & Publication
update assets set industry_id = 116 where industry_id in (118);                    -- -> Entertainment

-- Metals & Mining
update assets set industry_id = 23 where industry_id in (29);                      -- -> Steel
update assets set industry_id = 70 where industry_id in (106, 254);                -- -> Other Industrial Metals & Mining

-- Oil Gas & Consumable Fuels
update assets set industry_id = 7 where industry_id in (253, 85);                  -- -> Oil & Gas Integrated

-- Power
update assets set industry_id = 38 where industry_id in (121);                     -- -> Utilities - Regulated Electric

-- Realty
update assets set industry_id = 41 where industry_id in (84);                      -- -> Real Estate - Diversified

-- Textiles
update assets set industry_id = 43 where industry_id in (78);                      -- -> Textile Manufacturing

-- Transportation & Logistics
update assets set industry_id = 291 where industry_id in (284);                    -- -> Integrated Freight & Logistics
update assets set industry_id = (select industry_id from industries where name = 'Aviation' and market = 'india')
  where industry_id in (285, 286);

-- ===== USA =====

-- Communication Services
update assets set industry_id = 144 where industry_id in (210);                    -- -> Interactive Media & Services
update assets set industry_id = (select industry_id from industries where name = 'Publishing & Advertising' and market = 'usa')
  where industry_id in (241, 243);
update assets set industry_id = (select industry_id from industries where name = 'Telecommunication Services' and market = 'usa')
  where industry_id in (163, 188, 209);

-- Consumer Discretionary
update assets set industry_id = 237 where industry_id in (201);                    -- -> Apparel Accessories & Luxury Goods
update assets set industry_id = 235 where industry_id in (205, 226);               -- -> Casinos & Gaming
update assets set industry_id = 166 where industry_id in (160);                    -- -> Automotive Retail
update assets set industry_id = 229 where industry_id in (252);                    -- -> Home Improvement Retail
update assets set industry_id = (select industry_id from industries where name = 'Electronics & Distribution' and market = 'usa')
  where industry_id in (225, 222, 173);
update assets set industry_id = (select industry_id from industries where name = 'General Retail' and market = 'usa')
  where industry_id in (246, 146, 249);

-- Consumer Staples
update assets set industry_id = 197 where industry_id in (248, 180);               -- -> Consumer Staples Merchandise Retail
update assets set industry_id = 224 where industry_id in (161);                    -- -> Packaged Foods & Meats
update assets set industry_id = (select industry_id from industries where name = 'Tobacco & Alcoholic Beverages' and market = 'usa')
  where industry_id in (239, 177, 145);

-- Energy
update assets set industry_id = 157 where industry_id in (189);                    -- -> Oil & Gas Exploration & Production

-- Financials
update assets set industry_id = 150 where industry_id in (213, 274);               -- -> Multi-line Insurance

-- Health Care
update assets set industry_id = 192 where industry_id in (247, 227);               -- -> Health Care Services

-- Industrials
update assets set industry_id = 154 where industry_id in (202, 223);               -- -> Electrical Components & Equipment
update assets set industry_id = 203 where industry_id in (250);                    -- -> Passenger Airlines
update assets set industry_id = 206 where industry_id in (126);                    -- -> Industrial Machinery & Supplies & Components
update assets set industry_id = 178 where industry_id in (215);                    -- -> Air Freight & Logistics
update assets set industry_id = (select industry_id from industries where name = 'Business & Professional Services' and market = 'usa')
  where industry_id in (176, 165, 211);

-- Information Technology
update assets set industry_id = 233 where industry_id in (184);                    -- -> Electronic Equipment & Instruments

-- Materials
update assets set industry_id = 147 where industry_id in (170);                    -- -> Paper & Plastic Packaging Products & Materials
update assets set industry_id = 139 where industry_id in (207, 136);               -- -> Specialty Chemicals
update assets set industry_id = (select industry_id from industries where name = 'Metals & Mining' and market = 'usa')
  where industry_id in (221, 240, 242);

-- Real Estate
update assets set industry_id = 167 where industry_id in (231);                    -- -> Multi-Family Residential REITs
update assets set industry_id = 216 where industry_id in (230);                    -- -> Retail REITs
update assets set industry_id = (select industry_id from industries where name = 'Specialty & Industrial REITs' and market = 'usa')
  where industry_id in (232, 251, 244);
update assets set industry_id = (select industry_id from industries where name = 'Office REITs & Real Estate Services' and market = 'usa')
  where industry_id in (183, 140);
update assets set industry_id = (select industry_id from industries where name = 'Self-Storage & Data Center REITs' and market = 'usa')
  where industry_id in (214, 204);

-- Utilities
update assets set industry_id = 148 where industry_id in (152, 164, 133);          -- -> Multi-Utilities

-- ---------------------------------------------------------------------
-- 3) Clean up industry_scores for every retired (now-empty) industry
--    -- same FK lesson as 170_delete_orphan_sectors_industries.sql
-- ---------------------------------------------------------------------
delete from industry_scores
where industry_id in (
  select i.industry_id from industries i
  where not exists (select 1 from assets a where a.industry_id = i.industry_id)
);

-- ---------------------------------------------------------------------
-- 4) Delete the now-empty retired industries
-- ---------------------------------------------------------------------
delete from industries i
where not exists (select 1 from assets a where a.industry_id = i.industry_id);

-- ---------------------------------------------------------------------
-- 5) VERIFY
-- ---------------------------------------------------------------------

-- Should show the smallest surviving industry sizes -- expect the
-- floor to now be 2 only for a couple of genuine "no good sibling"
-- catch-alls (flagged in the summary); everything else should be 3+.
select i.industry_id, i.name, s.name as sector_name, i.market,
       count(a.asset_id) as stock_count
from industries i
join sectors s on s.sector_id = i.sector_id
left join assets a on a.industry_id = i.industry_id
group by i.industry_id, i.name, s.name, i.market
order by stock_count asc
limit 20;

-- Should return ZERO rows -- no real stock left pointing at a
-- deleted/retired industry_id
select a.asset_id, a.ticker, a.name
from assets a
where a.industry_id is not null
  and not exists (select 1 from industries i where i.industry_id = a.industry_id);
