# Spec — AIG (Automated Item Generation) System Architecture

Status: DRAFT v0.8 — see Amendment Log for the version history; this
header previously read "v0.1" long after the document had moved past it
(fixed 2026-08-18 cross-document consistency pass).
Governs: The architectural base of the AIG pipeline. Every component below
exists to satisfy one or more IMMUTABLE RULES in `constitution.md` (cited
inline as [Rn]).

---

## 1. System Overview

The AIG system is a **multi-stage, human-in-the-loop (HITL) pipeline** that
turns a domain knowledge source + a PBL problem specification into
validated assessment items and rubrics. It is explicitly NOT a single
LLM-call generator: generation, classification, and validation are
performed by *separate* processes so that no stage can mark its own work
[R8, R13].

```
Domain Corpus ──▶ Practice/Concept Extraction ──▶ Scenario Construction ─┐
                                                                          │
   Item Spec (radicals) ◀── Blueprint / Test Spec ◀───────────────────────┘
        │
        ▼
  Item Generator (LLM-1) ──▶ RAG Refiner (LLM-2) ──▶ Independent Bloom
        │                                                Classifier [R8]
        ▼                                                     │
  IWF Flaw Detector [R16]  ◀────────────────────────────────────┘
        │
        ▼
  Rubric Generator ──▶ Mutual-Exclusivity Linter [R12, R13]
        │
        ▼
  Human Review (SME + fairness/DIF) ──▶ Accept / Regenerate ──▶ Item Bank
                                                                     │
                                                                     ▼
                                                       Pilot / Psychometric
                                                       Validation (IRT, DIF,
                                                       discrimination)
```

---

## 2. Component Specifications

### 2.1 Blueprint / Test Specification Layer

- Every generation run is driven by a **two-way blueprint grid**: content
  domain × cognitive level (Bloom level, per [R6]–[R10]). This is the
  operational analogue of Downing's "Twelve Steps" Step 3 (Handbook of
  Test Development, ch. 1/ch. 9).
- Item bank target: **2.5× the operational test length per content ×
  cognitive-level cell** (Haladyna & Rodriguez, 2013, Table 2.1/2.2), so
  the bank tolerates attrition from the validation stages below.
- Each blueprint cell declares a **PBL integration mode** (FIRM / RELAXED /
  FLEXIBLE, [R3]) and a **rubric type** (holistic / analytic / single-point
  / generic, [R14]) before generation starts.

### 2.2 Radicals / Incidentals Control (item variant generation)

- Every item template separates **radicals** (elements that determine
  cognitive demand and difficulty — must be held constant across variants
  of the "same" item) from **incidentals** (superficial context — safe to
  vary for anti-cheating / uniqueness) (Gierl & Haladyna, 2012, via Burke,
  2025). This is the control mechanism that lets the system generate many
  parallel forms of one psychometrically-equivalent item.
- Radical fields are locked and versioned; incidental fields are the only
  ones exposed to a "regenerate variant" operation.

### 2.3 Practice/Concept Extraction & Scenario Construction (PBL layer)

- Source guideline/textbook material is parsed into a structured schema
  (goal / context / action / timing / person — a "5W" extraction, per
  Chen et al., BLOOMQA) rather than generating items directly from raw
  text.
- Extracted practices/concepts are filtered for clarity (≥ threshold) and
  deduplicated by similarity before being eligible for scenario
  construction — prevents redundant items inflating the bank.
- Scenario construction wraps a concept in an **ill-structured, real-life
  problem** [R1] that implicitly violates or tests the concept without
  naming it [R5]. A **leakage blocklist** (regex/keyword filter against
  absolutist terms, explicit failure language, and other answer-revealing
  cues, per Chen et al. Appendix A.1.2) runs on every generated scenario
  before it proceeds to item generation.

### 2.4 Item Generator (LLM-1) + RAG Refiner (LLM-2)

- **Two-stage generation**, not one: a baseline generator produces a raw
  item from the scenario; a second, stronger model refines/rewrites it
  grounded in retrieved source material (vector-retrieved top-k chunks
  from the domain corpus — textbooks, manuals, verified references)
  (Abdullah et al., multi-LLM RAG pipeline). Grounding in retrieved text
  is what allows the hallucination checks in §2.6 to be automatable.
- Generation prompts must explicitly instruct the model **not to invent**
  facts, names, dates, or statistics not present in the retrieved context
  (Burke, 2025) — this is a prompt-level control, verified downstream in
  §2.6, not a substitute for it.
- Each item is generated against the fixed **per-level template contract**
  in `constitution.md` R10 (verb bank + structural rule), never a free-form
  "generate a level-X question" instruction.

**Implementation-status disclosure (R10):** see `constitution.md` R10's own
implementation-status note for which half of this contract is actually
implemented in the delivered engine (verb bank: yes; structural rule: no)
— not repeated in full here, per the same disclosure pattern as §7.3's
R39 note.

### 2.5 Independent Bloom Classifier (auditor)

- A classifier **architecturally separate from the generator** (e.g., a
  fine-tuned discriminative model, not the same LLM asked to self-report)
  re-labels every generated item's cognitive level [R8]. Disagreement
  between the generator's intended level and the classifier's assigned
  level routes the item to human review rather than silent acceptance.
- MCQ format is only permitted for classifier-confirmed Remember /
  Understand / Apply / Analyze items [R9]. Items intended for Evaluate /
  Create are routed to the open-response generation path instead of the
  MCQ path.

### 2.6 Item-Writing-Flaw (IWF) Detector

- A rule-based screen checks each item against the 31-guideline / 19-flaw
  taxonomy (Haladyna, Downing & Rodriguez, 2002): ambiguity, cueing via
  absolute determiners, clang associations, grammatically inconsistent
  distractors, conspicuously correct/absurd options, answer-length
  giveaways, negation words, unverified/internet-sourced stems, and
  option-chaining (interdependent options) — the last directly enforcing
  [R12].
- More than one detected flaw ⇒ automatic reject/regenerate, never a
  warning-only pass-through [R16].
- Numeric/factual claims are checked against the retrieved source context
  from §2.4 (hallucination check) before the item can proceed — required
  for scenarios with data thresholds, dates, or statistics (Burke, 2025).

### 2.7 Rubric Generator + Mutual-Exclusivity Linter

- Rubric generation receives: assignment/item instructions, learning
  objectives, target Bloom level(s), and an explicit, non-optional
  instruction to make criteria and level-descriptions mutually exclusive
  [R12] — this instruction must be present in every rubric-generation
  prompt, not assumed.
- Output is limited to 3–6 major criteria [R15]; each criterion is checked
  against a **banned-vague-term list** ("adequate," "clear," "good," etc.
  without an operational definition).
- A **mechanical overlap linter** runs after generation: pairwise semantic-
  similarity check across criteria and across performance-level
  descriptions within each criterion, flagging any pair above a similarity
  threshold for human resolution [R13] — because generation-time
  instruction alone is empirically insufficient (Bailey, 2025).
- If the blueprint cell requires AI-usage disclosure [R4], the rubric must
  include AI-use as its own, separately-scored criterion — not folded into
  an existing criterion (which would itself violate exclusivity).

### 2.8 Human Review Layer

Mirrors the Handbook of Test Development workflow (chs. 15–16) and the
Guia BNI-Enade workflow (encomenda → elaborador → CAA review → linguistic/
sensitivity review):
1. **SME content review** — accuracy, relevance, alignment to the
   blueprint cell.
2. **Editorial/linguistic review** — clarity, translation/localization
   consistency.
3. **Fairness/DIF-oriented review** — reviewers with no vested interest in
   retaining the item review any item flagged for potential bias (cultural
   references, region-specific framing, e.g. Burke's "Black Friday"
   example).
4. **Accept / Regenerate decision point** — every rejection is logged with
   a reason code (which rule/flaw triggered it), feeding back into
   generator/refiner prompt tuning.
5. **Document & archive** — full audit trail (prompt, retrieved context,
   raw output, refined output, all review decisions) retained for
   accreditation and challengeability (Burke, 2025).

### 2.9 Item Bank + Psychometric Validation

- Accepted items enter the bank tagged with: content cell, Bloom level
  (generator-intended AND classifier-confirmed), radicals/incidentals
  metadata, rubric type, PBL integration mode, and full provenance.
- **Pilot/field-test stage** treats deployed items as a measurement
  instrument, not a finished product:
  - Item discrimination: **Δ_model = max − min accuracy** across
    respondent/model pool (threshold > 0.5 = strong discrimination).
  - Cognitive-level differentiation: **Δ_bloom** across levels within the
    same content cell (threshold > 0.2 = meaningful separation) — this is
    the empirical test required by [R11]; a Bloom label is not considered
    validated until this statistic is computed.
  - Below-chance-accuracy items are auto-flagged for removal.
  - Full IRT (Item Response Theory) calibration is the target end-state
    once sample size allows; DIF (Differential Item Functioning) analysis
    is run wherever fairness review (2.8.3) flagged a concern.
- Statistical model reference: binomial GLMM,
  `logit(p) = β0 + β_group + β_bloom + u_item`, following Chen et al.
  (BLOOMQA), adaptable from "model pool" to "student cohort" once deployed
  with real learners.

### 2.10 AI-Mediation Governance Layer (cross-cutting)

- Formalizes the triadic AI–Academic–Student relationship (Agostini &
  Picasso's AI-MAAS model) across two levels:
  - **AI-Mediated Summative**: AI drafts feedback/scoring under
    academic-authored rubrics; one-way AI→student; academic moderates
    before release. Applies to FIRM-mode PBL assessments [R3].
  - **AI-Mediated Formative**: bidirectional AI↔student interaction
    (mentor/tutor/peer role), continuous rather than end-of-course.
    Applies to RELAXED/FLEXIBLE-mode PBL assessments.
- This layer does not generate items itself; it governs how AI-generated
  items/rubrics/feedback are surfaced to students and how AI involvement is
  disclosed, satisfying [R3]/[R4] at the delivery stage, not just the
  authoring stage.

---

## 3. Item Validity Checklist (acceptance gate)

Before any item exits the pipeline to the bank, it must pass the
16-question interpretive-argument checklist (Haladyna & Rodriguez, 2013,
Table 1.5), adapted as an automatable/human-hybrid gate:
target domain match, universe-of-generalization fit, format-choice
justification (MCQ vs. open per [R9]), scoring-key accuracy, content
classification, cognitive-demand classification (§2.5), editorial pass
(§2.6), currency of source material, linguistic-complexity review,
fairness review (§2.8.3), pretesting eligibility, and a final
disposition decision (accept / revise / reject) — logged, not implicit.

---

## 4. Multi-Agent Generator ↔ Judge Architecture (v0.2 — Module 2 pass)

This section formalizes §2.4/§2.5 into an explicit multi-agent architecture
and folds in the synthetic-data-privacy requirements of R17–R20. It is
provisional: bias-mitigation design for the Judge Agent specifically
(position bias, verbosity bias) and the SLM/Green-AI efficiency framing are
carried forward as open items to Modules 3 and 4 respectively — this pass
establishes the routing skeleton and the synthetic-data-specific curation
layer they will attach to.

### 4.1 Generator Agent

- Two applicable modes, chosen per artifact type:
  - **Item/content generation** — the two-stage generator + RAG-refiner
    from §2.4 (Abdullah et al.), or the richer **LM-AIG** pattern (Lee,
    Son & Jia, 2025): a dedicated **Item Writer Agent** producing candidate
    items under AutoGen-style orchestration.
  - **Synthetic (non-item) data generation** — e.g., synthetic student
    profiles/response patterns used to stress-test the pipeline without
    touching real records (R17). Here the Generator Agent must be a
    **frozen, in-context-conditioned LLM** (no fine-tuning on sensitive
    data, R19), following Seedat's **CLLM** design: prompt = Background
    (task/feature description) + In-Context Examples (small, non-sensitive
    or already-synthetic seed set) + Instructions (generate diverse,
    structurally faithful samples).
- Regardless of mode, the Generator Agent is never trusted as its own
  validator — every output is routed to a Judge Agent that is
  architecturally distinct from it [R8, R13].
- **Position-content decoupling (amendment, see Amendment Log below).**
  Where a blueprint cell requires the correct answer to land at a specific,
  programmatically pre-assigned position for corpus-wide balance (R21),
  that position constraint must **never** be injected into the same
  generation call that establishes the content's factual/logical
  correctness. Doing so forces the Generator Agent to satisfy two
  competing objectives — positional compliance and content correctness —
  in a single call, and content correctness measurably degrades as a
  result. The Generator Agent must instead always write the correct
  answer into a fixed, position-agnostic slot (e.g., always `option_a`)
  under zero positional instruction; any R21 position balancing is then
  applied as a separate, purely mechanical relabeling step performed
  strictly *after* generation. This rule generalizes a concrete
  implementation finding — see the Amendment Log.
- **Generalization to all stacked constraints (v0.7, constitution.md
  R38).** Position-content coupling was one instance of a broader,
  independently-documented phenomenon: constraint order/co-presence in a
  single prompt measurably biases which constraints an LLM actually
  satisfies (Zeng et al., 2502.17204v1). This applies to every constraint
  this Generator Agent stacks in one call — Bloom-level verb, verbosity
  limit, mutual-exclusivity, factual correctness — not just position vs.
  content. No constraint above may be treated as satisfied on the strength
  of prompt position or ordering alone; §4.2's mechanical pre-filter and
  the Judge Agent's checks are the actual enforcement mechanism for each
  one, the prompt is only a request.

### 4.2 Synthetic Judge Agent

Two complementary judge mechanisms, applied in sequence — a cheap
statistical filter first, an LLM-based judge second, so the expensive judge
only sees pre-filtered candidates (this ordering is also where the Module 4
SLM/Pareto-efficiency work will attach):

1. **Learning-dynamics curator (statistical, non-LLM, first pass).**
   Following Seedat's CLLM curation mechanism: train a lightweight
   classifier on the small trusted seed set, run it over checkpoints,
   and compute per-generated-sample **average confidence** and
   **aleatoric uncertainty**. Discard samples with low confidence AND low
   uncertainty (i.e., confidently wrong — likely mislabeled/incoherent).
   This step is cheap, model-agnostic, and — per R20 — measurably reduces
   propagated bias (empirically cut equalized-odds violation from ~0.90 to
   ~0.08–0.13 in Seedat's controlled study). Proportion-discarded is itself
   a usable **hardness proxy**: datasets with high discard rates should be
   flagged for regeneration before proceeding, not silently accepted at a
   lower volume.
2. **LLM-based Critic/Judge Agent (second pass, on curated candidates
   only).** Following LM-AIG's pattern: a **Critic Agent** orchestrates
   parallel specialist reviewers (**Content**, **Linguistic**, **Bias**),
   each scoring against a defined rubric, synthesized by a **Meta
   Reviewer/Editor Agent**. Alternatively, T2F's stricter single-purpose
   **Validation Agent** pattern applies where the design goal is "tolerate
   upstream noise, guarantee final-output correctness only" rather than
   per-stage verification. Cross-provider judging (generator and judge from
   different model families/vendors, e.g. Sotelo Chico et al.'s GPT-4o-mini
   generator + Claude-3-Haiku judge) is **mandatory**, not merely preferred
   — see [R26]: same-model judging measurably inflates scores toward the
   generator's own output (+10% to +25% self-preference win rate, Zheng
   et al., 2023).

#### 4.2.1 Bias-Mitigated Judge Protocol (Module 3)

Every LLM-based Judge Agent call — Critic, specialist reviewer, or Meta
Reviewer — must be wrapped by this protocol, not left as a single raw call
[R21–R26]:

1. **Position-bias control**: run the judge call in both option/candidate
   orderings (bidirectional swap) and declare a **tie** on disagreement,
   never silently pick one direction. For MCQ-format items specifically,
   use majority-vote over ≥10 random option reorderings rather than a
   single swap (Pezeshkpour & Hruschka, NAACL 2024) — MCQ option-order
   sensitivity (13–85% accuracy swing) is larger than typical pairwise
   position bias. This control audits the *judge's* susceptibility to
   position bias; it presumes the *generator* already produces content
   whose correctness does not depend on which position it is assigned to
   — see §4.1's position-content decoupling requirement, which this
   protocol depends on but does not itself enforce.
2. **Verbosity/length-confound audit**: before deploying any judge model
   version, run it against a paired same-content-different-length probe
   set and record the measured bias **direction and magnitude for that
   specific model version** [R22, R25] — do not port a correction from a
   different judge model. Store the result alongside the model version ID.
3. **Reasoning wrapper**: require chain-of-thought self-explanation or
   reference-guided grading (generate a reference answer/solution first,
   grade against it) before the verdict is emitted — reference-guided
   grading cut math-item failure rate 70%→15% in Zheng et al. (2023) and is
   the preferred wrapper for any item with a computable correct answer
   (i.e., most MCQ items in this pipeline).
4. **Escalation, not debate, on disagreement**: if step 1's swap disagrees,
   or the Content/Linguistic/Bias reviewers disagree, route to a
   **Meta-Judge in "Conclude" mode** (synthesize a fresh verdict) rather
   than a multi-agent debate loop — Ma et al. (EMNLP 2025 Findings) found
   debate *amplifies* bias after the first round, while Conclude-mode
   meta-judging measurably reduces it.
5. **Leniency check against human baseline**: the Judge Agent's overall
   accept-rate per content cell is periodically compared against a human
   SME accept-rate on the same sample [R24]. A judge accept-rate
   persistently near 100% while human review (§2.8) rejects a materially
   higher fraction is itself a bias signal requiring judge recalibration,
   not evidence the items are simply good.
6. Optionally, where cost allows: route the judge's verdict through a
   dedicated **reasoning-based bias detector** (RBD) — a small model
   fine-tuned to inspect a verdict, flag suspected bias, and trigger
   judge self-correction (Yang et al., NeurIPS 2025) — before the verdict
   is finalized. This is a strengthening layer, not a replacement for
   steps 1–5.

### 4.3 Routing Logic

```
Generator Agent ──▶ Learning-Dynamics Curator ──▶ [discard-rate check]
                                │                        │
                          (curated set)              > threshold?
                                │                        │
                                ▼                       yes → flag dataset
                     LLM Critic/Judge Agent(s)            for regeneration,
                    (Content / Linguistic / Bias)         do not silently
                                │                          downsize
                                ▼
                     Meta Reviewer / Editor Agent
                                │
                        Accept / Regenerate
                                │
                                ▼
                  Human Review (§2.8) / Item Bank (§2.9)
```

- For synthetic (non-item) data specifically, the routing gains one more
  mandatory gate before Human Review: the **Privacy Audit** (R18) —
  k-anonymization / delta-presence / identifiability score, and the
  NewRowSynthesis-style duplication check — run on the curated set, not
  the raw generator output, so it measures what will actually ship.
- No dataset — item or synthetic-profile — reaches the bank/export step
  through a path that skips the Judge Agent stage, even under time
  pressure; this is a routing invariant, not a configurable option.
- Updated for Module 3: no item reaches the operational bank (§2.9) without
  also clearing the **IRT Calibration Layer** (§4.4) below — the Meta
  Reviewer/Editor Agent's "Accept" is necessary but not sufficient; §4.4 is
  a distinct, later gate that most items will not clear on first pass
  (calibration requires response data, so newly generated items enter the
  bank *provisionally*, tagged "uncalibrated," until §4.4 runs).

### 4.4 IRT Calibration Layer

Formalizes [R27]–[R30]: classical reliability (§2.9's original discrimination
statistics, Δ_model/Δ_bloom) is retained as a fast first-pass filter, but no
item is considered fully validated until it clears IRT-level calibration.

1. **Model choice**: default to a **1PL/Rasch** model for MCQ items scored
   as correct/incorrect (matches Liu, Bhandari & Pardos, BJET 2025's
   LLM-respondent calibration methodology directly); use a **Graded
   Response Model (GRM)** for polytomous outputs — i.e., rubric-scored
   open-response items from the Evaluate/Create path [R9] — following
   Angelelli et al. (2510.24739v3). Where multiple content dimensions are
   blueprint-relevant (§2.1's content × Bloom grid), a **Multidimensional
   IRT (MIRT)** extension is used instead of forcing a unidimensional fit
   (Taschetto & Fileto; Balepur et al., ACL 2025).
2. **Minimum parameters per item**: difficulty (b) and discrimination (a)
   at minimum; a 4-parameter extension (adding guessing c and feasibility
   d — Zhou et al., AAAI-26, PSN-IRT) is used where MCQ guessing is a
   material concern.
3. **Respondent pool**: real student response data is preferred but subject
   to [R17]; where unavailable, an **LLM-respondent ensemble** substitutes,
   mixed 1:1 with any available human respondents where possible [R30] —
   never LLM-only calibration presented as final. LLM-respondent difficulty
   estimates are reported with their correlation coefficient to any
   available human-calibrated reference, not as a standalone figure.
   **Concrete simulate-then-fit method (v0.7, R35–R36):** build a simulated
   classroom of N LLM "students" role-played at graded proficiency levels,
   collect correct/incorrect responses per item, and fit ability +
   difficulty jointly via Rasch/1PL (Acquaye et al., 2601.09953v1,
   §4.1) — never ask a model to state difficulty directly (R35). Respondent
   models must be selected empirically per content domain, not by
   solve-accuracy: their best correlations came from models with *lower*
   task-solve accuracy (Gemma-2/3, 72–83% solve accuracy) than from
   higher-solving models (Qwen2.5-32B/Llama-3.3-70B, 92–93%) (R36). Where
   full classroom simulation is too costly for the batch size, Kolesnikova
   et al.'s (2605.18562v1) pairwise-comparison-plus-Bradley-Terry method is
   the higher-accuracy/higher-cost alternative (mean ρ ≈ 0.73 vs. human/
   Rasch-calibrated difficulty, but ≈20× the judge-API calls of an absolute-
   judgment pass, §3.3/Table 8-9); their absolute-judgment-plus-soft-
   token-probability variant is the cheaper fallback (mean ρ ≈ 0.67 at
   roughly the cost of a single judge pass per item, §3.3/Table 3, 5).
   Whichever method is used, its content-domain validation range must be
   disclosed (R36) — none of these methods has been validated on this
   pipeline's own item pool yet.
4. **Item selection / bank pruning**: use **Fisher information** to
   prioritize which calibrated items are most informative to retain,
   following the ATLAS (2511.04689v3) and PSN-IRT (Zhou et al.) pattern —
   this is also the basis for future adaptive-testing delivery, not just
   bank pruning.
5. **Hard rejection gate**: an item with negative or
   statistically-indistinguishable-from-zero discrimination is
   automatically removed from the bank [R28] — logged with the same
   reason-code mechanism as §2.8's human-review rejections, not silently
   dropped.
6. **AI-vs-human parity check**: discrimination-index distributions for
   AI-generated items are compared against any human-authored items in the
   same content cell; a systematic AI-origin discrimination gap [R29]
   blocks that content cell from full deployment until closed, and is
   reported per-cell in the validation report (see `plan.md` Phase 6/9).
7. **Model-fit diagnostics**: report RMSEA (or an equivalent fit index) per
   calibrated item bank/subscale, following ATLAS's practice of surfacing
   fit diagnostics that prior LLM-item-bank work largely omitted.
8. **Co-monotonicity check**: for any content cell with both human- and
   AI-authored items, verify that difficulty/discrimination *rankings*
   agree across origin, not just that aggregate reliability statistics
   match [R27] — this is the check that classical reliability alone would
   have missed (Angelelli et al., 2510.24739v3).

---

## 5. Green AI / SLM-Optimized Routing (v0.4 — Module 4 pass)

Resolves the SLM-placement open item from Module 3 by giving the §4.3
routing graph a concrete difficulty-tiered, energy-aware execution model,
rather than leaving "which stage gets a small model" as a judgment call.

### 5.1 Model Tiering

Partition the available model pool into three capability tiers — **SLM**
(small, e.g. <3B), **MLM** (mid, e.g. 3–13B), **LLM** (frontier/cloud) —
following R2-Reasoner's (WWW '26) grouped-search pattern. Each subtask
(not each whole pipeline stage) is labeled **easy/medium/hard** via a
cheap confidence signal — the α-quantile of the generating model's own
token probability — and assigned to the matching tier by default:
easy→SLM, medium→MLM, hard→LLM. This reuses the confidence-scoring
infrastructure already required for §4.2's learning-dynamics curator,
rather than standing up a second difficulty-estimation system.

- **Escalation, not re-routing from scratch**: if the assigned tier fails
  (verified via the Judge Agent / Meta-Reviewer, §4.2), escalate within-tier
  to a stronger model in the same group first, then cross-tier, bounded to
  a small number of iterations — mirroring R2-Reasoner's grouped search
  (≤20 iterations in their setup) rather than an unbounded retry loop.
- **Task decomposition precedes routing**: apply this tiering at the
  *subtask* level (e.g., one distractor-plausibility check, one factual
  lookup, one Bloom-level template fill), not at the level of "generate
  this whole item." R2-Reasoner's central empirical finding — 84.46% API
  cost reduction and 71.14% energy reduction vs. the strongest baseline,
  with accuracy maintained or improved on 4 of 6 benchmarks — comes
  specifically from this finer granularity; coarse task-level SLM/LLM
  routing (i.e., "use a small model for easy items, a large one for hard
  items") captures much less of the available savings.

### 5.2 Stage-by-Stage SLM Anchor Points

- **Learning-dynamics curator (§4.2 step 1)**: already non-LLM and cheap;
  unaffected by this section.
- **Generator Agent first draft**: a strong SLM candidate — but model
  *size* is not a reliable proxy for efficiency. SLM-Bench (15 SLMs × 9
  tasks × 4 hardware configs) found Llama-3.2-1B achieved the *highest
  accuracy* among SLMs tested but performed *poorly* on computation and
  energy efficiency, while Phi-1.5B ranked best on combined
  computation+energy efficiency without leading on accuracy, and
  Mistral-7B offered the most balanced/versatile profile. Correctness does
  **not** correlate with computational/energy efficiency — the smallest
  model is not automatically the greenest one. Model selection per stage
  must be benchmarked empirically against the specific metric being
  optimized (§5.5), never assumed from parameter count.
- **Bias/verbosity-confound audit (§4.2.1 step 2)**: a strong SLM
  candidate — it is a narrow, repeated classification task, not open
  generation.
- **Judge Agent / Meta-Reviewer**: keep on the MLM/LLM tier by default.
  Kim et al. (BEA 2025) showed LLM-judge leniency bias is a live risk even
  at capable model sizes (o3-mini rated ~100% "Satisfied" where a human
  expert rejected 11–67%); downgrading this role to an SLM is only
  permitted after the periodic leniency check (§4.2.1 step 5) demonstrates
  the smaller judge does not regress accept-rate divergence from the human
  baseline.

### 5.3 Pareto-Optimal Configuration Selection

Adopt GREEN's (2505.01468v1) two-stage pattern to make "Pareto efficiency"
an operational procedure, not an aspiration:

1. **Predict** the (validation-performance, energy) trade-off for
   candidate model+configuration choices — via a lightweight learned
   predictor trained on a cross-domain knowledge base analogous to
   EcoTaskSet (1,767 logged training/inference runs across CV/NLP/RecSys
   in the source paper), or, at this pipeline's smaller scale, direct
   empirical benchmarking of the actual candidate models on representative
   AIG subtasks.
2. **Compute the Pareto frontier** of non-dominated (accuracy, energy)
   configurations, then apply preference-based ranking with explicit,
   documented weights (ωA for accuracy, ωE for energy/cost,
   ωA + ωE = 1) to select the deployed configuration per pipeline stage.
   Re-run this selection whenever a new model becomes available or an
   existing model's measured profile drifts — it is a recurring procedure,
   not a one-time architecture decision.

### 5.4 Efficiency Metrics for Reporting

Adopt the resource taxonomy from Bai et al.'s "Beyond Efficiency" survey
(2401.00625v4): report, at minimum, per pipeline release —
**computation** (FLOPs), **latency/throughput**, **energy** (kWh, tracked
via CodeCarbon/Zeus-style instrumentation, as used in both SLM-Bench and
GREEN), **financial cost** (a "$-per-parameter" or $-per-generated-item
normalized figure), and — wherever the pipeline is distributed — network
communication volume. Report these across the **whole lifecycle**
(generation + curation + judging + calibration), not training alone: for
a deployed AIG system, cumulative inference-time cost dominates one-time
training/setup cost, mirroring the survey's explicit caution against
training-only carbon/cost accounting (cf. BLOOM's full-lifecycle
reporting, cited therein).

### 5.5 Ties to §4.3 Routing Diagram

This section refines, not replaces, §4.3: every arrow in that diagram now
resolves to a tier-tagged model choice (§5.1–5.2), and every model-choice
decision is re-derivable from the Pareto procedure in §5.3, evaluated
against the metrics in §5.4. The routing invariant from §4.3 — no
item/dataset skips the Judge Agent stage — is unaffected; this section
only changes *which model* sits behind each stage, never whether a stage
runs.

### 5.6 Auditable Proxy Energy Reporting for Black-Box APIs (v0.7, Module 7, R37)

Where §5.1–5.5's model-tiering/Pareto infrastructure is not implemented
(as is currently the case — see `CONTEXT.md`, Module 4 status) and
generation runs entirely against a black-box cloud API (e.g., Groq) with
no GPU-level telemetry, §5.4's efficiency metrics cannot be measured
directly. This does not waive R34/R37's reporting requirement; it changes
what must be logged:

1. **Per-call proxy log (mandatory, always available from the API
   response):** input token count, output token count, model identifier/
   version string, and a boolean flag for extended/reasoning-mode
   generation. This is the minimum set Chung et al. (2601.22076v1, §5.5)
   identify as causally sufficient to explain most inference-energy
   variation even without direct measurement.
2. **Relative energy-proxy score, explicitly labeled uncalibrated:**
   `proxy_score = output_tokens` (optionally weighted by a published
   per-token reference constant, e.g. Wang et al.'s 2512.01644v1 ≈1.72
   J/token A100 figure, purely for order-of-magnitude intuition) —
   reported as a **relative** figure for comparing configurations within
   this project's own runs, never converted to an absolute joule/kWh claim
   without a hardware-specific calibration constant this project does not
   have (Vartziotis et al., 2607.26571v1, §3.5).
3. **Disclosure requirement:** any report of this proxy score must state,
   adjacent to the number, that it is a token-count-derived relative proxy
   without hardware calibration for the Groq/LPU inference backend
   actually used — satisfying R37's disclosure clause, not silently
   presenting it as a §5.4-compliant efficiency metric.

---

## 6. Grading / Scoring Delivery Engine (v0.5 — Module 5 pass)

Extends §2.10's AI-Mediation Governance Layer with a concrete downstream
architecture: what actually happens when a student response meets an
AIG-generated item and its associated rubric (§2.7). This is the natural
consumer of everything upstream — the validated rubric (R12–R16), the
calibrated item bank (§4.4) — and closes the loop from item generation to
student assessment, rather than leaving "grading" as an unspecified
downstream concern.

### 6.1 Architecture

Adapted from Rangan (ETFI 2026, "Efficacy of AI-Driven Evaluation of Exams
and Tests"), a multimodal pipeline validated on 2,091 real graded
responses:

```
Student Response ──▶ Input Acquisition ──▶ Interpretation Engine
  (text/handwriting/                          (parse response,
   multimodal)                                 handle non-text input)
                                                      │
                                                      ▼
                                     Rubric-Aligned Evaluation Engine
                                    (score against §2.7's validated rubric)
                                                      │
                              ┌───────────────────────┼───────────────────┐
                              ▼                                           ▼
                    Visual Annotation                        Mastery-Mapping /
                  (teacher-style feedback                    Adaptive Module
                   overlay, per R4's AI-use                 (feeds §4.4's Fisher-
                   disclosure where FIRM mode)                information-based
                                                              item selection)
```

### 6.2 Deployment Validation Bar [R33]

Before this engine is deployed on real student work, it must clear the
same disaggregated reporting bar as any human-vs-AI comparison in this
system: per-content-domain Cohen's κ against human graders (Rangan's study
demonstrates 0.863–1.000 is achievable across four subjects, not a single
pooled number), exact-match accuracy, and explicit disclosure of known
failure modes (e.g., degraded accuracy on messy handwriting or
unconventional diagrams) — an aggregate-only accuracy figure does not
satisfy this bar.

### 6.3 LangTest as the Judge/Evaluation Test Harness

Grounds the tool referenced but not yet sourced in `constitution.md`
R21–R26, spec §4.2.1, and `plan.md` Phase 9: **LangTest** (Nazir et al.,
*Software Impacts* 19, 2024) is a concrete, citable implementation of the
perturbation-based and bias/fairness testing this system already
specifies. It provides 60+ test types across robustness (casing, typos,
entity/demographic-name substitution), bias, fairness, and toxicity, plus
automated data-augmentation retraining when a test fails — operationalized
against the same "holistic evaluation" framing (Liang et al.'s HELM) this
Spec Kit's bias-audit sections already assume. This is the concrete
library `plan.md` Phase 9's DBPA-style perturbation testing and bias
hypothesis testing should be implemented on top of — no separate tool
needs to be built for that layer.

### 6.4 Statistical Reporting Standard [R34]

Every statistical comparison this system reports (model vs. model, prompt
vs. prompt, judge version vs. judge version) must include
variance-decomposed or resampling-based uncertainty, not a single point
estimate — following Sälevä, Ataman & Lignos (IJCNLP-APACL 2025), who show
between-domain/task variance frequently dominates and can swamp genuine
model differences on small evaluation sets. This applies to every
statistic already specified elsewhere in this document: Δ_model/Δ_bloom
(§2.9), IRT parameter estimates (§4.4), TSTR utility gaps
(`plan.md` Phase 8), and Cohen's κ (§6.2) alike.

### 6.5 Figure/Reporting Standard for Validation Outputs

Any IRT curve, discrimination plot, Cohen's-κ table, or pipeline diagram
produced by this system or its accompanying thesis chapters follows
Rougier, Droettboom & Bourne (PLOS Comp. Biol., 2014, "Ten Simple Rules
for Better Figures"): perceptually appropriate colormaps (sequential for
ordered values like difficulty, diverging for signed values like DIF,
never rainbow/jet), no truncated axes that exaggerate a difference,
self-contained captions, and minimal non-data "chartjunk." This is a
minimum bar, not a style preference — a misleading validation figure is a
reporting-integrity issue, not a cosmetic one, given R34's uncertainty
requirements above it.

### 6.6 This Spec Kit's Own Maintenance Process [R31, R32]

Per Piskala (2602.00180v1), this three-document set (`constitution.md`,
`spec.md`, `plan.md`) is maintained as a **spec-anchored** artifact:
specification and any eventual implementation are co-maintained, drift
must be caught and either rejected or logged as an amendment (see each
document's Amendment Log / module-tagged sections), and no passing
implementation is treated as proof the underlying rule was correct — see
R32's "false confidence" caution, which applies to this document's own
Amendment Log entries as much as to any code that eventually implements
them.

---

## 7. Synthetic / LLM-Generated Data Auditing Extensions (v0.7, Module 9 pass)

Extends the Judge Agent (§4.2) with two concretely implementable checks
that its current four mechanical checks (position, verbosity, mutual
exclusivity, Bloom-verb alignment) do not cover, per constitution.md
R39–R41, plus an explicit scope note on the dimension that remains
unimplemented.

### 7.1 Answer-Key Self-Consistency Check (R40)

For every candidate item that reaches the Judge Agent, resample the
blind-solve step (§4.2.1) K ≥ 3 times under independent sampling
(temperature/seed varied, option order re-shuffled per R21's existing
protocol) and compute the majority-vote agreement rate on the resolved
answer, following the `AccSC`/`Agree` pattern (Zhang et al., 2601.17717,
§3.2). An item whose blind-solve verdict is not stable across resamples is
not eligible for approval on a single-pass verdict alone — this is
additive to, not a replacement for, the existing R21 position-bias
resampling, and may reuse the same K blind-solve calls where the sampling
axes overlap (position reshuffle already resamples the judge call; this
check additionally requires varying the sampling seed/temperature so
disagreement is not solely attributable to option order).

### 7.2 Cross-Item Diversity Check (R41)

After `build_candidate_pool()`'s ranking (§4.3) but before final batch
delivery, compute pairwise embedding cosine similarity (`Self-CosSim`,
Zhang et al. §2.2) across the delivered batch's stems. Items forming a
near-duplicate cluster above a similarity threshold (to be calibrated
empirically against this pipeline's own delivered batch, per the pattern
already established in `spec.md`'s Open Questions for other thresholds)
are flagged for regeneration or replacement from the reserve pool — a
batch that is individually valid per item but redundant across items does
not satisfy R41.

### 7.3 Faithfulness/Attribution Check — Explicit Out-of-Scope Note (R39 disclosure)

The survey's faithfulness/attribution metrics (AIS, `Attr_auto`, `F1_AP`,
§2.3) require scoring generated content against a versioned source corpus
— the §2.4 RAG-refiner design this deliverable does not implement (per
`CONTEXT.md`: this deliverable rewrites already-existing dataset items
using EDA diagnosis as feedback, not generation grounded in a retrieved
source corpus). This dimension therefore remains **unimplemented**, and
per R39 must be disclosed as such wherever this pipeline's validation
coverage is reported — it is not covered by §7.1/§7.2, nor by any existing
§4.2 check.

---

## Open Questions / Future Work

This closes the five-module literature pass
(`literatura/mod_1_fundacao_pedagogica_pbl/` through
`literatura/mod_5_eng_spec_artifacts/`). Remaining open items, carried
forward as implementation-time or future-research questions rather than
"next module" deferrals:

- Concrete similarity-threshold values for the mutual-exclusivity linter
  (§2.7) and the leakage blocklist (§2.3), and concrete confidence/
  aleatoric-uncertainty thresholds for §4.2's curator — implementation
  scoping (see `plan.md`).
- Full IRT feasibility (§4.4) depends on minimum respondent pool size —
  Liu et al. (BJET, 2025) used N≥99 for Rasch validity with LLM
  respondents; PISA-scale human calibration uses N=250–750/item/country.
  This thesis's target pool size is not yet fixed — `plan.md` Phase 9
  scoping.
- Which specific bias-audit thresholds (§4.2.1 step 2/5) trigger automatic
  judge-model rollback vs. a warning — implementation scoping.
- Concrete (ωA, ωE) default weights for §5.3's Pareto ranking, and the
  specific SLM/MLM/LLM models to benchmark first — `plan.md` Phase 11
  scoping; two Module 4 sources (`19801_pub.pdf`, `2024.emnlp-main.1215.pdf`)
  remain unread and may contain additional efficiency-metric or
  SLM-comparison detail worth a follow-up pass before finalizing weights.
- Concrete variance-decomposition thresholds for §6.4 (what counts as
  "swamping" a model difference in this pipeline's specific domains) —
  implementation scoping, following Sälevä et al.'s methodology but
  requiring this system's own pilot data to calibrate.

---

## Amendment Log

- v0.6 (implementation-finding amendment, WAPLA 2026 competition run):
  during `WAPLA_AIG_Engine.py` implementation, a concrete instance of a
  position-content coupling failure mode was diagnosed — injecting the
  R21-balanced target letter into the Generator Agent's prompt *before*
  content existed caused the generator to reliably satisfy the positional
  instruction while intermittently sacrificing the factual/logical
  correctness of the option placed there (documented dataset cases:
  items 63, 392, 457; full diagnostic writeup in
  `relatorio/relatorio_tecnico.tex`, §"Descoberta Metodológica Central"). Per
  R31's no-silent-drift requirement, this is logged here as a backported
  amendment rather than left as undocumented implementation drift: §4.1 is
  amended to state position-content decoupling as a general architectural
  rule (not merely a one-off fix for this engine), and §4.2.1 step 1 is
  cross-referenced to clarify that its judge-side position-bias control
  presumes, but does not itself enforce, this generator-side decoupling.
  See `plan.md`'s and `CONTEXT.md`'s matching Amendment Log entries.
- v0.7 (second literature wave, Modules 6–9 — active implementation, not
  deferred literature): four architecture-level additions, matching
  `constitution.md`'s new R35–R41. §4.1 is extended to generalize the v0.6
  position-content decoupling amendment into a standing rule about all
  stacked Generator Agent constraints (R38). §4.4 step 3 gains a concrete
  simulate-then-fit respondent methodology plus a cheaper pairwise/
  absolute-judgment fallback (R35–R36). New §5.6 specifies an auditable
  token-count proxy for energy reporting where hardware instrumentation is
  unavailable (R37) — a partial, honestly-labeled answer to the Green AI
  reporting gap disclosed in `relatorio_tecnico.tex`. New §7 adds an
  answer-key self-consistency check and a cross-item diversity check to
  the Judge Agent (R40–R41), with an explicit scope note that the
  faithfulness/attribution dimension (R39) remains unimplemented because
  it requires a source corpus this deliverable's architecture does not
  have. See `constitution.md`'s and `plan.md`'s matching v0.7 entries.
- v0.8 (2026-08-18 cross-document consistency pass — gap disclosure, not
  new architecture): `constitution.md` gained R42–R45 (schema field
  ordering, judge-consistency resampling, constrained decoding, exact
  length control) across its v0.8–v0.12 entries, and `plan.md` gained a
  matching v0.8 entry the same day — but this document never received a
  corresponding architectural section, and has no R42–R45 mentions
  anywhere. Logged here as a known gap, per R31, rather than left as
  silent drift between the three documents. Current ground truth, per
  `constitution.md`'s own corrected entries (not this document, which
  still has no §-level home for any of these four rules): R42 (schema
  field order) was implemented backwards on first attempt — both
  Pydantic schemas had reasoning fields *after* the answer/verdict fields
  they justify, the opposite of the rule — and was only corrected same-day
  after a code audit (`constitution.md` v0.9); R43
  (`--judge-consistency-check`) and R44 (`guided_json` constrained
  decoding) were never implemented at all despite v0.8's original claim —
  no such CLI flag exists, and the `vllm_local` provider path uses generic
  `response_format: json_object`, never vLLM's schema-constrained decoding
  (`constitution.md`'s v0.8 entry, corrected note); R45 (Design D,
  countdown-marker length control) was implemented and calibrated, with
  partial, non-conclusive results logged in `CONTEXT.md` §8, not in this
  document. A real architectural write-up for R42–R45 (where in the
  Generator/Judge Agent pipeline each belongs, per this document's own
  §4 structure) remains future work.
- v0.9 (2026-08-19, R45 status correction): the v0.8 entry above
  understated R45 — "partial, non-conclusive results" was accurate as of
  that entry's own date, but Design D's calibration was completed the
  same day: 33.3%→50.0% approval on a paired 30-item sample (+16.7
  points), confirmed directionally at full 239-item production scale
  (length-extreme rate 73.2%, down from an 82.9% pre-Design-D baseline).
  The mechanism is real but unreliable per-attempt (77.3% marker
  malformation rate) — "conclusive" in the sense of a measured, repeated
  effect, not a fully solved problem. See `constitution.md`'s matching
  v0.13 entry for the full accounting; the architectural write-up gap
  noted in v0.8 above (no section-level home for R42–R45 in this
  document) remains open and is not addressed by this entry.
