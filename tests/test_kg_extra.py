"""Knowledge-graph checks for authorship, current office, quantities and currency
(member2_data/kg_extra.py). Wikidata is simulated: no network. Each case was found by
probing unseen claims (all four were wrong before)."""
from member2_data import kg_extra
from member2_data.kg_extra import name_matches


class Linker:
    """Exact-name search: name -> item ids."""
    def __init__(self, exact, top=None):
        self.exact, self.top = exact, top or {}

    def search_places(self, text, language="en"):
        return tuple(self.exact.get(text, ()))

    def search_entity(self, text, language="en"):
        return type("M", (), {"qid": self.top.get(text) or (self.exact.get(text) or [None])[0]})()


class WD:
    """statements[(qid, pid)] -> list of statements; names/labels from `names`."""
    def __init__(self, statements, names):
        self.st, self.nm = statements, names

    def statements(self, qid, pid):
        return self.st.get((qid, pid), [])

    def names(self, ids, language="en"):
        return {i: {n.casefold() for n in self.nm.get(i, [])} for i in ids}

    def labels(self, ids, language="en"):
        return {i: self.nm[i][0] for i in ids if self.nm.get(i)}


def item(q):
    return {"value": {"id": q}, "rank": "normal", "qualifiers": {}}


def ended(q):
    return {"value": {"id": q}, "rank": "normal", "qualifiers": {"P582": [{}]}}


def qty(amount, unit="Q11573", rank="normal"):
    return {"value": {"amount": f"+{amount}", "unit": f"http://www.wikidata.org/entity/{unit}"}, "rank": rank,
            "qualifiers": {}}


NAMES = {"Q_tagore": ["Rabindranath Tagore", "Tagore"], "Q_premchand": ["Premchand"],
         "Q_murmu": ["Droupadi Murmu"], "Q_patil": ["Pratibha Patil"], "Q_yen": ["Japanese yen", "yen"],
         "Q_euro": ["euro"], "Q_rupee": ["Indian rupee"]}


def test_names_match_by_words():
    assert name_matches("Tagore", {"rabindranath tagore"}) and name_matches("J. K. Rowling", {"j. k. rowling"})
    assert name_matches("rupee", {"indian rupee"}) and not name_matches("Premchand", {"rabindranath tagore"})


def test_authorship_supports_the_author_and_contradicts_another_known_person():
    linker = Linker({"Gitanjali": ["Q_git"], "Premchand": ["Q_premchand"], "Rabindranath Tagore": ["Q_tagore"]})
    wd = WD({("Q_git", "P50"): [item("Q_tagore")]}, NAMES)
    assert kg_extra.check("Rabindranath Tagore wrote Gitanjali.", "en", linker, wd).status == "supported"
    assert kg_extra.check("Gitanjali was written by Tagore.", "en", linker, wd).status == "supported"
    v = kg_extra.check("Premchand wrote Gitanjali.", "en", linker, wd)
    assert (v.status, v.actual_text) == ("contradicted", ("Rabindranath Tagore",))
    # an author name Wikidata does not know never contradicts
    assert kg_extra.check("Somebody Unknown wrote Gitanjali.", "en", linker, wd).status == "unknown"


def test_a_former_office_holder_is_not_the_current_one():
    linker = Linker({"Droupadi Murmu": ["Q_murmu"], "Pratibha Patil": ["Q_patil"]},
                    top={"President of India": "Q_pres"})
    wd = WD({("Q_pres", "P1308"): [item("Q_murmu"), ended("Q_patil")],
             ("Q_murmu", "P39"): [item("Q_pres")], ("Q_patil", "P39"): [ended("Q_pres")]}, NAMES)
    assert kg_extra.check("Droupadi Murmu is the President of India.", "en", linker, wd).status == "supported"
    v = kg_extra.check("Pratibha Patil is the President of India.", "en", linker, wd)
    assert (v.status, v.actual_text) == ("contradicted", ("Droupadi Murmu",))


def test_quantities_with_units_and_tolerance():
    linker = Linker({"Mount Everest": ["Q_ev"], "India": ["Q_in", "Q_other_india"]})
    wd = WD({("Q_ev", "P2044"): [qty(8848.86)],
             ("Q_in", "P1082"): [qty(1326093247, "1", rank="preferred"), qty(361088090, "1")]}, NAMES)
    assert kg_extra.check("Mount Everest is 8,849 metres tall.", "en", linker, wd).status == "supported"
    assert kg_extra.check("Mount Everest is 29,032 feet tall.", "en", linker, wd).status == "supported"
    assert kg_extra.check("Mount Everest is 7,200 metres tall.", "en", linker, wd).status == "contradicted"
    assert kg_extra.check("माउंट एवरेस्ट की ऊंचाई ५,००० मीटर है।", "hi", Linker({"माउंट एवरेस्ट": ["Q_ev"]}), wd
                          ).status == "contradicted"
    # the preferred (current) value decides, not an old census
    assert kg_extra.check("India has a population of about 1.4 billion.", "en", linker, wd).status == "supported"
    assert kg_extra.check("India has a population of about 600 million.", "en", linker, wd).status == "contradicted"
    assert kg_extra.check("भारत की जनसंख्या लगभग 140 करोड़ है।", "hi", Linker({"भारत": ["Q_in"]}), wd).status == "supported"


def test_currency_in_both_languages():
    linker = Linker({"Japan": ["Q_jp"], "euro": ["Q_euro"], "India": ["Q_in"], "जापान": ["Q_jp"], "यूरो": ["Q_euro"]})
    wd = WD({("Q_jp", "P38"): [item("Q_yen")], ("Q_in", "P38"): [item("Q_rupee")]},
            {**NAMES, "Q_yen": ["Japanese yen", "yen", "जापानी येन", "येन"]})
    assert kg_extra.check("The currency of Japan is the yen.", "en", linker, wd).status == "supported"
    assert kg_extra.check("The currency of Japan is the euro.", "en", linker, wd).status == "contradicted"
    assert kg_extra.check("The currency of India is the rupee.", "en", linker, wd).status == "supported"
    assert kg_extra.check("जापान की मुद्रा येन है।", "hi", linker, wd).status == "supported"
    assert kg_extra.check("जापान की मुद्रा यूरो है।", "hi", linker, wd).status == "contradicted"


def test_other_claims_are_left_to_the_general_path():
    assert kg_extra.check("The Taj Mahal is located in Agra.", "en", Linker({}), WD({}, {})) is None
