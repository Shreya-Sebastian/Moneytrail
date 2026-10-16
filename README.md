# Moneytrail

moneytrail reads the CSV exports from Dutch banks (ING, Rabobank, ABN AMRO and bunq)
and tells you who you pay and which payments repeat. It runs on your own machine and
stores everything in a local DuckDB file.

Every Dutch bank lets you download your transactions, but the files are hard to use.
The same shop appears under a dozen different names, each bank uses its own format,
and nothing tells you which payments are subscriptions. Most budgeting apps solve this
by connecting to your bank account. I wanted to see how far you can get from the
export files alone, without the data leaving your computer.

Most of the work turned out to be in the data itself: working out who a payment
actually went to, and measuring how often that goes right.

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

### Merchant investigator

Some shops never show their own name. A cafe run by a holding company shows up as
`CCV*JV HOLDING B.V.`, and no rule can turn that into "Cafe Jansz". For these I built a
small agent that runs on a local model (qwen3:8b through Ollama, on a laptop GPU), so no
transaction data leaves the machine.

It only looks at merchants where a statement name is a legal entity (B.V., V.O.F.,
holding, horeca and so on). It can call five tools: the merchant's own payment history,
a search over the rest of the account, a company register search, a register lookup by
number, and a map search. It ends by giving a name, a category, a confidence and the
tool results it relied on.

Two rules keep it from making things worse:

- It may answer "unknown", and the prompt says that is better than a wrong name.
- A name is only accepted if it appears in something a tool returned or in the
  statements. A name the model made up is rejected and the rules' name stays.

The synthetic shops don't exist, so a real register can't find them. Each persona gets a
simulated register and map instead: shops that trade under their own name are derived
from the catalogue, and the hard cases are written by hand with look-alikes, such as the
same legal name in another city, a holding with several trade names, or a different
business with a similar name nearby. The held-out world was written without reference to the
investigator's code or prompt.

I compared three ways of naming the same cases: the rules, the same model shown the same
history but without tools, and the agent. The prompt was written on the dev set and
the held-out set was run once.

| held-out, 4 bank formats | rules | model, no tools | agent |
|---|---|---|---|
| Hard cases named correctly | 0 of 4 | 0 of 4 | 3 of 4 |
| Easy cases still correct (of 24) | 21 | 22 to 23 | 23 to 24 |
| Correct names made wrong | - | 0 | 0 |
| Category correct (of 28) | - | 23 to 24 | 25 to 26 |
| Tool calls per case | - | - | 2.5 |
| Seconds per case | - | about 1 | 5.4 |

On the dev set the agent named both hard cases and kept all 15 easy ones.

What went wrong on the held-out set:

- **One hard case never reached the agent.** A terminal cuts `EL AMRANI HAIR V.O.F.` to
  `EL AMRANI HAIR V`, so no legal form is left for the filter to see. End to end that
  makes 3 of the 5 hard shops. I haven't fixed the filter, because I found the problem in
  the held-out set.
- **The insurer.** Contents insurance is collected by `ACHMEA SCHADEVERZEKERINGEN N.V.`,
  which in the register has six trade names, and another Achmea company also uses
  "Centraal Beheer". The agent kept the legal name. That is wrong, but it is not a made-up name.
- **Mixed groups.** `Stichting Mollie Payments` contains several web shops, because the
  rules merged them on the shared IBAN. No name is right for the whole group. This has
  to be fixed in merchant resolution.

No answers were rejected as made up, and the agent never renamed a merchant the rules
already had right. Both safeguards are covered by tests with a scripted model in place
of the real one. These are small numbers: five hard shops in one simulated world.

### Imports

Each transaction gets an id built from its contents. Importing the same file twice,
or two exports with overlapping dates, doesn't create duplicates.

## Testing

`moneytrail synth` generates 18 months of
transactions for a made-up person, with the correct answers stored alongside. It
writes the same history in all four banks' formats, and `moneytrail eval` compares
the pipeline's output against the stored answers.

There are two sets of synthetic data:

- **dev** (`--set dev`): a person in Utrecht. I wrote this catalogue alongside the
  rules and use it while developing, so it flatters the rules.
- **heldout** (`--set heldout`): a different person in Eindhoven, with different
  shops. It was written separately, from how Dutch statements look, without
  reference to the matching code. It adds kinds of messiness the dev set doesn't
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

The held-out set is the fairer measure. Going through the failures on it:

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
- Let the investigator's filter catch legal forms that have been cut off (`V` for
  V.O.F.), then write a new held-out world to measure it.
- Connect the investigator to real sources (OpenStreetMap, and a company register) for
  use on real exports. It only searches the simulated worlds for now.
- Categories (groceries, transport and so on) labelled by an LLM, then distilled into a small model that runs locally. I want to compare accuracy against cost and speed for both.
- A read-only MCP server, so an MCP client can answer questions about your spending.
- A balance forecast for the end of the month.

## Usage

```bash
python -m venv .venv
source .venv/bin/activate                        # Windows: .venv\Scriptsctivate
pip install -e ".[dev]"

moneytrail synth --out data/demo                 # synthetic exports for all four banks
moneytrail synth --set heldout --out data/heldout   # the held-out set
moneytrail eval data/demo/ing -v                 # score against the stored answers
moneytrail import data/demo/ing/statement.csv    # or your own exports; the bank is detected
moneytrail merchants
moneytrail recurring

ollama pull qwen3:8b                             # the investigator's local model
moneytrail eval-agent data/heldout/ing --set heldout -v --out runs/heldout

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
  investigate.py the merchant investigator: tools, agent loop, safeguards
  llm.py         client for a local Ollama server
  world.py       simulated company register and map (hand-written parts in synth/world_*.py)
  evaluate_agent.py  rules vs model without tools vs agent
  cli.py
```
