"""Held-out merchant catalogue: a second, independent persona for measuring moneytrail.

This catalogue was written WITHOUT access to the merchant-resolution rules, the recurring
detector or the evaluation code. It was written only from a description of how Dutch bank
statements look, so a score on it says something about how the system does on data it
was not tuned to. Never tune the rules against it.

Persona: Mila Verhoeven, 28, a process engineer at a photonics firm, renting a flat in
Eindhoven (Stratum). She climbs, rides a Swapfiets, takes the train to Amsterdam and
Den Bosch now and then, and splits a lot of bills with friends through Tikkie.

Kinds of messiness it contains:
- card-terminal / PSP prefixes and wrappers: CCV*, SumUp *, "SUMUP  *", ZETTLE_*, iZ *,
  SQ *, MSP*, PAYPAL *, UBER *, "AAB INZ", "via Stichting Mollie Payments", with varied
  spacing
- branch numbers, upper- and mixed-case city names, and names cut off by terminals
- abbreviations and squashed words (V.D., EHV, VANMOLL, AH), legal forms (B.V., BV, N.V.,
  V.O.F., VOF, GmbH, SE, S.C.A, Stichting / Stg)
- shops seen only under an unrelated legal or holding name (hard=True): a lunchroom run
  by a holding, a chip shop run by a V.O.F., a takeaway run by a catering B.V., a barber
  under the owner's name, contents insurance under the insurer's group entity
- name collisions: the persona's own savings account, her parents and a bakery all share
  the surname Verhoeven; a cafe and a pharmacy are both "De Kroon"; a friend and a
  butcher are both "van der Heijden"
- shared settlement accounts: three small web shops paid by iDEAL through Mollie's
  third-party-funds foundation, and two merchants paid through PayPal
- one brand under several legal entities (NS Reizigers / NS International / NS Groep;
  Thuisbezorgd / Takeaway.com Payments; Albert Heijn / AH to go)
- renames part-way through a series (T-Mobile to Odido; the climbing gym's new owner)
- people: friends paying and being paid, Tikkie requests both ways, own savings account
- recurring: salary, rent, utilities, insurance, monthly / four-weekly / yearly
  subscriptions, price changes (including New-Year rises under 5%), two cancellations,
  a subscription plus ad-hoc spending at the same merchant (NS), and two subscriptions
  at the same merchant with different amounts (Odido internet and mobile)
"""

from __future__ import annotations

from moneytrail.synth.catalog import Merchant, Plan, Spend

HOME_CITY = "Eindhoven"
OTHER_CITIES = ("Amsterdam", "'s-Hertogenbosch", "Maastricht", "Rotterdam", "Tilburg")

TIKKIE_WHAT = (
    "pizza", "bier", "boodschappen", "festivalkaartjes", "verjaardag Lotte", "etentje",
    "weekendje Ardennen", "cadeau Bram", "bowlen", "taxi", "klimmen", "sushi",
)
PEOPLE = ("Lotte de Wit", "Bram Kuipers", "Sanne van der Heijden", "Joost Bakker", "Iris Peeters", "Ruben Smits")

TERMINAL_WIDTHS = (16, 18, 20, 22, 25)
TRUNCATE_SHARE = 0.45


def _m(id: str, name: str, category: str, hard: bool = False) -> Merchant:
    return Merchant(id=id, name=name, category=category, hard=hard)


_ALL = [
    # income / housing / utilities / insurance
    _m("kempen_photonics", "Kempen Photonics (salary)", "income"),
    _m("vesteda", "Vesteda", "housing"),
    _m("vandebron", "Vandebron", "utilities"),
    _m("brabant_water", "Brabant Water", "utilities"),
    _m("odido", "Odido", "utilities"),
    _m("zilveren_kruis", "Zilveren Kruis", "insurance"),
    _m("centraal_beheer", "Centraal Beheer", "insurance", hard=True),
    # groceries
    _m("albert_heijn", "Albert Heijn", "groceries"),
    _m("jumbo", "Jumbo", "groceries"),
    _m("lidl", "Lidl", "groceries"),
    _m("bakkerij_verhoeven", "Bakkerij Verhoeven", "groceries"),
    _m("slagerij_vd_heijden", "Slagerij van der Heijden", "groceries"),
    _m("toko_semarang", "Toko Semarang", "groceries"),
    _m("bonenbaron", "Bonenbaron", "groceries"),
    # eating out
    _m("cafe_de_kroon", "Cafe De Kroon", "eating_out"),
    _m("lucifer_coffee", "Lucifer Coffee", "eating_out", hard=True),
    _m("cafetaria_hoekje", "Cafetaria 't Hoekje", "eating_out", hard=True),
    _m("wok_palace", "Wok Palace", "eating_out", hard=True),
    _m("thuisbezorgd", "Thuisbezorgd", "eating_out"),
    _m("van_moll", "Van Moll", "eating_out"),
    # shopping
    _m("bol", "bol.com", "shopping"),
    _m("coolblue", "Coolblue", "shopping"),
    _m("hema", "HEMA", "shopping"),
    _m("action", "Action", "shopping"),
    _m("zalando", "Zalando", "shopping"),
    _m("decathlon", "Decathlon", "shopping"),
    _m("rijwielshop_online", "Rijwielshop Online", "shopping"),
    _m("wolkenwol", "Wolkenwol", "shopping"),
    _m("vinted", "Vinted", "shopping"),
    # personal care / health / fitness
    _m("kruidvat", "Kruidvat", "personal_care"),
    _m("barbershop_stratum", "Barbershop Stratum", "personal_care", hard=True),
    _m("apotheek_de_kroon", "Apotheek De Kroon", "health_fitness"),
    _m("neoliet", "Neoliet climbing gym", "health_fitness"),
    # transport
    _m("ns", "NS", "transport"),
    _m("swapfiets", "Swapfiets", "transport"),
    _m("uber", "Uber", "transport"),
    # entertainment / education
    _m("spotify", "Spotify", "entertainment"),
    _m("videoland", "Videoland", "entertainment"),
    _m("nrc", "NRC", "entertainment"),
    _m("icloud", "iCloud", "entertainment"),
    _m("museumkaart", "Museumkaart", "entertainment"),
    _m("pathe", "Pathe", "entertainment"),
    _m("effenaar", "Effenaar", "entertainment"),
    _m("steam", "Steam", "entertainment"),
    _m("bibliotheek", "Bibliotheek Eindhoven", "education"),
    # people, savings, cash
    _m("tikkie", "Tikkie", "transfers"),
    _m("sanne", "Sanne van der Heijden", "transfers"),
    _m("joost", "Joost Bakker", "transfers"),
    _m("parents", "Mum and dad", "transfers"),
    _m("savings", "Own savings account", "savings"),
    _m("geldmaat", "Cash withdrawal (Geldmaat)", "cash"),
]
MERCHANTS: dict[str, Merchant] = {m.id: m for m in _ALL}


ADHOC: list[Spend] = [
    # --- groceries ---------------------------------------------------------------
    Spend("albert_heijn", "card",
          ("ALBERT HEIJN {store}", "AH {store} {CITY}", "Albert Heijn {store} {City}", "AH to go {City} {store}"),
          8.0, (2.5, 65.0)),
    Spend("jumbo", "card",
          ("Jumbo {City} {store}", "JUMBO SUPERMARKTEN {store}", "JUMBO{store} {CITY}"),
          3.5, (3.0, 70.0)),
    Spend("lidl", "card", ("Lidl {store} {City}", "LIDL {store} {CITY}", "Lidl Nederland GmbH {store}"), 2.5, (4.0, 45.0)),
    Spend("bakkerij_verhoeven", "card",
          ("BAKKERIJ VERHOEVEN", "CCV*BAKKERIJ VERHOEVEN", "Bakkerij Verhoeven {City}", "BAKKERIJVERHOEVEN"),
          2.5, (2.10, 3.45, 4.20, 5.95, 8.40), menu=True),
    Spend("slagerij_vd_heijden", "card",
          ("SLAGERIJ V.D. HEIJDEN", "SumUp  *Slagerij vd Heijden", "Slagerij van der Heijden VOF"),
          0.8, (6.0, 32.0)),
    Spend("toko_semarang", "card", ("SUMUP *TOKO SEMARANG", "SumUp *Toko Semarang {City}"), 0.8, (4.0, 28.0)),
    Spend("bonenbaron", "ideal",
          ("Bonenbaron via Stichting Mollie Payments", "Stichting Mollie Payments"),
          0.4, (14.95, 24.90, 29.85), menu=True,
          remittance="M{ref} 0000 Bonenbaron bestelling", iban_owner="mollie"),
    # --- eating out --------------------------------------------------------------
    Spend("cafe_de_kroon", "card",
          ("CAFE DE KROON", "CCV*CAFE DE KROON {CITY}", "Cafe de Kroon {City}", "iZ *Cafe De Kroon"),
          2.0, (4.5, 48.0)),
    Spend("lucifer_coffee", "card",
          ("CCV*BRUGMAN&ZN HOLDING", "BRUGMAN EN ZN HOLDING B.V.", "Brugman & Zn Holding BV {CITY}"),
          4.0, (3.40, 3.90, 4.20, 7.50, 8.95), menu=True),
    Spend("cafetaria_hoekje", "card",
          ("J.M. JANSSEN HORECA V.O.F.", "SumUp  *JM Janssen Horeca", "JANSSEN HORECA VOF {CITY}"),
          1.0, (4.5, 19.0)),
    Spend("wok_palace", "card", ("HUANG CATERING B.V.", "ZETTLE_*Huang Catering BV", "HUANG CATERING {CITY}"), 0.7, (12.0, 38.0)),
    Spend("thuisbezorgd", "ideal",
          ("Thuisbezorgd.nl", "Takeaway.com Payments B.V.", "TAKEAWAY.COM PAYMENTS BV"),
          1.5, (14.0, 42.0), remittance="Thuisbezorgd.nl bestelling {ref}"),
    Spend("van_moll", "card",
          ("iZ *Van Moll Brouwerij", "VAN MOLL CRAFT BEER BV", "VANMOLL {CITY}"),
          1.3, (5.5, 55.0)),
    # --- shopping ----------------------------------------------------------------
    Spend("bol", "ideal", ("bol.com b.v.", "BOL.COM BV"), 1.4, (7.0, 120.0), remittance="{ref} bestelling bol.com"),
    Spend("coolblue", "ideal", ("Coolblue B.V.", "COOLBLUE BV ROTTERDAM"), 0.2, (19.0, 420.0),
          remittance="Coolblue bestelnummer {ref}"),
    Spend("hema", "card", ("HEMA {City} {store}", "HEMA BV EHV{store}", "Hema {store}"), 1.0, (2.0, 35.0)),
    Spend("action", "card", ("ACTION {store}", "Action {City} {store}", "ACTION NEDERLAND BV"), 1.3, (1.5, 30.0)),
    Spend("zalando", "ideal", ("Zalando SE", "Zalando Payments GmbH"), 0.3, (25.0, 140.0), remittance="{ref} Zalando"),
    Spend("decathlon", "card", ("DECATHLON {store}", "Decathlon {City}", "DECATHLON NETHERLANDS BV"), 0.3, (8.0, 90.0)),
    Spend("rijwielshop_online", "ideal",
          ("Rijwielshop Online via Stichting Mollie Payments", "Stichting Mollie Payments"),
          0.2, (9.0, 75.0), remittance="M{ref} 0000 Rijwielshop Online order", iban_owner="mollie"),
    Spend("wolkenwol", "ideal",
          ("Wolkenwol via Stichting Mollie Payments", "Stichting Mollie Payments", "Stg Mollie Payments Wolkenwol"),
          0.25, (12.0, 60.0), remittance="M{ref} 0000 Wolkenwol", iban_owner="mollie"),
    Spend("vinted", "ideal", ("PayPal Europe S.a.r.l. et Cie S.C.A", "PAYPAL *VINTED"), 0.4, (6.0, 45.0),
          remittance="{ref} PAYPAL Vinted UAB", iban_owner="paypal"),
    # --- personal care / health ---------------------------------------------------
    Spend("kruidvat", "card", ("KRUIDVAT {store}", "Kruidvat {store} {CITY}", "KRUIDVAT{store}"), 1.3, (2.0, 30.0)),
    Spend("barbershop_stratum", "card", ("SUMUP *EL AMRANI HAIR", "EL AMRANI HAIR V.O.F.", "SQ *EL AMRANI HAIR"),
          0.7, (22.50, 25.00, 27.50), menu=True),
    Spend("apotheek_de_kroon", "card", ("APOTHEEK DE KROON", "Apotheek de Kroon B.V.", "APOTHEEK DE KROON {CITY}"),
          0.3, (3.5, 24.0)),
    Spend("neoliet", "card", ("NEOLIET EINDHOVEN", "CCV*NEOLIET KLIMHAL", "Neoliet Klimhal Ehv"), 0.6, (2.5, 18.0)),
    # --- transport -----------------------------------------------------------------
    Spend("ns", "card", ("NS GROEP IZ NS REIZIGERS", "NS {CITY} {store}", "NS REIZIGERS BV {CITY}"), 1.8, (3.0, 28.0)),
    Spend("ns", "ideal", ("NS International B.V.", "NS INTERNATIONAL BV"), 0.15, (39.0, 160.0),
          remittance="NS International boeking {ref}"),
    Spend("uber", "card", ("UBER *TRIP HELP.UBER.COM", "UBER   *TRIP", "Uber BV"), 0.3, (9.0, 32.0)),
    # --- entertainment ---------------------------------------------------------------
    Spend("pathe", "card", ("PATHE {CITY}", "Pathe Theaters B.V.", "MSP*PATHE {City}"), 0.5, (11.50, 14.50, 23.00, 29.00),
          menu=True),
    Spend("effenaar", "card", ("STG EFFENAAR", "Effenaar {City}", "CCV*EFFENAAR"), 0.4, (4.0, 38.0)),
    Spend("steam", "ideal", ("PayPal Europe S.a.r.l. et Cie S.C.A", "PAYPAL *STEAM GAMES"), 0.2, (4.99, 59.99),
          remittance="{ref} PAYPAL Valve Corporation Steam", iban_owner="paypal"),
    # --- people ----------------------------------------------------------------------
    Spend("tikkie", "ideal", ("Tikkie", "AAB INZ TIKKIE", "ABN AMRO Bank NV inz Tikkie"), 2.5, (4.0, 45.0),
          remittance="Tikkie ID {ref}, {what}, {person}"),
    Spend("tikkie", "transfer_in", ("AAB INZ TIKKIE", "Tikkie"), 0.8, (5.0, 60.0),
          remittance="Tikkie ID {ref}, {what}, via {person}"),
    Spend("sanne", "transfer_in", ("S. van der Heijden", "SANNE VAN DER HEIJDEN", "S VD HEIJDEN"), 0.5, (8.0, 90.0),
          remittance="{what}"),
    Spend("sanne", "transfer_out", ("S. van der Heijden", "Sanne vd Heijden"), 0.2, (10.0, 60.0), remittance="{what}"),
    Spend("joost", "transfer_out", ("J BAKKER", "Joost Bakker", "J.W. Bakker"), 0.4, (10.0, 75.0), remittance="{what}"),
    Spend("parents", "transfer_in",
          ("P.J.M. VERHOEVEN EN/OF A. VERHOEVEN-SMITS", "Fam Verhoeven", "P J M Verhoeven"),
          0.25, (25.0, 250.0), remittance="{what}"),
    Spend("savings", "transfer_out", ("M.A. Verhoeven", "M A VERHOEVEN"), 0.3, (50.0, 400.0),
          remittance="extra sparen"),
    # --- cash ------------------------------------------------------------------------
    Spend("geldmaat", "atm", ("GELDMAAT {CITY} {store}", "Geldmaat {City}"), 0.6, (20.0, 50.0, 70.0, 100.0), menu=True),
]


def _next_month(first_month: int, months: int, calendar_month: int) -> int | None:
    """Offset (>= 1) of the first occurrence of `calendar_month`, or None if not in range."""
    for offset in range(1, months):
        if (first_month - 1 + offset) % 12 + 1 == calendar_month:
            return offset
    return None


def _rise(base: float, new: float, at: int | None) -> tuple[tuple[int, float], ...]:
    return ((0, base),) if at is None else ((0, base), (at, new))


def recurring_plans(first_month: int, months: int) -> list[Plan]:
    jan = _next_month(first_month, months, 1)  # New-Year rises (salary CAO, health premium)
    jul = _next_month(first_month, months, 7)  # annual rent increase on 1 July
    odido_from = min(5, months - 1)
    gym_from = min(8, months - 1)
    return [
        Plan("salary", "kempen_photonics", "transfer_in", ((0, "KEMPEN PHOTONICS B.V."),), "monthly", 24,
             _rise(3184.62, 3296.07, jan), remittance="Salaris {month} pers.nr 004417"),
        Plan("rent", "vesteda", "direct_debit", ((0, "VESTEDA WONINGEN BV"),), "monthly", 1,
             _rise(1245.00, 1307.25, jul), remittance="Huur {period} Kruisstraat 88-B Eindhoven"),
        Plan("energy", "vandebron", "direct_debit", ((0, "Vandebron Energie B.V."),), "monthly", 12,
             ((0, 118.00),), remittance="Termijnbedrag {month} klantnr 7730215"),
        Plan("water", "brabant_water", "direct_debit", ((0, "BRABANT WATER N.V."),), "monthly", 20,
             ((0, 19.40),), remittance="Voorschot drinkwater {period}"),
        Plan("odido_internet", "odido", "direct_debit",
             ((0, "T-MOBILE NETHERLANDS B.V."), (odido_from, "ODIDO NETHERLANDS B.V.")), "monthly", 25,
             ((0, 52.50),), remittance="Thuis internet factuur {ref}"),
        Plan("odido_mobile", "odido", "direct_debit",
             ((0, "T-MOBILE NETHERLANDS B.V."), (odido_from, "ODIDO NETHERLANDS B.V.")), "monthly", 25,
             ((0, 17.50),), remittance="Mobiel abonnement factuur {ref}"),
        Plan("health_insurance", "zilveren_kruis", "direct_debit",
             ((0, "ZILVEREN KRUIS ZORGVERZEKERINGEN NV"),), "monthly", 1,
             _rise(142.35, 147.90, jan), remittance="Premie {month} polis 190344521"),
        Plan("contents_insurance", "centraal_beheer", "direct_debit",
             ((0, "ACHMEA SCHADEVERZEKERINGEN N.V."),), "yearly", 15,
             ((0, 138.72),), remittance="Jaarpremie inboedel en aansprakelijkheid {ref}", start=2),
        Plan("nsflex", "ns", "direct_debit", ((0, "NS REIZIGERS B.V."),), "monthly", 22,
             ((0, 32.00),), remittance="NS Flex Dal Voordeel {month}"),
        Plan("swapfiets", "swapfiets", "direct_debit", ((0, "Swapfiets B.V."),), "monthly", 3,
             ((0, 19.90),), remittance="Swapfiets Original {period}"),
        Plan("climbing", "neoliet", "direct_debit",
             ((0, "NEOLIET KLIMHAL EINDHOVEN"), (gym_from, "BLOC NEOLIET B.V.")), "four_weekly", 6,
             ((0, 54.50),), remittance="Lidmaatschap 4 weken {ref}"),
        Plan("spotify", "spotify", "card", ((0, "Spotify AB"),), "monthly", 9,
             ((0, 11.99), (min(6, months - 1), 12.99))),
        Plan("icloud", "icloud", "card", ((0, "APPLE.COM/BILL"),), "monthly", 17, ((0, 2.99),)),
        Plan("videoland", "videoland", "direct_debit", ((0, "Videoland via RTL Nederland B.V."),), "monthly", 14,
             ((0, 9.99),), remittance="Videoland Plus {month}", stop=min(9, months)),
        Plan("nrc", "nrc", "direct_debit", ((0, "NRC MEDIA B.V."),), "monthly", 4,
             ((0, 15.00),), remittance="NRC Digitaal {period}", start=1, stop=min(14, months)),
        Plan("museumkaart", "museumkaart", "ideal", ((0, "Stichting Museumkaart"),), "yearly", 11,
             ((0, 75.00),), remittance="Verlenging Museumkaart {ref}", start=4),
        Plan("library", "bibliotheek", "direct_debit", ((0, "BIBLIOTHEEK EINDHOVEN"),), "yearly", 2,
             ((0, 49.00),), remittance="Contributie bibliotheek {ref}", start=7),
        Plan("savings", "savings", "transfer_out", ((0, "M.A. Verhoeven"),), "monthly", 25,
             ((0, 400.00),), remittance="Sparen"),
    ]
