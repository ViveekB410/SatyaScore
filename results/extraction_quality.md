# Claim extraction quality — before / after (task 1.1)

All 50 English LLM answers in `raw_responses.json`, re-extracted with the old extractor (`HEAD`) and the current one. Every claim scored with the same rules (`claim_extractor.claim_quality`, also used by `flag_quality.py`).

| | old | new |
| --- | --- | --- |
| claims extracted | 266 | 204 |
| **broken claims** | **38/266 (14.3%)** | **0/204 (0.0%)** |
| claims that lost a % or $ from their source | 2 | 0 |

## Broken claims by reason
| reason | old | new |
| --- | --- | --- |
| no_finite_clause | 29 | 0 |
| stripped_symbol | 2 | 0 |
| too_short | 7 | 0 |

## Extraction method
| method | old | new |
| --- | --- | --- |
| decomposed_appos | 19 | 8 |
| decomposed_base | 219 | 90 |
| decomposed_conj | 28 | 10 |
| sentence_level | 0 | 96 |

## Sentences that now produce no claim (34)
Instead of emitting a broken fragment, the new extractor skips sentences that have no subject: list labels, headings, and bare gerund items. These are unjudgeable as stand-alone claims. **Known loss:** a real claim is dropped if spaCy's small model mis-parses its verb as a noun (e.g. "...the points system awards drivers points..."); a larger parser would fix that. Every skipped sentence:

- Sputum tests : Smear microscopy : To detect TB bacteria in sputum.
- Culture : To grow TB bacteria in a laboratory.
- Nucleic acid amplification tests (NAATs) : To detect genetic material of TB bacteria.
- Mantoux test (Tuberculin skin test) : To detect the body's immune response to TB bacteria.
- Tetanus Poliomyelitis (Oral Polio Vaccine and Inactivated Polio Vaccine)
- Militarism : Build-up of military forces and arms races.
- Nationalism : Rise of patriotic sentiment and ethnic tensions.
- Alliance System : Complex network of alliances between European powers (e.g., Triple Entente and Triple Alliance).
- It works as follows: Light absorption :
- Light-dependent reactions
- Temperature increase : The trapped heat warms the Earth's surface and atmosphere, leading to rising global temperatures.
- Right to Equality (Articles 14-18)
- Right to Freedom (Articles 19-22)
- Right against Exploitation (Articles 23-24)
- Right to Freedom of Religion (Articles 25-28)
- Right to Cultural and Educational Rights (Articles 29-30) Right to Constitutional Remedies (Article 32)
- Ensuring the integrity of the electoral process.
- Registering and regulating political parties.
- Maintaining the electoral rolls and voter lists.
- Setting election schedules and rules.
- Monitoring campaign finance and expenditure.
- Implementing the Model Code of Conduct for political parties and candidates.
- Addressing electoral complaints and disputes.
- Currency Management: Managing the supply of currency and coins.
- Banking Regulation: Supervising and regulating commercial banks.
- Lender of Last Resort: Providing liquidity to banks during financial crises.
- Foreign Exchange Management: Regulating foreign exchange transactions.
- Government Banker: Managing the government's accounts and providing banking services.
- The rules for a run-out are:
- Qualifier 1 : 1st-ranked team vs. 2nd-ranked team.
- Eliminator : 3rd-ranked team vs. 4th-ranked team.
- Qualifier 2 : Winner of Eliminator vs. loser of Qualifier 1. Final : Winner of Qualifier 1 vs. winner of Qualifier 2.
- Its significance includes:
- In Formula 1, the points system awards drivers points based on their finishing position in a Grand Prix.

_Scope: this measures the live extractor on the source answers. The annotated gold claims in `gold_final.csv` are fixed and are not re-extracted, so their 44 broken rows stay as they are (tracked in `claim_quality.csv`)._

