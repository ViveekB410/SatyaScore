"""Version 2 knowledge-graph relations (member2_data/kg_relations.py). Wikidata is simulated: no network."""
import pytest

from member2_data import kg_extra


class Linker:
    """named[text] -> [(qid, description)]."""
    def __init__(self, named):
        self.named = named

    def search_named(self, text, language="en", kinds=()):
        hits = self.named.get(text, [])
        if kinds:
            typed = tuple(q for q, d in hits if any(k in d for k in kinds))
            if typed:
                return typed, True
        return tuple(q for q, _ in hits), False

    def search_places(self, text, language="en"):
        return tuple(q for q, _ in self.named.get(text, []))


class WD:
    def __init__(self, st, names):
        self.st, self.nm = st, names

    def statements(self, qid, pid):
        return self.st.get((qid, pid), [])

    def names(self, ids, language="en"):
        return {i: {n.casefold() for n in self.nm.get(i, [])} for i in ids}

    def labels(self, ids, language="en"):
        return {i: self.nm[i][0] for i in ids if self.nm.get(i)}


def item(q):
    return {"value": {"id": q}, "rank": "normal", "qualifiers": {}}


def date(y, precision=11):
    return {"value": {"time": f"+{y}-05-01T00:00:00Z", "precision": precision}, "rank": "normal", "qualifiers": {}}


NAMES = {"Q30": ["United States of America", "USA"], "Q145": ["United Kingdom"], "Q16": ["Canada"],
         "Q668": ["India", "भारत"], "Q884": ["South Korea"], "Q_actor": ["actor", "actress", "अभिनेता"],
         "Q_dancer": ["dancer"], "Q_rapper": ["rapper"], "Q_nolan": ["Christopher Nolan"],
         "Q_spielberg": ["Steven Spielberg"], "Q_melb": ["Mel B"], "Q_gosling": ["Ryan Gosling"]}


@pytest.fixture(autouse=True)
def relations_on(monkeypatch):
    monkeypatch.setenv("SATYASCORE_KG_RELATIONS", "1")


def status(claim, linker, wd, language="en"):
    r = kg_extra.check(claim, language, linker, wd)
    return None if r is None else r.status


def test_switched_off_by_default(monkeypatch):
    monkeypatch.delenv("SATYASCORE_KG_RELATIONS")
    linker = Linker({"Janet Leigh": [("Q_jl", "American actress")]})
    wd = WD({("Q_jl", "P27"): [item("Q30")]}, NAMES)
    assert kg_extra.check("Janet Leigh was Canadian.", "en", linker, wd) is None


def test_nationality_supports_and_contradicts():
    linker = Linker({"Janet Leigh": [("Q_jl", "American actress")]})
    wd = WD({("Q_jl", "P27"): [item("Q30")]}, NAMES)
    assert status("Janet Leigh was Canadian.", linker, wd) == "contradicted"
    assert status("Janet Leigh was American.", linker, wd) == "supported"
    assert status("Janet Leigh was not Canadian.", linker, wd) is None  # negation: never decided


def test_is_a_needs_every_fact_checked_for_support():
    linker = Linker({"Danny Brown": [("Q_db", "American rapper")]})
    wd = WD({("Q_db", "P27"): [item("Q30")], ("Q_db", "P106"): [item("Q_rapper")]}, NAMES)
    assert status("Danny Brown is an American rapper.", linker, wd) == "supported"
    assert status("Danny Brown is a Canadian rapper.", linker, wd) == "contradicted"
    # occupation is support-only: a wrong one gives no decision, never a contradiction
    assert status("Danny Brown is an American dancer.", linker, wd) is None
    # an unchecked word ("controversial") blocks support but not a contradiction
    assert status("Danny Brown is a controversial American rapper.", linker, wd) is None
    assert status("Danny Brown is a controversial Canadian rapper.", linker, wd) == "contradicted"


def test_work_country_and_year():
    linker = Linker({"Varsity Blues": [("Q_vb", "1999 film by Brian Robbins")],
                     "The Cry of the Owl": [("Q_c1", "1987 film"), ("Q_c2", "2009 film")]})
    wd = WD({("Q_vb", "P495"): [item("Q30")], ("Q_vb", "P577"): [date(1999)],
             ("Q_c1", "P577"): [date(1987)], ("Q_c2", "P577"): [date(2009)]}, NAMES)
    assert status("Varsity Blues is an American film.", linker, wd) == "supported"
    assert status("Varsity Blues is a 1999 American film.", linker, wd) == "supported"
    assert status("Varsity Blues is a 2002 American film.", linker, wd) == "contradicted"
    assert status("Varsity Blues is a 1999 American comedy film.", linker, wd) is None  # genre not checked
    # namesakes: one remake matching the year supports; contradiction needs all to disagree
    assert status("The Cry of the Owl is a 2009 film.", linker, wd) == "supported"
    assert status("The Cry of the Owl is a 2002 thriller film.", linker, wd) == "contradicted"


def test_released_in_year_and_decade_precision_ignored():
    linker = Linker({"Stadium Arcadium": [("Q_sa", "album")], "Old Song": [("Q_os", "song")]})
    wd = WD({("Q_sa", "P577"): [date(2006)], ("Q_os", "P577"): [date(1960, precision=8)]}, NAMES)
    assert status("Stadium Arcadium was released in 2006.", linker, wd) == "supported"
    assert status("Stadium Arcadium was released in 2009.", linker, wd) == "contradicted"
    assert status("Stadium Arcadium came out at least by 2009.", linker, wd) is None
    assert status("Old Song was released in 1964.", linker, wd) is None  # only a decade on record


def test_country_location_and_origin():
    linker = Linker({"Colosseum": [("Q_col", "amphitheatre in Rome")],
                     "Cheese in the Trap": [("Q_cit", "South Korean television series")]})
    wd = WD({("Q_col", "P17"): [item("Q_italy")], ("Q_cit", "P495"): [item("Q884")]},
            {**NAMES, "Q_italy": ["Italy"]})
    # "country" (P17) was dropped by the dev keep-or-drop rule: no decision
    assert status("The Colosseum is in the United States.", linker, wd) is None
    assert status("The Colosseum is located in Italy.", linker, wd) is None
    assert status("Cheese in the Trap comes from South Korea.", linker, wd) == "supported"


def test_director_cast_performer():
    linker = Linker({"Inception": [("Q_inc", "2010 film by Christopher Nolan")],
                     "Christopher Nolan": [("Q_nolan", "British-American filmmaker")],
                     "Steven Spielberg": [("Q_spielberg", "American filmmaker")],
                     "Ryan Gosling": [("Q_gosling", "Canadian actor")],
                     "Wannabe": [("Q_wb", "1996 single by the Spice Girls")], "Mel B": [("Q_melb", "English singer")]})
    wd = WD({("Q_inc", "P57"): [item("Q_nolan")], ("Q_inc", "P161"): [item("Q_dicaprio")],
             ("Q_wb", "P175"): [item("Q_spice")]}, {**NAMES, "Q_dicaprio": ["Leonardo DiCaprio"],
                                                   "Q_spice": ["Spice Girls"]})
    assert status("Inception was directed by Christopher Nolan.", linker, wd) == "supported"
    assert status("Steven Spielberg directed Inception.", linker, wd) == "contradicted"
    assert status("Inception was directed by Nolan and Spielberg.", linker, wd) is None
    assert status("Ryan Gosling starred in Inception.", linker, wd) is None  # cast is support-only
    assert status("Leonardo DiCaprio starred in Inception.", linker, wd) == "supported"
    assert status("Wannabe is a song by Mel B.", linker, wd) == "contradicted"
    assert status("Wannabe is a song by Spice Girls.", linker, wd) == "supported"


def test_pronoun_subjects_and_failed_lookups_are_not_decided():
    linker = Linker({"It": [("Q_it", "1990 miniseries")]})
    wd = WD({("Q_it", "P495"): [item("Q30")]}, NAMES)
    assert status("It is a Canadian miniseries.", linker, wd) is None

    class Down(WD):
        def statements(self, qid, pid):
            return None
    linker = Linker({"Janet Leigh": [("Q_jl", "American actress")]})
    assert status("Janet Leigh was Canadian.", linker, Down({}, NAMES)) is None


def test_hindi_nationality_and_location():
    linker = Linker({"शाहरुख़ ख़ान": [("Q_srk", "भारतीय अभिनेता")], "ताजमहल": [("Q_tm", "मकबरा")]})
    wd = WD({("Q_srk", "P27"): [item("Q668")], ("Q_srk", "P106"): [item("Q_actor")],
             ("Q_tm", "P17"): [item("Q668")]}, NAMES)
    assert status("शाहरुख़ ख़ान एक भारतीय अभिनेता हैं।", linker, wd, "hi") == "supported"
    assert status("शाहरुख़ ख़ान एक पाकिस्तानी अभिनेता हैं।", linker, wd, "hi") == "contradicted"
    assert status("ताजमहल भारत में स्थित है।", linker, wd, "hi") is None  # P17 dropped
    assert status("ताजमहल पाकिस्तान में स्थित है।", linker, wd, "hi") is None
    assert status("ताजमहल पाकिस्तान में स्थित नहीं है।", linker, wd, "hi") is None


def test_a_contradiction_names_the_wrong_word():
    linker = Linker({"Danny Brown": [("Q_db", "American rapper")]})
    wd = WD({("Q_db", "P27"): [item("Q30")], ("Q_db", "P106"): [item("Q_rapper")]}, NAMES)
    r = kg_extra.check("Danny Brown is a Canadian rapper.", "en", linker, wd)
    assert r.status == "contradicted" and r.expected_value == "Canadian"
