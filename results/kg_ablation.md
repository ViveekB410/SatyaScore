# KG ablation — can it be run on this dataset?

PRD 5.1 calls the KG ablation "the single most important experiment". KG_conf needs (a) a relation phrase from `RELATION_TO_PID`, (b) two named entities (English NER only; no Hindi NER), (c) a Wikidata triple.

## Coverage on the 456 gold claims (offline, exact)
- Claims containing a relation phrase (condition a): **0 / 456**.
- Hindi claims: 190, all without English-style NER entities, so condition (b) fails for every one.
- Generous upper bound: English claims containing any relation keyword (born, died, capital, located, founded, established, president, prime minister, member of, part of, headquarter, citizen): **13**, most of which are not person/place→entity facts. Examples:

  - Jawaharlal Nehru was the first Prime Minister of India.
  - Babur founded the Mughal Empire in 1526.
  - Chhatrapati Shivaji Maharaj was an Indian king and a member of the Bhonsle Maratha clan.
  - The United Nations was founded on October 24 1945.
  - The President of India is elected through an indirect election process where the electoral college consists of
  - The candidate with the majority of votes more than 50 of the total votes is elected as the President of India.
  - India roles include Conducting elections to the Parliament State Legislatures and the offices of the President
  - Presidential Assent If the bill is passed by both houses the Rajya Sabha is sent to the President of India for
  - Signing into Law The President signs the bill.
  - Note If the President returns the bill to the Parliament for reconsideration Parliament is sent back to the ho
  - If the Parliament passes the bill again with or without amendments Parliament is sent back to the President wh
  - The main differences are Membership Lok Sabha has 543 elected members while Rajya Sabha has 245 members with 2
  - Governor is typically the President, on the advice of the Prime Minister or the Council of Ministers.

**Conclusion:** KG's domain — simple relational facts ("X was born in Y", "X is the capital of Y") — is essentially absent from this dataset of descriptive LLM answers. The PRD's KG ablation (target F1 gain ≥ +0.03) **cannot be measured here**: it would run on 0 claims as the table stands, and at most a handful with phrasing tuned after reading these claims (which would also fit the table to the evaluation set). This is a property of the dataset, recorded as a finding, not a KG result either way.

## Verifier sanity check on relational claims (live Wikidata)
| claim | expected | got | KG_conf |
| --- | --- | --- | --- |
| Narendra Modi is the Prime Minister of India. | supported | supported | 1.0 |
| Narendra Modi is the President of India. | unknown | unknown | None |
| Paris is the capital of France. | supported | supported | 1.0 |
| Paris is the capital of Germany. | contradicted | contradicted | 0.0 |
| The Taj Mahal is located in India. | supported | supported | 1.0 |
| Mahatma Gandhi was born in India. | supported | supported | 1.0 |
| Mahatma Gandhi was born in Pakistan. | contradicted | contradicted | 0.0 |

- **7/7** correct. "unknown" means no KG signal (the scorer renormalises around it); only a single-valued property with a different recorded value counts as a contradiction.

