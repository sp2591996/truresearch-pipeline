-- =====================================================================
-- PHASE 1: Reclassify the ~29 "unclassified" India stocks into the
-- correct existing sector/industry (no deletions, fully reversible).
-- Safe to run as-is.
-- =====================================================================

-- Aether Industries -> Chemicals > Specialty Chemicals
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Chemicals' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'))
WHERE ticker = 'AETHER';

-- Avanti Feeds -> Chemicals > Agricultural Inputs
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Agricultural Inputs' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'))
WHERE ticker = 'AVANTIFEED';

-- Azad Engineering -> Capital Goods > Aerospace & Defense
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Aerospace & Defense' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'AZAD';

-- Bagmane Prime Office REIT -> Realty > Real Estate - Diversified
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Real Estate - Diversified' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'))
WHERE ticker = 'BAGMANE';

-- Black Box -> Information Technology > Information Technology Services
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Information Technology' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Information Technology Services' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Information Technology' AND market = 'india'))
WHERE ticker = 'BBOX';

-- Bharat Coking Coal -> Metals & Mining > Thermal Coal
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Thermal Coal' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'))
WHERE ticker = 'BHARATCOAL';

-- Brookfield India Real Estate Trust -> Realty > Real Estate - Diversified
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Real Estate - Diversified' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'))
WHERE ticker = 'BIRET';

-- Clean Max Enviro Energy -> Power > Utilities - Renewable
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Power' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Utilities - Renewable' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Power' AND market = 'india'))
WHERE ticker = 'CLEANMAX';

-- Central Mine Planning & Design Institute -> Metals & Mining > Thermal Coal
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Thermal Coal' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'))
WHERE ticker = 'CMPDI';

-- Cupid Ltd (contraceptives/personal care) -> Fast Moving Consumer Goods > Household & Personal Products
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Fast Moving Consumer Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Household & Personal Products' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Fast Moving Consumer Goods' AND market = 'india'))
WHERE ticker = 'CUPID';

-- Embassy Office Parks REIT -> Realty > Real Estate - Diversified
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Real Estate - Diversified' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Realty' AND market = 'india'))
WHERE ticker = 'EMBASSY';

-- Fractal Analytics -> Information Technology > Information Technology Services
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Information Technology' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Information Technology Services' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Information Technology' AND market = 'india'))
WHERE ticker = 'FRACTAL';

-- H.E.G. Ltd (graphite electrodes) -> Capital Goods > Specialty Industrial Machinery (sector already correct, only industry was missing)
UPDATE assets SET
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Industrial Machinery' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'HEG';

-- INOX India (cryogenic equipment) -> Capital Goods > Specialty Industrial Machinery
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Industrial Machinery' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'INOXINDIA';

-- Kirloskar Brothers (pumps) -> Capital Goods > Specialty Industrial Machinery
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Industrial Machinery' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'KIRLOSBROS';

-- KSB Ltd (pumps) -> Capital Goods > Specialty Industrial Machinery
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Industrial Machinery' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'KSB';

-- MTAR Technologies (precision eng, aerospace/defense) -> Capital Goods > Aerospace & Defense
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Aerospace & Defense' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'MTARTECH';

-- Privi Speciality Chemicals -> Chemicals > Specialty Chemicals
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Specialty Chemicals' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Chemicals' AND market = 'india'))
WHERE ticker = 'PRIVISCL';

-- Rubicon Research (pharma) -> Healthcare > Drug Manufacturers - Specialty & Generic (sector already correct)
UPDATE assets SET
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Drug Manufacturers - Specialty & Generic' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Healthcare' AND market = 'india'))
WHERE ticker = 'RUBICON';

-- Sansera Engineering (auto parts) -> Automobile and Auto Components > Auto Parts
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Automobile and Auto Components' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Auto Parts' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Automobile and Auto Components' AND market = 'india'))
WHERE ticker = 'SANSERA';

-- SPR Auto Technologies (ex-Shriram Pistons) -> Automobile and Auto Components > Auto Parts
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Automobile and Auto Components' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Auto Parts' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Automobile and Auto Components' AND market = 'india'))
WHERE ticker = 'SHRIPISTON';

-- Sterlite Technologies (optical fiber / telecom infra) -> Telecommunication > Communication Equipment
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Telecommunication' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Communication Equipment' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Telecommunication' AND market = 'india'))
WHERE ticker = 'STLTECH';

-- TD Power Systems (generators/motors) -> Capital Goods > Electrical Equipment & Parts
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Electrical Equipment & Parts' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Capital Goods' AND market = 'india'))
WHERE ticker = 'TDPOWERSYS';

-- Thangamayil Jewellery -> Consumer Durables > Luxury Goods
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Consumer Durables' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Luxury Goods' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Consumer Durables' AND market = 'india'))
WHERE ticker = 'THANGAMAYL';

-- Vedanta Aluminium Metal -> Metals & Mining > Aluminum
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Aluminum' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'))
WHERE ticker = 'VAML';

-- Vedanta Power -> Power > Utilities - Regulated Electric
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Power' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Utilities - Regulated Electric' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Power' AND market = 'india'))
WHERE ticker = 'VEDPOWER';

-- Vedanta Iron and Steel -> Metals & Mining > Steel
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Steel' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Metals & Mining' AND market = 'india'))
WHERE ticker = 'VISL';

-- Vedanta Oil and Gas -> Oil Gas & Consumable Fuels > Oil & Gas Integrated
UPDATE assets SET
  sector_id = (SELECT sector_id FROM sectors WHERE name = 'Oil Gas & Consumable Fuels' AND market = 'india'),
  industry_id = (SELECT industry_id FROM industries WHERE name = 'Oil & Gas Integrated' AND sector_id = (SELECT sector_id FROM sectors WHERE name = 'Oil Gas & Consumable Fuels' AND market = 'india'))
WHERE ticker = 'VOGL';

-- =====================================================================
-- VERIFY: run this after the updates above -- should return ZERO rows
-- (every real stock now has both a sector and an industry; the
-- currency-pair/index/commodity rows like AEDINR, GOLD, NIFTY50 etc.
-- are expected to stay null -- they aren't companies)
-- =====================================================================
select asset_id, ticker, name, sector_id, industry_id
from assets
where (sector_id is null or industry_id is null)
  and ticker not in (
    'AEDINR','BRENTCRUDE','EURINR','GBPINR','GOLD','JPYINR','KWDINR',
    'NATGAS','NIFTY100','NIFTY50','NIFTYBANK','OMRINR','SARINR','SENSEX',
    'SILVER','USDINR','WTICRUDE','DOWJONES','NASDAQCOMP','RUSSELL2000','SPX500'
  );
