# Number guard: Verified only if the evidence contains the claim's numbers

**Decision rule (fixed before running):** adopt only if (a) wiki false-number claims marked Verified fall by at least half, (b) wiki true claims marked Verified fall by at most 5%, (c) annotated gold-Verified claims marked Verified fall by at most 10%. The guard never creates a Hallucinated verdict.

| set | claims | marked Verified: guard off | guard on |
|---|---|---|---|
| wiki, TRUE claims | 154 | 115 | 101 |
| wiki, FALSE-number claims (wrongly Verified) | 89 | **27** | **3** |
| annotated, gold Verified | 89 | 55 | 39 |
| annotated, gold Hallucinated (wrongly Verified) | 10 | 4 | 4 |

(a) met (27 -> 3); (b) NOT met (115 -> 101); (c) NOT met (55 -> 39). **Do not adopt.**

## True claims that lose Verified (the cost)

- [wiki, en] He is generally considered one of the greatest Mughal emperors.
- [wiki, en] There are two main types of stroke.
- [wiki, en] Bangladesh is seen by various financial institutions as one of the Next Eleven.
- [wiki, en] It is one of the six principal organs of the United Nations.
- [wiki, en] The aftermath of World War II saw the rise of two global superpowers the United States and the Soviet Union.
- [wiki, en] Extant eukaryotes are traditionally grouped into four kingdoms: animals, plants, fungi and protists.
- [wiki, en] About one-third of the land surface of the Earth is arid or semi-arid.
- [wiki, en] The process of digestion has three stages.
- [wiki, en] Virat Kohli's career began when he made his debut in List A cricket playing against Services in the Ranji One-Day Trophy.
- [wiki, hi] ये अनुच्छेद संविधान के आवश्यक तत्व माने जाते हैं, जिसे भारतीय संविधान सभा द्वारा 1947 से 1949 के बीच विकसित किया गया था।
- [wiki, hi] मनुष्यों ने ४००० ईसा पूर्व के आसपास घोड़ों को पालतू बनाना शुरू कर दिया, और उनका पालतूकरण ३००० ईसा पूर्व से व्यापक रूप से फैला हुआ माना जाता हैं।
- [wiki, hi] इसका क्षेत्रफल ४,३०,००० वर्ग किलोमीटर तथा आयतन ७८,२०० घन किलोमीटर है।
- [wiki, hi] यहां लगभग २००० वर्ष तक हिन्दू सभ्यता का प्रभुत्व रहा।
- [wiki, hi] २००७ में, ९०३ मिलियन से अधिक अंतरराष्ट्रीय पर्यटकों के आगमन के साथ, २००६ की तुलना में ६.६ % की वृद्धि दर्ज की गई।
- [annotated, en] The Indian Constitution guarantees the following six fundamental rights.
- [annotated, en] India has won 8 Olympic gold medals in hockey.
- [annotated, en] In chess tournaments a win is typically scored as 1 point a draw as 0.5 points and a loss as 0 points.
- [annotated, en] Playoffs The top 4 teams qualify for the playoffs.
- [annotated, hi] २) प्रतिरक्षा कोशिकाएं : व्हाइट ब्लड सेल्स जैसे न्यूट्रोफिल और मैक्रोफेज वायरस को पहचानकर और नष्ट करके काम करते हैं।
- [annotated, hi] ६) इंटरफेरॉन : कुछ कोशिकाएं इंटरफेरॉन नामक प्रोटीन का उत्पादन करती हैं जो वायरस की प्रतिलिपि बनाने से रोकते हैं।
- [annotated, hi] निर्वात में प्रकाश की गति लगभग 299,792,458 मीटर प्रति सेकंड है।
- [annotated, hi] यह आयोग संविधान के अनुच्छेद 324 के तहत स्थापित किया गया है और इसके मुख्य कार्य हैं: चुनावों का संचालन और प्रबंधन करना।
- [annotated, hi] यह इंग्लैंड में आयोजित किया गया था और इसमें 8 टीमों ने भाग लिया था।
- [annotated, hi] हॉकी में भारत ने 8 ओलंपिक स्वर्ण पदक जीते हैं।
- [annotated, hi] क्वालिफायर 2 : क्वालिफायर 1 की हारने वाली टीम और एलिमिनेटर की जीतने वाली टीम एक दूसरे के साथ मैच खेलती हैं।
- [annotated, hi] फाइनल : क्वालिफायर 1 की जीतने वाली टीम और क्वालिफायर 2 की जीतने वाली टीम एक दूसरे के साथ मैच खेलती हैं।
- [annotated, hi] चौथे स्थान पर आने वाले ड्राइवर को 12 अंक मिलते हैं।
- [annotated, hi] इसके कई कारण हो सकते हैं, जिनमें शामिल हैं: १) अनुवांशिक कारक २) मोटापा ३) शारीरिक निष्क्रियता ४) अस्वस्थ आहार ५) उम्र ६) अन्य स्वास्थ्य समस्याएं, जैसे कि उच्च रक्तचाप और उच्च कोलेस्ट्रॉल।
- [annotated, hi] प्रकाश संश्लेषण की समीकरण है: ६ सीओ२ + ६ एच२ओ + प्रकाश ऊर्जा → सी६एच₁₂ओ६ + ६ ओ२ इस प्रकार, प्रकाश संश्लेषण एक महत्वपूर्ण प्रक्रिया है जो पृथ्वी पर जीवन को बनाए रखने में मदद करती है।
- [annotated, hi] ४) यदि फील्डर ने गेंद को विकेट पर मार दिया है और बल्लेबाज क्रीज से बाहर है, तो अम्पायर रन-आउट का संकेत देता है और बल्लेबाज आउट हो जाता है।
