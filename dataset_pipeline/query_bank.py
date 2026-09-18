"""
Seed query bank for dataset generation.

PRD ref: Section 11.2 Step 1 — "Create 1,500+ factual questions in English
and Hindi covering Healthcare, History, Science, Government, and Sports."

HONESTY NOTE: this is a curated SEED set (10 per domain per language = 100
total), not the full 1,500+. Section 16's ethical guidance says to prefer
synthetic/generic factual queries over ones mimicking real patient/citizen
scenarios, which is what these are. Scaling to 1,500+ is meant to happen
via `expand_queries()` below — programmatic templating (swapping entities
into query templates) — rather than hand-writing 1,500 questions one at a
time. That expansion function is a real, working implementation; it's the
seed content itself that's intentionally small and reviewable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Domain = Literal["healthcare", "history", "science", "government", "sports"]
Language = Literal["en", "hi"]


@dataclass
class SeedQuery:
    query_id: str
    text: str
    domain: Domain
    language: Language


# 10 hand-written seed questions per domain, English. Deliberately generic/
# factual (per Section 16 ethical guidance — no real-patient-style framing).
_SEED_EN: dict[Domain, list[str]] = {
    "healthcare": [
        "What are the common symptoms of dengue fever?",
        "How does the human immune system respond to a viral infection?",
        "What is the recommended dosage frequency for a standard paracetamol tablet?",
        "What causes Type 2 diabetes?",
        "How is tuberculosis typically diagnosed?",
        "What vaccinations are part of India's Universal Immunisation Programme?",
        "What are the main differences between bacterial and viral infections?",
        "How does high blood pressure affect the cardiovascular system?",
        "What is the role of insulin in the human body?",
        "What are the WHO's guidelines on daily water intake?",
    ],
    "history": [
        "When did India gain independence from British rule?",
        "Who was the first Prime Minister of India?",
        "What were the main causes of the First World War?",
        "When was the Indian Constitution adopted?",
        "Who founded the Mughal Empire?",
        "What was the significance of the Dandi March?",
        "When did the Battle of Plassey take place?",
        "Who was Chhatrapati Shivaji Maharaj?",
        "What was the Non-Cooperation Movement?",
        "When was the United Nations founded?",
    ],
    "science": [
        "What is the chemical formula for water?",
        "How does photosynthesis work?",
        "What causes the seasons to change on Earth?",
        "What is the speed of light in a vacuum?",
        "How do vaccines train the immune system?",
        "What is the difference between mass and weight?",
        "How does the greenhouse effect contribute to climate change?",
        "What is the theory of plate tectonics?",
        "How do black holes form?",
        "What is the function of DNA in living organisms?",
    ],
    "government": [
        "How is the President of India elected?",
        "What are the fundamental rights guaranteed by the Indian Constitution?",
        "How many members are in the Lok Sabha?",
        "What is the role of the Election Commission of India?",
        "How does a bill become a law in the Indian Parliament?",
        "What is the difference between the Lok Sabha and Rajya Sabha?",
        "What is the tenure of a Chief Minister in an Indian state?",
        "What is the function of the Reserve Bank of India?",
        "How is a state Governor appointed?",
        "What is the significance of Article 370?",
    ],
    "sports": [
        "How many players are on a cricket team?",
        "When was the first Cricket World Cup held?",
        "What are the rules for a run-out in cricket?",
        "How many Olympic gold medals has India won in hockey?",
        "What is the offside rule in football?",
        "How is a chess game scored in tournaments?",
        "What is the format of the Indian Premier League?",
        "How many sets are played in a standard tennis match?",
        "What is the significance of the Ranji Trophy?",
        "How does the points system work in Formula 1?",
    ],
}

# Direct Hindi translations of the same 50 seed questions, preserving
# query_id alignment (e.g. healthcare_en_00 <-> healthcare_hi_00) so
# cross-lingual comparisons of the same underlying fact are possible.
_SEED_HI: dict[Domain, list[str]] = {
    "healthcare": [
        "डेंगू बुखार के सामान्य लक्षण क्या हैं?",
        "मानव प्रतिरक्षा प्रणाली वायरल संक्रमण पर कैसे प्रतिक्रिया करती है?",
        "एक सामान्य पैरासिटामोल टैबलेट की अनुशंसित खुराक आवृत्ति क्या है?",
        "टाइप 2 मधुमेह का कारण क्या है?",
        "तपेदिक (टीबी) का निदान आमतौर पर कैसे किया जाता है?",
        "भारत के सार्वभौमिक टीकाकरण कार्यक्रम में कौन से टीके शामिल हैं?",
        "बैक्टीरियल और वायरल संक्रमण में मुख्य अंतर क्या हैं?",
        "उच्च रक्तचाप हृदय प्रणाली को कैसे प्रभावित करता है?",
        "मानव शरीर में इंसुलिन की भूमिका क्या है?",
        "दैनिक जल सेवन पर WHO के दिशानिर्देश क्या हैं?",
    ],
    "history": [
        "भारत को ब्रिटिश शासन से स्वतंत्रता कब मिली?",
        "भारत के पहले प्रधानमंत्री कौन थे?",
        "प्रथम विश्व युद्ध के मुख्य कारण क्या थे?",
        "भारतीय संविधान कब अपनाया गया था?",
        "मुग़ल साम्राज्य की स्थापना किसने की?",
        "दांडी मार्च का महत्व क्या था?",
        "प्लासी की लड़ाई कब हुई थी?",
        "छत्रपति शिवाजी महाराज कौन थे?",
        "असहयोग आंदोलन क्या था?",
        "संयुक्त राष्ट्र की स्थापना कब हुई थी?",
    ],
    "science": [
        "पानी का रासायनिक सूत्र क्या है?",
        "प्रकाश संश्लेषण कैसे काम करता है?",
        "पृथ्वी पर मौसम बदलने का कारण क्या है?",
        "निर्वात में प्रकाश की गति कितनी है?",
        "टीके प्रतिरक्षा प्रणाली को कैसे प्रशिक्षित करते हैं?",
        "द्रव्यमान और भार में क्या अंतर है?",
        "ग्रीनहाउस प्रभाव जलवायु परिवर्तन में कैसे योगदान देता है?",
        "प्लेट टेक्टोनिक्स का सिद्धांत क्या है?",
        "ब्लैक होल कैसे बनते हैं?",
        "जीवित जीवों में डीएनए का कार्य क्या है?",
    ],
    "government": [
        "भारत के राष्ट्रपति का चुनाव कैसे होता है?",
        "भारतीय संविधान द्वारा प्रदत्त मौलिक अधिकार क्या हैं?",
        "लोकसभा में कितने सदस्य होते हैं?",
        "भारत के चुनाव आयोग की भूमिका क्या है?",
        "भारतीय संसद में एक विधेयक कानून कैसे बनता है?",
        "लोकसभा और राज्यसभा में क्या अंतर है?",
        "किसी भारतीय राज्य में मुख्यमंत्री का कार्यकाल कितना होता है?",
        "भारतीय रिजर्व बैंक का कार्य क्या है?",
        "राज्यपाल की नियुक्ति कैसे होती है?",
        "अनुच्छेद 370 का महत्व क्या था?",
    ],
    "sports": [
        "क्रिकेट टीम में कितने खिलाड़ी होते हैं?",
        "पहला क्रिकेट विश्व कप कब आयोजित हुआ था?",
        "क्रिकेट में रन-आउट के नियम क्या हैं?",
        "हॉकी में भारत ने कितने ओलंपिक स्वर्ण पदक जीते हैं?",
        "फुटबॉल में ऑफसाइड नियम क्या है?",
        "टूर्नामेंट में शतरंज के खेल का स्कोर कैसे होता है?",
        "इंडियन प्रीमियर लीग का प्रारूप क्या है?",
        "एक मानक टेनिस मैच में कितने सेट खेले जाते हैं?",
        "रणजी ट्रॉफी का महत्व क्या है?",
        "फॉर्मूला 1 में अंक प्रणाली कैसे काम करती है?",
    ],
}


def get_seed_queries() -> list[SeedQuery]:
    """Returns all 100 seed queries (50 English + 50 Hindi, aligned by domain/index)."""
    queries = []
    for domain, questions in _SEED_EN.items():
        for i, text in enumerate(questions):
            queries.append(SeedQuery(f"{domain}_en_{i:02d}", text, domain, "en"))
    for domain, questions in _SEED_HI.items():
        for i, text in enumerate(questions):
            queries.append(SeedQuery(f"{domain}_hi_{i:02d}", text, domain, "hi"))
    return queries


# Templates for programmatic expansion toward the PRD's 1,500+ target.
# Each template has a {entity} slot; filling it from a domain-appropriate
# entity list multiplies one template into many real, distinct questions.
_EXPANSION_TEMPLATES: dict[Domain, list[str]] = {
    "history": [
        "When did {entity} become the Prime Minister of India?",
        "What is {entity} best known for in Indian history?",
    ],
    "sports": [
        "How many international matches has {entity} played?",
        "What team does {entity} currently play for?",
    ],
    "government": [
        "What are the key responsibilities of {entity}?",
    ],
}


def expand_queries(
    domain: Domain, entities: list[str], language: Language = "en"
) -> list[SeedQuery]:
    """
    Programmatic query expansion: fills domain-specific templates with a
    list of real entity names to generate many distinct, real questions
    from one template — this is how the seed set scales toward Section
    11.2's 1,500+ target without hand-writing each one.

    Note: only implemented for English and only for domains with defined
    templates above (history, sports, government) — healthcare/science
    template-based expansion is riskier (easy to generate a template that
    accidentally implies false claims, e.g. "What disease does {entity}
    have?"), so those two domains are left for careful manual authorship
    rather than templating, per Section 16's care-around-health-content note.
    """
    if language != "en":
        raise NotImplementedError("Template expansion is currently English-only")
    templates = _EXPANSION_TEMPLATES.get(domain)
    if not templates:
        raise ValueError(f"No expansion templates defined for domain={domain!r}")

    queries = []
    counter = 0
    for template in templates:
        for entity in entities:
            queries.append(
                SeedQuery(
                    query_id=f"{domain}_en_expanded_{counter:04d}",
                    text=template.format(entity=entity),
                    domain=domain,
                    language=language,
                )
            )
            counter += 1
    return queries
