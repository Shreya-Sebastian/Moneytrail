"""Hand-written register entries and places for the held-out persona (Eindhoven).

These cover the shops that only appear under a legal or holding name, plus look-alikes:
companies with nearly the same legal name in other cities, holdings and group entities
with several trade names, entries that share an owner's surname or initials, and places
in Eindhoven with similar names that belong to someone else. A lookup alone should not
settle the answer; the address, the kind of place and the home city have to be checked.
"""

from moneytrail.world import Company, Place

COMPANIES = [
    # --- contents insurance under the insurer's group entity --------------------------
    Company("80524917", "Achmea Schadeverzekeringen N.V.",
            ("Centraal Beheer", "Interpolis", "FBTO", "Avéro Achmea", "Achmea Schadeservice", "Inshared"),
            "Laan van Malkenschoten 20", "Apeldoorn", "Non-life insurance"),
    Company("80631254", "Achmea Pensioen- en Levensverzekeringen N.V.",
            ("Centraal Beheer", "Interpolis", "Achmea Pensioenen"),
            "Laan van Malkenschoten 20", "Apeldoorn", "Life insurance and pensions"),
    Company("58302261", "Achmea Schadeverzekeringen Holding B.V.", (),
            "Handelsweg 2", "Zeist", "Holding companies"),
    # --- Lucifer Coffee, run by a holding with more than one business -------------------
    Company("68940173", "Brugman & Zn Holding B.V.",
            ("Lucifer Coffee", "Lucifer Roastery", "Brugman Vastgoed"),
            "Kleine Berg 34", "Eindhoven", "Holding companies; cafes; wholesale of coffee"),
    Company("61772408", "Brugman Holding B.V.", ("Brugman Interieurbouw",),
            "Overtoom 211", "Amsterdam", "Holding companies; joinery"),
    Company("53318896", "Brugman en Zonen B.V.", ("Brugman Installatietechniek",),
            "Zestienhovensekade 410", "Rotterdam", "Plumbing and heating installation"),
    # --- Cafetaria 't Hoekje, a V.O.F. named after its owner ------------------------------
    Company("67215530", "J.M. Janssen Horeca V.O.F.", ("Cafetaria 't Hoekje",),
            "Stratumsedijk 61", "Eindhoven", "Snack bars and takeaways"),
    Company("67480312", "J.M. Janssen Beheer B.V.", (),
            "Aalsterweg 210", "Eindhoven", "Holding companies"),
    Company("56093847", "J.M.A. Janssen Installatietechniek", ("Janssen Installaties Eindhoven",),
            "Boschdijk 455", "Eindhoven", "Electrical installation"),
    Company("62847105", "Janssen Horeca B.V.", ("Grand Café Janssen",),
            "Piusplein 18", "Tilburg", "Restaurants and cafes"),
    Company("65520978", "Hoekske Horeca B.V.", ("Eetcafé 't Hoekske",),
            "Woenselse Markt 22", "Eindhoven", "Restaurants and cafes"),
    # --- Wok Palace, a takeaway run by a catering B.V. ----------------------------------
    Company("69381142", "Huang Catering B.V.", ("Wok Palace", "Huang Party Catering"),
            "Geldropseweg 88", "Eindhoven", "Restaurants; event catering"),
    Company("57026694", "Huang Catering Services B.V.", ("Golden Dragon Catering",),
            "Katendrechtse Lagedijk 77", "Rotterdam", "Event catering"),
    Company("85147730", "Lin & Chen Horeca V.O.F.", ("New Wok Palace",),
            "Kastelenplein 160", "Eindhoven", "Restaurants"),
    # --- Barbershop Stratum, under the owner's name -------------------------------------
    Company("66810359", "El Amrani Hair V.O.F.", ("Barbershop Stratum",),
            "Leenderweg 143", "Eindhoven", "Hairdressers and barbers"),
    Company("63395021", "Y. el Amrani Hair & Beauty", ("Salon Yasmina",),
            "Korvelseweg 98", "Tilburg", "Hairdressers and beauty salons"),
    Company("81920467", "El Amrani Holding B.V.", (),
            "Javastraat 61", "Amsterdam", "Holding companies"),
    Company("64458823", "El Amrani Transport", (),
            "Hurksestraat 19", "Eindhoven", "Road freight transport"),
    Company("86630154", "Stratum Barbers B.V.", ("Stratum Barbers",),
            "Geldropseweg 230", "Eindhoven", "Hairdressers and barbers"),
    # --- decoys for name collisions among the easy merchants ----------------------------
    Company("60218749", "Verhoeven Brood en Banket B.V.", ("Bakkerij Verhoeven",),
            "Heuvelring 41", "Tilburg", "Bakeries"),
    Company("82290375", "De Kroon Holding B.V.", ("Hotel De Kroon",),
            "Vrijthof 23", "Maastricht", "Holding companies; hotels"),
]

PLACES = [
    Place("Centraal Beheer", "insurer office", "Laan van Malkenschoten 20", "Apeldoorn"),
    Place("Interpolis", "insurer office", "Spoorlaan 298", "Tilburg"),
    Place("FBTO", "insurer office", "Zuidersingel 4", "Leeuwarden"),
    Place("Lucifer Coffee", "cafe", "Kleine Berg 34", "Eindhoven"),
    Place("Lucifer Roastery", "coffee roastery (wholesale)", "Torenallee 22", "Eindhoven"),
    Place("Brugman Vastgoed", "office", "Willemstraat 51", "Eindhoven"),
    Place("Cafetaria 't Hoekje", "snack bar", "Stratumsedijk 61", "Eindhoven"),
    Place("Eetcafé 't Hoekske", "cafe", "Woenselse Markt 22", "Eindhoven"),
    Place("Grand Café Janssen", "cafe", "Piusplein 18", "Tilburg"),
    Place("Wok Palace", "takeaway", "Geldropseweg 88", "Eindhoven"),
    Place("Huang Party Catering", "catering kitchen", "De Run 4210", "Veldhoven"),
    Place("New Wok Palace", "restaurant", "Kastelenplein 160", "Eindhoven"),
    Place("Barbershop Stratum", "barber", "Leenderweg 143", "Eindhoven"),
    Place("Stratum Barbers", "barber", "Geldropseweg 230", "Eindhoven"),
    Place("Salon Yasmina", "hair and beauty salon", "Korvelseweg 98", "Tilburg"),
    Place("Bakkerij Verhoeven", "bakery", "Heuvelring 41", "Tilburg"),
    Place("Hotel De Kroon", "hotel", "Vrijthof 23", "Maastricht"),
]
