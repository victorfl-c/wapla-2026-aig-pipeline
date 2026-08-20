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

## 9. Detailed Methodology for Notebook Update (Staged, Not Yet Applied)

> ✅ **RESOLVED (2026-08-20, before notebook rebuild) — was a blocking
> flag; now fixed and confirmed.**
>
> **Confirmed final deliverable:** `output/entregavel_2_100_questoes_qwen_validated.csv`
> is the canonical final deliverable — named as such in `relatorio_tecnico.tex`
> ("o arquivo final entregue", lines ~419–420 and ~535–536), the newer of
> the two candidate files (mtime 2026-08-19 18:33 vs.
> `entregavel_2_100_questoes_design_d_full.csv`'s 03:52 the same day, ~14.5h
> earlier), and matches commit `2af972f`'s message ("new final deliverable:
> entregavel_2_100_questoes_qwen_validated.csv"). Both files check out
> clean: 100 data rows each, 0 duplicate `question_id`s in either.
>
> **The gap that was found:** `qwen_validated.csv` had never actually been
> committed to git — `.gitignore`'s `output/*.csv` blanket rule only had an
> exception for the *old* `..._design_d_full.csv` (line 15), not this one.
> An oversight, not an intentional exclusion, per explicit user decision.
>
> **Fix applied:** added `!output/entregavel_2_100_questoes_qwen_validated.csv`
> and `!output/aig_audit_trail_qwen_remediation.jsonl` to `.gitignore`
> (mirroring the existing exception pattern for the old CSV), then
> committed both files plus the audit trail as commit `8281d04` ("Track the
> real final deliverable CSV (qwen_validated), previously untracked due to
> .gitignore oversight"), on top of `f6e9156`. Verified via
> `git ls-files output/`: both `entregavel_2_100_questoes_design_d_full.csv`
> (first pass) and `entregavel_2_100_questoes_qwen_validated.csv` (final
> pass) are now tracked, alongside `aig_audit_trail_qwen_remediation.jsonl`.
>
> **The notebook rebuild may now proceed using
> `entregavel_2_100_questoes_qwen_validated.csv` with full confidence as
> the canonical final deliverable.**

**Purpose:** `relatorio_tecnico.tex` was cut aggressively on 2026-08-20 to
fit the SBC page limit (single-column template, not two-column as
originally assumed — see Amendment Log v1.3). The full, uncut narrative
detail below is staged here for a **future** Kaggle notebook restructuring
pass (rule-by-rule explanations, new visualizations, fuller narrative
arc) — explicitly **not** attempted tonight; tonight's deadline is the
report only. Content below is verbatim or near-verbatim from the
pre-cut report sections, kept in Portuguese to be directly reusable.

### 9.1 Design C→D Narrative (full, pre-cut version)

> O acoplamento posição-conteúdo não foi o único achado arquitetural
> deste projeto -- apenas o primeiro. Um segundo ciclo completo de
> diagnóstico, correção e teste segue a mesma lógica científica: hipótese,
> teste, refutação quando aplicável, causa-raiz, nova hipótese
> fundamentada em literatura, novo teste, confirmação parcial com
> explicação de mecanismo.
>
> **Hipótese 1 (R42) -- ordem dos campos do schema.** Tam et al. (2024,
> "Let Me Speak Freely?") mostram que forçar um modelo a comprometer-se
> com uma resposta antes de sua justificativa causa colapso de acurácia
> específico por tarefa (86,51%→23,44% no GSM8K), e confirmam que a causa
> é estrutural -- a ordem literal dos campos no schema JSON -- não um
> artefato de parsing. Uma auditoria de código encontrou exatamente essa
> inversão em WAPLA_AIG_Engine.py: o schema GeneratedItem declarava
> correct_option antes de generator_notes, e JudgeVerdict declarava
> blind_solve_shuffled_label antes de blind_solve_reasoning e verdict
> antes de reasons -- o oposto exato do que R42 exige, nos dois schemas,
> nas duas direções. A correção reordenou os campos e, criticamente, os
> prompts de sistema do gerador e do juiz (que ainda listavam a ordem
> antiga na instrução "responda com exatamente estes campos" -- a parte
> que de fato governa a ordem de geração sob decodificação em modo JSON
> simples, já que R44/decodificação restrita por schema não está em
> vigor).
>
> **Teste 1 (Design C) -- refutado.** A hipótese natural seguinte foi que
> um alvo numérico de comprimento, calculado por item e injetado no
> prompt (substituindo a instrução abstrata de "±20% da média"),
> reduziria a taxa de rejeição por viés de verbosidade. Testado em
> calibração pareada sobre os 30 itens de maior contagem de falhas
> estruturais: a taxa de aprovação permaneceu idêntica (33,3%→33,3%), e a
> taxa de opção correta como extremo de comprimento não melhorou
> (82,9%→85,9%, se algo, piorou ligeiramente). Inspeção direta dos
> comprimentos gerados revelou a causa-raiz: o item 63 (aprovado) ficou
> 8-12 palavras abaixo do alvo em todas as cinco opções, e ainda assim
> passou, por sorte na dispersão relativa entre as cinco; o item 98
> (rejeitado) chegou perto do alvo em 4 das 5 opções e mesmo assim
> falhou. A verificação mecânica (check_verbosity()) não depende de
> nenhum valor absoluto -- ela testa apenas se a opção correta é o
> extremo estrito (máximo ou mínimo) entre cinco valores. Um alvo
> absoluto, por mais preciso que seja, não altera essa variável de
> decisão baseada em ranking.
>
> **Nova hipótese (R45), fundamentada em literatura nova.** Xie & Lee
> (2508.13805, "Prompt-Based One-Shot Exact Length-Controlled Generation")
> demonstram que modelos de linguagem não conseguem manter um contador
> interno de tokens de forma confiável (a autoatenção não possui um
> acumulador explícito), de modo que qualquer alvo absoluto de
> comprimento -- por mais preciso que seja -- está sujeito à mesma
> limitação. Sua técnica, CAPEL (Countdown-Aided Prompting for Exact
> Length), externaliza a contagem por meio de marcadores visíveis e
> decrescentes intercalados com as palavras geradas (ex.:
> `<5>Olá,<4>mundo!<3>Como<2>vai<1>você?<0>`), elevando o cumprimento
> estrito de comprimento no MT-Bench-LI de menos de 30% para mais de 95%
> com gpt-4.1. Este projeto adotou o mecanismo (Design D), generalizando-o
> -- de forma reconhecidamente não testada pelos autores originais --
> para forçar paridade exata entre cinco campos JSON paralelos numa única
> chamada, em vez de um único texto contínuo.
>
> **Teste 2 (Design D) -- confirmação parcial, com mecanismo explicado.**
> Na mesma calibração pareada de 30 itens: a taxa de aprovação subiu de
> 33,3% para 50,0% (+16,7 pontos percentuais), e a taxa de extremo de
> comprimento caiu de 82,9% para 76,7% -- a primeira melhoria real
> observada nas duas tentativas. Mas o mecanismo não funciona de forma
> confiável: 77,3% dos attempts continham ao menos uma opção com
> sequência de marcadores malformada (cauda de marcadores vazios sem
> palavra entre eles: 105 ocorrências; sequência incorreta/incompleta:
> 97; texto residual após `<0>`: 35) -- nenhum caso de a instrução ser
> simplesmente ignorada. phi-4 tenta executar o protocolo de contagem
> regressiva quase sempre, mas frequentemente o executa mal -- exatamente
> a ressalva que Xie & Lee documentam para modelos menores ou mais
> protegidos por guardrails (o4-mini, gpt-4o-mini no estudo original). A
> melhoria observada, portanto, não vem de o mecanismo funcionar de forma
> confiável, mas de uma minoria de execuções corretas ser suficiente para
> deslocar o resultado agregado -- uma intervenção imperfeita ainda tendo
> valor esperado positivo.
>
> **Confirmação em escala.** A execução completa dos 239 itens confirma a
> direção do Teste 2: taxa de extremo de comprimento de 73,2% --
> consistente com (na verdade, ligeiramente melhor que) o resultado da
> amostra de 30 itens, e mensuravelmente abaixo da linha de base
> pré-Design-D (82,9%).
>
> **O achado mais defensável: o piso estrutural de ~40%.** Para cinco
> valores de comprimento gerados de forma independente e sem qualquer
> correlação entre comprimento e correção, o puro acaso já torna a opção
> correta o extremo estrito (máximo ou mínimo) em ~40% dos casos -- por
> simetria, P(é o máximo) + P(é o mínimo) = 1/5 + 1/5 = 2/5, para cinco
> valores distintos. Nenhuma correção do lado da geração pode levar a taxa
> de rejeição por extremo de comprimento a zero: esse é um piso
> combinatório, não um sintoma de viés. A taxa observada nas execuções
> deste projeto -- 82,9% antes do Design D, 73,2% depois, em escala
> completa -- fica bem acima desse piso em ambos os casos, o que é a
> evidência quantitativa de que existe, sim, um viés de verbosidade real
> e mensurável além do ruído combinatório inevitável -- e que o Design D
> fechou uma fração real, mas parcial, desse excesso (de ~43 pontos
> percentuais acima do piso para ~33). Separar "piso estatístico
> inevitável" de "viés corrigível" é, em si, uma contribuição
> metodológica, não apenas uma nota de rodapé sobre os números.

### 9.2 Energy Measurement Methodology (full, pre-cut version)

> Seguindo o objetivo de medição de Chung et al. (2026, "Where Do the
> Joules Go?") e de Wang et al. (2026), que instrumentam energia de
> inferência diretamente no hardware em vez de estimá-la apenas a partir
> de contagens de token, este projeto amostrou `nvidia-smi
> --query-gpu=power.draw,utilization.gpu,memory.used` a cada 2 segundos
> durante toda a duração da execução completa do pool de 239 itens
> (Design D, R45), do início do processo até a escrita do CSV/JSONL
> finais. A energia total foi calculada integrando a potência instantânea
> (W) ao longo do tempo pela regra do trapézio, convertendo
> Watt-segundos em Watt-horas (dividido por 3600) e depois em
> quilowatt-horas. Diferente de Chung et al., que usa a ferramenta Zeus
> (You, Chung & Chowdhury, 2023) para leitura direta de contadores de
> energia da GPU, esta medição usa amostragem periódica de potência
> instantânea como aproximação mais leve do mesmo objetivo -- não uma
> reprodução da instrumentação exata deles. Vartziotis et al. (2026)
> mostram que estimar energia a partir de contagem de tokens exige
> constantes de calibração específicas por arquitetura de GPU (H100 vs.
> A100 já diferem em ~30-35%); a medição direta de potência aqui descrita
> contorna completamente esse problema de calibração, pois mede a
> potência real no hardware efetivamente usado, não uma estimativa
> derivada de tokens.
>
> Resultados completos: duração total 5h08min (308,3 min;
> 15:00:21-20:08:30); potência média 291,5 W; potência de pico 408,8 W;
> energia total 1,498 kWh (1.497,85 Wh); 93/239 itens aprovados (38,9%);
> 0,0161 kWh/item (16,1 Wh/item) aprovado. Escopo: mede apenas consumo de
> GPU via nvidia-smi, não inclui overhead de CPU/memória do host, energia
> de rede, nem infraestrutura compartilhada do cluster; não é comparável
> às execuções via Groq, cuja energia permanece inteiramente
> não-mensurável a partir deste projeto.

### 9.3 Judge Cross-Validation Audit — Full Findings (pre-cut version)

> Após a entrega do lote de 100 itens (phi-4 gerador, gpt-oss-20b juiz),
> este projeto conduziu uma auditoria adicional: reexecutar o mesmo
> protocolo de blind-solve e verificação de qualidade usando um segundo
> modelo-juiz independente, qwen3.6-27b, sobre o texto já entregue, sem
> regenerar nenhum item.
>
> **Achado.** 27% dos 100 itens (27/100) foram sinalizados por
> qwen3.6-27b com bloom_alignment_ok=False, e até 50% falharam ao menos
> um dos quatro critérios de qualidade sob a reauditoria mais rigorosa. A
> causa recorrente: itens cujo stem usa o verbo do nível declarado
> ("Analisar") apenas retoricamente (ex.: "Ao analisar a Semântica,
> pode-se afirmar que ela é o ramo da linguística que..."), sem exigir de
> fato decomposição, comparação ou inferência -- efetivamente itens de
> recuperação de definição (nível Lembrar/Compreender) travestidos de
> análise.
>
> Comparando com o histórico de julgamento do juiz original sobre os
> mesmos itens: gpt-oss-20b havia aprovado 7 dos 8 casos inspecionados
> manualmente com justificativas quase idênticas e genéricas -- **both
> verbatim quotes, for the notebook's rule-by-rule appendix:**
> - *"The task requires analysis, matching Bloom level."* (qid 106)
> - *"Bloom level 'Analisar' matches the analytical nature of the
>   question."* (qid 779)
> - (additional near-identical boilerplate seen across qids 26, 457, 528:
>   "The cognitive demand of selecting the correct statement aligns with
>   the 'Analyze' Bloom level" / "matching the declared Bloom level" —
>   full set of 5 verbatim quotes recorded in this conversation's turn
>   analyzing "Part 2: Same items, historical Phi-4/gpt-oss-20b pairing")
>
> Sem nunca engajar com a demanda cognitiva real do item: evidência
> direta, não apenas estatística agregada, de um juiz insensível a esta
> dimensão específica de qualidade.
>
> **Correção.** `determine_target_level()` foi estendida com uma tabela
> de correção pontual (`QWEN_BLOOM_DEMOTION_OVERRIDES`), informada pelo
> próprio raciocínio já registrado do juiz qwen3.6-27b: 23 question_ids
> cujo texto de rejeição citava explicitamente recuperação/reconhecimento
> de definição foram rebaixados de "Analisar" para "Compreender" antes da
> regeneração. Os itens afetados (43 no total, incluindo 20 com outros
> defeitos não relacionados a Bloom) foram regenerados a partir da linha
> original do dataset -- nunca a partir do texto já reescrito -- com
> gpt-oss-20b como gerador (Design D intacto) e qwen3.6-27b como juiz; 7
> itens com defeito de contexto incompleto na fonte foram encaminhados
> diretamente ao pool de reserva, sem tentativa de regeneração. A
> composição final de nível de Bloom mudou de 100 "Analisar" para 70
> Analisar / 22 Compreender / 8 Aplicar.
>
> **Remediation run stats** (for notebook narrative): 2h55min runtime
> (18:28:29-21:23:39 UTC), 156 total generation attempts, 50/50 slots
> resolved (100% fill rate), 3 free-reserve items tried first (all
> failed their own judge-only re-check), 1 backfill slot needed 2 hops
> before landing (qid 364→176 failed→440 succeeded).
>
> **Stem-genericity follow-up finding:** R41 re-check surfaced a
> similarity=1.0000 pair (qid 439/510, both Múltipla Escolha Complexa) —
> investigated and confirmed as a false positive for content duplication
> (completely different topics), but real: gpt-oss-20b defaults to a
> generic, reusable stem template for Asserção-Razão/Múltipla Escolha
> Complexa formats ("Ao analisar as asserções, assinale a alternativa
> correta.") where phi-4 always wove in the specific topic. A targeted
> fix (explicit topic-specificity instruction injected into generator
> feedback) resolved 2/4 identified cases (qid 73, 582); the remaining 2
> (439/510) stayed generic because their regeneration attempts failed for
> an unrelated reason — Complex-MC's short combinatorial option phrases
> tripping the length-bias mechanical check, not a stem-specificity issue.

### 9.4 Full `tab:cobertura` (28 rows, pre-consolidation)

The report's coverage table originally had one row per rule/rule-range
before the 2026-08-20 consolidation (12 "Fora de escopo" rows → 1). Full
git history of the pre-consolidation table is in commit `2af972f` and
earlier — `git show 2af972f:relatorio/relatorio_tecnico.tex` (before the
2026-08-20 cutting commits) has the complete 28-row version with
individual notes for R1–R5, R11, R14–R16, R17–R19, R27–R30, R35–R36,
R39, R40, R43–R44, §5, §6, §2.7–2.9 each as their own row. Reuse that
git-historical version directly for the notebook's rule-by-rule appendix
rather than retyping — it is the authoritative, already-verified source.

### 9.5 Deferred: Notebook Restructuring (rule-by-rule, new viz, narrative arc)

**Explicitly logged as a scoped NEXT task, not attempted tonight
(2026-08-20 deadline is the report only):**
- Rewrite the Kaggle notebook's markdown narration to walk rule-by-rule
  (R1 through R45) rather than the current denser prose, using §9.1–9.4
  above as source material.
- Add new visualizations beyond the 7 EDA figures already produced (3
  currently active in the report, 4 commented out for space — see
  `relatorio_tecnico.tex` §Evidências) — candidates: a Bloom-level
  composition before/after chart (100 Analisar → 70/22/8), a
  per-attempt approval-rate timeline for the remediation run, a
  judge-agreement heatmap (gpt-oss-20b vs. qwen3.6-27b per check).
- Restore the 4 commented-out figures (fig:verbosidade-tipo, fig:r9,
  fig:composto, fig:overview) into the notebook narrative even though
  they were cut from the report for page-length reasons.
- Build a fuller narrative arc connecting: original submission →
  Phi-4/gpt-oss-20b calibration (Design C→D) → post-submission
  cross-judge audit (qwen3.6-27b) → remediation → final deliverable —
  the report compresses this to headline findings; the notebook has
  room for the full arc.

### 9.6 Rule-by-Rule (R1–R45) Plain-Language Reference

Written for the notebook's future rule-by-rule walkthrough section. Each
entry: plain-language gist + this project's actual implementation status
(source: `tab:cobertura` in `relatorio_tecnico.tex` / this session's
module-by-module audits — not aspirational, verified by tracing code).

**§I PBL (R1–R5) — Fora de escopo, all five.** This entry reuses
already-existing items, not scenarios generated from scratch, so this
whole group doesn't apply to the actual task.
- R1: every item must come from a messy, real-life problem, never a bare
  recall fact.
- R2: distinguish Problem-Based (apply knowledge) vs. Project-Based
  (construct knowledge) items.
- R3: any AI role in a PBL artifact must be disclosed via an explicit
  integration model.
- R4: where AI use is uneven across students, the rubric must score
  "use of AI" as its own criterion.
- R5: scenario text must never leak the answer into the problem
  statement itself.

**§II Bloom's Taxonomy (R6–R11).**
- R6 (Parcial): Bloom is the mandatory cognitive-level scheme, with its
  known validity limits acknowledged. `check_bloom_verb()` implements
  the verb-gate half; no independent classifier.
- R7 (Fora de escopo): cognitive level should use the dual-dimension
  model (process × knowledge type); not modeled here.
- R8 (Parcial, folded into R6 row): no self-reported cognitive level
  without independent re-classification. `check_bloom_verb()` is
  mechanical but not a trained independent classifier as R8 demands.
- R9 (Implementado): MCQ is illegal for Avaliar/Criar.
  `determine_target_level()` demotes those to Analisar before
  generation — confirmed zero Avaliar/Criar items delivered in MCQ.
- R10 (Parcial): each Bloom level needs a fixed, level-specific
  template. Verb-bank half has code; the "structural template" half
  (causa/efeito for Analisar, prós/contras for Avaliar, etc.) has none
  — every level gets the same option-structure instructions.
- R11 (Fora de escopo): Bloom-difficulty is a hypothesis to test
  empirically per domain, not assumed. No discrimination statistics
  computed anywhere in this pipeline.

**§III Rubrics (R12–R16) — mostly Fora de escopo** (this competition's
schema is MCQ-only, no rubric generation), except:
- R12–R13 (Implementado): rubric/option criteria must be mutually
  exclusive, mechanically verified, not LLM-self-enforced.
  `check_mutual_exclusivity()` (Jaccard) does this for free-text
  options; templated formats get exclusivity by construction.
- R14 (Fora de escopo): every rubric must declare its type before
  generation.
- R15 (Fora de escopo): rubric criteria limited to 3–6, no vague terms
  ("adequate," "clear").
- R16 (Implementado, folded into R22 row): items with >1 detected flaw
  must be rejected, not silently warned. The mechanical pre-filter does
  exactly this.

**§IV Synthetic Data / Privacy (R17–R20).**
- R17–R19 (Fora de escopo): no real student data may ever train/condition
  any model; validate synthetic data jointly on fidelity+privacy; prefer
  frozen in-context generation over fine-tuning. None of this applies —
  this pipeline rewrites existing items, never generates student-response
  data from scratch.
- R20 (Implementado): bias introduced by a generator LLM must be
  actively audited/curated out. The mechanical pre-filter substitutes
  for the trained CLLM curator `spec.md` originally specified.

**§V LLM-as-a-Judge Bias Mitigation (R21–R26).**
- R21 (Parcial): every judge verdict needs an explicit position-bias
  control (min. bidirectional swap-and-average, tie on inconsistency).
  Default mode is single-shuffle blind-solve, not the 10-reordering
  majority vote R21's floor requires (`--rigorous-position-check`
  exists but was never used in a real run).
- R22 (Implementado): judge rubrics must mechanically neutralize
  verbosity, verified per judge model via a length-confound probe.
  `check_verbosity()` (CV=0.35) + the one-time confound audit do this.
- R23 (Parcial, same gap as R21): no judgment accepted from a single
  uncorrected judge call — single-shuffle mode doesn't fully satisfy
  this either.
- R24 (Desviado): judges must never be trusted for leniency calibration
  without a human-expert control group. No human reviewer exists in
  this automated script — disclosed, not silently skipped.
- R25 (Implementado): bias-mitigation config is tied to a specific judge
  model version, re-audited on every upgrade. The verbosity-confound
  audit is re-run at the start of every session against the actual
  judge model in use.
- R26 (Implementado): judge must never be the same model/checkpoint/
  close-family variant as the generator. Enforced by a hard assertion
  in code (`_model_family` check, raises if violated).

**§VI IRT Calibration (R27–R30) — Fora de escopo, all four.** No
respondent pool (human or LLM) exists to calibrate against; classical
reliability metrics alone aren't accepted as validation, IRT parameters
aren't computed, discrimination-based exclusion isn't implemented, AI
items aren't compared against a human-authored discrimination bar.

**§VII Engineering & Reporting Rigor (R31–R34) — Implemented, with a
caveat.**
- R31: spec-anchored artifact maintenance — divergences registered
  explicitly (this whole document, `spec.md`, `plan.md` amendment logs).
- R32: a passing spec check is evidence of matching, not of the spec
  being correct — motivated re-checking Bloom-difficulty and R9's MCQ
  boundary assumptions this session.
- R33: human-vs-AI comparisons need per-domain inter-rater agreement,
  not pooled figures. N/A (no human grading comparison exists).
- R34: statistical comparisons need variance decomposition/resampling,
  not point estimates. The EDA's own bootstrap CIs satisfy this; the
  same-day Design C/D calibration comparisons (n=30, no bootstrap) do
  **not** satisfy R34 on their own — flagged explicitly, not silently
  passed off as rigorous.

**§VIII IRT/LLM-Respondent Difficulty (R35–R36) — Fora de escopo, both.**
R35: never use direct LLM difficulty judgment; must simulate-then-fit
IRT instead. R36: respondent-model selection must not default to the
strongest solver, and must report validated domains. Neither implemented
— gated on the same missing respondent pool as R27–R30.

**§IX Energy Reporting (R37) — Implemented.** Where hardware
instrumentation is unavailable, log energy-proxy signals at minimum.
Exceeded via real `nvidia-smi` power sampling (not just a proxy) for the
local vLLM runs: 1.498 kWh / 239 items, 16.1 Wh/item approved.

**§X Multi-Constraint Position Bias (R38) — Implemented.** No stacked
constraint may be assumed satisfied by prompt order alone. The
mechanical pre-filter verifies every constraint independently and
post-generation — this rule is itself the generalization of the
position-content-coupling finding (§Descoberta Metodológica Central).

**§XI Synthetic/LLM Data Auditing (R39–R41).**
- R39 (Fora de escopo): passing the mechanical filter + judge is never
  a complete audit. N/A — no synthetic student-data corpus exists here.
- R40 (Fora de escopo): answer keys need independent resampled
  self-consistency verification, not a single generator/judge assertion.
  Default mode (`n_reorderings=1`) never resamples for this; the
  10-reordering flag could serve double duty but was never invoked in a
  real run.
- R41 (Auditoria independente pós-hoc): batches need a cross-item
  diversity check before delivery. `tools/diversity_check_r41.py`
  implements this as a standalone post-hoc script, not integrated into
  the selection pipeline — found and helped resolve one genuine
  near-duplicate pair (528/26).

**§XII Second Literature Wave (R42–R44).**
- R42 (Implementado, v0.9-corrected): schema field ordering must put
  justification before verdict. Both Pydantic schemas AND both system
  prompts needed fixing (schema-only was insufficient under JSON-mode
  generation).
- R43 (Fora de escopo): no judge verdict trusted from a single pass
  without a resampled consistency-check mode using non-zero
  temperature. Not implemented — and this project's own post-submission
  cross-judge audit (§9.3 above) is now direct empirical evidence of
  exactly the risk R43 exists to catch.
- R44 (Fora de escopo): grammar-constrained decoding must be used
  wherever the local backend supports it, not prompting-only JSON. Not
  implemented in this pipeline.

**§XIII Exact Length Control (R45) — Implemented.** Exact (not
approximate) output length requires visible countdown markers, never an
implicit length instruction. Design D: `strip_countdown_markers()` +
`describe_countdown_malformation()`. Real but partial improvement
(33.3%→50.0% approval in isolated calibration), with a 77.3%
marker-malformation rate — the mechanism works often enough to move the
aggregate, not reliably per-attempt.

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
- v1.3 (2026-08-20): Adds §9 "Detailed Methodology for Notebook Update
  (Staged, Not Yet Applied)". `relatorio_tecnico.tex` was cut from
  ~9,300 to ~3,500 main-text words to fit the SBC page limit once it
  became clear the template is single-column, not two-column as
  originally assumed (a page-density miscalculation, not new content
  duplication — confirmed no duplicated sections/paragraphs during
  diagnosis). Full pre-cut narrative (Design C→D arc, energy-measurement
  methodology, the qwen3.6-27b cross-judge audit with verbatim
  boilerplate quotes, the pre-consolidation 28-row coverage table) is
  staged in §9 for a future Kaggle notebook restructuring pass — not
  attempted tonight; tonight's deadline was the report only. §9.5 scopes
  that future notebook work explicitly so it isn't attempted piecemeal
  or forgotten.
- v1.4 (2026-08-20): Confirmed `entregavel_2_100_questoes_qwen_validated.csv`
  is the true final deliverable content-wise (named as such in
  `relatorio_tecnico.tex`, newer by ~14.5h, and matches commit `2af972f`'s
  message) — but found it had never been committed to git (excluded by
  `.gitignore`'s `output/*.csv` rule, which only re-included the old
  `..._design_d_full.csv`). Per explicit user decision (an oversight, not
  intentional untracking), added a matching `.gitignore` exception plus
  one for `aig_audit_trail_qwen_remediation.jsonl`, and committed both
  files as `8281d04`. §9's blocking flag is now marked resolved; the
  notebook rebuild proceeds using `entregavel_2_100_questoes_qwen_validated.csv`
  as the confirmed canonical deliverable.
- v1.5 (2026-08-20, `SPEC_notebook_final.md` executed): rebuilt
  `notebooke091850abb.ipynb` as the final Kaggle submission artifact,
  per the spec's full checklist:
  - **New "Rule Reference" section** (3 markdown cells, right after the
    intro) covering all 45 constitution.md rules in plain language, with
    status sourced directly from `constitution.md`'s own inline notes —
    not a paraphrase from memory.
  - **AIG-7 rebuilt**: `GENERATOR_SYSTEM_PROMPT`/`JUDGE_SYSTEM_PROMPT` and
    `build_generator_messages`/`build_judge_messages` replaced with the
    exact current `WAPLA_AIG_Engine.py` versions (Design D included, rule
    citations already stripped from the LLM-facing text) — extracted
    directly from the engine file via line-range slicing and verified
    byte-identical by executing both the notebook cell and the real
    engine module side by side (only intentional diff: `build_generator_
    messages`'s task_params string still says "Design D, constitution R45"
    in the shipped engine — a leftover the earlier prompt-cleanup pass
    missed because it only touched the two system-prompt constants, not
    this per-call user-message builder; cleaned to just "Design D" in the
    notebook's copy, `WAPLA_AIG_Engine.py` itself left untouched per this
    task's no-behavior-change constraint — flagged here as a small
    residual finding, not fixed at the source).
  - **New Design D markdown + code cells** (`strip_countdown_markers()`,
    `describe_countdown_malformation()`, `compute_target_word_count()`)
    with the honest 33.3%→50.0%/77.3%-malformation numbers and the
    Design C refutation — verified functionally identical to the engine
    via direct comparison, not just visual inspection.
  - **AIG-4 schemas fixed**: `GeneratedItem`/`JudgeVerdict` field order was
    still R42-*violating* in the pre-existing notebook (`correct_option`
    before `generator_notes`; `blind_solve_shuffled_label` before
    `blind_solve_reasoning`; `reasons` after `verdict`) — corrected to
    match the real engine, with a markdown note explaining why (Tam et al.
    2024, the same finding already cited elsewhere in this project).
  - **AIG-9/AIG-12 updated**: `generator_agent()`/`process_item()` now
    thread Design D's `target_word_count` through and log countdown
    malformation to the audit trail (diagnostic only, never gates
    acceptance) — extracted from the engine and patched via targeted,
    verified string replacement, not hand-retyped.
  - **AIG-15 rewritten**: documents all three real generator/judge
    configurations this pipeline actually ran (original Groq conception;
    phi-4+gpt-oss-20b production run; gpt-oss-20b+qwen3.6-27b post-
    submission validation), with the active variables set to the
    stage-3 configuration that produced the final deliverable.
  - **New "Post-Submission Refinement" section**: motivation (R43's gap,
    Rating Roulette/SURE literature), the 27%/50% cross-judge finding with
    the verbatim boilerplate quotes from §9.3 above, the correction
    (23 demoted, 43 regenerated, 7 backfilled, 70/22/8 final composition),
    the R41 re-check (before/after Self-CosSim), and a short Scalable
    Oversight framing (Irving 2018, Kenton 2024).
  - **Final Results rebuilt**: now loads `entregavel_2_100_questoes_qwen_
    validated.csv` (not `design_d_full.csv`), with the real headline
    numbers (93/239=38.9%+10/40=25.0%, 1.498 kWh/16.1 Wh-per-item, the
    cross-judge 27%/50% finding) always printed regardless of which local
    files are attached — since no single audit trail spans both the
    original run and the remediation pass, the attempts-histogram uses the
    original production run's trail with an explicit note about that
    scope limit.
  - **New "Specification Coverage Table"** (25-row pre-consolidation
    version, recovered via `git show 2af972f:relatorio/relatorio_tecnico.tex`
    per §9.4's own instruction, translated to English) and **"Document
    Mapping"** table added before/after "Deliverable 3."
  - **Verification**: every code cell across all 92 cells parses
    (`ast.parse`); the two riskiest hand-ported blocks (prompts, Design D
    helpers) were executed and diff-checked against the real
    `WAPLA_AIG_Engine.py` module directly, not just read visually. A full
    sequential dry-run execution (`DRY_RUN=True`, real HF dataset load,
    real network) was attempted as the closing verification step — see
    the next entry for its outcome once complete.
  - **Self-caught error, disclosed per this project's established
    practice**: an early attempt to append the R45 status correction to
    `spec.md` via a quick Python one-liner had a `content[:-0]` typo
    (`-0 == 0` in Python, so the slice was empty) that silently
    **truncated `spec.md` from 838 lines to 12** — caught immediately by
    a routine `wc -l` sanity check before packaging the Kaggle folder,
    restored in full from this conversation's own earlier verbatim read of
    the file (no data was actually lost, since the full content was still
    in-context), and the append redone correctly via direct file I/O.
    Flagging this explicitly rather than quietly fixing it, matching this
    project's established standard for self-caught mistakes.
  - **Doc sync**: `constitution.md` (new inline R45 implementation-status
    note + v0.13 Amendment Log entry), `spec.md` (v0.9 entry correcting
    the stale "partial, non-conclusive" R45 characterization), and
    `plan.md` (matching v0.10 entry) all now agree that R45/Design D is
    implemented and calibrated, not merely "proposed" or "partial."
- v1.6 (2026-08-20, dry-run verification result — real bug found and
  fixed): the closing `DRY_RUN=True` verification (v1.5 above) initially
  ran clean across all 92 cells (`ast.parse` + real sequential execution,
  real HF dataset load, real network) but an explicit smoke test that
  actually exercised `RUN_PIPELINE_NOW=True` (the real generator→pre-
  filter→judge→backfill loop under the mock) came back **0/6 approved**,
  every attempt failing with `'NoneType' object has no attribute 'group'`.
  Root cause: the notebook's `_mock_generator_response()` (AIG-8) still
  read `TARGET_LETTER: (\w)` out of the generator prompt — but the
  *current* `build_generator_messages()` (position-content decoupling)
  never puts `TARGET_LETTER` in that prompt anymore; the generator always
  writes the correct answer as `option_a`, and `apply_position_shuffle()`
  relocates it mechanically afterward, entirely outside the prompt.
  **This exact same bug was verified present in the currently-shipped
  `WAPLA_AIG_Engine.py` itself** (`_mock_generator_response`, identical
  regex, identical crash — confirmed by directly running `python
  WAPLA_AIG_Engine.py --dry-run --pool-size 3` and observing 0% approval
  with `'NoneType' object has no attribute 'group'` on every attempt) —
  meaning **`--dry-run` mode on the shipped competition script is
  currently broken**, and has been since whichever change removed
  `TARGET_LETTER` from the prompt (a `git blame`/`git log -p` on that one
  line would date it precisely, not yet done). Per this task's explicit
  scope boundary ("não tocar em `WAPLA_AIG_Engine.py` de forma que mude
  comportamento"), **only this notebook's copy of the mock was fixed**
  (rewritten to always place the correct content at `A`, matching the
  real Rule 2 behavior, with a stable per-item hash — trimmed of any
  appended feedback text — replacing the old `(discipline, target_letter,
  target_level)` bucket key since `target_letter` is no longer available
  to the mock at all) — `WAPLA_AIG_Engine.py` itself was left untouched
  and this bug remains live there. **Flagging this prominently for the
  user's own decision**: fixing the shipped script's `--dry-run` mock is
  a trivial, behavior-isolated change (the mock only runs under
  `--dry-run`, never in a real API run) but is a genuine, separate fix
  the user should explicitly authorize, not something bundled silently
  into a "notebook rebuild" task. After the notebook's mock fix, the same
  smoke test (pool_size=6) passed 6/6 approved with a normal
  attempts-histogram and `correct_option` distribution — confirmed
  working, not just non-crashing.
  - **Side effect found and reverted**: running the notebook's real EDA
    cells (Deliverable 1) in this sandboxed verification environment —
    which has no `pt_core_news_sm` spaCy model installed — silently used
    the regex-based Bloom-verb-extraction fallback instead of the real
    spaCy path the original committed analysis used, and in doing so
    **overwrote 7 committed, git-tracked EDA output files**
    (`output/01_overview_distributions.png` through
    `output/06_composite_flaw_count.png`, and `output/eda_summary.txt`)
    with regex-fallback-quality numbers (e.g. "115 items (48.1%) no verb
    detected" instead of the original spaCy-based "96 items (40.2%)").
    Caught via a routine `git status`/`git diff` check before packaging or
    committing anything; all 7 files were restored via `git checkout --`
    to their original, spaCy-computed committed state. The gitignored,
    untracked `output/flaw_summary.csv` was also regenerated with the
    regex-fallback numbers and could **not** be restored the same way (no
    committed history exists for a gitignored file) — harmless for
    anything already delivered (the original real production run already
    consumed its own, correctly-spaCy-computed copy of this file months
    ago and that output is locked in), but worth knowing: a fresh, real
    (non-sandboxed) run of `WAPLA_EDA.ipynb`/this notebook's Deliverable-1
    section, in an environment with spaCy installed, will naturally
    regenerate it correctly again on its own.
  - Also removed several other local, gitignored test-only artifacts this
    verification pass created (`output/aig_engine.log`,
    `output/entregavel_2_100_questoes.dryrun.csv`,
    `output/aig_audit_trail.dryrun.jsonl`,
    `output/_smoketest_audit_trail.jsonl`,
    `output/07_final_position_bias_correction.png`) — none were tracked,
    none affect any deliverable.
  - **Net verification status**: all 92 notebook cells parse and execute
    without error under `DRY_RUN=True`, including a real, non-trivial
    end-to-end smoke test of the actual generator→judge→backfill loop —
    confirmed working, not merely non-crashing. `kaggle_submission_final/`
    was re-populated with the corrected notebook and the now-synced `.md`
    files after this fix.
