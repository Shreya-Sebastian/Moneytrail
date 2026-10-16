"""Hand-written register entries and places for the dev persona (Utrecht).

These cover the shops that only appear under a legal name, plus look-alikes: another
company with nearly the same legal name in a different city, and holdings with more
than one trade name, so a lookup alone doesn't settle the answer.
"""

from moneytrail.world import Company, Place

COMPANIES = [
    # Cafe Jansz is run by JV Holding; the holding also has an events business.
    Company("68120457", "JV Holding B.V.", ("Cafe Jansz", "Jansz Events"), "Oudegracht 112", "Utrecht",
            "Holding companies; cafes"),
    Company("71455032", "JV Holding Amsterdam B.V.", ("Vermeer Vastgoed",), "Keizersgracht 401", "Amsterdam",
            "Holding companies; real estate"),
    Company("59003318", "J.V. Holland Holding B.V.", (), "Industrieweg 4", "Nieuwegein",
            "Holding companies"),
    # Tokyo Ramen is run by TKR Horeca, which also runs a sushi delivery kitchen.
    Company("74318826", "TKR Horeca B.V.", ("Tokyo Ramen", "TKR Sushi Delivery"), "Voorstraat 41", "Utrecht",
            "Restaurants"),
    Company("80022179", "TKR Holding B.V.", ("TKR Logistics",), "Waalhaven 12", "Rotterdam",
            "Holding companies; freight transport"),
]

PLACES = [
    Place("Cafe Jansz", "cafe", "Oudegracht 112", "Utrecht"),
    Place("Jansz Events", "office", "Kanaalweg 3", "Utrecht"),
    Place("Tokyo Ramen", "restaurant", "Voorstraat 41", "Utrecht"),
    Place("TKR Sushi Delivery", "takeaway kitchen", "Atoomweg 50", "Utrecht"),
    Place("Cafe Janssen", "cafe", "Lange Nieuwstraat 9", "Utrecht"),
]
