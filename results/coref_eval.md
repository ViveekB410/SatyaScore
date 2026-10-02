# Pronoun resolution: nearest entity vs sentence subject (heldout: 400 Wikipedia introductions)

Pronouns it / its / he / his / she / her after the first sentence; RIGHT = the referent names the article's subject (labels by construction, see coref_eval.py).

| rule | right | **wrong** | unresolved |
|---|---|---|---|
| nearest | 93 | **206** | 135 |
| salience | 287 | **117** | 30 |

**Decision rule (fixed before this run):** adopt "salience" only if wrong referents are fewer and right referents not fewer than with "nearest".

(a) fewer wrong: met (206 -> 117); (b) right not fewer: met (93 -> 287). **Adopt: COREF_RULE = "salience".**

## nearest: examples of wrong referents

| article | pronoun | resolved to | sentence |
|---|---|---|---|
| Australia national cricket team | it | England | Along with England, it is the joint oldest team in Test cricket history, playing and winning the first ever Test match i |
| Australia national cricket team | its | New Zealand | The team draws its players from teams playing in the Australian domestic competitions – the Sheffield Shield, the Austra |
| Europe | It | the Eastern Hemisphere | It is bordered by the Arctic Ocean to the north, the Atlantic Ocean to the west, the Mediterranean Sea to the south, and |
| Algae | It | AL | It excludes the land plants (embryophytes). |
| Palestinian right of armed resistance | it | Israeli | Whether it is Palestinians who have the right to resist against the Israeli occupation, or it is Israel that has the rig |
| Palestinian right of armed resistance | it | Israeli | Whether it is Palestinians who have the right to resist against the Israeli occupation, or it is Israel that has the rig |
| Croup | It | Scots | It often starts or is worse at night and normally lasts one to two days. |
| Akbar | He | Bairam Khan | He is generally considered one of the greatest Mughal emperors. |
| Single transferable vote | it | STV | STV aims to approach proportional representation based on votes cast in the district where it is used, so that each vote |
| Savitribai Phule | she | Sagunabai Kshirsagar | In 1848, together with Jyotirao and Sagunabai Kshirsagar, she established the first school for girls at the residence of |
| Crustacean | It | Crustaceans | It is now well accepted that hexapods (insects and entognathans) are cladistically crustaceans, with the two groups now  |
| Bread | it | the Middle East | Throughout recorded history and around the world, it has been an important part of many cultures' diets. |
| Bread | It | the Middle East | It is one of the oldest human-made foods, having been of significance since the dawn of agriculture, and plays an essent |
| European Cup and UEFA Champions League records and statistics | it | Real Madrid | Real Madrid is the most successful club in the tournament, winning it fifteen times. |
| Thanjavur | It | Indian | It is the 12th biggest city in Tamil Nadu. |

## salience: examples of wrong referents

| article | pronoun | resolved to | sentence |
|---|---|---|---|
| Algae | It | alga | It excludes the land plants (embryophytes). |
| Palestinian right of armed resistance | it | the conduct | Whether it is Palestinians who have the right to resist against the Israeli occupation, or it is Israel that has the rig |
| Palestinian right of armed resistance | it | the conduct | Whether it is Palestinians who have the right to resist against the Israeli occupation, or it is Israel that has the rig |
| Croup | It | Fever | It often starts or is worse at night and normally lasts one to two days. |
| Akbar | He | Bairam Khan | He is generally considered one of the greatest Mughal emperors. |
| Single transferable vote | it | STV | STV aims to approach proportional representation based on votes cast in the district where it is used, so that each vote |
| South Africa | it | the country | Covering an area of 1,221,037 square kilometres (471,445 square miles), the country has a population of over 63 million  |
| Crustacean | It | Crustaceans | It is now well accepted that hexapods (insects and entognathans) are cladistically crustaceans, with the two groups now  |
| European Cup and UEFA Champions League records and statistics | it | Real Madrid | Real Madrid is the most successful club in the tournament, winning it fifteen times. |
| 2024 Indian general election | his | Narendra Modi | This marked Modi's third term as prime minister and his first time heading a coalition government, with the Telugu Desam |
| C. V. Raman | his | K. S. Krishnan | In 1930, Raman received the Nobel Prize in Physics "for his work on the scattering of light and for the discovery of the |
| Birth control | it | Planning | Some cultures limit or discourage access to birth control because they consider it to be morally, religiously, or politi |
| Meningitis | it | A non-blanching rash | A non-blanching rash (a rash that does not fade when a glass is rolled over it) may also be present. |
| Uranus | It | The planet's atmosphere | It has a marked axial tilt of 82.23°, with a retrograde rotation period of 17 hours and 14 minutes. |
| Uranus | its | The planet's atmosphere | This means that in an 84-Earth-year orbital period around the Sun, its poles get around 42 years of continuous sunlight, |

## Record of runs

- **Pre-registered run** (code at commit 031784e, rule fixed before the run): nearest 93 right / 206 wrong;
  salience 277 right / 128 wrong. Rule met -> salience adopted.
- **After a bug fix found while checking examples** (a subject such as "Its dome" or "This monument" had become
  the topic, giving "Its dome's gardens"; such subjects now point back to the topic): the table above,
  salience 287 right / 117 wrong. Reported as a check, not used for the decision.
- "Wrong" over-counts: some pronouns really refer to something other than the article subject
  ("The work is notable for its contribution", "Lamarck proposed his theory"), and some resolutions name the
  subject differently ("The human immunodeficiency virus" for HIV/AIDS). This affects both rules.
