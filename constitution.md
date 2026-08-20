# Constitution — AIG System for PBL-Aligned Assessment

Status: DRAFT v0.1 — Module 1 (Fundação Pedagógica / PBL) grounding pass.
Scope: Immutable rules governing an Automated Item Generation (AIG) system for
Problem-Based Learning (PBL) contexts. These rules are non-negotiable design
constraints — any future spec/plan/implementation that conflicts with a rule
below must change, not the rule, unless the rule itself is amended here with
its rationale updated.

---

## I. Problem-Based Learning (PBL) — Immutable Rules

**R1. Every generated item must originate from an ill-structured, real-life
problem, never a bare recall fact.**
The problem is the pedagogical "driving force," not decoration on top of
content (Savery, 2006, via Divjak, Svetec & Pažur Aničić, 2025). An item
stem that only restates a textbook definition without situating it in a
scenario violates this rule.

**R2. The system must distinguish and tag Problem-Based (PrBL — knowledge
application) items from Project-Based (PjBL — knowledge construction) items.**
These are pedagogically distinct and require different generation and
scoring logic (Divjak et al., 2025).

**R3. Any AI involvement in a PBL assessment artifact must be disclosed and
governed by an explicit integration model, never silently embedded.**
Adopt one of three empirically-derived modes per assessment context
(Divjak et al., 2025):
- **FIRM** — AI use is mandatory and instructed in detail. Required for
  freshman-level or high-stakes summative assessment.
- **RELAXED** — AI use is permitted, no reporting required. Reserved for
  low-stakes formative/early-phase work.
- **FLEXIBLE** — AI use is optional and student-decided, but must be
  reported.
A given assessment must declare which mode governs it before items are
generated.

**R4. Where students may use AI unevenly, the rubric must explicitly score
the *use of AI* as its own criterion.**
Failing to do so produces an unfair assessment when some students used AI
and others did not (Divjak et al., 2025).

**R5. Scenario generation must never leak the answer into the problem
statement.**
A violation/problem scenario must describe symptoms or consequences of a
failure implicitly, and must never name the underlying concept, rule, or
"correct practice" it is testing (structurally generalized from the
practice→violation-scenario technique in Chen et al., BLOOMQA, 2601.20253v1).

**Implementation status (2026-08-18 audit): R1–R5, collectively, out of
scope for this deliverable — zero code.** This deliverable rewrites
existing, already-flagged dataset items using EDA-diagnosed structural
flaws as feedback; it never constructs a PBL scenario from a domain corpus
(R1), tags PrBL/PjBL (R2), declares a FIRM/RELAXED/FLEXIBLE integration mode
(R3), scores AI-use as its own rubric criterion (R4), or runs a leakage
blocklist against generated scenarios (R5). None of Section I shapes any
item this pipeline has produced. Full disclosure: Amendment Log entry v0.12
below, and `relatorio_tecnico.tex`'s specification-coverage table
(`tab:cobertura`, row "R1–R5").

---

## II. Strict Bloom's Taxonomy Alignment — Immutable Rules

**R6. Bloom's Taxonomy is adopted as the mandatory cognitive-level
classification scheme for every item, with its known validity limitations
explicitly acknowledged and mitigated — not ignored.**
Rationale for the caveat: SME classification-consistency studies show
agreement as low as 34–77% (kappa 0.12–0.60), and Gierl (1997) found only
54% correspondence between item-writer-intended and student-perceived
cognitive level (Haladyna & Rodriguez, 2013, ch. 3, who call this a
"conceptual swamp" after Lewis & Smith, 1993). The taxonomy is retained
for its standardization and communicability value, but **no cognitive-level
label is trusted from self-report alone** — see R8.

**R7. Cognitive level must be operationalized through the dual-dimension
model (cognitive process × knowledge type), with the metacognitive
knowledge dimension excluded from automated generation/grading.**
Metacognitive items require judging the validity of "novel strategies,"
which cannot be reliably auto-graded (Abdullah et al., "Enhanced Bloom's
Taxonomy" pipeline paper).

**R8. No item's cognitive-level label may be accepted from the generating
LLM's self-report. It must be independently re-classified by a separate
classifier or process before acceptance.**
This is a three-layer, non-collapsible validation stack: (1) generation
with level-targeted verb banks/templates, (2) an *independent* auditor —
e.g., a fine-tuned classifier separate from the generator (Hwang et al.,
2023, reached 83.79% accuracy with a RoBERTa+CNN classifier) — (3) human
expert sign-off. Trusting the generator's own label is explicitly
prohibited: Hwang et al. found 70% of GPT-labeled "Synthesis" items were
reclassified as "Comprehension" by an independent classifier.

**R9. Multiple-choice format is restricted to the Remember, Understand,
Apply, and Analyze levels. Evaluate and Create must not be assessed via
MCQ.**
These upper levels require open-ended reasoning that cannot be validly
assessed by a closed-choice format (Krathwohl, 2002; Brookhart, 2010, via
Chen et al., BLOOMQA). Evaluate/Create items must use an open-response or
performance-based format with human or rubric-mediated scoring.

**R10. Each Bloom level must be generated/verified via a fixed,
level-specific template — never a single generic "write a question at
level X" instruction.**
Minimum required per-level contract (synthesizing Abdullah et al.'s verb
banks and Chen et al.'s guiding-question/option-rewrite rules):
| Level | Verb bank (examples) | Structural rule |
|---|---|---|
| Remember | define, identify, list | Verbatim-fact recall; options may be verbatim source statements |
| Understand | summarize, classify | Options reframed as cause/effect |
| Apply | solve, implement | Options reframed as forward-looking actions in a new context |
| Analyze | organize, contrast | Options expanded with pros/cons comparisons |
| Evaluate | criticize, judge | Not MCQ — see R9 |
| Create | design, compose | Not MCQ — see R9 |

**Implementation status (2026-08-18 audit): only the verb-bank column is
implemented; the structural-rule column is not.** `WAPLA_AIG_Engine.py`'s
`check_bloom_verb()` mechanically verifies a canonical verb for the
declared level is literally present in the item's cognitive text — never
trusted from the generator's self-report — and this fired 26 times across
real (non-dry-run) sessions on 2026-08-18, directly causing regeneration.
But `target_level` is used for exactly two things in the codebase: selecting
which verb bank to show the generator, and checking a verb from that bank
afterward. The structural-rule column — verbatim-fact recall for Remember,
options reframed as cause/effect for Understand, forward-looking actions
for Apply, pros/cons comparisons for Analyze — has no corresponding code
anywhere: every Bloom level receives identical option-structuring
instructions in the generator prompt, differing only in which verb is
required. This rule's claim is narrowed accordingly: R10 is satisfied for
the verb-bank contract only. The structural-rule contract is
**documented, not implemented**, per R31 (no silent drift) — the same
disclosure standard applied to R11 below. (Separately, and not a defect:
the Evaluate/Create rows of this table are structurally unreachable in the
current pipeline, since R9's demotion logic redirects every Avaliar/Criar
item to Analisar before `target_level` ever reaches `check_bloom_verb()`
or the generator prompt.)

**R11. Bloom-difficulty is a hypothesis to be empirically tested per domain,
not an assumed property of the item.**
LLM performance does not reliably track the intended human cognitive
hierarchy — in some domains, Analyze items were empirically *easier* for
models than Remember items (Chen et al., BLOOMQA). Any claim that an item
"targets level X" must be paired with the discrimination statistics defined
in `spec.md` (Δ_bloom), not asserted from the generation prompt alone.

**Implementation status (2026-08-18 audit): aspirational, zero code.** No
discrimination statistic — Δ_bloom, or any cross-level accuracy/pass-rate
comparison for the same content — is computed anywhere in
`WAPLA_AIG_Engine.py`. `target_level` functions purely as a
generation/verification label (R9's demotion gate, R10's verb-bank check);
nothing in the pipeline compares difficulty or discrimination across Bloom
levels. Every item this pipeline has produced is labeled with a target
level asserted from the generation prompt alone — precisely what this rule
prohibits doing without accompanying discrimination data. R11 does not
shape any of today's results and must not be read as satisfied by anything
currently implemented.

---

## III. Rubric Design — Immutable Rules

**R12. Rubric criteria must be mutually exclusive: no two criteria (and no
two performance-level descriptions within a criterion) may overlap in what
they measure or credit.**
This is the anchor rule requested for this module. Sources, all converging
independently on the same requirement:
- Bailey (2025), rubric-construction step 3: "each description and each
  characteristic should be mutually exclusive" (adapted from Kuhs, Johnson,
  Agruso & Monrad, 2001).
- Downing (Handbook of Test Development, ch. 12, Rule 22): "Keep choices
  independent; choices should not be overlapping in meaning."
- Guia de Elaboração e Revisão de Itens (Inep/MEC BNI-Enade), §3.3.11
  *Independência*: "Construa itens independentes, de modo que o acerto de
  um não fique subordinado ao acerto do outro... não formule itens com
  opções de resposta encadeadas."
- Raymond & Neustel (Handbook of Test Development, ch. 9, p.205), citing
  Fleishman & Quaintance (1984): classification schemes should satisfy
  "mutually exclusive classification," while noting this is difficult to
  achieve in practice — the AIG pipeline must therefore include an
  automated overlap check, not rely on manual diligence alone.

**R13. LLMs must not be trusted to self-enforce mutual exclusivity; it must
be explicitly instructed and then independently, mechanically verified.**
Bailey (2025) notes AI does not reliably enforce mutual exclusivity on its
own — it must be prompted for explicitly and manually/automatically
verified before use. See `spec.md` for the required validation stage.

**R14. Every rubric must declare its type (holistic, analytic, single-point,
or generic) before generation, and the type constrains generation logic.**
Analytic rubrics (multi-criteria × multi-level matrix) are required
wherever diagnostic, per-criterion feedback is pedagogically necessary
(e.g., PBL formative loops); holistic is permitted only for low-stakes,
fast-turnaround summative contexts (Bailey, 2025; Handbook of Test
Development, ch. 13).

**R15. Rubric criteria must be limited to 3–6 major criteria and must avoid
undefined evaluative terms ("adequate," "clear," "good") — every criterion
must be concrete and independently scorable without reference to any other
criterion.**
(Bailey, 2025.) This is the mechanical complement to R12: exclusivity
without concreteness still produces rater disagreement.

**R16. Any item or rubric exhibiting more than one detected item-writing
flaw (per the 31-guideline, 19-flaw taxonomy) must be rejected or sent to
regeneration, not silently accepted with a warning.**
(Haladyna, Downing & Rodriguez, 2002, reproduced in Handbook of Test
Development ch. 12; operationalized as the IWF detector in Hwang et al.,
2023.) Flawed items measured up to 15 percentage points harder with ~3.5
points lower pass rates than standard items (Downing, 2005) — flaws are not
cosmetic, they corrupt measurement.

---

## IV. LGPD / Privacy — Immutable Rules

**R17. No real, identifiable student data may ever be used to train, fine-tune,
prompt, or few-shot condition any generation, curation, or judge model.**
Traditional anonymization is not a sufficient substitute for this rule, not a
loophole around it. Kostopoulos, Tsiakmaki & Kotsiantis (2026) audited a real
institutional LMS dataset and found k-anonymity = 1 and l-diversity = 1 —
i.e., effectively zero protection — even after standard de-identification.
Liu et al. (BJET, 2025) cite a real breach (Illuminate Education, 820,000
student records) as the concrete cost of relying on anonymization alone, and
state plainly that k-anonymity/l-diversity are "considered relatively
outdated" now that differential-privacy-based synthetic data generation
exists. Under LGPD (Lei Geral de Proteção de Dados) — this project's
governing regime — and by the same logic under GDPR, only synthetic or
formally privacy-audited surrogate data may enter the pipeline in place of
real student records.

**R18. Every synthetic dataset must be validated jointly on fidelity/utility
AND privacy — never on one axis alone — and no single generator may be
assumed to win on both.**
Liu et al. (2025) is explicit: "no single generator wins on all axes...
privacy and utility must be evaluated jointly and choice depends on the use
case." Minimum required metrics before any synthetic dataset is accepted:
- **Utility**: Train-on-Synthetic-Test-on-Real (TSTR) performance gap vs. a
  real-data-trained baseline (AUCROC or task-appropriate equivalent).
- **Privacy**: at minimum one membership/re-identification-oriented check
  (k-anonymization, delta-presence, or an identifiability score) and one
  duplication check confirming no synthetic record is a near-exact copy of
  a real one (the "NewRowSynthesis" pattern, Barr, Guo & Sezgin, 2502.09566).

**R19. Prefer frozen, in-context (zero-/few-shot) generation over fine-tuning
whenever the conditioning data could contain real personal information.**
Fine-tuning on small, sensitive datasets carries materially higher
memorization and membership-inference risk than prompting a frozen
black-box LLM with in-context examples — GAN-style generators are
demonstrably vulnerable to membership-inference attacks at n < 10,000
(Barr, Guo & Sezgin, 2502.09566). Seedat's CLLM architecture (PhD thesis,
ch. 4) is built on exactly this principle: a frozen LLM conditioned via
in-context learning, never fine-tuned on the scarce/sensitive Dtrain. This
is also the operational mechanism satisfying R17 in practice, not just in
policy.

**R20. Any bias introduced by a generator LLM into synthetic data must be
actively audited and curated out, not assumed absent because the source
data was itself unbiased.**
Seedat (ch. 4.3.2) shows LLM-introduced bias can be detected via standard
fairness metrics on the generated data (Demographic Parity Difference,
Equalized Odds Difference) and mitigated via learning-dynamics-based
curation, which empirically reduced equalized-odds violation from
Δ ≈ 0.89–0.90 (biased synthetic set) to Δ ≈ 0.13–0.08 (curated set) in a
controlled study. This curation step is mandatory wherever synthetic data
stands in for real student data under R17.

---

## V. LLM-as-a-Judge Bias Mitigation — Immutable Rules

**R21. Every LLM-judge verdict must be produced under an explicit
position-bias control before it is accepted as final — minimum bar:
bidirectional swap-and-average, declaring a tie on inconsistency.**
Zheng et al. (NeurIPS 2023, MT-Bench/Chatbot Arena) found raw judge
consistency as low as 23.8% (Claude-v1, default prompt) before order-swap
correction, rising to 56.2–65% after prompt fixes. For MCQ-format items
specifically (the AIG system's primary output), Pezeshkpour & Hruschka
(NAACL 2024 Findings) found option-order sensitivity gaps of 13–85% in
accuracy and recommend **majority-vote calibration over ≥10 random
reorderings** as the concrete mitigation. Position-bias magnitude is
model/version-dependent and reportedly near-negligible in some newer judge
models (Soumik, 2604.23178v2: ≤0.04) — this does not waive the control; it
means the control's *cost* may be tunable per model, not that it may be
skipped (see R25).

**R22. Every LLM-judge rubric must mechanically neutralize verbosity/length
as a scoring factor, verified per judge model via a length-confound audit
(paired same-content-different-length probes) — never assumed corrected by
instruction alone.**
Uncorrected, verbosity bias reaches up to 91.3% failure rate under a
repetitive-list attack (Zheng et al., 2023) and causes the largest single
verdict-flip rate (31.3%) among four studied biases (Yang et al., NeurIPS
2025, RBD paper). Critically, **direction is not universal**: Soumik
(2604.23178v2) found Gemini/Llama favor verbosity (+0.24 to +0.44) while
Claude Sonnet 4 favors *concision* (−0.12) — a single fixed-direction
length correction would be wrong for a subset of judge models. The audit
must therefore be re-run per judge model, not applied as a global constant.

**R23. No item, rubric, or synthetic-data judgment may be accepted from a
single, uncorrected judge call.**
At least one of the following must wrap every judge invocation: bidirectional
position swap (R21), chain-of-thought self-explanation prior to verdict, or
reference-guided grading (generate a reference answer first, grade against
it) — the last cut math-item failure rate from 70% to 15% in Zheng et al.
(2023). Multi-agent debate is explicitly **not** an acceptable substitute:
Ma et al. (EMNLP 2025 Findings) found multi-agent debate *amplifies* bias
after the first round; only a "Conclude"-mode meta-judge (synthesizing a
fresh verdict rather than selecting among existing ones) measurably reduced
it.

**R24. LLM judges evaluating AIG-generated educational items must never be
trusted for leniency calibration without a human-expert control group.**
Kim et al. (BEA 2025, STAIR-AIG) found LLM judges (including o3-mini) rated
items "Satisfied" in nearly 100% of cases across categories where a human
expert flagged 11–67% as "Dissatisfied," missing vague terminology, obvious
answer clues, cultural insensitivity, and conceptual inaccuracy that only
the human caught. This is the judge-layer instance of [R8]'s no-self-report
principle — it must be re-applied at the judge layer, not assumed satisfied
because R8 covers the generator.

**R25. Bias-mitigation configuration is tied to a specific judge model
version and must be re-audited on every judge model upgrade — never assumed
transferable across models or carried forward unchanged.**
Both the magnitude and the *direction* of a given bias vary across model
families and drift across versions of the same family (Soumik, 2604.23178v2).
Every bias-audit result stored in the system must be timestamped and tagged
with the exact judge model/version it was measured against [cf. R11's
analogous caution for Bloom-difficulty claims].

**R26. The Judge Agent must never be the same model, checkpoint, or
close-family variant as the Generator Agent for any item accepted without
further mandatory human review.**
Self-enhancement/self-preference bias is well-documented and large: GPT-4
judges favored GPT-4-authored content by +10% win rate, Claude-v1 favored
its own by +25% (Zheng et al., 2023); Bavaresco et al. (ACL 2025,
JUDGE-BENCH) independently confirm LLM judges show a systematic positive
bias toward machine-generated text generally. Cross-provider judging
(generator and judge from different vendors/families) is the required
default configuration, not an optional hardening step.

---

## VI. Item Response Theory (IRT) Calibration — Immutable Rules

**R27. No AIG item may be considered "validated" on classical reliability
metrics alone (Cronbach's alpha/omega, raw facility/pass-rate). IRT-level
parameters — at minimum difficulty (b) and discrimination (a) — must be
estimated and checked before an item is considered calibrated.**
Angelelli, Oliva, Arima & Ciavolino (2510.24739v3) show AI-generated and
human-authored instruments can be statistically indistinguishable on
classical reliability while diverging sharply in IRT-based item information,
factor structure, and item-parameter ordering — their **"co-monotonicity"**
check (do human and AI item-difficulty/discrimination rankings agree?)
failed even where Cronbach's alpha did not detect any problem. Classical
reliability is necessary but was empirically shown insufficient.

**R28. Items with negative, or statistically indistinguishable-from-zero,
discrimination must be automatically excluded from the operational item
bank — not merely down-weighted or flagged for optional review.**
(Balepur et al., ACL 2025, citing Rodriguez et al., 2021: negative
discriminability indicates a faulty item, not merely a hard one.) This is
the IRT-level complement to the IWF flaw detector [R16]: an item can pass
lexical/structural flaw screening and still fail IRT validation, and must
still be excluded.

**R29. AI-generated items must meet the same discrimination-index bar as
human-authored items before entering the same operational bank; a
systematically lower discrimination index for AI-origin items is a
rejection signal, not an accepted baseline to normalize around.**
Ahmed, Kerr & O'Malley (BMC Med. Educ., 2025) found AI-generated
single-best-answer items scored DI = 0.24 vs. 0.28 for human-authored items,
with only 12/50 AI items reaching the DI > 0.3 summative-exam threshold
versus 24/50 human items. This gap must be closed pre-deployment (via
curation/regeneration), not accepted as an inherent property of AI-authored
content.

**R30. Wherever LLM respondents substitute for human examinees during item
calibration — permissible specifically to satisfy the no-real-student-data
constraint [R17] during early piloting — resulting difficulty estimates
must be reported with their correlation to any available human-calibrated
ground truth, and the narrower proficiency spread of LLM respondent pools
must be explicitly corrected for, never treated as equivalent to a human
sample.**
Liu, Bhandari & Pardos (BJET, 2025) found LLM-respondent-calibrated item
difficulty correlates with human-calibrated difficulty at r = 0.83
(GPT-3.5, Rasch/1PL) but LLM respondent-pool proficiency SD (0.29–0.58) is
roughly half human SD (0.98) — LLM-only calibration cannot replicate
population variance. Their best-validated mitigation, a 1:1 mixed
human:LLM respondent ensemble, raised Spearman ρ from 0.89 (human-only,
N=50) to 0.93 — mixed-ensemble calibration is the required pattern
wherever full human piloting is not yet available, not LLM-only
calibration presented as a finished substitute.

---

## VII. Engineering & Reporting Rigor — Immutable Rules

**R31. This Spec Kit (constitution.md, spec.md, plan.md) must be maintained
as a "spec-anchored" artifact set: specification and implementation are
co-maintained, and any implementation that diverges from a documented rule
must either be rejected or trigger an explicit, logged amendment — never
silent drift.**
Piskala (2602.00180v1) distinguishes three rigor levels for
specification-driven development: **spec-first** (spec guides the initial
build, then drifts), **spec-anchored** (spec and code co-maintained, sync
enforced — "the sweet spot for most production systems"), and
**spec-as-source** (spec is the only human-edited artifact; used in
safety-critical model-based design, e.g. ISO 26262 Simulink workflows).
"Code is the implementation detail of the specification — not the other
way around." This formalizes the Amendment Log practice already followed
in Sections I–VI.

**R32. A passing specification check is evidence the implementation
matches the specification, not evidence the specification itself is
correct — this must be guarded against by periodic substantive review of
the rules themselves, not just their enforcement.**
Piskala (2602.00180v1) names this failure mode explicitly as **"false
confidence,"** alongside over-specification, "specification rot," and
"specification as bureaucracy" — a passing test suite proves conformance,
not validity. Applies directly to this constitution: R1–R30 must
periodically be re-checked against new evidence (as R11, R25 already
require for their specific domains), not treated as permanently settled
once encoded.

**R33. Any human-vs-AI grading/judging comparison reported by this system
must report inter-rater agreement (e.g., Cohen's κ) per subject/content
domain, not a single pooled figure, and must disclose known failure modes
alongside aggregate success metrics.**
Rangan (ETFI 2026, "Efficacy of AI-Driven Evaluation of Exams and Tests")
reports κ per subject on 2,091 real graded responses — Math 0.918, Social
Science 0.900, Science 0.863, English 1.000 — alongside 94.98% exact-match
accuracy, a 26× speed-up over human grading, *and* explicit disclosure of
degraded accuracy on messy handwriting/unconventional diagrams and a
slight positive AI bias. This disaggregated-plus-failure-mode reporting
is the bar for any AI-vs-human comparison in this system, not merely the
headline accuracy number.

**R34. Statistical comparisons between pipeline configurations (models,
prompts, judge versions) must report variance decomposition or
resampling-based uncertainty, not a single point estimate, and must not
claim a meaningful difference from a single benchmark run.**
Sälevä, Ataman & Lignos (IJCNLP-APACL 2025) show that between-language/
task variance frequently dominates and can swamp genuine model-vs-model
differences on small benchmarks: "using fixed benchmarks may understate
the differences between two models" without resampling/multi-seed
evaluation. This extends [R25]'s per-model-version bias-audit requirement
to *all* statistical claims made about the pipeline, not judge-bias claims
alone — see `plan.md` Phase 9's permutation-testing infrastructure.

---

## VIII. IRT / LLM-Respondent Difficulty Estimation — Immutable Rules

**R35. Direct LLM difficulty judgment (asking a model to state an item's
percent-correct or difficulty directly) must never be used as an item's
difficulty estimate. Difficulty must instead be derived by fitting an IRT
model to LLM *simulated-response* data — a role-played test-taker actually
answering the item — never from a model's stated opinion of how hard the
item is.**
Acquaye, Huang, Carpuat & Rudinger (2601.09953v1) found direct LLM
difficulty/percent-correct estimation is essentially uninformative:
correlation with real NAEP outcomes ranged from ρ = 0.01–0.15 for GPT-4o
and −0.139 to 0.137 across 10 open-source models (§5.1). By contrast,
fitting a Rasch (1PL) IRT model to a simulated classroom of LLM "students"
(role-played at graded proficiency levels, answering the item; correct/
incorrect responses fit jointly for ability and difficulty) reached r =
0.78 for a single model and ρ up to 0.82 for a weighted ensemble
(§5.2–5.3). This extends R30's LLM-respondent-ensemble requirement by
specifying **how** the respondent pool must be used (simulate-then-fit),
not merely that it may substitute for humans. Scope caveat: the same paper
found distractor/wrong-answer match rates between simulated and real
students of only 31–47% (barely above the 20–25% chance baseline for 4–5
option MCQs, §5.4) — this method calibrates the *difficulty* parameter,
never the plausibility of specific distractors, and must not be
represented as validating distractor quality.

**R36. Respondent-model selection for difficulty simulation (R35) must not
default to the strongest/highest-solve-accuracy model, and any validated
respondent-model/method must report which content domains it was
validated against — it may not be assumed to generalize to untested
domains.**
Acquaye et al. found models that solve the target items well are *worse*
difficulty simulators: Qwen2.5-32B and Llama-3.3-70B (92–93% solve
accuracy on the questions themselves) yielded only r = 0.51–0.62, while
Gemma-2/3 models with markedly lower solve accuracy (72–83%) produced the
strongest correlations (§5.2, "Models that struggle to solve the questions
themselves better simulate student performance"). Domain-dependence is
separately confirmed by Kolesnikova, Fedyanin, Hofman, Brinkhuis &
Bolsinova (2605.18562v1): LLM-as-expert difficulty estimation degrades for
linguistically complex, non-arithmetic item types (mean Spearman ρ falling
from ≈0.77 for Subtraction to 0.501 for Text Problems, Table 7). This is
the same caution R11 already requires for Bloom-difficulty claims, applied
here to difficulty-estimation methodology itself.

---

## IX. Auditable Energy Reporting for Black-Box Inference — Immutable Rules

**R37. Where direct hardware energy instrumentation is unavailable (e.g., a
black-box cloud inference API), the pipeline must still log the
causally-relevant proxy signals for energy consumption on every call — at
minimum: input and output token counts, the model identifier, and whether
extended/reasoning-mode generation was used — and must report any derived
energy figure explicitly as an uncalibrated relative proxy, never as a
measured absolute joule/kWh figure.**
Wang, Xiao, Yan et al. (2512.01644v1) measured output-token count as the
dominant, near-deterministic energy driver on instrumented hardware:
energy scales linearly with output length (R² = 0.999, ≈1.72 J/generated
token on an A100) while input/prompt length is nearly irrelevant (R² =
0.071) (§4.3.1). Chung, Wu, Ma & Chowdhury (2601.22076v1), measuring 46
models × 7 tasks × 1,858 configurations, found task type alone drives up
to 25× energy-per-response differences — dominated by output length (e.g.,
10× more output tokens for reasoning tasks) compounded with
batching-dependent per-token cost — and GPU batching/utilization state
alone can shift energy-per-token by 3–5× (a variable invisible to the API
caller) (§3.1, 4.1). Their core prescriptive finding is that root-cause
energy diagnosis requires tracing through auditable proxies — model
choice, quantization, batch size/GPU count, output token count — even
where GPU wattage itself cannot be measured (§5.5). Critically, Vartziotis
et al. (2607.26571v1) show that converting token counts into absolute
joules requires GPU-architecture-specific calibration constants (α_TC,
e_HBM) empirically fit per hardware generation (H100 vs. A100 already
differ by ~30–35%, Table 1), and explicitly warn these "should be
recalibrated when applying the methodology to a different GPU generation,
inference engine, batching regime, or serving configuration" (§3.5) — no
such calibration exists for this project's actual inference hardware
(Groq's proprietary LPU accelerators). This rule mandates the auditable
proxy log as the floor requirement and explicitly prohibits presenting a
token-derived number as a calibrated kWh figure without hardware-specific
validation — closing part of the Green AI disclosure gap (`spec.md` §5.4)
honestly, via proxy reporting, rather than reporting nothing at all.

**Implementation status (2026-08-18, exceeded — real measurement, not
just the proxy floor):** this rule's own precondition ("where direct
hardware energy instrumentation is unavailable") stopped applying once
generation moved from Groq's black-box hosted API to a locally-served
vLLM instance on project-controlled GPU hardware. Direct instrumentation
*was* available there, and was used: `nvidia-smi
--query-gpu=power.draw,utilization.gpu,memory.used` sampled every 2
seconds for the full duration of the 239-item production run, with total
energy computed by trapezoidal integration of instantaneous power over
time. Result: **1.498 kWh** total (1,497.85 Wh), **16.1 Wh per approved
item** (93/239 approved in that run) — a real, calibrated absolute
figure, not the uncalibrated relative proxy this rule mandates as a
floor for the black-box case. This does not waive the rule for any
future black-box-API-only run (the proxy-logging floor above still
applies whenever direct instrumentation is genuinely unavailable) — it
means this project's own local-hardware runs cleared a higher bar than
R37 requires, not that R37 became moot. Full methodology in
`relatorio_tecnico.tex` §"Medição Real de Energia" and `CONTEXT.md` §9.2.

---

## X. Multi-Constraint Position Bias — Immutable Rules

**R38. No constraint in a multi-constraint generation prompt (e.g.,
Bloom-level verb, target position, verbosity limit, mutual-exclusivity
requirement, factual correctness) may be assumed satisfied merely because
of where it appears in the prompt. Every safety/validity-critical
constraint must be verified mechanically, post-generation, independent of
prompt order — and any prompt-reordering mitigation must be empirically
validated per model and per constraint type before being trusted, never
applied as a fixed universal heuristic.**
Zeng, He, Ren, Liang, Xiao et al. (2502.17204v1) show constraint order
alone shifts per-constraint compliance by ~5–7 percentage points in
single-turn generation and by ~10–25 percentage points in multi-turn/
iterative generation, across six tested model families (LLaMA3-8B/70B,
LLaMA2-13B, Mistral-7B, Qwen2.5-7B, GPT-4o-mini) (§4.2, Fig. 4–5).
Critically, the effect's *direction* is not uniform across constraint
types: while most constraint types improve when placed earlier
("hard-to-easy" order), output-boundary constraints (e.g., "end with
phrase X") and content-inclusion constraints get *worse* under the same
reordering (Startend accuracy fell 62.92%→57.42% as difficulty-order moved
from easy-first to hard-first, §4.2, Table 1) — a single fixed reordering
heuristic cannot be trusted across all constraint types. The authors
explicitly state they investigate the phenomenon "without offering a
solution" (§7, Limitations). This generalizes, with independent literature
grounding, this project's own mid-implementation finding
(`relatorio_tecnico.tex` §3, "Descoberta Metodológica Central") that
stacking a positional constraint and a content-correctness constraint in
one generation call caused the generator to reliably satisfy position
while intermittently sacrificing correctness: that was one specific
instance of exactly this general phenomenon, not an isolated
implementation bug. `spec.md` §4.1's position-content decoupling amendment
is the concrete mitigation for that one case; this rule generalizes the
underlying requirement to every other stacked constraint the Generator
Agent prompt carries.

---

## XI. Synthetic / LLM-Generated Data Auditing — Immutable Rules

**R39. Passing the mechanical pre-filter and Judge Agent (position,
verbosity, mutual exclusivity, Bloom-verb alignment) must never be
represented as a complete quality-or-trustworthiness audit of a generated
item. Any claim that an item or item batch has been "validated" must
explicitly state which dimensions of a quality/trustworthiness taxonomy
were actually checked, and which were not.**
Zhang, Hu, Le, Torsha, Jiang, Bui, Chang, Chuang, Xiong et al. (2601.17717,
TMLR 06/2026) organize LLM-generated-content evaluation into two pillars
and, in this project's terms, seven checkable dimensions: **Quality**
(validity, fidelity, diversity, utility) and **Trustworthiness**
(faithfulness, safety, robustness, fairness, privacy/provenance, benchmark
contamination) (§1). This pipeline's four mechanical checks map only to
"validity"; fidelity, diversity, faithfulness, safety, and benchmark
contamination are entirely unaddressed by the current Judge Agent. The
survey's own audit of 8 published text-generation papers found validity
explicitly reported by 0/8, faithfulness by 2/8, safety by 1/8, and
benchmark contamination by 1/8 (Table 2) — under-disclosure of audit scope
is the empirically documented norm this rule is designed to prevent, not a
hypothetical risk.

**R40. A generated item's answer key must never be accepted as correct
solely because the Generator Agent or a single Judge Agent pass asserts
it. Correctness must be independently checked via a resampled
self-consistency/re-derivation method, with the agreement rate reported.**
The same survey documents concrete methods for exactly this purpose:
`AccSC`/`Agree` resample K independent reasoning derivations and check
majority-vote agreement on the final answer, and `Accverify` compares a
derivation against an external ground truth or tool (§3.2). This is the
item-level complement to R8/R24's no-self-report principle: a single LLM
pass claiming an answer is correct is not self-verifying, whether that
pass belongs to the Generator or the Judge.

**R41. A generated item batch must be checked for cross-item diversity/
redundancy before delivery — no two items in the final delivered batch may
be near-duplicates in phrasing or content, even if each individually
passes per-item validation.**
The current Judge Agent evaluates every candidate in isolation and never
compares across the delivered batch. Zhang et al. (2601.17717) catalog
diversity/redundancy metrics precisely for this gap — mean pairwise
embedding cosine similarity (`Self-CosSim`, lower = better spread),
type-token ratio, Distinct-N, and n-gram entropy (`Ent-n`) — designed to
detect mode collapse and near-duplicate generation across a batch (§2.2).
Per-item validity checks (R9–R16, R21–R26) are necessary but not
sufficient for a delivered batch: an item-by-item-valid but highly
redundant batch still fails this rule.

---

## XII. Second Literature Wave — Implemented Tier-1 Fixes (Modules 10, 11, 13)

Unlike Modules 6–9 (§VIII–XI, findings only), the three rules below are
backed by an actual code change in `WAPLA_AIG_Engine.py`, made the same
day these findings were extracted — selected specifically because each
extends existing code rather than requiring new architecture (see
Amendment Log v0.8).

**R42. Schema field ordering must place rationale/reasoning/justification
fields BEFORE the answer/verdict field they justify, in every structured-
output schema this pipeline defines.**
Tam, Wu, Tsai, Lin, Lee & Chen (2408.02442, "Let Me Speak Freely?") found
forcing a model to commit to an answer key before its reasoning caused
severe, task-specific accuracy collapse — 38 points on Last Letter
Concatenation (74.7%→28.0%), 63 points on GSM8K (86.51%→23.44%) — and
confirmed the cause is structural, not a parsing artifact: 100% of one
model's JSON responses on the affected task placed the answer key before
the reasoning key, while the actual JSON parse-error rate on that same
task was only 0.148%. This generalizes R38's (multi-constraint position
bias) finding to schema-level field order specifically:
`GeneratedItem.generator_notes` and `JudgeVerdict.blind_solve_reasoning`/
`reasons` must precede `correct_option`/`blind_solve_shuffled_label`/
`verdict` respectively, never follow them.

**R43. No judge verdict may be trusted from a single pass without an
available consistency-check mode, and that mode — when enabled — must use
sampling, never temperature=0.0, to resample for consistency.**
Haldar & Hockenmaier (EMNLP 2025 Findings, "Rating Roulette") measured
cross-run self-inconsistency on identical repeated inputs: Krippendorff's
α ranged 0.27–0.79 across models and tasks, with the best model agreeing
with itself on only 61.3% of 3 identical runs on MT-Bench. Critically,
disabling sampling (temperature=0.0) to force determinism *reduced*
human-agreement relative to sampling + majority vote across every model
tested — "there is a trade-off between self-reliability and performance,
and it is not trivial to address both simultaneously." Their own
recommendation, adopted here as the concrete mechanism: aggregate ≥3
independently sampled runs via majority vote — they tested up to 5–10
runs and found no additional benefit past 3. This is orthogonal to R21's
position-bias reordering, which targets a different failure mode.

**R44. Wherever locally-served inference supports grammar-constrained
decoding against this pipeline's own Pydantic schemas, it must be used —
prompting-only JSON generation may not be assumed reliable above trivial
schema complexity.**
Geng, Cooper, Moskal, Jenkins, Berman, Ranchin, West, Horvitz & Nori
(2501.10868, JSONSchemaBench) found prompting-only compliance falls from
90% on simple schemas to as low as 13% on complex real-world schemas
(median 175 fields), while the best constrained-decoding framework
reached 0.87–1.00 compliance on the same schemas. Critically, constrained
decoding did not cost task accuracy in their tests — it *improved* it by
roughly 3–4 points on every reasoning task tested, contradicting the
common assumption of a quality tradeoff (the authors attribute prior
reports of degradation to poor prompting/schema design, not constrained
decoding itself). Per R32's "false confidence" caution: this rule
currently applies only where a locally-served backend accepts a
guided_json-equivalent parameter (this pipeline's `vllm_local/` provider
path) — this project's hosted Groq models do not support it today, so
this is not yet a universal guarantee across every model this pipeline
can call.

---

## XIII. Exact Length Control for Structured Generation — Immutable Rules

**R45. Where a generation call requires an EXACT (not approximate) output
length — including forcing multiple parallel fields to the SAME exact
word count, as opposed to a soft target/tolerance band — the generator
prompt must externalize the counting via visible, sequentially-
decrementing countdown markers and explicit counting rules, never rely
on an internal/implicit length instruction alone.**
Xie & Lee (2508.13805, "Prompt-Based One-Shot Exact Length-Controlled
Generation with LLMs") show that LLMs cannot reliably maintain an
internal token counter (self-attention has no explicit accumulator), so
instructing a target length directly ("write exactly N words") is
fundamentally unreliable regardless of how the target is computed or how
tight its tolerance is stated — this generalizes this project's own
finding (Design C, tested same-day) that injecting a concrete numeric
target without externalizing the count produced no measurable
improvement. Their countdown-marker suffix ("CAPEL") instead has the
model emit sequentially-decrementing markers `<N>word<N-1>word...<1>word<0>`
interleaved with the actual content, turning length tracking into visible
"pattern completion" rather than an invisible internal count. Reported
results: MT-Bench-LI strict length compliance with gpt-4.1 rises from
below 30% (naive instruction) to above 95% (countdown prompt); across
eleven tested models, exact-match (EM) length compliance rises from 9.7%
to 96.3% for gpt-4.1 and from 3.4% to 79.8% for Qwen3-8B; on open-ended
1–1000-token generation, EM rises from 1.9% to 94.2% (GPT-4.1) and from
0.6% to 72.1% (Qwen3-8B), with mean absolute length deviation dropping
roughly 80–100%. The paper's own headline framing: "nearly perfect (99%)
compliance across diverse target lengths... in both English and
Chinese." **Caveat, mirroring this constitution's existing per-model-
validation requirement [R25, R36]:** the same paper found the technique
can *increase* error for certain small or safety-hardened models
(o4-mini, gpt-4o-mini) — chain-of-thought guardrails can misread the
countdown as a disclosure request and refuse/truncate, or the model may
simply ignore the markers — so this must be validated per generator
model before being trusted, not assumed universal. **Scope caveat, per
[R32]'s false-confidence caution:** the paper's own experiments apply one
countdown sequence to one continuous output; using five independent
countdown sequences to length-match five parallel JSON fields in a
single call (this project's intended application, replacing the failed
Design C soft-target approach) is this pipeline's own untested
generalization of the paper's result, not a directly cited finding —
must be calibrated empirically before being trusted as a solved problem.

**Implementation status (2026-08-19, Design D calibrated and shipped):**
implemented in `WAPLA_AIG_Engine.py` as "Design D" —
`strip_countdown_markers()` mechanically strips the model's visible `<k>`
markers post-generation (never trusts self-transcription), and
`describe_countdown_malformation()` diagnoses (never gates on) whether the
raw, pre-strip text actually followed the protocol. Calibrated on a paired
30-item sample against the pre-Design-D baseline: approval rose from
33.3% to 50.0% (+16.7 points), and the length-extreme rate fell from
82.9% to 76.7% — the scope-caveat generalization above (one countdown
sequence per JSON field, five fields per call) does work, partially. But
the mechanism is **not reliable**: 77.3% of attempts contained at least
one malformed marker sequence (empty-marker tails, incorrect/incomplete
sequences, stray text after `<0>`) — the small/guardrail-hardened-model
caveat above turned out to apply more broadly than just o4-mini/
gpt-4o-mini-class models. The full 239-item production run confirms the
same direction at scale (length-extreme rate 73.2%, vs. 82.9%
pre-Design-D). Full methodology, the refuted Design C predecessor, and
the ~40% combinatorial-floor analysis separating "unavoidable noise" from
"correctable bias" are in `relatorio_tecnico.tex` §"Descoberta
Metodológica Central" and `CONTEXT.md` §9.1 (staged full version).

---

## Amendment Log

- v0.1: Established R1–R16 from Module 1 literature
  (`literatura/mod_1_fundacao_pedagogica_pbl/`). Bloom's Taxonomy validity
  critique (Haladyna & Rodriguez, 2013) acknowledged but taxonomy retained
  per user requirement of "strict Bloom's Taxonomy alignment" — mitigated
  via R8, R11, and mandatory independent verification rather than rejected.
- v0.2: Established R17–R20 (LGPD/Privacy) from Module 2 literature
  (`literatura/mod_2_motor_aig_sintetico/`). Gap noted: none of the Module 2
  sources gave a formal differential-privacy mechanism specific to synthetic
  *item* generation (as opposed to synthetic *student profile/tabular* data)
  — R17–R20 are written to cover both, but a DP mechanism for text/item
  generation specifically (cf. SynthTextEval's DP-SGD) remains a candidate
  for deeper treatment if the thesis scope requires it.
- v0.3: Established R21–R30 (LLM-as-a-Judge Bias Mitigation; IRT
  Calibration) from Module 3 literature
  (`literatura/mod_3_juiz_estatistica_tri/`). Note on evidence quality: the
  position/verbosity-bias magnitudes cited (R21, R22) come from several
  independent studies using different judge models and years (2023–2026);
  the rules mandate the *control mechanism*, not a fixed numeric bias
  magnitude, precisely because Soumik (2604.23178v2) demonstrates magnitude
  and direction are model/version-dependent and shift over time — this is
  the same caution already established for Bloom-difficulty claims in R11.
- v0.4: No new constitution rules added from Module 4
  (`literatura/mod_4_infra_green_ai/`) — Green AI/SLM-efficiency findings
  were architectural (routing, model tiering, Pareto selection) rather than
  immutable-rule-shaped, and were written into `spec.md` §5 and `plan.md`
  Phase 11 instead.
- v0.5 (final pass): Established R31–R34 (Engineering & Reporting Rigor)
  from Module 5 literature (`literatura/mod_5_eng_spec_artifacts/`). This
  closes the five-module literature review
  (`literatura/mod_1_fundacao_pedagogica_pbl/` through
  `literatura/mod_5_eng_spec_artifacts/`). R31–R32 are notably
  self-referential: they govern how this Spec Kit itself must be
  maintained going forward, not just the AIG system it describes. Two
  Module 4 sources remain unread (`19801_pub.pdf`,
  `2024.emnlp-main.1215.pdf` — see `plan.md`'s Sequencing Notes); revisit
  before treating the R1–R34 rule set as final for defense/submission.
- v0.7 (second literature wave): established R35–R41 from four new
  modules ingested after the WAPLA 2026 submission —
  `literatura/mod_6_irt_llm_respondents/` (R35–R36),
  `literatura/mod_7_energy_measurement/` (R37),
  `literatura/mod_8_position_bias_generalization/` (R38), and
  `literatura/mod_9_synthetic_data_auditing/` (R39–R41). Logged per R31
  (no silent drift): these four modules are being folded into the
  pipeline as active implementation work, not retained as unused
  literature review. Two cross-references worth noting: R37 is written to
  partially close the previously-disclosed Green AI reporting gap
  (`relatorio_tecnico.tex` §"Escolha de Modelos") via auditable proxy
  logging rather than absolute energy figures, since no hardware
  calibration exists for this project's Groq inference backend; R38
  generalizes, with independent literature grounding, the
  position-content coupling bug this project found and fixed
  mid-implementation (see the v0.6 amendments to `spec.md` §4.1 and
  `CONTEXT.md`) into a standing rule about stacked-constraint prompts in
  general, not just the one position-vs-content case. Matching `spec.md`
  and `plan.md` Amendment Log entries record the architecture-level side
  of this expansion.
- v0.8 (second literature wave, Tier-1 fixes claimed): established R42–R44
  from `literatura/mod_11_judge_reliability_uncertainty/` and
  `literatura/mod_13_structured_output_reliability/`, and claimed at the
  time that all three were implemented the same day in
  `WAPLA_AIG_Engine.py`. A subsequent code audit (2026-08-17) found this
  claim was only true for R42, and only after a follow-up correction — see
  v0.9 below. R43 and R44 remain **not implemented**: no code audit has
  yet re-verified or corrected them, so treat both as open. Explicitly
  deferred, by the user's own scoping decision: Module 12 (differential
  item functioning for human vs. chatbot test-takers) and the Module 10
  distractor-plausibility checks (D-GEN entropy metric,
  overgenerate-and-rank) — logged as "planned, not yet implemented" in
  `plan.md` instead of promoted to a rule here, since they need more
  data/architecture planning than a same-day extension of existing code
  allows.
- v0.9 (R42 correction, 2026-08-17): the v0.8 claim that R42 was
  implemented was false as written — a code audit found `GeneratedItem`
  declared `correct_option` *before* `generator_notes`, and `JudgeVerdict`
  declared `blind_solve_shuffled_label` before `blind_solve_reasoning` and
  `verdict` before `reasons` — the exact backwards order R42 prohibits, in
  both schemas, in both directions. Fixed same day: both Pydantic classes
  reordered so reasoning fields precede the answer/verdict fields they
  justify, **and** the corresponding generator/judge system prompts in
  `build_generator_messages`/`build_judge_messages` (previously still
  listing the old, wrong field order in the "respond with exactly these
  fields" instruction — the part that actually governs generation order
  under this pipeline's JSON-mode-only decoding, since R44's
  schema-constrained decoding is not in place) were corrected to match, so
  the fix is not merely cosmetic at the Pydantic-class level. A
  calibration run (`--output-tag r42fix`, pool_size=30) was executed
  same day to measure the effect on discard rate — see `plan.md`/run logs
  for the result. R43 and R44 are unaffected by this entry and remain
  claimed-but-unverified per v0.8 above; do not assume either is fixed
  until each gets its own same-day-verified correction like this one.
- v0.10 (Module 14, R45 established): `literatura/mod_14_exact_length_control/`
  added and `2508.13805v1.pdf` downloaded same day; title/authors verified
  against the arXiv abstract page before use (`literatura/mod_14`'s only
  source, same rigor as every prior module). R45 established as the
  direct successor to the same-day Design C finding: Design C (a soft
  numeric word-count target, no countdown/externalized counting)
  measurably failed to reduce the correct-option-is-the-length-extreme
  rate on a 30-item calibration (82.9% before, 85.9% after — i.e., no
  improvement) — spot-checked generations showed the model frequently
  ignored the injected target outright, confirming an internal-counter
  reliability problem exactly as this paper independently diagnoses. R45
  is logged as **proposed, design not yet implemented** as of this entry
  — per the user's explicit request, the concrete prompt design (Design
  D) is presented for review before any code change, unlike R42–R44's
  same-day-implemented pattern. Follow-up entry required once Design D is
  approved, implemented, and calibrated — do not treat R45 as satisfied
  by this entry alone.
- v0.12 (2026-08-18 implementation-rigor audit, consolidated): a
  systematic pass checking claimed rules against actual code behavior —
  the same standard already applied to R42–R45 above, extended here to
  every rule this project's own pipeline is supposed to actively enforce.
  Three findings, none previously disclosed at the rule level:
  - **R1–R5 (§I, PBL foundations): out of scope, zero code, does not
    shape any delivered item.** This deliverable rewrites existing,
    already-flagged dataset items using EDA-diagnosed structural flaws as
    feedback; it never constructs a PBL scenario from a domain corpus, tags
    PrBL/PjBL, declares a FIRM/RELAXED/FLEXIBLE integration mode, scores
    AI-use as a rubric criterion, or runs a leakage blocklist. This has
    been disclosed in `relatorio_tecnico.tex`'s specification-coverage
    table (`tab:cobertura`, row "R1–R5") since that table was written;
    this entry brings `constitution.md` itself to the same standard,
    per R31 — no rule should be silently left implying more than its code
    delivers.
  - **R10 (§II, Bloom template): partially implemented, not fully.** The
    verb-bank half is real, mechanically enforced, and fired 26 times
    across today's real sessions. The structural-rule half (cause/effect
    reframing, pros/cons comparisons, forward-looking actions,
    verbatim-fact recall) has zero code — every Bloom level gets
    identical option-structuring instructions, differing only in which
    verb is required. See the inline scope note added to R10 above for
    the full accounting, including why the Evaluate/Create table rows are
    structurally unreachable given R9's demotion logic (not a defect,
    a documented consequence).
  - **R11 (§II, Bloom-difficulty as hypothesis): aspirational, zero
    code, same category as R1–R5.** No Δ_bloom or any cross-level
    discrimination statistic is computed anywhere in the pipeline;
    `target_level` is used only as a generation/verification label. See
    the inline scope note added to R11 above.

  Net effect of this entry: of every rule this project's pipeline
  actually touches end-to-end, R9, R12/R13, R21–R23, R25–R26, R38, and R42
  (as of its v0.9 correction) are confirmed genuinely implemented and
  evidenced; R10 is confirmed half-implemented; R1–R5, R11, R24, R27–R30,
  R37, R39–R41, R43, and R44 remain documented-but-unimplemented or
  explicitly deferred, per their own respective entries above. No rule in
  this document should be read as "implemented" merely because it has an
  amendment-log entry — that would repeat exactly the mistake R32 warns
  against.
- v0.13 (2026-08-19, R45 implementation-status follow-up, fulfilling the
  v0.10 commitment): Design D (countdown-marker exact length control) was
  implemented and calibrated the same day as this entry — see the inline
  implementation-status note now added to R45 above. Real but partial
  effect (33.3%→50.0% approval on a paired 30-item calibration, 77.3%
  marker-malformation rate; confirmed at full 239-item scale). This
  corrects the v0.12 net-effect summary immediately above, which omitted
  R45 from its "confirmed genuinely implemented" list — R45 belongs there
  alongside R9, R12/R13, R21–R23, R25–R26, R38, and R42, not in the
  unimplemented/deferred list. `spec.md`'s matching v0.8 entry (which
  logged R45 with only "partial, non-conclusive results" per `CONTEXT.md`
  §8) is superseded by this fuller account; see `spec.md`'s own v0.9 entry
  for the corresponding correction there.
- v0.14 (2026-08-20, R37 implementation-status follow-up — same category
  of correction as v0.13): the v0.12 net-effect summary two entries above
  lists R37 among the rules that "remain documented-but-unimplemented or
  explicitly deferred." That was true when v0.12 was written but is now
  stale: the real `nvidia-smi` power-measurement work (1.498 kWh over the
  239-item production run, 16.1 Wh/item approved — see the inline
  implementation-status note now added to R37 above) was completed
  afterward, the same way Design D's R45 calibration was. R37 belongs
  alongside R9, R12/R13, R21–R23, R25–R26, R38, R42, and R45 in the
  "confirmed genuinely implemented" list, not in the unimplemented/
  deferred one — in this case *exceeded*, not merely satisfied, since
  direct hardware instrumentation was actually available for these local
  runs, superseding the black-box-proxy floor the rule's text describes.
  Found during an external cross-consistency audit of the files staged
  for the Kaggle submission folder, not by the same-day implementation
  work itself (unlike R45's v0.13 entry) — flagged here per R31/R32
  rather than corrected silently, matching this document's own standard
  for a wrong or stale claim.
