# moneytrail

moneytrail reads the CSV exports from Dutch banks (ING, Rabobank, ABN AMRO and bunq)
and tells you who you pay and which payments repeat. It runs on your own machine and
stores everything in a local DuckDB file.

## Why I built this

After moving to Utrecht I had accounts at two banks and no clear idea where my money
went each month. Budgeting apps wanted access to my bank login, and the bank apps
only show one account each. I also found out I had been paying for a streaming
service I hadn't opened in months.

So I wanted something that works from the export files, keeps the data on my laptop,
and answers two questions: which subscriptions am I paying for, and what did they
cost me this year? The hard part turned out to be the data. Statement text is
messy enough that "who is this payment to?" is a real problem on its own.

## Example

```
$ moneytrail recurring
merchant                 cadence          amount  per month  next        notes
Stichting Mitros         monthly       €1,185.00  €1,185.00  2026-09-02  €1,150.00 -> €1,185.00 on 2026-01-01
CZ Zorgverzekeringen     monthly         €151.20    €151.20  2026-09-02  €142.35 -> €151.20 on 2026-01-01
Basic-Fit                four_weekly      €29.99     €32.60  2026-09-21
Netflix                  monthly          €15.99     €15.99  2026-09-02  €13.99 -> €15.99 on 2025-11-03
Disney Plus              monthly           €9.99      €9.99  -           stopped? last paid 2025-08-11
NS Reizigers             monthly           €5.60      €5.60  2026-09-11
```

## How it works

### Merchant resolution

One shop shows up under many names. Albert Heijn appears as `AH 2783 UTRECHT`,
`ALBERT HEIJN 5521`, `AH to go 8180 AMSTERDAM`, and `Albert Heijn 4321 Utre` when the
card terminal cuts the name off at 22 characters. Payment terminals add prefixes like
`CCV*`, `SumUp  *` and `Zettle_*`. Payment providers add their own wrappers, such as
`Stichting Derdengelden bol.com` or `NS GROEP IZ NS REIZIGERS`. ABN AMRO has no
counterparty column at all, so the name has to be parsed out of a fixed-width
description field.

Each name is first normalised: prefixes, branch numbers, cities and legal forms are
removed. Names are then merged if they:

- share a counterparty IBAN,
- have a high fuzzy-match score,
- are a truncated version of another name, or
- match as an acronym (`AH` and `Albert Heijn`).

The merchant keeps the most complete name among the common variants.

### Recurring payments

Payments are grouped by merchant, payment type and direction, then split into
amount bands. Each group is tested against weekly, four-weekly, monthly, quarterly
and yearly schedules. Cases it handles:

- **Four-weekly billing.** Gyms often charge every 28 days, which is 13 payments a year, not 12.
- **Price changes.** Small ones count too: a 3% rent increase is reported, while a single one-off amount in the middle of a series is ignored.
- **Stopped payments.** Series that are overdue by more than half a period are marked as stopped.
- **Mixed payments at one merchant.** A monthly NS Flex fee is found even though the same merchant also has one-off ticket purchases.
- **Two subscriptions under one name.** iCloud and Apple Music both appear as `APPLE.COM/BILL`.
- **Yearly renewals.** A single pair of payments a year apart only counts if nothing else from that merchant is in the data. Otherwise two €21.86 supermarket receipts would look like a subscription.

### Imports

Each transaction gets an id built from its contents. Importing the same file twice,
or two exports with overlapping dates, doesn't create duplicates.

## Testing it without real data

I don't want to use my own bank data, so `moneytrail synth` generates 18 months of
transactions for a made-up person, with the correct answers stored alongside. It
writes the same history in all four banks' formats, and `moneytrail eval` compares
the pipeline's output against the stored answers.

There are two sets of synthetic data:

- **dev** (`--set dev`): a person in Utrecht. I wrote this catalogue alongside the
  rules and use it while developing, so it flatters the rules.
- **heldout** (`--set heldout`): a different person in Eindhoven, with different
  shops. It was written separately, from a description of how Dutch statements look,
  without access to the matching code. It adds kinds of messiness the dev set doesn't
  have:
  - several shops paid through one payment provider's account,
  - two unrelated businesses with near-identical names,
  - branch numbers glued to the shop name,
  - more truncation widths.

  I only use it for reporting, never for tuning. After I change the rules because of
  something I saw in this set, it no longer counts as unseen, and the next version
  gets a fresh held-out set.

Results over 6 random seeds and 4 bank formats (24 files per set, about 1,050 transactions each):

| | dev | heldout |
|---|---|---|
| Merchant grouping (B-cubed F1) | 1.000 | 0.952 to 0.961 |
| Transactions with the right merchant name | 93.6% to 96.0% | 75.3% to 76.8% |
| Same, for shops that only show a legal company name | 0% | 0% |
| Recurring series found (precision / recall) | 1.000 / 1.000 | 0.944 to 1.000 / 0.944 |
| Price changes detected | 100% | 100% |
| Cancellations detected | 100% | 100% |

The held-out numbers are the ones to believe. Going through the failures on the held-out set:

**Wrong merges** (different merchants grouped together):
- Web shops that settle through one payment provider share an IBAN. Here that's
  Mollie's third-party-funds account, or PayPal for Vinted and Steam. The rules treat
  a shared IBAN as proof of one merchant, which is wrong for payment providers.
- The persona's own savings account (`M.A. Verhoeven`) was merged with her parents'
  joint account (`P.J.M. VERHOEVEN EN/OF A. VERHOEVEN-SMITS`).

**Missed merges** (one merchant split into several):
- `JUMBO9667 EINDHO`: when the branch number is glued to the name, the whole word gets
  dropped as a number.
- Abbreviations and spacing: `V.d.`, `vd` and `van der`; `&` and `En`; `Vanmoll` and
  `Van Moll`.

**Naming only** (grouped correctly, named badly):
- Five shops that only appear under a legal company name, as expected.
- Names that aren't in the data at all, like "Own savings account" or "iCloud" for
  `APPLE.COM/BILL`. These are partly a question of what the right answer is. I left the
  labels as they were written rather than adjusting them after seeing the results.

**Recurring:** the one missed series is a yearly payment that only occurs once in the
18 months, so there's nothing to detect.

## Next

- Fix the held-out failures that rules can fix:
  - stop trusting IBANs that belong to known payment providers,
  - split branch numbers off glued names,
  - handle Dutch abbreviations (`vd`, `v.d.`, `van der`).

  Then write a new held-out set to measure the result.
- A tool-using agent for merchants the rules can't name. It will search the rest of your history, OpenStreetMap and company registers, then suggest a name and category along with the evidence it used. I'll measure accuracy, number of steps and cost per case on the examples above.
- Categories (groceries, transport and so on) labelled by an LLM, then distilled into a small model that runs locally. I want to compare accuracy against cost and speed for both.
- A read-only MCP server, so an assistant like Claude Desktop can answer questions about your spending.
- A balance forecast for the end of the month.

## Usage

```bash
py -3.11 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

moneytrail synth --out data/demo                 # synthetic exports for all four banks
moneytrail synth --set heldout --out data/heldout   # the held-out set
moneytrail eval data/demo/ing -v                 # score against the stored answers
moneytrail import data/demo/ing/statement.csv    # or your own exports; the bank is detected
moneytrail merchants
moneytrail recurring

pytest
```

Put real exports in `exports/`. That folder is in `.gitignore`.

## Bank formats

The importers follow each bank's export layout. Transaction codes and description
formats can differ between export versions and account types, though. If a file doesn't
import cleanly, check `src/moneytrail/synth/export.py`: the writers there produce
exactly what each parser expects.

## Code layout

```
src/moneytrail/
  importers/     one parser per bank, all producing the same Transaction type
  merchants.py   name normalisation and merchant resolution
  recurring.py   schedules, price changes, stopped payments
  store.py       DuckDB storage and deduplication
  synth/         catalogues (dev, heldout), generator, per-bank writers, answers
  evaluate.py    grouping, naming and recurring-series scores
  cli.py
```
