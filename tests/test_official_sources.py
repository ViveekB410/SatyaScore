"""Official sources: World Bank / WHO statistics (member2_data/official_stats.py) and the
MedlinePlus evidence source (member3_backend/medline_expander.py). Simulated responses: no
network."""
from member2_data import official_stats as st
from member3_backend.evidence_rules import SubjectIndex, passage_site, passage_source


class Linker:
    def __init__(self, exact):
        self.exact = exact

    def search_places(self, text, language="en"):
        return tuple(self.exact.get(text, ()))


class WD:
    """Q_jp is a country (ISO code JPN); Q_tokyo is a city (no ISO code)."""
    def statements(self, qid, pid):
        return [{"value": "JPN", "rank": "normal"}] if (qid, pid) == ("Q_jp", "P298") else []

    def labels(self, ids, language="en"):
        return {"Q_jp": "Japan" if language == "en" else "जापान"}


def figures(monkeypatch, wb, who=None):
    monkeypatch.setattr(st, "world_bank", lambda session, iso, ind: wb.get(ind))
    monkeypatch.setattr(st, "who", lambda session, iso, code: (who or {}).get(code))


LINKER = Linker({"Japan": ["Q_jp"], "जापान": ["Q_jp"], "Tokyo": ["Q_tokyo"]})


def test_claims_are_read_in_english_and_hindi():
    assert st.parse("Life expectancy in Japan is 84 years", "en")[:3] == ("life", "Japan", 84.0)
    assert st.parse("The GDP of India is about $3.9 trillion", "en")[2] == 3.9e12
    assert st.parse("The literacy rate of India is about 78%", "en")[:3] == ("literacy", "India", 78.0)
    assert st.parse("भारत में जीवन प्रत्याशा लगभग 72 वर्ष है", "hi")[:3] == ("life", "भारत", 72.0)
    assert st.parse("The Taj Mahal is in Agra", "en") is None


def test_both_agencies_must_agree(monkeypatch):
    figures(monkeypatch, {"SP.DYN.LE00.IN": (2024, 84.0, "JP")}, {"WHOSIS_000001": (2023, 83.9)})
    v = st.check("Life expectancy in Japan is 84 years.", "en", LINKER, WD())
    assert v.status == "supported" and v.display["authority"] == "World Bank, WHO"
    assert st.check("Life expectancy in Japan is 65 years.", "en", LINKER, WD()).status == "contradicted"
    # the agencies disagree about the claim: no verdict
    figures(monkeypatch, {"SP.DYN.LE00.IN": (2024, 84.0, "JP")}, {"WHOSIS_000001": (2023, 79.0)})
    assert st.check("Life expectancy in Japan is 83 years.", "en", LINKER, WD()).status == "unknown"


def test_a_rounded_figure_is_accepted_at_its_precision(monkeypatch):
    # attempt 1 contradicted "The GDP of Tuvalu is about $0.1 billion" (0.066 billion)
    figures(monkeypatch, {"NY.GDP.MKTP.CD": (2024, 0.066e9, "JP")})
    assert st.check("The GDP of Japan is about $0.1 billion.", "en", LINKER, WD()).status == "supported"
    assert st.check("The GDP of Japan is about $0.5 billion.", "en", LINKER, WD()).status == "contradicted"


def test_only_countries_are_checked(monkeypatch):
    figures(monkeypatch, {"SP.POP.TOTL": (2025, 1.2e8, "JP")})
    assert st.check("Tokyo has a population of about 14 million.", "en", LINKER, WD()) is None  # city: Wikidata
    assert st.check("Japan has a population of about 120 million.", "en", LINKER, WD()).status == "supported"
    assert st.check("जापान की जनसंख्या लगभग 50 करोड़ है।", "hi", LINKER, WD()).status == "contradicted"


def test_a_failed_lookup_gives_no_signal(monkeypatch):
    def boom(*a):
        raise TimeoutError("slow")
    monkeypatch.setattr(st, "world_bank", boom)
    monkeypatch.setattr(st, "who", boom)
    assert st.check("Life expectancy in Japan is 84 years.", "en", LINKER, WD()).status == "unknown"


SAMPLE = """<?xml version="1.0" encoding="UTF-8"?><nlmSearchResult><list>
<document rank="0" url="https://medlineplus.gov/dengue.html">
<content name="title">&lt;span class="qt0"&gt;Dengue&lt;/span&gt;</content>
<content name="altTitle">Dengue Fever</content>
<content name="FullSummary">What is dengue?&lt;p&gt;Dengue is an infection caused by a virus. You can get it if an
infected mosquito bites you. Dengue does not spread from person to person.&lt;/p&gt;</content>
</document></list></nlmSearchResult>"""


def test_medlineplus_topics_are_parsed_linked_and_named():
    from member3_backend.medline_expander import SOURCES, parse, passage_id
    [t] = parse(SAMPLE)
    assert (t["title"], t["url"], t["alt"]) == ("Dengue", "https://medlineplus.gov/dengue.html", ["Dengue Fever"])
    assert t["text"].startswith("What is dengue?") and "Dengue is an infection" in t["text"]
    assert "\n\n" in t["text"]  # the heading is a separate paragraph
    SOURCES["Dengue"] = {"url": t["url"], "alt": t["alt"]}
    pid = passage_id("Dengue", 0)
    assert passage_site(pid) == "MedlinePlus" and passage_source(pid) == ("Dengue", "en", t["url"])
    # the topic and its "also called" names count as the subject for the evidence rule
    s = SubjectIndex(strict=True)
    assert s.on_topic("Dengue fever is spread by mosquitoes.", pid)
    assert not s.on_topic("Malaria is spread by mosquitoes.", pid)
