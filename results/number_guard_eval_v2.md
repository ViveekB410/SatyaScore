# Number guard, version 2 (fresh Wikipedia sentences)

**Decision rule (fixed before running, same as version 1):** adopt only if (a) wiki false-number claims marked Verified fall by at least half, (b) wiki true claims marked Verified fall by at most 5%, (c) annotated gold-Verified claims marked Verified fall by at most 10%. Version 2 checks only years and numbers >= 100 written in digits; the false copies change such a number.

| set | claims | marked Verified: guard off | guard on |
|---|---|---|---|
| wiki, TRUE claims | 166 | 109 | 103 |
| wiki, FALSE-number claims (wrongly Verified) | 140 | **36** | **11** |
| annotated, gold Verified | 89 | 58 | 58 |
| annotated, gold Hallucinated (wrongly Verified) | 10 | 4 | 4 |

(a) met (36 -> 11); (b) NOT met (109 -> 103); (c) met (58 -> 58). **Do not adopt.**

## True claims that lose Verified (the cost)

- [wiki, en] In 1965 the body was renamed as the International Cricket Conference and the body's current name was adopted in 1987.
- [wiki, en] The British Raj was the period of Crown rule in India between 1858 and 1947 for around 200 years of British occupation.
- [wiki, en] Its writing system is the Greek alphabet which has been used for approximately 2,800 years previously Greek was recorded in writing systems such as Linear B and the Cypriot syllabary.
- [wiki, en] Until 2016 both men's and women's tournaments were held together since 2018 both are held separately but in the same calendar year with the exception of 2018 and 2020–2023.
- [wiki, en] Broadcasting began with AM radio which became popular around 1920 with the spread of vacuum tube radio transmitters and receivers.
- [wiki, en] There are 234 assembly constituencies and 39 Lok Sabha constituencies.
