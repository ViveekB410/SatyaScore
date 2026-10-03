## 2. World Bank / WHO statistics (countries: seed 5) -- ATTEMPT 1

Recorded from results/official_sources_eval_stats_seed5.csv (the run was stopped by a session time
limit after this part, before writing its summary; the annotated-claims count (a) was not saved).

- Robustness, 40 random countries: TRUE claims 121, Verified 116, **contradicted 1**, no answer 4;
  FALSE claims 121, answered 121, **contradicted 121**.
- Countries not identified on Wikidata by their World Bank name: Gambia, The; Iran, Islamic Rep.;
  Korea, Rep.; Puerto Rico (US); Somalia, Fed. Rep.; Turkiye; Yemen, Rep.
- The contradicted TRUE claim: "The GDP of Tuvalu is about $0.1 billion." (official 0.066 billion,
  rounded in the claim; 15% tolerance).

(b) NOT met (1 TRUE claim contradicted). **Not adopted.** Attempt 2: the check also accepts a figure
within the precision it is written to; fresh countries (seed 6), same rules.