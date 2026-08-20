# Plan — Implementation Steps

Status: DRAFT v0.9 — see Amendment Log for the version history; this
header previously read "v0.1" long after the document had moved past it
(fixed 2026-08-18 cross-document consistency pass).
Traceability: each phase implements specific components from `spec.md` (§
references) under the constraints of `constitution.md` (R references).
This plan will grow incrementally as further literature modules are
ingested; treat phase boundaries as provisional.

---

## Phase 0 — Grounding (this pass, complete)

- Ingested Module 1 literature (`literatura/mod_1_fundacao_pedagogica_pbl/`,
  10 sources: PBL pedagogy, Bloom's Taxonomy AIG papers, psychometric test-
  development handbooks, rubric-design literature).
- Established immutable rules (`constitution.md` R1–R16) and architectural
  base (`spec.md` §1–3).
- **Open item carried forward**: none of the four PBL/rubric-focused papers
  in this module addressed Bloom's Taxonomy directly — that pillar was
  sourced from the three AIG/psychometrics papers instead. Flag for the
  thesis literature-review chapter that Bloom's-Taxonomy-in-PBL is a gap in
  the current corpus and may need a targeted follow-up source.

## Phase 1 — Domain & Blueprint Definition (spec §2.1)

1. Select the pilot content domain(s) for the thesis (must be specific
   enough to build a two-way blueprint grid — content × Bloom level).
2. Define the content taxonomy for that domain (topics/subtopics), checked
   for mutual exclusivity per the same principle as R12/R13 applied at the
   content-classification level (Fleishman & Quaintance criteria, Handbook
   ch. 9).
3. Draft the blueprint grid with target item counts per cell, applying the
   2.5× item-bank sizing rule (spec §2.1).
4. Assign PBL integration mode (FIRM/RELAXED/FLEXIBLE) and rubric type
   (holistic/analytic/single-point/generic) per blueprint cell.
5. **Deliverable**: `blueprint.yaml` (or equivalent) — machine-readable
   spec consumed by every downstream generation stage.

## Phase 2 — Corpus & Extraction Layer (spec §2.3)

1. Assemble and version the domain corpus (textbooks, manuals, verified
   reference material) — must be citable/traceable, per the "no
   internet-sourced unverified text" constraint (Guia BNI-Enade, §3.4).
2. Build the practice/concept extraction step (5W schema: goal / context /
   action / timing / person).
3. Implement clarity-scoring and similarity-based deduplication filters on
   extracted practices.
4. Implement scenario construction (ill-structured problem wrapping a
   concept, R1) with the leakage blocklist (R5) as a hard gate, not a
   warning.
5. **Deliverable**: extraction + scenario-construction module with unit
   tests covering leakage-blocklist true/false positive rates.

## Phase 3 — Generation Layer (spec §2.2, §2.4)

1. Define the radicals/incidentals schema per item template (Gierl &
   Haladyna, 2012) — radicals locked/versioned, incidentals exposed for
   variant regeneration.
2. Implement the two-stage generator: LLM-1 baseline generation → RAG
   retrieval over the versioned corpus → LLM-2 refinement grounded in
   retrieved chunks.
3. Encode the per-Bloom-level template contract (constitution R10: verb
   bank + structural rule) as the only permitted generation prompt shape —
   no free-form "generate a level-X question" path should exist in code.
4. Add the explicit anti-hallucination instruction (no invented names,
   dates, statistics) to every generation prompt, per Burke (2025).
5. **Deliverable**: generation service producing raw + refined item pairs
   with full prompt/context provenance logged (needed for Phase 6 audit
   trail).

## Phase 4 — Validation Layer (spec §2.5, §2.6, §2.7)

1. Stand up the independent Bloom-level classifier, architecturally
   separate from the generator model(s) (R8). Establish a baseline
   accuracy target before trusting it as an auditor (Hwang et al. reached
   83.79%; treat this as a lower bound to beat, not a target to merely
   match).
2. Route MCQ generation only through classifier-confirmed Remember /
   Understand / Apply / Analyze items (R9); build the separate open-
   response path for Evaluate/Create.
3. Implement the IWF rule-based flaw detector (31-guideline / 19-flaw
   taxonomy) with the >1-flaw hard-reject rule (R16).
4. Implement the rubric generator with the mandatory mutual-exclusivity
   instruction (R12/R13) and the banned-vague-term list (R15).
5. Implement the mechanical overlap linter (pairwise similarity across
   rubric criteria/levels) — calibrate the similarity threshold empirically
   against a small hand-labeled set of "known overlapping" vs. "known
   exclusive" rubric pairs before deploying it as a gate.
6. **Deliverable**: validation pipeline that takes a raw item+rubric pair
   and returns accept / reject / route-to-human with a machine-readable
   reason code per rejection.

**Planned, not yet implemented (Module 10, second literature wave):**
distractor-plausibility checking. Byun & Choi (2504.13439, D-GEN) propose
an entropy-based plausibility metric over a judge model's per-option
probability distribution, and a discrimination-preservation validity
criterion (good distractors must not invert known item-difficulty
ranking) — either could extend the mechanical pre-filter or the Judge
Agent's checks, but need a reference model/difficulty signal this
pipeline doesn't currently have. Scarlatos, Feng, Smith, Woodhead & Lan
(2405.05144, overgenerate-and-rank) propose generating ~10 distractor
candidates and ranking them via a model trained on real per-option
selection-frequency data — validated only on math MCQs with real student
response data this pipeline's item pool does not have an equivalent of.
Both need more data/architecture planning than the same-day extensions in
v0.8 allowed; deferred by explicit user decision, not silently dropped.

## Phase 5 — Human-in-the-Loop Review (spec §2.8)

1. Build the review queue and decision UI (SME content review → editorial
   review → fairness/DIF-flagged review → accept/regenerate).
2. Implement the audit-trail store: prompt, retrieved context, raw output,
   refined output, every review decision and reason code (Burke, 2025) —
   required for accreditation/challengeability, build this before piloting
   with real reviewers, not after.
3. Recruit/assign reviewers with no vested interest in item retention for
   the fairness-review step specifically (Zieky protocol, Handbook ch. 16).
4. **Deliverable**: end-to-end trace from "item generated" to "item
   accepted into bank or rejected with logged reason" for at least one
   full blueprint cell, reviewable by a human end to end.

## Phase 6 — Pilot & Psychometric Validation (spec §2.9)

1. Deploy the Phase 5 output set to a pilot respondent pool (student cohort
   or model pool, depending on thesis stage/access).
2. Compute Δ_model (>0.5 threshold) and Δ_bloom (>0.2 threshold)
   discrimination statistics per item; auto-flag below-chance items for
   removal (R11 empirical test).
3. Run DIF analysis on any item flagged during fairness review (Phase 5).
4. If sample size allows, fit IRT calibration; otherwise document why not
   and record it as future work.
5. **Deliverable**: psychometric validation report per blueprint cell,
   feeding back into Phase 1 blueprint revisions and Phase 3/4 prompt/
   detector tuning (closed loop, not one-shot).

## Phase 7 — AI-Mediation Delivery Governance (spec §2.10)

1. Implement the FIRM/RELAXED/FLEXIBLE disclosure logic at the point items
   and rubrics are surfaced to students, not just at generation time.
2. Implement the AI-MAAS summative (AI drafts, academic moderates) and
   formative (bidirectional, continuous) delivery modes as separate code
   paths, since they have different moderation/latency requirements.
3. **Deliverable**: delivery layer demo showing the same underlying item
   bank served correctly under both governance modes.

## Phase 8 — Privacy-Preserving Synthetic Data & TSTR Pipeline (spec §4, R17–R20)

Runs in parallel with Phases 2–4, not after them — it produces the
synthetic student-profile/response data that Phase 6's pilot stage may need
as a stand-in wherever real respondent access under R17 is not yet cleared.

1. **Generator Agent (synthetic-data mode)**: implement the CLLM pattern —
   frozen LLM + in-context examples from a small, non-sensitive or
   already-synthetic seed set (R19). Do not fine-tune on any dataset that
   could contain real student identifiers, even de-identified ones.
2. **Learning-dynamics curator**: train a lightweight classifier on the
   trusted seed set, compute per-sample average confidence and aleatoric
   uncertainty across training checkpoints, discard confidently-wrong
   samples (spec §4.2). Log the discard-rate hardness proxy per generated
   batch; batches above a to-be-calibrated discard-rate threshold are
   regenerated, not shipped at reduced volume.
3. **Privacy audit gate**: before any synthetic dataset leaves the
   pipeline, compute (a) a duplication/leakage check against real source
   records (NewRowSynthesis-style: reject if any synthetic row is a
   near-exact copy of a real row) and (b) at least one re-identification
   metric (k-anonymization, delta-presence, or identifiability score).
   Hard-fail on either check, per R18/R20 — no manual override path.
4. **Train-on-Synthetic-Test-on-Real (TSTR) harness**: train the intended
   downstream model/classifier on the curated, privacy-audited synthetic
   set; evaluate exclusively on a held-out **real** data split; report the
   utility gap (AUCROC or task-appropriate metric) against a real-data-
   trained baseline. This is the harness Module 3's statistical
   hypothesis-testing layer (Phase 9, pending) will attach significance
   testing to — build the harness now so there is something to attach it
   to.
5. **Deliverable**: a synthetic dataset + audit report (fidelity metrics,
   privacy metrics, TSTR utility gap, discard-rate log) for at least one
   pilot content domain, usable as a documented substitute for real
   respondent data wherever Phase 6 needs one.

## Phase 9 — Statistical Hypothesis Testing Layer for TSTR + LangTest (spec §4, constitution R11/R21–R30)

Attaches formal significance testing to the Phase 8 TSTR harness and to any
"is item/model A different from B" claim elsewhere in the pipeline (Bloom
Δ_bloom, judge bias audits, AI-vs-human discrimination parity). Sequenced
after Phase 8 produces a harness to attach to, and after Phase 4/5 produce
judge verdicts and item-level statistics worth testing.

1. **TSTR significance testing**: replace the raw utility-gap number from
   Phase 8 step 4 with a proper hypothesis test — permutation testing
   (following Rauba, Wei & van der Schaar's **DBPA**, ICML 2025:
   Monte-Carlo-sample outputs, compute a discrepancy statistic — e.g.
   Jensen-Shannon divergence on prediction distributions or an accuracy
   delta — and derive a p-value under exchangeability via permutation)
   rather than an unqualified point estimate. Apply Bonferroni or
   Benjamini-Hochberg correction wherever multiple content cells/blueprint
   slices are tested simultaneously in the same report (this is the same
   multiple-hypothesis-testing discipline as Seedat's SMART Testing,
   PhD thesis ch. 5 — see item 3 below).
2. **Bias hypothesis testing**: for judge-bias audits (spec §4.2.1 step 2)
   and any social/stereotype-bias checks on generated content, use
   **Bayesian hypothesis testing** (Bayes factor BF10) alongside or instead
   of a plain frequentist test where the goal is to demonstrate *absence*
   of bias (H0), not just detect its presence — Si et al. (Scientific
   Reports, 2025) note the frequentist exact binomial test cannot
   affirmatively support H0, while a Bayes factor can (evidence-strength
   table: BF>100 extreme, 30–100 very strong, 10–30 strong, 3–10 moderate,
   1–3 anecdotal). This is the preferred framework for "prove this judge
   is not systematically biased," not just "we didn't detect bias."
3. **Context-aware / self-falsifying failure discovery**: implement
   Seedat's **SMART Testing** pattern (PhD thesis ch. 5) as the pipeline's
   general model-evaluation layer: (i) LLM-generated failure-mode
   hypotheses conditioned on dataset + domain context (not blind slice
   search), (ii) operationalize each hypothesis as a concrete data-slice
   predicate, (iii) **self-falsification** — test the slice against
   held-out data with a frequentist test, ranking hypotheses by p-value,
   (iv) auto-generate a model/item failure report. This directly replaces
   naive "search every possible subgroup" testing, which SMART's authors
   show inflates both false positives and false negatives via unmanaged
   multiple testing — a risk equally present in item-bank subgroup analysis
   (e.g., per-demographic item fairness) as in general ML testing.
4. **LangTest integration**: implement the above as concrete, repeatable
   test suites using **LangTest** (John Snow Labs) as the harness-execution
   layer — robustness tests (perturbation-based, aligned with DBPA's
   perturb-and-compare pattern above), bias/fairness tests (aligned with
   R20/item-level DIF checks), and accuracy tests (aligned with the TSTR
   utility comparison) run as part of CI whenever the generator, judge, or
   curation model versions change [R25's re-audit-on-upgrade requirement].
5. **Deliverable**: a test-suite report per pipeline release — TSTR
   significance (with correction), judge-bias Bayes factors, and a SMART-style
   failure-mode report — versioned against the specific generator/judge/
   curator model versions it was run against (ties into R25).

## Phase 10 — Bias-Audited Judge Agent + IRT Calibration (spec §4.2.1, §4.4; R21–R30)

1. Implement the §4.2.1 judge wrapper: bidirectional position-swap (MCQ:
   ≥10-reordering majority vote), per-judge-model verbosity-confound audit
   (store result + model version), and a reasoning wrapper (CoT or
   reference-guided grading) around every judge call. **Caution (see
   Amendment Log)**: do not inject the R21-balanced target position into
   the same Generator Agent call that establishes content correctness —
   this measurably coupled positional compliance with content correctness
   in the WAPLA 2026 implementation (dataset items 63/392/457, now a
   documented amendment to `spec.md` §4.1). Always write content to a
   fixed, position-agnostic slot first, then relabel positions
   mechanically as a separate step after generation.
2. Enforce cross-provider generator/judge separation at the routing layer
   (R26) — reject any pipeline configuration where generator and judge
   share a model family/checkpoint for items destined to skip full human
   review.
3. Build the periodic judge-vs-human leniency check (§4.2.1 step 5):
   compare judge accept-rate to human SME accept-rate (Phase 5) per content
   cell; alert on divergence rather than waiting for a scheduled audit.
4. Implement the IRT Calibration Layer (§4.4): 1PL/Rasch for MCQ,
   GRM for rubric-scored open-response, MIRT where the blueprint spans
   multiple content dimensions. Start with the LLM-respondent-ensemble
   substitute (mixed 1:1 with any available human respondents, R30) since
   real student data availability is gated by Phase 5's ethics/IRB
   sequencing note below.
5. Implement the hard-rejection gate for negative/zero-discrimination items
   (R28) and the AI-vs-human discrimination-parity check (R29), both logged
   with reason codes into the same audit trail as §2.8's human-review
   rejections.
6. Report Fisher-information-based item rankings (for future adaptive
   delivery) and RMSEA/fit diagnostics per calibrated content cell.
7. **Deliverable**: a calibrated item bank subset (with b/a parameters,
   Fisher information, fit diagnostics, and AI-vs-human parity report) for
   at least one blueprint cell, plus a versioned judge-bias-audit record
   for the judge model(s) used to reach it.

**Planned, not yet implemented (Module 12, second literature wave):**
human-vs-chatbot differential item functioning (DIF). Zeinfeld, Blonder,
Strugatski, Rap, Bar-Dov & Alexandron (2603.23682) run parallel
Mantel-Haenszel and logistic-regression DIF tests treating chatbots as a
focal group against human test-takers as reference, matched on per-item
rest-score ability — and found that gating the test itself behind an
item-total-correlation ≥0.20 floor (the same discrimination bar as R29)
eliminates false positives seen otherwise. This is a genuinely new
psychometric check, not an extension of an existing one, and needs a
respondent-response dataset (human + chatbot answers to the same items)
this pipeline does not yet build — deferred by explicit user decision,
not silently dropped. A related paper (Belzak, Naismith & Burstein,
"Ensuring Fairness of Human- and AI-Generated Test Items," Duolingo/AIED
2023) covers the same DIF concept from an operational-deployment
perspective, but is not yet available in `literatura/
mod_12_differential_item_functioning/` — that specific PDF is paywalled
and needs manual/institutional retrieval before it can inform this phase.

## Phase 11 — Green AI / SLM-Optimized Routing (spec §5)

Implements the difficulty-tiered, Pareto-aware model routing that
resolves the Module 3 open question of "which pipeline stage tolerates a
smaller model." Depends on Phases 3/4 (a working Generator/Judge routing
graph to retrofit) but its benchmarking/tooling can be prepared earlier.

1. **Model pool tiering**: stand up the SLM/MLM/LLM capability groups
   (spec §5.1) and the α-quantile token-probability difficulty estimator,
   reusing the confidence-scoring code already built for the Phase 3
   learning-dynamics curator rather than duplicating it.
2. **Subtask-level routing**: decompose Generator/Judge Agent calls into
   subtasks (following R2-Reasoner's Task Decomposer + Subtask Allocator
   pattern) before applying tier routing — task-level-only routing was
   shown to capture much less of the available cost/energy savings than
   subtask-level routing.
3. **Escalation policy**: implement bounded within-tier-then-cross-tier
   escalation on Judge-detected failure (§5.1), not unbounded retry.
4. **Empirical model benchmarking**: before assigning any model to a
   stage, benchmark it on representative pipeline subtasks across
   accuracy, latency, and energy (via CodeCarbon or equivalent
   instrumentation) — do not assign a model to a "cheap" tier based on
   parameter count alone; SLM-Bench found the highest-accuracy SLM tested
   was also among the least energy-efficient.
5. **Pareto configuration selection**: implement the GREEN-style two-stage
   selection (spec §5.3) — predict or directly benchmark the
   (accuracy, energy) trade-off per candidate configuration, compute the
   Pareto frontier, and rank by explicit (ωA, ωE) weights. Document the
   chosen weights per deployment context (e.g., pilot/research use may
   favor ωE higher than a production deployment with strict quality
   bars).
6. **Efficiency metrics integration**: extend the Phase 9 test-suite
   report (LangTest-based) to include FLOPs, latency/throughput, energy
   (kWh), and a normalized $-per-item cost figure per pipeline release,
   covering the full generation+curation+judging+calibration lifecycle,
   not training/setup alone.
7. **Deliverable**: a routing configuration (tier assignment + escalation
   policy per subtask type) and a Pareto-frontier report justifying the
   deployed model choices, versioned alongside the judge-bias-audit
   records from Phase 10 (both are model-version-dependent artifacts that
   must be re-derived on any model upgrade, per R25).

## Phase 12 — Grading Delivery Engine, Reporting Standards & Documentation Process (spec §6; R31–R34)

Final phase of this literature-grounded plan. Implements the downstream
consumer of the item/rubric bank (§6.1), closes the statistical- and
figure-reporting standards (§6.4–6.5) that apply retroactively to every
earlier phase's validation reports, and formalizes how this Spec Kit
itself is maintained going forward.

1. **Grading Delivery Engine** (spec §6.1): implement Input Acquisition →
   Interpretation Engine → Rubric-Aligned Evaluation Engine → Visual
   Annotation + Mastery-Mapping, consuming the validated rubrics (Phase 1–2
   outputs, R12–R16) and feeding the mastery-mapping output into Phase 10's
   Fisher-information-based item selection (§4.4 step 4) for adaptive
   delivery.
2. **Deployment validation gate** (R33): before this engine touches real
   student work, produce the per-content-domain Cohen's κ + exact-match +
   failure-mode-disclosure report required by R33 — reuse the Phase 5/10
   human-review infrastructure to source the human-grader comparison set.
3. **LangTest integration** (concrete, not placeholder): implement Phase
   9's perturbation/bias/fairness test suites directly on **LangTest**
   (Nazir et al., *Software Impacts*, 2024) rather than a bespoke harness —
   its 60+ test types (robustness, bias, fairness, toxicity) and
   automated-augmentation-retraining loop cover the DBPA-style and
   bias-hypothesis-testing requirements already specified in Phase 9.
4. **Variance-decomposed statistical reporting** (R34): retrofit every
   prior phase's point-estimate statistics — Δ_model/Δ_bloom (Phase 6),
   IRT parameters (Phase 10), TSTR utility gaps (Phase 8), Pareto
   configuration comparisons (Phase 11) — with resampling-based or
   variance-decomposed uncertainty (bootstrap + multi-seed, following
   Sälevä, Ataman & Lignos, IJCNLP-APACL 2025), rather than treating this
   as a one-time addition; each phase's report template gets an
   uncertainty-column requirement.
5. **Figure/reporting standard** (R34/§6.5): apply the "Ten Simple Rules
   for Better Figures" checklist (Rougier, Droettboom & Bourne, PLOS Comp.
   Biol., 2014) to every validation figure produced across Phases 6–11
   before it enters the thesis or system dashboard — perceptually
   appropriate colormaps, no truncated/misleading axes, self-contained
   captions.
6. **Formalize this Spec Kit's maintenance process** (R31/R32): adopt the
   Specify → Plan → Implement → Validate cycle explicitly for future
   amendments to `constitution.md`/`spec.md`/`plan.md` — each new rule or
   architecture change gets a logged Amendment Log entry (already the de
   facto practice across Modules 1–5) with an explicit rationale, and each
   passing implementation is treated as conformance evidence only, never
   as proof the underlying rule was correct (R32's "false confidence"
   caution) — schedule periodic substantive re-review of R1–R34, not just
   enforcement checks.
7. **Deliverable**: a working grading engine with a published κ/accuracy/
   failure-mode report for at least one content domain; a retrofitted
   uncertainty report for every earlier phase's headline statistic; and a
   documented amendment process for this Spec Kit itself.

---

## Sequencing Notes

- Phases 1–4 can be developed against a synthetic/small corpus in parallel
  with literature ingestion for subsequent modules; Phases 5–7 require real
  reviewers/respondents and should be sequenced after the thesis's IRB/
  ethics or institutional approval process (if applicable) is confirmed —
  **check this before Phase 5 begins**. Phase 8 (synthetic data) is exactly
  what makes early Phase 1–4 development possible *without* waiting on that
  approval, and should be started early, not treated as a late add-on.
- Phase 9 depends on Phase 8 (needs the TSTR harness) and benefits from
  Phase 4/5 output (judge verdicts, item stats) but its statistical-testing
  *infrastructure* (permutation test runner, Bayes-factor calculator,
  LangTest suite scaffolding) can be built in parallel with Phases 1–4.
- Phase 10's IRT calibration (step 4) is gated the same way as Phase 6:
  real-respondent data requires the same ethics/IRB clearance noted above;
  the LLM-respondent-ensemble substitute (R30) is what allows Phase 10 to
  start before that clearance lands, mirroring Phase 8's role for Phase 6.
- Phase 11 is orthogonal to the ethics/IRB gating above — it can run in
  full parallel with Phases 1–10 once a routable Generator/Judge graph
  exists (post-Phase 3/4), since it optimizes *which model* answers a
  request, not *whether* real respondent data is involved.
- Every phase deliverable should be traceable back to the constitution
  rule(s) it satisfies, to keep the thesis's methodology chapter and the
  codebase in sync as more literature modules are added.
- **Gap carried from Module 4**: two sources
  (`literatura/mod_4_infra_green_ai/19801_pub.pdf` and
  `2024.emnlp-main.1215.pdf`) were not read in this pass; if Phase 11's
  benchmarking step surfaces a need for additional efficiency-metric or
  SLM-comparison grounding, revisit these before finalizing default
  (ωA, ωE) weights.
- Phase 12's items 4–5 (retrofitting variance-decomposition and figure
  standards onto earlier phases' reports) should run as a standing
  practice from the point Phase 12 starts, not as a single one-time
  cleanup pass — every subsequent report from Phases 6–11 should already
  comply, and Phase 12 exists to establish the standard, not to be revisited
  once and forgotten.
- This closes the five-module literature-grounded plan
  (`literatura/mod_1_fundacao_pedagogica_pbl/` through
  `literatura/mod_5_eng_spec_artifacts/`), covering Phases 0–12. Two
  Module 4 sources remain unread (noted above); everything else in the
  five assigned literature folders has been ingested into `constitution.md`
  (R1–R34), `spec.md` (§1–6), and this plan.

---

## Amendment Log

- v0.6 (implementation-finding amendment, WAPLA 2026 competition run):
  backports the position-content coupling finding diagnosed during
  `WAPLA_AIG_Engine.py` implementation (full writeup in
  `relatorio/relatorio_tecnico.tex`, §"Descoberta Metodológica Central";
  matching amendment in `spec.md` §4.1/§4.2.1 and `CONTEXT.md`). Phase 10
  item 1 above is amended with an explicit caution against injecting an
  R21-balanced target position into the same generation call that
  establishes content correctness — a failure mode that is generalizable
  beyond this one engine and should be treated as a standing implementation
  constraint for any future Generator Agent built against this plan, not
  just a fact about the one run where it was found.
- v0.7 (second literature wave, Modules 6–9): four new literature modules
  (`literatura/mod_6_irt_llm_respondents/` through
  `literatura/mod_9_synthetic_data_auditing/`) were ingested and are being
  implemented now, not deferred as future work — matching new
  `constitution.md` R35–R41 and new `spec.md` §4.1 extension, §4.4 step 3
  extension, §5.6, and §7. Concretely: Phase 10 (IRT Calibration, step 4)
  should be implemented against `spec.md` §4.4's new simulate-then-fit
  respondent methodology (R35–R36) rather than a generic "LLM-respondent
  ensemble" placeholder; Phase 11 (Green AI, currently unimplemented per
  its own phase note) gains a lower-cost, immediately implementable
  precursor in `spec.md` §5.6's auditable proxy-energy logging (R37), which
  does not require the full SLM/MLM/LLM tiering infrastructure Phase 11
  otherwise depends on; and Phase 4/10's validation layer gains two new
  Judge Agent checks from `spec.md` §7 (R40 self-consistency, R41
  diversity), with R39's faithfulness/attribution dimension logged as
  explicitly out of scope pending a source-corpus architecture this plan
  does not yet build. See `constitution.md`'s and `CONTEXT.md`'s matching
  v0.7 entries.
- v0.8 (second literature wave, Tier-1 fixes implemented): unlike v0.7,
  three findings from `literatura/mod_11_judge_reliability_uncertainty/`
  and `literatura/mod_13_structured_output_reliability/` were implemented
  the same day in `WAPLA_AIG_Engine.py`, matching new `constitution.md`
  R42–R44 — schema field reordering, a `--judge-consistency-check` flag
  (off by default), and a new `vllm_local/` provider path with
  `guided_json`. Phase 4 and Phase 10 above each gained a "Planned, not
  yet implemented" note for the two findings explicitly deferred by user
  decision: Module 10's distractor-plausibility checks (D-GEN entropy
  metric, overgenerate-and-rank — Phase 4) and Module 12's human-vs-
  chatbot differential item functioning (Phase 10), both logged here per
  R31 rather than silently dropped. See `constitution.md`'s matching v0.8
  entry.
- v0.9 (2026-08-18 cross-document consistency pass — correction, per R31):
  the v0.8 entry above claims R42–R44 "were implemented the same day."
  A code audit the same day found this was only true for R42, and only
  after a further same-day correction — the original R42 implementation
  had both Pydantic schemas' reasoning fields declared *after* the
  answer/verdict fields they justify, the exact opposite of the rule,
  fixed only once the audit caught it (`constitution.md` v0.9). R43
  (`--judge-consistency-check`) and R44 (`guided_json` constrained
  decoding) were **never implemented at all** despite this entry's
  original claim: no such CLI flag exists anywhere in `parse_args()`, and
  the `vllm_local` provider path sends generic
  `response_format: {"type": "json_object"}`, never vLLM's
  schema-constrained decoding. This entry is not deleted or silently
  edited — per R31/R32, a wrong claim gets a correcting entry, not a
  quiet rewrite. See `constitution.md`'s v0.9–v0.12 entries for the full
  audit trail, and `spec.md`'s matching v0.8 entry (which discloses the
  same gap from the architecture-document side).
- v0.10 (2026-08-19, R45 status correction): unlike R43/R44, R45 (Design D,
  countdown-marker exact length control) genuinely was implemented and
  calibrated — 33.3%→50.0% approval on a paired 30-item sample, confirmed
  directionally at full 239-item production scale (length-extreme rate
  73.2%, down from 82.9% pre-Design-D), with a 77.3% marker-malformation
  rate disclosing that the mechanism is real but unreliable per-attempt.
  See `constitution.md`'s matching v0.13 entry and `spec.md`'s matching
  v0.9 entry for the full accounting.
