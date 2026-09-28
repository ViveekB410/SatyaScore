# Professional fact-checks (Google Fact Check Tools API)

**Decision rule (fixed before running):** fact-checks become the live default only if (a) no fact-check decision is wrong on any set and (b) on the rumours set they correct at least 5 verdicts the pipeline alone got wrong.

| set | claims | a fact-check was found | a fact-check decided | decisions right | decisions wrong |
|---|---|---|---|---|---|
| rumours | 40 | 25 | 9 | 9 | **0** |
| train | 303 | 9 | 0 | 0 | **0** |
| test | 76 | 2 | 0 | 0 | **0** |
| round3 | 40 | 2 | 0 | 0 | **0** |

## Rumours set: verdicts

| | correct | rumours caught (Hallucinated) | true claims marked Hallucinated |
|---|---|---|---|
| pipeline alone | 13/40 | 3/25 | 1/15 |
| pipeline + fact-checks | 20/40 | 10/25 | 1/15 |

Verdicts corrected by a fact-check: **7**.

**Decision:** (a) no wrong decision: met (0 wrong); (b) at least 5 corrected: met (7). **Adopt: set SATYASCORE_FACTCHECK=true as the default.**

## Every fact-check decision

| set | claim | gold | fact-check | publisher: rating | checked claim |
|---|---|---|---|---|---|
| rumours | UNESCO declared Jana Gana Mana the best national anthem in the world. | Hallucinated | Hallucinated | [Snopes.com: False](https://www.snopes.com/fact-check/unesco-india-national-anthem/) | UNESCO declared India's national anthem, 'Jana Gana Mana,' to be the world's best. |
| rumours | Eating garlic prevents infection with the coronavirus. | Hallucinated | Hallucinated | [BBC: False - there's no evidence for this](https://www.bbc.co.uk/news/world-51735367) | Garlic can prevent coronavirus |
| rumours | UNESCO declared Narendra Modi the best prime minister in the world. | Hallucinated | Hallucinated | [FACTLY: FALSE](https://factly.in/narendra-modi-was-not-declared-as-the-worlds-best-prime-minister-by-the-unesco/) | Narendra Modi is declared as the Best Prime Minister in the World by UNESCO |
| rumours | COVID-19 vaccines contain microchips. | Hallucinated | Hallucinated | [AFP Fact Check: False](https://factcheck.afp.com/covid-19-vaccines-do-not-contain-tracking-devices) | Covid-19 vaccines contain tracking devices |
| rumours | COVID-19 vaccines make people magnetic. | Hallucinated | Hallucinated | [AP News: False](https://apnews.com/article/fact-checking-962624460714) | COVID-19 vaccines have resulted in some people becoming magnetic. |
| rumours | Drinking cow urine cures COVID-19. | Hallucinated | Hallucinated | [misbar.com: fake](https://www.misbar.com/en/factcheck/2021/05/10/no-evidence-cow-urine-cures-covid-19) | Drink cow urine to stop coronavirus. |
| rumours | Drinking alcohol protects you against COVID-19. | Hallucinated | Hallucinated | [misbar.com: myth](https://www.misbar.com/en/factcheck/2020/06/11/false-claim--drinking-alcohol-reduces-coronavirus-risk) | Consuming alcoholic beverages may help reduce the risk of infection by COVID-19. |
| rumours | यूनेस्को ने जन गण मन को दुनिया का सबसे अच्छा राष्ट्रगान घोषित किया है। | Hallucinated | Hallucinated | [विश्वास न्यूज: False](https://www.vishvasnews.com/viral/fact-check-unesco-india-national-anthem-ranking-post-in-fake/) | यूनेस्को ने 'जन गण मन' को दुनिया का सबसे अच्छा राष्ट्रगान घोषित किया है। |
| rumours | यूनेस्को ने नरेंद्र मोदी को दुनिया का सर्वश्रेष्ठ प्रधानमंत्री घोषित किया है। | Hallucinated | Hallucinated | [विश्वास न्यूज: False](https://www.vishvasnews.com/viral/fact-check-unesco-did-not-declare-pm-modi-as-the-best-prime-minister-of-the-world-fake-claim-viral/) | यूनेस्को ने भारत के प्रधानमंत्री नरेंद्र मोदी को दुनिया का सबसे बेहतरीन प्रधानमंत्री घोषित किया है। |
