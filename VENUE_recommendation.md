1. Single best recommendation: Software: Practice and Experience (SPE)

I would submit this paper to Software: Practice and Experience first.

The reason is not that SPE is the most prestigious venue on the list. It is that it gives the best combined expected value across fit, acceptance probability, publication cost, review speed, and the paper you actually have.

SPE explicitly wants practical techniques and tools, comparative evaluations, implemented systems, and completed projects that can serve as "how-to" models for practitioners. 
Wiley Online Library
+1
 That maps almost exactly onto this paper: controlled empirical characterization, deployment rules, reproducible experiments, and the released atlas_optimizer, which produces bundles, CSS mappings, loader code, and savings reports. 

paper(20260829-024920)

It also satisfies the financial constraint cleanly: decline OnlineOpen and publish conventionally with no APC. 
Wiley Online Library
+1
 SPE is currently Q1 by Scopus/SJR-related rankings, and Wiley reports a median 14–15 days to first decision. 
WUR Library
+1

Wiley reports only an 8% overall acceptance rate, so I would be more conservative than simply treating SPE as an easy journal. However, much of its editorial filtering concerns scope, and this manuscript is unusually well aligned with what SPE explicitly asks for. 
Wiley Online Library
+1

My estimate for this manuscript: roughly 40–50% eventual acceptance in essentially its current scientific form, rising to roughly 65–75% after the independent optimizer evaluation and consistency fixes identified in the previous review.

2. Ranked top 5
Rank	Venue	Why for this paper	Rough probability
1	Software: Practice and Experience	Best balance: empirical software/systems practice + usable tool + reproducibility + engineering rules; Q1; traditional route has no APC; very fast initial decision.	40–50% as-is; 65–75% revised
2	Computer Networks	Excellent domain fit because its scope explicitly includes Web, Web caching, Web performance, and network performance measurements, and it values complete work useful to implementers. SJR Q1; hybrid/subscription publication is compatible with no-APC traditional publishing. 
Elsevier Shop
+2
Elsevier Shop
+2
	30–40%
3	IEEE Internet Computing	Possibly the best practitioner audience: it explicitly seeks Internet technologies and implementations with actual impact on system development. Q1 and traditional IEEE publication requires no OA payment. Main disadvantage: the paper would need substantial compression to the magazine-style <5,000-word format. 
IEEE Computer Society
+2
IEEE Computer Society
+2
	25–35% after format rewrite
4	The Web Conference — Systems & Infrastructure	Best high-prestige conference match: ICORE A* and its systems track explicitly lists Web performance, measurement and characterization, empirical studies, implementations, and deployment lessons. 
The Web Conference 2026
+1
	12–18%
5	ACM Multimedia Systems (MMSys)	Better than ACM MM for this work: ICORE A, with explicit topics in network/system support for multimedia, performance evaluation, image coding, and an unusually strong artifact/reproducibility culture. 
ACM MMSys 2026
+2
ACM MMSys 2026
+2
	20–30%

There is one important qualification to ranks 4–5: ACM conferences no longer automatically satisfy your no-APC constraint. Since January 1, 2026, ACM proceedings are fully OA; if the corresponding author's institution is not in ACM Open, an APC normally applies unless the conference or a waiver covers it. 
cc.acm.org
+1
 Therefore, if ACM Open coverage is unavailable, I would remove TheWebConf and MMSys from consideration and move PAM into the top five.

PAM would then be my conference choice: ICORE B rather than A/A*, but the match is strong—measurement and analysis of networked systems, tools/software, application-layer measurement, QoE, reproducibility—and recent acceptance has been around 30%. Its Springer LNCS proceedings have a conventional no-publication-fee route; OA is optional. 
Springer
+4
PAM 2026
+4
PAM 2026
+4

3. Is anything actually a better home than SPE?

Under your combined constraints: no. SPE remains the best home.

There are two venues that beat it on individual dimensions.

The Web Conference is arguably the best topical audience. Its Systems & Infrastructure track could almost have been written for this paper: Web infrastructure, Web performance, measurement, empirical studies, implementation and lessons learned. 
The Web Conference 2026
 It is also much more prestigious as an A* conference. But its approximately 20% overall research-track acceptance rate understates the difficulty for this particular manuscript: reviewers will expect a stronger claim of broad Web research significance than SPE does. 
LinkedIn
 I estimate this paper below the conference average unless the external-validity/tool evaluation is substantially strengthened.

Computer Networks is arguably the best Q1 technical-domain journal alternative. Its explicit inclusion of Web performance makes scope defensible, and it may carry slightly more weight in networking. But there the HTTP/3 implementation-specific result, network-testbed generality, and the large codec/packing component become liabilities. SPE is more likely to value the whole package rather than asking whether the paper advances networking itself.

So my ordering is:

SPE for highest expected publication value; TheWebConf for a high-risk/high-prestige shot if ACM fees are covered; Computer Networks for a somewhat more technical Q1 journal gamble.

4. Conference-specific assessment

MMSys has the strongest artifact fit. Its formal artifact-review program attempts independent reproduction from source code, traces, datasets and instructions. 
ACM MMSys 2026
 The released optimizer plus one-command reconstruction of the study would play very well there. The issue is framing: the manuscript would need to become a multimedia delivery system paper rather than primarily a Web engineering paper.

TheWebConf has the strongest Web-practitioner fit. The optimizer, browser implementation, measured deployment trade-offs and engineering rules are exactly the kind of systems evidence its infrastructure track permits. The missing independent evaluation of atlas_optimizer would nevertheless be a conspicuous weakness at A* level.

PAM is the safest conference fit. It explicitly welcomes systems-based measurement, practical applications, tools/software and reproducibility, and its review cycle is fast: PAM 2026 went from an October 15 submission deadline to November 17 notification. 
PAM 2026
 Prestige is the trade-off: ICORE B.

IMC is not where I would send this version. IMC is ICORE A and exceptionally artifact-friendly, but it describes itself as a highly selective venue for measurement-based research in data communications and emphasizes insights into network structure, operational network performance and measurement methodology. 
SIGCOMM Conferences
+1
 Your HTTP experiments support the paper; they are not the paper's fundamental contribution. I would put the paper-specific probability around 10–15%.

ACM Multimedia is also not a priority. It is A*, but the 2026 CFP emphasizes novel theoretical/algorithmic multimedia contributions and explicitly states a preference for inherently multimedia/multimodal research. 
ACM Multimedia 2026
+1
 That reproduces much of the TMM mismatch. I would estimate ~8–12%.

Bottom line: submit to SPE. It is the rare case where the less flashy venue is not a compromise: its editorial definition of a valuable paper matches the actual contribution better than the higher-prestige alternatives.