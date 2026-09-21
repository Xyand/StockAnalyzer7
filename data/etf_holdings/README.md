# Fund holdings files

Drop a fund's **complete** holdings file here as `<SYMBOL>.csv` — for example
`VOO.csv` — and StockAnalyzer7 will use it instead of the top-ten list that free
quote APIs publish. This is what takes look-through coverage from roughly 40% of
a broad index fund to 100%.

## Where to get them

Every major issuer publishes these for free on each fund's own page:

| Issuer | Where |
|---|---|
| iShares / BlackRock | fund page → **Holdings** → "Detailed Holdings and Analytics" (CSV) |
| SPDR / State Street | fund page → **Holdings** → "Daily Holdings" (CSV or XLSX) |
| Vanguard | fund page → **Portfolio & Management** → holdings table (export) |
| Invesco | fund page → **Holdings** → "Full Holdings" (CSV) |
| Schwab | fund page → **Portfolio** → holdings export |

Save as CSV. XLSX files need converting first.

## Format

The parser is forgiving: it finds the header row underneath any preamble and
accepts the column names issuers actually use.

- **Weight** (required): `Weight (%)`, `% of Net Assets`, `Portfolio Weight`,
  `Holding Percent`, `Allocation`, … — percents or fractions, either works.
- **Ticker** (optional): `Ticker`, `Symbol`, `Identifier`, …
- **Name** (optional, but needed for holdings with no ticker such as bonds):
  `Name`, `Security Name`, `Description`, …
- **Asset class** (optional): `Asset Class`, `Security Type` — improves the
  asset-class breakdown for bond and multi-asset funds.
- **Sector**, **Location/Country** (optional): improve the sector and country
  breakdowns.

A minimal file:

```csv
Ticker,Name,Sector,Asset Class,Weight (%)
AAPL,Apple Inc.,Information Technology,Equity,7.12
MSFT,Microsoft Corporation,Information Technology,Equity,6.44
,U.S. Treasury Note 4.25% 2030,,Fixed Income,1.02
```

## Fetching them automatically

Create `sources.json` in this directory mapping symbols to public CSV URLs:

```json
{
  "IVV": "https://www.ishares.com/us/products/.../1467271812596.ajax?fileType=csv",
  "SPY": "https://www.ssga.com/.../holdings-daily-us-en-spy.xlsx"
}
```

The file is downloaded on first use and cached here as `<SYMBOL>.csv`, so later
runs work offline. Set `SA_ISSUER_DOWNLOADS=0` to disable downloading entirely.

Files in this directory are git-ignored apart from this README — they are large,
they change daily, and they are yours to refresh.
