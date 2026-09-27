# Diagnosis: true statements through the live pipeline

120 lead sentences of Wikipedia articles (true by construction; seed 7): seen = article in the evidence index, unseen = not in it. 146 claims extracted. A true claim marked **Hallucinated is a false alarm**.

## Verdicts on true claims (live rule)

| group | lang | claims | Verified | Uncertain | **Hallucinated (false alarm)** |
|---|---|---|---|---|---|
| seen | en | 54 | 37 | 8 | **9** (17%) |
| seen | hi | 21 | 18 | 2 | **1** (5%) |
| unseen | en | 51 | 8 | 22 | **21** (41%) |
| unseen | hi | 20 | 11 | 4 | **5** (25%) |

## Why the 36 false alarms happened

- decided by the KG: 0
- decided by NLI: 36, of which: *(corrected by hand: a display bug printed "-36"; fixed in diagnose_true_claims.py)*
  - the deciding passage was **not the top-1** (most similar) passage: 26
  - another retrieved passage **entailed** the claim (P(entail) ≥ 0.5) but a contradicting passage won: 4
  - seen group: the article the sentence came from was in the top 3: 10 of 10; the deciding passage came from that article: 7

## Same NLI numbers, other aggregation rules (diagnostic, true claims only)

| rule | Verified | Uncertain | Hallucinated (false alarms) |
|---|---|---|---|
| current (most decisive) | 74 | 36 | 36 |
| top-1 passage only | 56 | 71 | 19 |
| support-first | 73 | 40 | 33 |

Fewer false alarms here is necessary but not sufficient: a rule must also keep catching real hallucinations, which only the labelled splits can show.

## Every false alarm

| group | lang | claim | deciding passage (rank) | passages: title sim e c |
|---|---|---|---|---|
| seen | en | The Battle of Plassey was a decisive victory of the British East India Company under the l | 3.0 | Battle of Plassey 0.816 e0.014 c0.003; Battle of Plassey 0.766 e0.002 c0.989; Indian independence movement 0.609 e0.0 c0.996 |
| seen | en | Bhimrao Ramji Ambedkar is 14. | 3.0 | B. R. Ambedkar 0.486 e0.606 c0.024; B. R. Ambedkar 0.457 e0.023 c0.007; B. R. Ambedkar 0.443 e0.003 c0.966 |
| seen | en | Bhimrao Ramji Ambedkar is April 1891 6 December 1956. | 1.0 | B. R. Ambedkar 0.575 e0.001 c0.996; B. R. Ambedkar 0.558 e0.003 c0.006; B. R. Ambedkar 0.557 e0.001 c0.0 |
| seen | en | Association football commonly known as football or soccer is a team sport played between t | 1.0 | Association football 0.848 e0.007 c0.989; Association football 0.821 e0.068 c0.002; Association football 0.742 e0.005 c0.013 |
| seen | en | Malaria is a mosquito-borne infectious disease that is transmitted by the bite of Anophele | 3.0 | Malaria 0.85 e0.964 c0.004; Malaria 0.768 e0.156 c0.058; Blood 0.76 e0.0 c0.994 |
| seen | en | Blood transports metabolic waste products away from those same cells. | 3.0 | Blood 0.691 e0.041 c0.004; Blood 0.621 e0.338 c0.434; Blood 0.572 e0.016 c0.935 |
| seen | en | Blood is a specialized form of connective tissue and body fluid in the circulatory system  | 2.0 | Blood 0.833 e0.151 c0.002; Blood 0.757 e0.004 c0.437; Blood 0.698 e0.007 c0.002 |
| seen | en | The Moon is the only natural satellite of Earth. | 3.0 | Earth 0.826 e0.947 c0.011; Moon 0.764 e0.006 c0.596; Moon 0.73 e0.002 c0.988 |
| seen | en | The Rajya Sabha also known as Council of States is the upper house of the Parliament of In | 2.0 | Rajya Sabha 0.857 e0.928 c0.028; Lok Sabha 0.815 e0.019 c0.938; Rajya Sabha 0.781 e0.013 c0.026 |
| seen | hi | संयुक्त राज्य अमेरिका और सोवियत रूस के बीच उत्पन्न तनाव की स्थिति को शीत युद्ध के नाम से ज | 2.0 | Cold War 0.808 e0.279 c0.003; Cold War 0.767 e0.089 c0.791; United States 0.703 e0.003 c0.023 |
| unseen | en | The oxidation state or oxidation number are fully ionic. | 1.0 | Oxygen 0.66 e0.005 c0.967; Periodic table 0.635 e0.009 c0.411; Periodic table 0.59 e0.029 c0.891 |
| unseen | en | The Nineteenth Amendment to the United States Constitution is Amendment XIX. | 1.0 | Constitution of India 0.572 e0.005 c0.409; Constitution of India 0.564 e0.002 c0.064; United States 0.543 e0.033 c0.024 |
| unseen | en | The Japan national cricket team is the men's team that represents Japan in international c | 3.0 | Japan 0.549 e0.014 c0.407; India men's national field h 0.541 e0.009 c0.007; India men's national field h 0.537 e0.034 c0.557 |
| unseen | en | The prime minister of Canada is the head of government of Canada. | 3.0 | Prime Minister of India 0.697 e0.006 c0.693; Prime Minister of India 0.657 e0.199 c0.738; Prime Minister of India 0.623 e0.003 c0.84 |
| unseen | en | Manila is officially the City of Manila. | 2.0 | Mumbai 0.449 e0.004 c0.083; Paris 0.446 e0.001 c0.942; Mumbai 0.445 e0.017 c0.083 |
| unseen | en | The Sunrisers Hyderabad (often abbreviated as SRH) are a franchise cricket team based in H | 2.0 | Ranji Trophy 0.563 e0.004 c0.125; Indian Premier League 0.496 e0.014 c0.633; 2026 Indian Premier League 0.496 e0.014 c0.633 |
| unseen | en | The Government of Punjab or locally as the State Government is the supreme governing autho | 1.0 | Governor (India) 0.705 e0.006 c0.982; British Raj 0.678 e0.02 c0.345; Governor (India) 0.639 e0.004 c0.136 |
| unseen | en | Mir Syed Jafar Ali Khan Mirza Muhammad Siraj 2 July 1757 commonly known as Siraj ud-Daulah | 3.0 | Shivaji 0.404 e0.25 c0.376; Taj Mahal 0.403 e0.042 c0.626; Indian independence movement 0.402 e0.015 c0.943 |
| unseen | en | The history of Gujarat began with Stone Age settlements followed by Chalcolithic and Bronz | 2.0 | India 0.624 e0.134 c0.391; India 0.619 e0.016 c0.558; Mumbai 0.577 e0.174 c0.03 |
| unseen | en | This is the list of heads of state of Brazil which brings together all monarchs and presid | 2.0 | Brazil 0.624 e0.048 c0.085; Brazil 0.591 e0.004 c0.519; Brazil 0.59 e0.006 c0.075 |
| unseen | en | The original members of the World Trade Organization are the parties to the General Agreem | 2.0 | Australia 0.619 e0.001 c0.04; Global warming 0.534 e0.004 c0.83; Climate change 0.534 e0.004 c0.83 |
| unseen | en | Peripheral artery disease is PAD. | 1.0 | Heart 0.551 e0.003 c0.924; Diabetes 0.551 e0.01 c0.125; Hypertension 0.539 e0.46 c0.115 |
| unseen | en | Peripheral artery disease is a vascular disorder that causes abnormal narrowing of arterie | 1.0 | Heart 0.738 e0.008 c0.627; Diabetes 0.675 e0.003 c0.015; Hypertension 0.668 e0.002 c0.001 |
| unseen | en | Leptin from Greek λεπτός leptos thin or light or small also known as obese protein is a pr | 2.0 | Insulin 0.645 e0.01 c0.005; Insulin 0.634 e0.002 c0.948; Nutrition 0.624 e0.035 c0.083 |
| unseen | en | The prime minister of Australia is the head of government of the Commonwealth of Australia | 3.0 | Prime Minister of India 0.693 e0.005 c0.77; Australia 0.661 e0.239 c0.176; Prime Minister of India 0.64 e0.005 c0.983 |
| unseen | en | Sir William Jones is 28 September 1746 27 April 1794. | 1.0 | Isaac Newton 0.399 e0.008 c0.328; Isaac Newton 0.373 e0.006 c0.141; French Revolution 0.366 e0.008 c0.1 |
| unseen | en | Sir William Jones was a British philologist scholar and judge. | 3.0 | Charles Darwin 0.509 e0.004 c0.192; Isaac Newton 0.467 e0.01 c0.756; Charles Darwin 0.465 e0.005 c0.927 |
| unseen | en | This is a list of notable biologists with a biography in Wikipedia. | 3.0 | Charles Darwin 0.493 e0.018 c0.693; Charles Darwin 0.487 e0.011 c0.781; Artificial intelligence 0.469 e0.0 c0.992 |
| unseen | en | The Economic Freedom Fighters is EFF. | 3.0 | Brazil 0.398 e0.004 c0.3; Egypt 0.384 e0.002 c0.923; United States 0.374 e0.004 c0.962 |
| unseen | en | The Economic Freedom Fighters is a communist and black nationalist political party in Sout | 1.0 | Germany 0.39 e0.001 c0.947; United States 0.388 e0.002 c0.654; Cold War 0.385 e0.022 c0.151 |
| unseen | en | The secret ballot also known as the Australian ballot is a voting method in which a voter' | 2.0 | Australia 0.491 e0.071 c0.452; Election Commission of India 0.464 e0.003 c0.663; Election Commission of India 0.449 e0.005 c0.574 |
| unseen | hi | जवाहरलाल नेहरू स्टेडियम, भारत की राजधानी नयी दिल्ली में स्थित एक बहुउद्देशीय स्टेडियम है,  | 3.0 | London 0.577 e0.006 c0.0; Ranji Trophy 0.556 e0.36 c0.178; London 0.548 e0.002 c0.357 |
| unseen | hi | आईसीसी (ICC) क्रिकेट विश्व कप २०११, दसवां क्रिकेट विश्व कप था और इसकी मेजबानी टेस्ट क्रिके | 3.0 | Cricket World Cup 0.798 e0.001 c0.003; Cricket 0.764 e0.003 c0.027; Cricket World Cup 0.746 e0.003 c0.994 |
| unseen | hi | रक्तचाप रक्तवाहिनियों में बहते रक्त द्वारा वाहिनियों की दीवारों पर द्वारा डाले गये दबाव को | 3.0 | Hypertension 0.776 e0.0 c0.001; Hypertension 0.696 e0.001 c0.001; Heart 0.682 e0.012 c0.808 |
| unseen | hi | भारत की अन्तरिम सरकार 1 दिसंबर,1915 को काबुल, अफगानिस्तान में भारतीय राष्ट्रवादियों द्वारा | 1.0 | World War I 0.57 e0.007 c0.323; Indian independence movement 0.567 e0.003 c0.006; Indian independence movement 0.551 e0.06 c0.242 |
| unseen | hi | वृक्क या गुर्दे का जोड़ा एक मानव अंग हैं, जिनका प्रधान कार्य मूत्र उत्पादन (रक्त शोधन कर)  | 2.0 | Heart 0.633 e0.072 c0.724; Heart 0.575 e0.003 c0.996; Blood 0.563 e0.031 c0.122 |
