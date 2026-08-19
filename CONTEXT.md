# CONTEXT.md — WAPLA 2026 Project Reference

**Purpose of this file**: single source of truth for any developer (human or
AI) picking up this project cold. Read this before touching
`constitution.md`, `spec.md`, `plan.md`, or the implementation files.

**Methodology**: this project follows **Spec-Driven Development (SDD)**. The
Spec Kit (`constitution.md` → `spec.md` → `plan.md`) is maintained as a
**spec-anchored** artifact set (R31/R32): specification and implementation
are co-maintained, and any code that diverges from a documented rule must
either be rejected or trigger a logged amendment — never silent drift.
Read those three files in that order before reading any code.

---

## Current State as of 2026-08-18

**The rest of §1–7 below predates this note and is stale in places** — it
was written when the pipeline had only been dry-run, before git existed,
and before the technical report was drafted. Rather than rewrite §1–7
tonight, this note corrects the specific false claims and points to where
the real current state actually lives:

- **The real (non-dry-run) pipeline has been run**, repeatedly, against
  local `vllm_local` models (`phi-4` generator, `gpt-oss-20b` judge) and
  earlier against hosted providers (Groq, Anthropic) — not dry-run-only as
  §7 below still claims. Final graded result: **100/100 approved**
  (`output/entregavel_2_100_questoes_design_d_full.csv`), achieved across
  two passes (93/239 full-pool + a targeted 10/40 second pass over the
  hardest remaining backfilled items). Full numbers in
  `relatorio/relatorio_tecnico.tex` §"Métricas da Execução Completa."
- **The technical report is written and final** —
  `relatorio/relatorio_tecnico.tex`, not "not started" as §1's table below
  still says.
- **Git is initialized** (`.git/` exists) — not "no `.git` directory" as
  §7 below still claims.
- **API keys are configured** (`.env`: `GROQ_API_KEY`, `GEMINI_API_KEY`,
  `ANTHROPIC_API_KEY`, `HF_TOKEN`) — not "no API keys configured" as §7
  below still claims. Local-model runs don't need any of these; earlier
  same-project runs against Groq/Anthropic did use them.
- **Post-submission exploratory work** (separate from the graded
  deliverable, never touching its output files) is tracked in §8 below,
  including a full R1–R11 implementation-rigor audit and a first
  post-submission experiment (Round 1, R10's structural half — null
  result on approval rate, see §8 for the honest accounting).

## 1. Project Overview

**Competition**: WAPLA 2026 — *Quality of AI-Generated Educational
Questions*.

**Core task**: given a dataset of AI-generated multiple-choice educational
items that were **rejected** for quality reasons, diagnose *why* they were
rejected, then build a pipeline that repairs a batch of them into
structurally valid items — under a fixed, immutable rule set derived from
a 5-module literature review (PBL pedagogy, Bloom's Taxonomy, LLM-as-judge
bias, IRT psychometrics, engineering rigor).

**Deliverables**:

| # | Deliverable | Status | Artifact |
|---|---|---|---|
| 1 | Reproducible EDA notebook diagnosing the 239 rejected items | ✅ Complete | [`WAPLA_EDA.ipynb`](WAPLA_EDA.ipynb) |
| 2 | 100 generated/repaired questions (competition CSV schema) | ✅ Complete — 100/100 approved, real (non-dry-run) run | [`output/entregavel_2_100_questoes_design_d_full.csv`](output/entregavel_2_100_questoes_design_d_full.csv) |
| 3 | Technical report | ✅ Complete | [`relatorio/relatorio_tecnico.tex`](relatorio/relatorio_tecnico.tex) |

**Evaluation phases/criteria** (as operationalized by this project's own
Spec Kit, since the competition brief itself is not stored as a separate
file in this repo — `constitution.md`/`spec.md` *are* the operational
translation of the brief):
- Structural validity of the 100 delivered items (no position bias, no
  verbosity bias, Bloom-level/verb alignment, mutual exclusivity of
  options) — mechanically checked, see §5 below.
- Independent LLM-judge approval with position-bias and verbosity-bias
  controls (R21, R22, R23).
- Cross-provider generator/judge separation (R26) — self-preference bias
  control.
- Full audit trail (prompt → generation → judge verdict) for every item,
  approved or not (`output/aig_audit_trail.jsonl`).

---

## 2. Current Project Structure

```
meu_projeto_mestrado/
├── constitution.md          # Immutable rules R1-R34 (the "why")
├── spec.md                  # Architecture §1-6 (the "what")
├── plan.md                  # Phased implementation plan 0-12 (the "how/when")
├── CONTEXT.md                # THIS FILE
├── mempalace.yaml            # Memory-room config (literatura/ indexing tool)
├── WAPLA_EDA.ipynb            # Deliverable 1: structural diagnosis notebook
├── WAPLA_AIG_Engine.py        # Deliverable 2: Generator<->Judge repair engine
├── literatura/                # Source PDFs, organized by module (see §3)
│   ├── mod_1_fundacao_pedagogica_pbl/     (10 PDFs)
│   ├── mod_2_motor_aig_sintetico/         (10 PDFs)
│   ├── mod_3_juiz_estatistica_tri/        (19 PDFs)
│   ├── mod_4_infra_green_ai/              (7 PDFs)
│   └── mod_5_eng_spec_artifacts/          (5 PDFs)
└── output/                    # All generated artifacts (git-trackable, not source)
    ├── 01_overview_distributions.png
    ├── 02_verbosity_bias.png
    ├── 02b_verbosity_bias_by_question_type.png
    ├── 03_position_bias.png
    ├── 04_bloom_confusion_matrix.png
    ├── 05_r9_format_violation.png
    ├── 06_composite_flaw_count.png
    ├── eda_summary.txt              # Text summary of EDA findings
    ├── flaw_summary.csv              # 239 rows, per-item flaw diagnosis (EDA output, engine input)
    ├── entregavel_2_100_questoes.csv  # Deliverable 2 CSV (currently from a --dry-run)
    ├── aig_audit_trail.jsonl          # Full per-attempt audit log (397 entries from the dry run)
    ├── aig_engine.log                 # Run log
    └── judge_bias_audit_log.json      # (only written on a real, non-dry-run execution)
```

**Not present yet**: `.git` (no version control initialized), no
`requirements.txt`/`pyproject.toml` (dependencies are implicit — see §4),
no `README.md`, no technical report draft.

---

## 3. Module Mapping

The literature review is organized into 5 modules under `literatura/`, each
of which fed a specific, additive pass over `constitution.md`, `spec.md`,
and `plan.md`. **This structure is the backbone of the whole Spec Kit** —
every immutable rule (R*) traces back to one of these five folders.

### Module 1 — `mod_1_fundacao_pedagogica_pbl/` (Fundação Pedagógica / PBL)
- **Purpose**: ground the system in Problem-Based Learning pedagogy,
  Bloom's Taxonomy alignment, and rubric-design theory.
- **Sources (10)**: PBL pedagogy papers, Bloom's-Taxonomy AIG papers,
  psychometric test-development handbooks (Handbook of Test Development,
  Guia BNI-Enade), rubric-design literature.
- **Rules produced**: R1–R16 (`constitution.md` §I–III).
- **Spec sections**: `spec.md` §1–3 (system overview, blueprint layer,
  radicals/incidentals, extraction, item-writing-flaw detector, rubric
  generator, human review, item bank, validity checklist).
- **Plan phases**: Phase 1 (Domain & Blueprint), Phase 2 (Corpus &
  Extraction), Phase 3 (Generation), Phase 4 (Validation), Phase 5 (HITL
  Review) — **not implemented** (see §4 below); the competition
  deliverable only needed a subset of this architecture.
- **Status**: literature ingestion complete (v0.1 amendment). Known gap:
  none of the 4 PBL/rubric papers addressed Bloom's Taxonomy directly —
  flagged as a literature-review gap in `plan.md` Phase 0.

### Module 2 — `mod_2_motor_aig_sintetico/` (Motor AIG Sintético)
- **Purpose**: privacy-preserving synthetic data generation for the AIG
  engine (LGPD/GDPR compliance), multi-agent Generator↔Judge routing
  skeleton.
- **Sources (10)**: synthetic-data privacy papers (Seedat's CLLM thesis,
  Liu et al. BJET), multi-agent AIG architecture papers (LM-AIG, Abdullah
  et al. multi-LLM RAG pipeline).
- **Rules produced**: R17–R20 (`constitution.md` §IV, LGPD/Privacy).
- **Spec sections**: `spec.md` §4 (Multi-Agent Generator↔Judge
  Architecture), §4.1 (Generator Agent), §4.2 (Synthetic Judge Agent —
  learning-dynamics curator + LLM critic), §4.3 (routing logic).
- **Plan phases**: Phase 8 (Privacy-Preserving Synthetic Data & TSTR) —
  **not implemented**; not in scope for the competition's 100-item repair
  deliverable (which uses real, already-public rejected items, not
  synthetic student data).
- **Status**: complete (v0.2 amendment). Noted gap: no formal
  differential-privacy mechanism specific to synthetic *item* text (as
  opposed to tabular data) — candidate for deeper treatment if thesis
  scope requires it.

### Module 3 — `mod_3_juiz_estatistica_tri/` (Juiz e Estatística / TRI = IRT)
- **Purpose**: LLM-as-judge bias mitigation (position, verbosity,
  self-preference) and Item Response Theory calibration.
- **Sources (19)** — the largest module: judge-bias papers (Zheng et al.
  MT-Bench, Pezeshkpour & Hruschka, Bavaresco et al. JUDGE-BENCH, Kim et
  al. STAIR-AIG), IRT/psychometrics papers (Angelelli et al.,
  Balepur et al., Zhou et al. PSN-IRT, Liu/Bhandari/Pardos BJET).
- **Rules produced**: R21–R30 (`constitution.md` §V–VI).
- **Spec sections**: `spec.md` §4.2.1 (Bias-Mitigated Judge Protocol —
  **this is the section `WAPLA_AIG_Engine.py` implements most directly**),
  §4.4 (IRT Calibration Layer).
- **Plan phases**: Phase 9 (Statistical Hypothesis Testing / LangTest),
  Phase 10 (Bias-Audited Judge Agent + IRT Calibration).
- **Status**: complete (v0.3 amendment). **This is the module with the
  most direct code implementation** — the Judge Agent's blind-solve
  protocol, verbosity-confound audit, and R26 cross-provider enforcement
  in `WAPLA_AIG_Engine.py` all trace to this module.

### Module 4 — `mod_4_infra_green_ai/` (Infra / Green AI)
- **Purpose**: energy/cost-aware model routing (SLM vs. MLM vs. LLM
  tiering), Pareto-efficient configuration selection.
- **Sources (7)**: R2-Reasoner (grouped-search routing), SLM-Bench,
  GREEN (Pareto selection), "Beyond Efficiency" survey.
- **Rules produced**: **none** — findings were architectural, not
  rule-shaped, and were written directly into `spec.md` §5 instead.
- **Spec sections**: `spec.md` §5 (Green AI / SLM-Optimized Routing).
- **Plan phases**: Phase 11 (Green AI / SLM-Optimized Routing) — **not
  implemented**; out of scope for the competition deliverable (no model
  tiering infrastructure exists yet; the engine currently supports
  exactly two model slots, generator and judge, chosen via CLI flags).
- **Status**: v0.4 amendment. **⚠️ Two sources unread**:
  `19801_pub.pdf` and `2024.emnlp-main.1215.pdf` — revisit before
  finalizing any Pareto weight defaults if this module is extended.

### Module 5 — `mod_5_eng_spec_artifacts/` (Engenharia / Spec Artifacts)
- **Purpose**: engineering and reporting rigor for the Spec Kit itself,
  and for a downstream grading-delivery engine.
- **Sources (5)**: Piskala's spec-driven-development rigor-levels paper,
  Rangan's AI-grading efficacy study, "Ten Simple Rules for Better
  Figures," LangTest paper, IJCNLP-APACL variance-decomposition paper.
- **Rules produced**: R31–R34 (`constitution.md` §VII).
- **Spec sections**: `spec.md` §6 (Grading/Scoring Delivery Engine, LangTest
  test harness, statistical reporting standard, figure standard, this Spec
  Kit's own maintenance process).
- **Plan phases**: Phase 12 (Grading Delivery Engine, Reporting Standards
  & Documentation Process) — **not implemented**; out of scope for the
  competition deliverable (there is no downstream grading engine yet).
- **Status**: complete, v0.5 (final) amendment — closes the 5-module
  literature pass.

---

## 4. Implementation Progress

### ✅ Implemented

**`WAPLA_EDA.ipynb`** (35 cells, Deliverable 1 — complete and run):
- Loads `aiboxlab/ai-generated-questions-quality` from Hugging Face
  (239 rejected items, single split named `"data"`, **not** `"train"` —
  the loader is defensive against this).
- §1.1 Data quality overview: null-count audit, case-duplication check on
  `discipline` (found real issue — see §6 below).
- §2 Verbosity bias analysis: bootstrap CI on (correct − mean distractor)
  option length, per-question-type breakdown.
- §3 Position bias analysis: chi-square goodness-of-fit of `correct_option`
  vs. uniform distribution.
- §4 Bloom's Taxonomy verb-level mismatch: dual extraction path (spaCy
  `pt_core_news_sm` primary, regex-stem-matching fallback), §4.1 extends
  extraction from stem-only to full cognitive text (stem + assertions/
  statements) — important fix, since boilerplate stems in
  Asserção-Razão/Múltipla-Escolha-Complexa items made stem-only extraction
  systematically undercount.
- §5 Composite structural flaw score (`structural_flaw_count`, 0–4) — no
  model involved, pure rule-based flagging.
- §6 Summary written to `output/eda_summary.txt`.
- **Outputs**: 7 PNG figures, `eda_summary.txt`, and — critically —
  `flaw_summary.csv` (239 rows), which is the **only input contract**
  `WAPLA_AIG_Engine.py` depends on.

**`WAPLA_AIG_Engine.py`** (1413 lines, Deliverable 2 — pipeline built, one
dry run executed):
- Implements `spec.md` §4 (Generator↔Judge architecture) and §4.2.1
  (Bias-Mitigated Judge Protocol), with **explicitly documented
  deliberate deviations** from the literal spec text (see the module
  docstring, lines 1–32):
  - The trained learning-dynamics classifier (§4.2 step 1) is
    reimplemented as a **deterministic, rule-based mechanical pre-filter**
    — the deliverable's brief forbids training any model.
  - The 10-reordering majority-vote position check (§4.2.1 step 1) is a
    **single-shuffle blind-solve** by default (cost reasons); the full
    10-reordering version is available via `--rigorous-position-check`.
  - The human-SME leniency check (§4.2.1 step 5) is **not performed** —
    there is no human reviewer in this automated script. Logged as an
    explicit unresolved gap in the run summary (`print_run_summary`),
    not silently skipped.
- **Mid-implementation amendment (2026-08-12): position–content
  coupling.** An early version of the engine injected the R21-required
  `TARGET_LETTER` into the Generator Agent's prompt *before* the item's
  content existed, forcing the generator to satisfy positional and
  content correctness as competing objectives within a single call.
  Manual inspection of judge blind-solve disagreements on items 63,
  392, and 457 showed the generator reliably satisfied the positional
  instruction but not always the content's factual correctness — a
  prompt-design flaw, not a capability limit of the generator model.
  **Fixed** by fully decoupling the two: the generator now always
  writes the correct answer as `option_a`, with no positional
  instruction competing with content generation, and
  `apply_position_shuffle()` mechanically repositions the
  already-correct content to the corpus-balanced `TARGET_LETTER` only
  *after* generation — a pure string swap, not a generation-time
  constraint. Logged here per R31 (no silent drift): this finding was
  previously documented only in `relatorio/relatorio_tecnico.tex` §3
  ("Descoberta Metodológica Central: Acoplamento entre Posição e
  Conteúdo"), never backported into this Spec Kit. Cross-referenced in
  `spec.md` §4.2.1 and `plan.md` Phase 10; see this file's Amendment
  Log (v1.1) below.
- **Key components** (§ numbers refer to in-file section comments):
  - §3–4: Bloom verb bank (PT), shared verbatim with the notebook for
    narrative consistency; `determine_target_level()` demotes
    R9-illegal Avaliar/Criar items to Analisar (since the competition
    schema mandates single-best-answer MCQ).
  - §5: `build_candidate_pool()` — merges `flaw_summary.csv` with the
    original HF dataset, ranks by `structural_flaw_count` descending.
  - §6: Pydantic schemas `GeneratedItem`, `JudgeVerdict` — no free-text
    parsing of judge verdicts trusted (R8/R13).
  - §7: Mechanical pre-filter — `check_position` (R21), `check_verbosity`
    (R16/R22), `check_mutual_exclusivity` (R12/R13, Jaccard similarity),
    `check_bloom_verb` (R10).
  - §8: LLM client abstraction — `litellm` preferred, `openai` SDK
    fallback, deterministic offline mock for `--dry-run`.
  - §9: Prompt builders (Portuguese) — `GENERATOR_SYSTEM_PROMPT`,
    `JUDGE_SYSTEM_PROMPT`.
  - §11–12: `generator_agent()`, `judge_agent()` — judge does a **blind
    solve** on shuffled option labels before ever seeing the claimed
    correct answer (position-bias decorrelation, R21/R23).
  - §13: `run_verbosity_confound_audit()` — one-time, judge-model-version-
    tagged calibration probe (R22/R25), run once per batch, not per item.
  - §14: `process_item()` — per-item orchestration: Generator →
    mechanical pre-filter → LLM Judge → retry (feeding back rejection
    reasons) up to `--max-retries` (default 3) → backfill pool on
    exhaustion.
  - §16: CLI entrypoint — `enforce_r26()` hard-fails if generator and
    judge model families match (cross-provider judging is mandatory,
    override via `--allow-same-model-judge` for local debugging only).
- **Status of the one completed run**: `output/aig_engine.log` confirms
  `DRY_RUN=True` — **this was a mock run to validate pipeline plumbing,
  not a real LLM-generated deliverable**. Result: 184/239 candidates
  mock-approved, top 100 selected → `entregavel_2_100_questoes.csv`
  (101 lines incl. header), full audit trail written (397 entries).
  **A real run against actual LLM APIs has not yet happened.**

### 🚧 In Progress / Partially Covered
- Nothing is mid-implementation right now; the codebase is at a clean
  stopping point (dry run validated, real run pending a model/API
  decision — see §7).

### ❌ Not Yet Implemented (by design — out of scope for the competition deliverable)
Everything in `plan.md` Phases 1, 2, 5, 6, 7, 8, 9, 11, 12 remains
unbuilt. This is expected: those phases assume infrastructure the
competition deliverable doesn't require or doesn't yet have access to —
real student respondents / IRB clearance (Phases 5, 6), a downstream
grading-delivery product (Phase 12), full synthetic-data privacy tooling
(Phase 8), model-tiering infra (Phase 11), and formal hypothesis-testing
harnesses (Phase 9). The two implemented artifacts (`WAPLA_EDA.ipynb`,
`WAPLA_AIG_Engine.py`) are a **deliberately scoped subset** of Phases 3/4/10
sufficient to satisfy Deliverables 1 and 2 of the competition brief.

---

## 5. Technical Specifications

### Dataset
- **Source**: [`aiboxlab/ai-generated-questions-quality`](https://huggingface.co/datasets/aiboxlab/ai-generated-questions-quality)
  (Hugging Face), single split named **`data`** (not `train`).
- **Size**: 239 rejected AI-generated items. Rejection reason is **not**
  labeled in the dataset — it was reverse-engineered via structural
  metadata analysis in `WAPLA_EDA.ipynb`.
- **Competition schema** (`COMPETITION_SCHEMA` in `WAPLA_AIG_Engine.py`):
  ```
  question_id, question_type, discipline, taxonomy_level,
  base_text, stem, assertion_i, assertion_ii,
  statement_i, statement_ii, statement_iii, statement_iv,
  option_a, option_b, option_c, option_d, option_e,
  correct_option
  ```
- **`question_type`** (4 formats, each with different option-generation
  logic — see `QUESTION_FORMAT` dict):
  | Type | Count | Format class | Options are... |
  |---|---|---|---|
  | Afirmação Incompleta | 113 | `standard` | free-text, LLM-authored |
  | Múltipla Escolha Simples | 80 | `standard` | free-text, LLM-authored |
  | Múltipla Escolha Complexa | 30 | `complex_mc` | orchestrator-templated combinatorial phrases over 4 roman-numeral statements — mutually exclusive **by construction** |
  | Asserção-Razão | 16 | `assertion_reason` | orchestrator-templated from 5 fixed logical-pattern sentences — mutually exclusive **by construction** |
- **`discipline`**: 26 raw label values, but only **22 unique
  case-insensitively** — e.g. `"ARTE CONTEMPORÂNEA"` (32 items) vs.
  `"Arte Contemporânea"` (10 items) are the same discipline fragmented by
  case. **Not yet normalized anywhere in the pipeline** — flagged as an
  open item (§7).
- **`taxonomy_level`** (declared Bloom level) distribution is heavily
  skewed: Avaliar 166 (69%), Analisar 45, Aplicar 19, Criar 6,
  Compreender 3, Lembrar 0. **172 items (72%) are declared
  Avaliar/Criar — structurally illegal for MCQ under R9** — this is the
  single largest driver of the demotion logic in
  `determine_target_level()`.

### Structural diagnosis findings (from `output/eda_summary.txt`)
1. **Verbosity bias**: correct option is +2.29 words longer than mean
   distractor on average (95% bootstrap CI [+1.74, +2.88], Wilcoxon
   p=3.64e-16); correct option is the *longest* in 49.8% of items vs. a
   20% chance baseline.
2. **Position bias**: `correct_option == "A"` in 80.8% of items
   (95% CI [75.7%, 85.8%]) vs. 20% chance; χ²=558.1, p=1.82e-119.
3. **Bloom's Taxonomy mismatch**: 96 items (40.2%) contain no canonical
   Bloom-level verb anywhere in the full cognitive text; among items with
   an unambiguous verb match, declared/inferred level mismatch rate is
   68.2%; 172 items (72.0%) are R9-illegal (Avaliar/Criar in MCQ format).
4. **Composite**: mean 2.27/4 tracked structural flaws per item; only
   4 items (1.7%) have zero tracked flaws.

### Quality criteria (operationalized from `constitution.md`)
The engine mechanically enforces, per generated item, before it can be
accepted:
- **Position independence** (R21) — the Generator Agent always writes the
  correct answer into a fixed, position-agnostic slot (`option_a`) under
  zero positional instruction; the corpus-wide balanced target letter is
  applied **mechanically, after generation**, as a pure string relabel
  (`apply_position_shuffle()`), verified by the judge's blind solve. This
  decoupled design is itself a backported amendment (see Amendment Log
  below) — the original design injected the target letter into the
  generation prompt *before* content existed, which measurably coupled
  positional compliance with content correctness (documented dataset
  cases: items 63, 392, 457) and has since been corrected.
- **Length neutrality** (R16/R22) — no option (especially the correct one)
  is a length outlier; coefficient-of-variation threshold 0.35.
- **Mutual exclusivity** (R12/R13) — pairwise Jaccard similarity check on
  free-text option formats; templated formats are exclusive by
  construction.
- **Bloom-verb alignment** (R9/R10) — the item's cognitive text must
  contain a verb from the target level's verb bank; MCQ format is
  restricted to Lembrar/Compreender/Aplicar/Analisar (R9 — Avaliar/Criar
  items are demoted, never shipped as MCQ under their original level).
- **Independent judge approval** (R8/R23/R26) — a judge model
  architecturally distinct (different provider family) from the
  generator must independently blind-solve and approve the item; any
  single check failing anywhere in the protocol rejects the item.

### LLM generation strategy
- **Not** the full `spec.md` §2.4 two-stage (baseline generator → RAG
  refiner grounded in a versioned domain corpus) design — this
  deliverable **rewrites already-existing flawed items** using the EDA's
  structural diagnosis as feedback, rather than generating new items from
  scratch off a domain corpus. This is a deliberate, documented scoping
  decision, not an oversight.
- Two swappable model slots: `--generator-model` (default
  `gpt-4o-mini`) and `--judge-model` (default
  `claude-3-5-haiku-20241022`), enforced cross-provider by R26. The
  models actually used for the real (non-dry-run) run are
  `groq/openai/gpt-oss-20b` (generator) and `groq/qwen/qwen3.6-27b`
  (judge) — see `relatorio_tecnico.tex` §"Escolha de Modelos" for the
  full justification. External validation worth noting here: Korthals,
  Akrong, Geller, Rosenbusch, Grasman & Visser (*Mach. Learn. Knowl.
  Extr.* 2026, 8(3):74, "Towards Reliable LLM Grading Through
  Self-Consistency and Selective Human Review" — the SURE method)
  evaluated `gpt-oss-20b` specifically as a grading/judge model and found
  it the strongest of three models tested, outperforming the much larger
  Llama-3.3-70B-Instruct — independent evidence (published after this
  project's own model choice) that this pipeline's judge-model pick is
  reasonable, not just convenient.
- Model access is abstracted via `litellm` (preferred, uniform
  multi-provider interface) with a fallback to the plain `openai` SDK
  (endpoint-swappable via `base_url`), and a fully deterministic
  `--dry-run` mock requiring no API keys or network access.
- Retry loop: up to `--max-retries` (default 3) attempts per item,
  feeding the previous attempt's rejection reasons back into the next
  generation prompt; items that exhaust retries fall to a documented
  backfill/failure path (not silently dropped, not silently accepted).

---

## 6. Architecture & Integration

### Data flow (as actually implemented)
```
literatura/ (5 module folders, 51 PDFs total)
        │  (literature review, human-driven)
        ▼
constitution.md (R1-R34)  ──governs──▶  spec.md (§1-6)  ──phases──▶  plan.md (Phase 0-12)
        │                                                                    │
        │ (rules cited inline as [Rn] throughout code/notebook)            │ (only Phases
        ▼                                                                    │  0/3/4/10-subset
Hugging Face dataset (aiboxlab/ai-generated-questions-quality, 239 items)   │  implemented)
        │
        ▼
WAPLA_EDA.ipynb  ──produces──▶  output/flaw_summary.csv (239 rows, structural_flaw_count)
                                          │
                                          ▼
                          WAPLA_AIG_Engine.py build_candidate_pool()
                          (ranks by flaw_count desc, merges with original dataset)
                                          │
                                          ▼
                    Per-item: Generator Agent → Mechanical Pre-Filter → Judge Agent
                              (retry w/ feedback, up to 3x)  → approve/backfill
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                                            ▼
     output/entregavel_2_100_questoes.csv          output/aig_audit_trail.jsonl
     (competition-schema CSV, top 100)              (every attempt, every verdict)
                                          │
                                          ▼
                          output/judge_bias_audit_log.json
                          (only on real, non-dry-run runs)
```

### Integration points
- **`flaw_summary.csv` is the hard contract** between the two
  deliverables: `WAPLA_AIG_Engine.py` refuses to run
  (`FileNotFoundError`) if it's missing, and explicitly does **not**
  recompute the flaw diagnosis itself — the notebook is the sole source
  of truth for `structural_flaw_count` and the four `flag_*` boolean
  columns.
- **Bloom verb bank is duplicated, not shared**, between
  `WAPLA_EDA.ipynb` (cell 19, `BLOOM_VERBS_PT`) and
  `WAPLA_AIG_Engine.py` (§3, `BLOOM_VERBS_PT`) — kept in sync manually
  "for narrative/methodological consistency" per the engine's module
  docstring. **Risk**: any future edit to one verb bank must be mirrored
  in the other by hand; no shared module currently factors this out.
- **`mempalace.yaml`** configures an external memory/indexing tool
  (`wing: meu_projeto_mestrado`) with two "rooms" — `literatura` (indexes
  everything under `literatura/`) and `general` (catch-all). This is a
  developer-tooling config, not part of the AIG pipeline's runtime data
  flow.
- **No shared `requirements.txt`**: `WAPLA_AIG_Engine.py` imports
  `pandas`, `numpy`, `pydantic`, `tenacity`, and optionally `spacy`
  (with graceful regex fallback), `litellm` or `openai`, and `datasets`
  (Hugging Face). `WAPLA_EDA.ipynb` additionally uses `matplotlib`. These
  are currently only discoverable by reading the `import` statements in
  each file.

---

## 7. Next Steps & Open Questions

### Priority tasks
- [x] **Run the real (non-dry-run) pipeline.** ~~The only execution so
      far is `--dry-run` (mock LLM).~~ Done — see "Current State as of
      2026-08-18" above: 100/100 approved, real local-model run.
- [x] **Write the technical report** (Deliverable 3). ~~No draft exists
      yet.~~ Done — `relatorio/relatorio_tecnico.tex`, documents the EDA
      findings, engine architecture, spec deviations, and final run
      statistics.
- [ ] **Normalize the `discipline` case-duplication issue** (26 raw → 22
      unique case-insensitively) — currently unaddressed anywhere in the
      pipeline; affects any per-discipline reporting in the technical
      report.
- [ ] **Add a `requirements.txt`/`pyproject.toml`** — dependencies are
      currently only implicit in import statements across two files.
- [x] **Initialize git version control.** ~~The project currently has no
      `.git` directory.~~ Done — `.git/` exists (see "Current State as of
      2026-08-18" above).

### Blockers / uncertainties
- ~~No API keys configured yet~~ — **resolved**: `.env` has
  `GROQ_API_KEY`/`GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`HF_TOKEN` (see
  "Current State as of 2026-08-18" above). The graded run used local
  `vllm_local` models and needed none of these; they matter for any future
  hosted-provider run.
- **spec.md §4.2.1 step 5 (human-SME leniency check) has no
  implementation path** in a fully automated competition script — this is
  logged as an accepted, permanent gap for this deliverable (per the
  engine's own module docstring), not something to solve before
  submission, but should be called out explicitly in the technical report
  per R24/R33's disclosure requirements.
- **Two Module 4 literature sources remain unread**
  (`literatura/mod_4_infra_green_ai/19801_pub.pdf`,
  `2024.emnlp-main.1215.pdf`) — only relevant if Green AI/SLM routing
  (`spec.md` §5 / `plan.md` Phase 11) is ever brought into scope.

### Decisions needed
- [ ] Final `--generator-model` / `--judge-model` pair for the submitted
      run (cost vs. quality vs. R26 compliance).
- [ ] Whether to run `--rigorous-position-check` for the final batch
      given its ~10x judge-call cost multiplier.
- [ ] Whether `--pool-size` should be widened beyond the default (all 239
      flaw-ranked candidates) — the dry run showed 184/239 (77%) mock
      approval, comfortably above the 100 needed, but real-LLM approval
      rates may differ.
- [ ] Whether the technical report should also report the classical
      Δ_model/Δ_bloom discrimination statistics from `spec.md` §2.9 —
      these are specified but **not computed anywhere in the current
      code**, since they require a respondent pool this deliverable does
      not build.

---

## 8. Post-Submission Experiments (LAK Expansion)

**Scope note:** everything in this section is exploratory work conducted
*after* the graded deliverable (93→100/100, `--output-tag
design_d_full`) was finalized, using separate `--output-tag` values that
never touch `output/entregavel_2_100_questoes_design_d_full.csv` or its
audit trail. None of these findings change `relatorio_tecnico.tex`'s
already-final 93/100→100/100 narrative — they're logged here for a
possible future LAK submission, kept explicitly out of the graded report.
Each round tests exactly one addition, in isolation, against the same
30-item calibration pool (`--pool-size 30`, same flaw-ranked top-30 used
in every prior same-day calibration) and the same immediately-prior
baseline (`design_d_fix`, the last 30-item calibration before this
section's experiments began: 15/30 approved = 50.0%, length-extreme
76.7%, mutual-exclusivity 11.6%, Bloom-verb-missing 1/86 = 1.2%). A
snapshot of the pre-Round-1 `WAPLA_AIG_Engine.py` is kept so each round
can be re-implemented from the same starting point rather than stacking
on the previous round's change, per the explicit "one addition at a time"
constraint for this line of experiments.

### Round 1 — Completing R10's structural half

**What changed:** added `BLOOM_STRUCTURAL_RULE_PT` (a per-legal-level
dict: Lembrar → verbatim-fact options, Compreender → cause/effect framing,
Aplicar → forward-looking-action framing, Analisar → pros/cons-comparison
framing, matching `constitution.md` R10's table exactly), a new Rule 6 in
`GENERATOR_SYSTEM_PROMPT` describing the mechanism, and a per-item
`BLOOM_STRUCTURAL_RULE` task_params injection in `build_generator_messages()`
(gated to the `standard` format only, same gating as the existing
countdown/word-count instructions — `complex_mc`/`assertion_reason` never
have LLM-authored option text). Run: `--output-tag round1_r10structural`.

**Results, 30 items, directly vs. the `design_d_fix` baseline:**

| Metric | Baseline (design_d_fix) | Round 1 |
|---|---|---|
| Approval rate | 50.0% (15/30) | 53.3% (16/30) |
| Length-extreme rate | 76.7% | 75.3% |
| Mutual-exclusivity flagged | 11.6% | 10.1% |
| **Bloom-verb missing** | **1.2% (1/86)** | **3.4% (3/89)** |
| Judge rejections | 3.5% | 5.6% |

**Item-level churn:** 8 items flipped backfilled→approved, 7 flipped
approved→backfilled (net +1). This is an even, roughly-symmetric churn at
n=30 with a non-deterministic generator (temperature=0.5, no fixed
inference seed) — indistinguishable from ordinary run-to-run noise, not
good evidence of a real approval-rate effect in either direction.

**Honest verdict:** no clear signal that completing R10's structural half
improved or harmed approval rate, length-extreme rate, or mutual-exclusivity
— all differences are within a plausible noise band at this sample size.
The one number worth flagging is directional, not conclusive: Bloom-verb-missing
rejections went *up* (1→3 occurrences), the opposite of what R10-structural
was meant to help with. This is consistent with — though this single data
point does not prove — the R38 stacking-constraint risk already discussed
in `constitution.md`: adding a fifth instruction to an already-dense
generator prompt (countdown-marker length control, correction-priority,
Bloom-verb, mutual-exclusivity, now Bloom-structure) may be trading a small
amount of compliance on the pre-existing verb-bank check for the new
structural instruction. Worth re-testing at a larger sample before drawing
a firm conclusion either way.

**Next steps (not yet run):** Round 2 (best-of-N generation, select
lowest length-CV before the mechanical pre-filter) and Round 3 (a
length-equalization second pass forbidden from changing meaning) are
specified but not implemented. Both must be built from the pre-Round-1
baseline snapshot, not from Round 1's modified code, to keep each round's
causal attribution clean.

---

## Amendment Log (for this file)

- v1.0 (2026-07-17): Initial creation. Reflects repository state after
  Deliverable 1 (EDA notebook) complete and Deliverable 2 (AIG engine)
  built and dry-run-validated (184/239 mock-approved, 100 selected), but
  not yet run against real LLM APIs. Technical report (Deliverable 3) not
  started.
- v1.1 (2026-08-12): Backports the position-content coupling finding
  (diagnosed and corrected in `WAPLA_AIG_Engine.py` during pipeline
  calibration; full diagnostic writeup in
  `relatorio/relatorio_tecnico.tex` §"Descoberta Metodológica Central")
  into this file, per R31's no-silent-drift requirement. `spec.md` §4.1
  and `plan.md` Phase 10 carry matching amendment entries. This file's §5
  "Position independence" description is updated to describe the
  corrected, decoupled design (mechanical post-generation relabel via
  `apply_position_shuffle()`); the prior wording described only the
  pre-fix design, in which the target letter was injected into the
  generation prompt before content existed.
- v1.2 (2026-08-18): Adds §8 "Post-Submission Experiments (LAK
  Expansion)", logging Round 1 (R10 structural-half completion) with its
  isolated calibration result. Explicitly out of scope for the already-
  graded deliverable — `relatorio_tecnico.tex`'s 93/100→100/100 narrative
  is unaffected by anything in §8, per the user's explicit instruction
  that this line of experiments is post-submission exploratory work, not
  a revision of the submitted report.
