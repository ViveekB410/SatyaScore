# Version 2 Wikidata relations on the dev sets (keep-or-drop check)

1754 dev claims that no v1 source decided; rule: keep a relation if >= 90% of its decisions are correct; contradictions below 90% -> support only.

| relation | supported (correct/all) | contradicted (correct/all) | all decisions correct |
|---|---|---|---|
| country | 3/4 | 1/1 | 80% (4/5) |
| country of origin | 2/2 | 0/0 | 100% (2/2) |
| director | 2/2 | 2/2 | 100% (4/4) |
| nationality | 1/1 | 3/3 | 100% (4/4) |
| year of a work | 0/0 | 2/2 | 100% (2/2) |

## Wrong decisions (up to 6 per relation)

**country**

- fever/en gold=Hallucinated supported: Tijuana is in Mexico. (Wikidata: Mexico)
