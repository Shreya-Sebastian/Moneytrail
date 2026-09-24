"""Who the synthetic persona pays, and how those payments show up on a statement.

The persona is a recent graduate living in Utrecht. Statement names are modelled on
the messiness of real Dutch exports: card-terminal prefixes, store numbers, city
suffixes, truncation, legal entity names that differ from the shop's trading name,
and a company rename part-way through.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Merchant:
    id: str
    name: str  # what a person would call it: the answer the resolver should reach
    category: str
    hard: bool = False  # statements only ever show a legal entity, never the shop name


@dataclass(frozen=True)
class Spend:
    """Ad-hoc spending at one merchant."""

    merchant: str
    kind: str
    names: tuple[str, ...]  # statement name templates, most common first
    per_month: float
    amount: tuple[float, ...]  # (low, high), or a menu of fixed prices when menu=True
    menu: bool = False
    remittance: str = ""
    iban_owner: str = ""  # collect into another party's account (a payment provider's), not the merchant's own


@dataclass(frozen=True)
class Plan:
    """A recurring payment. Month offsets are relative to the first generated month."""

    id: str
    merchant: str
    kind: str
    names: tuple[tuple[int, str], ...]  # (from month, statement name)
    cadence: str  # "monthly" | "four_weekly" | "yearly"
    day: int
    amounts: tuple[tuple[int, float], ...]  # (from month, amount)
    remittance: str = ""
    start: int = 0
    stop: int | None = None  # first month it no longer happens
    iban_owner: str = ""  # as Spend.iban_owner


MERCHANTS = {
    m.id: m
    for m in [
        Merchant("albert_heijn", "Albert Heijn", "groceries"),
        Merchant("jumbo", "Jumbo", "groceries"),
        Merchant("lidl", "Lidl", "groceries"),
        Merchant("ekoplaza", "Ekoplaza", "groceries"),
        Merchant("bakkerij_jansen", "Bakkerij Jansen", "groceries"),
        Merchant("koffiebar_de_stoep", "Koffiebar De Stoep", "eating_out"),
        Merchant("cafe_jansz", "Cafe Jansz", "eating_out", hard=True),
        Merchant("tokyo_ramen", "Tokyo Ramen", "eating_out", hard=True),
        Merchant("la_piazza", "La Piazza", "eating_out"),
        Merchant("eetcafe_de_zaak", "Eetcafe De Zaak", "eating_out"),
        Merchant("thuisbezorgd", "Thuisbezorgd", "eating_out"),
        Merchant("bol", "bol.com", "shopping"),
        Merchant("coolblue", "Coolblue", "shopping"),
        Merchant("hema", "HEMA", "shopping"),
        Merchant("action", "Action", "shopping"),
        Merchant("zara", "Zara", "shopping"),
        Merchant("broese", "Broese", "shopping"),
        Merchant("kruidvat", "Kruidvat", "personal_care"),
        Merchant("etos", "Etos", "personal_care"),
        Merchant("ns", "NS", "transport"),
        Merchant("swapfiets", "Swapfiets", "transport"),
        Merchant("pathe", "Pathe", "entertainment"),
        Merchant("geldmaat", "Geldmaat", "cash"),
        Merchant("tikkie", "Tikkie", "transfers"),
        Merchant("friend_jdevries", "J. de Vries", "transfers"),
        Merchant("friend_sanne", "Sanne Bakker", "transfers"),
        Merchant("friend_tnguyen", "T. Nguyen", "transfers"),
        Merchant("friend_ljansen", "L. Jansen", "transfers"),
        Merchant("employer", "Veldhuis Data", "income"),
        Merchant("landlord", "Mitros", "housing"),
        Merchant("own_savings", "M. Visser (savings)", "savings"),
        Merchant("netflix", "Netflix", "entertainment"),
        Merchant("spotify", "Spotify", "entertainment"),
        Merchant("disney_plus", "Disney Plus", "entertainment"),
        Merchant("apple", "Apple", "entertainment"),
        Merchant("basic_fit", "Basic-Fit", "health_fitness"),
        Merchant("ziggo", "Ziggo", "utilities"),
        Merchant("odido", "Odido", "utilities"),
        Merchant("vattenfall", "Vattenfall", "utilities"),
        Merchant("vitens", "Vitens", "utilities"),
        Merchant("cz", "CZ", "insurance"),
        Merchant("duo", "DUO", "education"),
        Merchant("anwb", "ANWB", "insurance"),
        Merchant("duolingo", "Duolingo", "education"),
    ]
}

HOME_CITY = "Utrecht"
OTHER_CITIES = ("Amsterdam", "Den Haag", "Rotterdam", "Leiden", "Delft", "Eindhoven")
TIKKIE_WHAT = ("Pizza", "Borrel", "Bioscoop", "Boodschappen weekend", "Cadeau Lisa", "Etentje", "Taxi")
PEOPLE = ("J. de Vries", "Sanne Bakker", "T. Nguyen", "L. Jansen", "R. Smit")  # for {person} in remittances
TERMINAL_WIDTHS = (22,)  # widths at which truncating card terminals cut names off
TRUNCATE_SHARE = 0.4  # share of card terminals that truncate
FRIENDS = {
    "friend_jdevries": "J. de Vries",
    "friend_sanne": "Sanne Bakker",
    "friend_tnguyen": "T. Nguyen",
    "friend_ljansen": "L. Jansen",
}

ADHOC = [
    Spend("albert_heijn", "card", ("AH {store} {CITY}", "ALBERT HEIJN {store}", "AH to go {store} {CITY}", "Albert Heijn {store} {City}"), 8, (4, 85)),
    Spend("jumbo", "card", ("JUMBO {CITY} {store}", "Jumbo {City}", "JUMBO SUPERMARKTEN"), 3, (5, 70)),
    Spend("lidl", "card", ("LIDL {store} {CITY}", "Lidl {City}"), 2, (6, 60)),
    Spend("ekoplaza", "card", ("Ekoplaza {City}", "EKOPLAZA {store}"), 0.7, (8, 45)),
    Spend("bakkerij_jansen", "card", ("SumUp  *Bakkerij Jansen", "CCV*BAKKERIJ JANSEN", "Bakkerij Jansen VOF"), 3, (2.95, 3.60, 4.25, 6.80, 8.40), menu=True),
    Spend("koffiebar_de_stoep", "card", ("Zettle_*Koffiebar De Sto", "KOFFIEBAR DE STOEP", "SumUp  *Koffiebar De Stoep"), 5, (2.90, 3.40, 3.80, 4.50, 6.80), menu=True),
    Spend("cafe_jansz", "card", ("CCV*JV HOLDING B.V.", "JV Holding B.V."), 2, (8, 35)),
    Spend("tokyo_ramen", "card", ("SumUp  *TKR Horeca BV", "TKR HORECA"), 0.8, (15, 40)),
    Spend("la_piazza", "card", ("Restaurant La Piazza", "CCV*LA PIAZZA {CITY}", "Zettle_*La Piazza"), 1, (25, 80)),
    Spend("eetcafe_de_zaak", "card", ("Eetcafe De Zaak", "CCV*EETCAFE DE ZAAK"), 0.8, (18, 60)),
    Spend("thuisbezorgd", "card", ("TAKEAWAY.COM*THUISBEZ", "Thuisbezorgd.nl via Takeaway.com", "Mollie*Thuisbezorgd.nl"), 2.5, (15, 45)),
    Spend("bol", "ideal", ("bol.com", "Stichting Derdengelden bol.com", "BOL.COM BV"), 1.5, (8, 120), remittance="{ref} bol.com bestelling"),
    Spend("coolblue", "ideal", ("Coolblue B.V.", "Coolblue"), 0.3, (20, 400), remittance="Bestelling {ref}"),
    Spend("hema", "card", ("HEMA {City}", "HEMA {store} {CITY}"), 1, (3, 40)),
    Spend("action", "card", ("Action {store} {CITY}", "ACTION {City}"), 1, (2, 35)),
    Spend("zara", "card", ("ZARA {City}", "Zara Nederland BV"), 0.4, (20, 90)),
    Spend("broese", "card", ("Broese Boekverkopers", "BROESE {CITY}"), 0.3, (12, 45)),
    Spend("kruidvat", "card", ("Kruidvat {store}", "KRUIDVAT {CITY}"), 1.5, (3, 30)),
    Spend("etos", "card", ("Etos {City}", "ETOS {store}"), 0.5, (3, 25)),
    Spend("ns", "card", ("NS GROEP IZ NS REIZIGERS", "NS-{City} {store}", "NS Reizigers"), 3, (4, 30)),
    Spend("pathe", "card", ("Pathe {City}", "PATHE {CITY}"), 0.6, (11, 32)),
    Spend("geldmaat", "atm", ("GELDMAAT {CITY} {store}", "Geldmaat {City}"), 0.5, (20, 50, 70, 100), menu=True),
    Spend("tikkie", "ideal", ("AAB INZ TIKKIE",), 2, (5, 45), remittance="Tikkie ID {ref}, {what}, Van {person}"),
    *[
        Spend(fid, "transfer_in", (name,), 0.3, (5, 60), remittance="Terug voor {what}")
        for fid, name in FRIENDS.items()
    ],
]


def recurring_plans(first_month: int, months: int) -> list[Plan]:
    """`first_month` is the calendar month (1-12) of offset 0, so price rises can land in January."""
    january = next((i for i in range(months) if (first_month - 1 + i) % 12 == 0), None)
    new_year = january if january is not None else months  # no January in range -> no rise
    return [
        Plan("salary", "employer", "transfer_in", ((0, "Veldhuis Data B.V."),), "monthly", 24, ((0, 3150.00), (12, 3280.00)), "Salaris {month}"),
        Plan("rent", "landlord", "transfer_out", ((0, "Stichting Mitros"),), "monthly", 1, ((0, 1150.00), (new_year, 1185.00)), "Huur {month} Kanaalstraat 88"),
        Plan("savings", "own_savings", "transfer_out", ((0, "M. Visser"),), "monthly", 26, ((0, 300.00),), "Sparen"),
        Plan("netflix", "netflix", "direct_debit", ((0, "Netflix International B.V."),), "monthly", 3, ((0, 13.99), (8, 15.99)), "Netflix {period}"),
        Plan("spotify", "spotify", "card", ((0, "Spotify P2F7A3C9D1"),), "monthly", 14, ((0, 10.99), (10, 11.99))),
        Plan("disney_plus", "disney_plus", "direct_debit", ((0, "Disney Plus"),), "monthly", 9, ((0, 9.99),), "Disney+ {period}", stop=6),
        Plan("icloud", "apple", "card", ((0, "APPLE.COM/BILL"),), "monthly", 20, ((0, 0.99),)),
        Plan("apple_music", "apple", "card", ((0, "APPLE.COM/BILL"),), "monthly", 8, ((0, 10.99),), start=4),
        Plan("basic_fit", "basic_fit", "direct_debit", ((0, "Basic-Fit Nederland B.V."),), "four_weekly", 5, ((0, 29.99),), "Lidmaatschap {period}", start=2),
        Plan("ziggo", "ziggo", "direct_debit", ((0, "Ziggo B.V."),), "monthly", 25, ((0, 52.50),), "Ziggo {period}"),
        Plan("mobile", "odido", "direct_debit", ((0, "T-Mobile Netherlands B.V."), (7, "Odido Netherlands B.V.")), "monthly", 22, ((0, 20.00),), "Abonnement {period}"),
        Plan("health_insurance", "cz", "direct_debit", ((0, "CZ Zorgverzekeringen"),), "monthly", 1, ((0, 142.35), (new_year, 151.20)), "Premie zorgverzekering {period}"),
        Plan("energy", "vattenfall", "direct_debit", ((0, "Vattenfall Klantenservice N.V."),), "monthly", 18, ((0, 135.00), (11, 118.00)), "Termijnbedrag {month}"),
        Plan("water", "vitens", "direct_debit", ((0, "Vitens N.V."),), "monthly", 28, ((0, 19.40),), "Voorschot water {period}"),
        Plan("study_loan", "duo", "direct_debit", ((0, "DUO"),), "monthly", 21, ((0, 45.00),), "Aflossing studieschuld {period}", start=3),
        Plan("ns_flex", "ns", "direct_debit", ((0, "NS Reizigers B.V."),), "monthly", 12, ((0, 5.60),), "NS Flex Dal Voordeel {period}"),
        Plan("swapfiets", "swapfiets", "direct_debit", ((0, "Swapfiets B.V."),), "monthly", 1, ((0, 19.90),), "Swapfiets {period}"),
        Plan("anwb", "anwb", "direct_debit", ((0, "ANWB B.V."),), "yearly", 15, ((0, 64.00),), "Contributie {period}", start=3),
        Plan("duolingo", "duolingo", "card", ((0, "DUOLINGO"),), "yearly", 11, ((0, 89.99),), start=5),
    ]
