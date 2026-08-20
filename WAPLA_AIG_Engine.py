"""WAPLA 2026 -- AIG Refinement Engine (Deliverable 2).

Multi-agent Generator <-> Judge pipeline that repairs the 100 most
structurally flawed rejected items (per output/flaw_summary.csv, produced by
WAPLA_EDA.ipynb) and writes an approved 100-item CSV in the competition's
exact schema.

Architecture reference: spec.md Section 4 ("Multi-Agent Generator <-> Judge
Architecture") and Section 4.2.1 ("Bias-Mitigated Judge Protocol"). Rule
citations (Rn) throughout this file refer to constitution.md.

Deliberate adaptations vs. the literal spec text (documented here once,
referenced by rule number at each call site):

  * spec.md Section 4.2 step 1 describes a *trained* learning-dynamics
    classifier (Seedat's CLLM curator). This deliverable's brief forbids
    training any model, so that stage is reimplemented as a deterministic,
    rule-based MECHANICAL PRE-FILTER -- architecturally the same role (a
    cheap, non-LLM gate that runs before the expensive LLM Judge call), just
    without a trained classifier behind it.
  * spec.md Section 4.2.1 step 1 specifies majority-vote over >= 10 option
    reorderings for MCQ position-bias auditing of the judge. At 100 items x
    up to 3 attempts, that is up to 3,000 extra judge calls just for this
    check. The default here is a single-shuffle "blind-solve" decorrelation
    (still model-agnostic to which letter is being graded); the full
    10-reordering majority vote is available via --rigorous-position-check
    for a smaller or higher-stakes batch.
  * spec.md Section 4.2.1 step 5 (leniency check against a human SME
    baseline) cannot be performed inside a fully automated script -- there
    is no human reviewer here. This is logged as an explicit, unresolved gap
    in the final run summary rather than silently skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import aiohttp
import numpy as np
import pandas as pd

# litellm also calls dotenv.load_dotenv() internally on import (DEV mode by
# default), but that call is made from litellm's own __init__.py deep in
# site-packages -- python-dotenv's frame-based .env discovery walks up from
# THAT file's location, not this script's, and never reaches this project's
# .env when run as `python WAPLA_AIG_Engine.py` (confirmed empirically: it
# only works by accident under `python -c`). Loading it explicitly here,
# before litellm is ever imported, is what actually makes it reliable.
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# 0. Reproducibility
# --------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
RNG = random.Random(SEED)  # dedicated PRNG instance, isolated from any
                             # library that also mutates the global `random`
                             # module state (keeps letter/pattern assignment
                             # deterministic regardless of call order).

# --------------------------------------------------------------------------
# 1. Paths & competition schema
# --------------------------------------------------------------------------
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

FLAW_SUMMARY_PATH = OUTPUT_DIR / "flaw_summary.csv"
DELIVERABLE_PATH = OUTPUT_DIR / "entregavel_2_100_questoes.csv"
AUDIT_TRAIL_PATH = OUTPUT_DIR / "aig_audit_trail.jsonl"
JUDGE_BIAS_AUDIT_PATH = OUTPUT_DIR / "judge_bias_audit_log.json"
LOG_PATH = OUTPUT_DIR / "aig_engine.log"
TOKEN_USAGE_LOG_PATH = OUTPUT_DIR / "aig_token_usage.json"

# --dry-run uses its own output files so a mock/plumbing-validation run can
# never append mock entries into, or overwrite, the real multi-session
# accumulated deliverable/audit-trail produced across actual API runs.
DRYRUN_DELIVERABLE_PATH = OUTPUT_DIR / "entregavel_2_100_questoes.dryrun.csv"
DRYRUN_AUDIT_TRAIL_PATH = OUTPUT_DIR / "aig_audit_trail.dryrun.jsonl"

HF_DATASET_ID = "aiboxlab/ai-generated-questions-quality"

# Exact column order required by the competition (user-specified, distinct
# from the source dataset's internal column order -- see module docstring).
COMPETITION_SCHEMA = [
    "question_id", "question_type", "discipline", "taxonomy_level",
    "base_text", "stem", "assertion_i", "assertion_ii",
    "statement_i", "statement_ii", "statement_iii", "statement_iv",
    "option_a", "option_b", "option_c", "option_d", "option_e",
    "correct_option",
]

OPTION_LETTERS = ["A", "B", "C", "D", "E"]
OPTION_COLS = ["option_a", "option_b", "option_c", "option_d", "option_e"]
LETTER_TO_COL = dict(zip(OPTION_LETTERS, OPTION_COLS))

# "standard" formats have free-text, LLM-authored options where mutual
# exclusivity is a real, checkable risk (R12/R13). "complex_mc" and
# "assertion_reason" options are orchestrator-templated (see
# place_options_at_letters) and mutually exclusive BY CONSTRUCTION -- their
# text legitimately shares heavy boilerplate ("estão corretas", "As duas
# asserções são..."), which would make a naive similarity check on them a
# systematic false-positive generator, not a real quality signal.
QUESTION_FORMAT = {
    "Múltipla Escolha Simples": "standard",
    "Afirmação Incompleta": "standard",
    "Múltipla Escolha Complexa": "complex_mc",
    "Asserção-Razão": "assertion_reason",
}

# --------------------------------------------------------------------------
# 2. Logging
# --------------------------------------------------------------------------
logger = logging.getLogger("wapla_aig_engine")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))
logger.addHandler(_console)


def _attach_file_logging() -> None:
    """Deliberately NOT called at module import time: a FileHandler opened
    in mode='w' at import scope would truncate output/aig_engine.log every
    time this module is imported (e.g. by a test script or a notebook
    reusing its functions), not only when the pipeline actually runs.
    Called once, explicitly, from main_async()."""
    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    logger.addHandler(file_handler)

# --------------------------------------------------------------------------
# 3. Bloom verb bank (constitution.md R10), reused verbatim from
#    WAPLA_EDA.ipynb for narrative/methodological consistency between the
#    diagnosis (EDA) and the repair (this engine).
# --------------------------------------------------------------------------
BLOOM_VERBS_PT: dict[str, list[str]] = {
    "Lembrar": ["definir", "identificar", "listar", "nomear", "reconhecer",
                "recordar", "memorizar", "citar", "enumerar"],
    "Compreender": ["resumir", "explicar", "interpretar", "exemplificar",
                     "parafrasear", "descrever", "traduzir"],
    "Aplicar": ["aplicar", "resolver", "implementar", "demonstrar",
                 "utilizar", "executar", "empregar", "calcular"],
    "Analisar": ["analisar", "organizar", "contrastar", "comparar",
                  "diferenciar", "examinar", "categorizar", "discriminar",
                  "investigar", "distinguir", "classificar"],
    "Avaliar": ["avaliar", "criticar", "julgar", "argumentar", "justificar",
                 "defender", "validar", "ponderar"],
    "Criar": ["criar", "projetar", "compor", "elaborar", "formular",
               "desenvolver", "propor", "planejar", "inventar", "produzir"],
}
LEVEL_ORDER = ["Lembrar", "Compreender", "Aplicar", "Analisar", "Avaliar", "Criar"]
R9_MCQ_LEGAL_LEVELS = {"Lembrar", "Compreender", "Aplicar", "Analisar"}
R9_MCQ_ILLEGAL_LEVELS = {"Avaliar", "Criar"}
VERB_TO_LEVEL = {v: level for level, verbs in BLOOM_VERBS_PT.items() for v in verbs}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


# Canonical, fixed Assercao-Razao answer template (constitution R12/R16:
# mutually-exclusive-by-construction, since each option encodes a distinct
# logical pattern). Kept as literal Python data, never LLM-authored, which
# structurally eliminates verbosity bias for this question_type (R22): every
# item draws from the exact same five, near-equal-length sentences.
ASSERTION_REASON_TEMPLATES: list[dict] = [
    {"pattern": "both_true_ii_justifies_i",
     "text": "As duas asserções são proposições verdadeiras, e a segunda é uma justificativa correta da primeira."},
    {"pattern": "both_true_ii_does_not_justify_i",
     "text": "As duas asserções são proposições verdadeiras, mas a segunda não é uma justificativa correta da primeira."},
    {"pattern": "i_true_ii_false",
     "text": "A primeira asserção é uma proposição verdadeira, e a segunda é uma proposição falsa."},
    {"pattern": "i_false_ii_true",
     "text": "A primeira asserção é uma proposição falsa, e a segunda é uma proposição verdadeira."},
    {"pattern": "both_false",
     "text": "As duas asserções são proposições falsas."},
]

# --------------------------------------------------------------------------
# 4. Verb extraction (Bloom-level detection) -- same spaCy-primary /
#    regex-fallback design as WAPLA_EDA.ipynb, kept import-safe so this
#    script never hard-fails at startup if spaCy or its PT model are
#    unavailable in the grading environment.
# --------------------------------------------------------------------------
_USE_SPACY = False
_NLP = None
try:
    import spacy  # noqa: F401
    try:
        _NLP = spacy.load("pt_core_news_sm")
        _USE_SPACY = True
    except OSError:
        logger.warning("spaCy 'pt_core_news_sm' not found locally; using regex-based verb extraction.")
except ImportError:
    logger.warning("spaCy not installed; using regex-based verb extraction.")

_ARTICLE_PREP = {"a", "o", "as", "os", "de", "da", "do", "das", "dos",
                  "em", "na", "no", "nas", "nos", "um", "uma"}
_VERB_ROOTS = {v: (v[:-2] if len(v) > 5 else v) for v in VERB_TO_LEVEL}


def extract_bloom_levels(text: str) -> set[str]:
    """Returns the set of distinct Bloom levels whose verb bank is matched
    in `text`. Two extraction paths, chosen once at import time via
    _USE_SPACY (see above)."""
    if _USE_SPACY:
        doc = _NLP(str(text))
        return {VERB_TO_LEVEL[tok.lemma_.lower()] for tok in doc
                if tok.pos_ in ("VERB", "AUX") and tok.lemma_.lower() in VERB_TO_LEVEL}

    tokens = re.findall(r"[a-zà-ÿ]+", strip_accents(str(text)).lower())
    levels: set[str] = set()
    for i, tok in enumerate(tokens):
        if i > 0 and tokens[i - 1] in _ARTICLE_PREP:
            continue
        for verb, root in _VERB_ROOTS.items():
            root_noacc = strip_accents(root)
            if tok.startswith(root_noacc) and len(tok) <= len(root_noacc) + 4:
                levels.add(VERB_TO_LEVEL[verb])
                break
    return levels


def build_cognitive_text(row: dict) -> str:
    """Concatenates every field that can carry a Bloom command verb.
    Mirrors WAPLA_EDA.ipynb Section 4.1's fix: for Assercao-Razao and
    Multipla Escolha Complexa, the stem is boilerplate and the real verb
    lives in the assertions/statements."""
    parts = [str(row.get("stem", "") or "")]
    for col in ("assertion_i", "assertion_ii", "statement_i", "statement_ii",
                "statement_iii", "statement_iv"):
        val = row.get(col)
        if val:
            parts.append(str(val))
    return " ".join(parts)


def compute_target_word_count(row: pd.Series) -> Optional[int]:
    """Derive a single concrete word-count target from THIS item's own
    original five options, before generation, so the target reflects this
    item's natural scope rather than an arbitrary constant. All five
    rewritten options are told to hit the SAME target (parity, not
    variety). Originally built for the soft numeric-target approach that
    predates constitution R45; that approach was superseded by R45's
    countdown-marker mechanism, but this target computation was kept and
    is still called from process_item() to supply the shared target that
    the countdown markers (build_generator_messages' ALVO DE CONTAGEM
    REGRESSIVA line) count down to. Returns None if the original options
    aren't available (falls back to no injected target)."""
    lengths = [len(str(row.get(col)).split())
               for col in ("option_a", "option_b", "option_c", "option_d", "option_e")
               if pd.notna(row.get(col))]
    if not lengths:
        return None
    return max(3, round(sum(lengths) / len(lengths)))


def describe_word_count_violations(item: "GeneratedItem", target: int, tolerance: int = 2) -> list[str]:
    """Reports the EXACT numeric miss per option against the target
    computed by compute_target_word_count(), independent of and additional
    to check_verbosity()'s own pass/fail reasons (that function is
    deliberately left unchanged -- this is a generation-side prompt aid,
    not a filter change). Called with tolerance=2 by the pre-R45 soft
    target and with tolerance=0 by constitution R45's exact countdown
    target (see process_item()'s mechanical_reject branch) -- same
    function, two different tolerance regimes. Only meaningful for the
    'standard' format, where option text is actually LLM-authored."""
    lo, hi = target - tolerance, target + tolerance
    violations = []
    for col in ("option_a", "option_b", "option_c", "option_d", "option_e"):
        n = len(getattr(item, col).split())
        if n < lo or n > hi:
            violations.append(f"{col} teve {n} palavras (alvo era {lo}-{hi}).")
    return violations


_COUNTDOWN_MARKER_RE = re.compile(r"<(\d+)>")


def strip_countdown_markers(text: str) -> str:
    """Design D (constitution R45, Xie & Lee 2508.13805 'CAPEL'): mechanically
    strips the model's visible <k> countdown markers from a generated option
    string, reconstructing clean prose -- never trusts the model to
    self-transcribe a clean version, since the markers are a fixed,
    regex-detectable format and stripping them is 100% deterministic. A
    no-op (returns text unchanged, modulo whitespace collapsing) when no
    markers are present, so this is safe to call on non-compliant output
    too -- it just falls through to check_verbosity()'s existing checks
    unchanged, same as any other generation failure."""
    stripped = _COUNTDOWN_MARKER_RE.sub(" ", text)
    return re.sub(r"\s+", " ", stripped).strip()


def describe_countdown_malformation(raw_text: str, target: int) -> Optional[str]:
    """Design D diagnostic ONLY -- does not gate acceptance (that remains
    check_verbosity()'s job on the stripped text, unchanged). Reports
    whether the RAW, pre-strip option text actually followed the CAPEL
    countdown-marker protocol: markers present, strictly decreasing
    target..0 with no skip/repeat, a word between every consecutive pair
    of markers (catches a markers-only tail), and nothing after <0>. Used
    purely to measure how often the generator followed the mechanism."""
    matches = list(_COUNTDOWN_MARKER_RE.finditer(raw_text))
    if not matches:
        return "nenhum marcador de contagem regressiva encontrado (instrução ignorada)."
    values = [int(m.group(1)) for m in matches]
    expected = list(range(target, -1, -1))
    if values != expected:
        return (f"sequência de marcadores incorreta (esperado {target}..0 decrescente "
                f"sem pular/repetir, obteve {values}).")
    for i in range(len(matches) - 1):
        between = raw_text[matches[i].end():matches[i + 1].start()]
        if not between.strip():
            return f"dois marcadores consecutivos sem palavra entre eles (<{values[i]}><{values[i + 1]}>)."
    tail = raw_text[matches[-1].end():]
    if tail.strip():
        return f"texto extra após <0>: {tail.strip()[:40]!r}."
    return None


# One-off remediation override, 2026-08-19: qid -> corrected level, for items
# from entregavel_2_100_questoes_design_d_full.csv that qwen3.6-27b's
# re-audit (tools/reaudit_bloom_qwen.py, output/reaudit_bloom_qwen_pool100.jsonl)
# flagged bloom_alignment_ok=False with reasoning identifying the item as
# genuine recall/recognition content ("Lembrar"/"Compreender"), not real
# Analisar-level demand. Declared "Analisar" was the ORIGINAL dataset's
# label, carried through unchanged by determine_target_level() before this
# override existed -- this is not a generalizable content classifier, it is
# a lookup keyed to already-computed judge evidence for these 50 specific
# question_ids. Does not apply to any question_id outside this dict.
QWEN_BLOOM_DEMOTION_OVERRIDES: dict[int, str] = {
    qid: "Compreender" for qid in [
        26, 29, 106, 132, 138, 246, 364, 374, 392, 457, 483, 489, 516, 519,
        528, 559, 623, 745, 779, 794, 808, 830, 840,
    ]
}


def determine_target_level(original_level: str,
                            question_id: Optional[int] = None) -> tuple[str, bool]:
    """Constitution R9: MCQ format is illegal for Evaluate/Create-level
    content. Since the competition deliverable's schema mandates a
    single-best-answer MCQ output for every item, an item declared
    Avaliar/Criar is demoted to Analisar (the nearest legal MCQ ceiling)
    rather than shipped as a self-contradictory R9 violation. Returns
    (target_level, was_demoted).

    question_id, if given, is checked against QWEN_BLOOM_DEMOTION_OVERRIDES
    first -- the one-off remediation lookup above -- before the R9 check."""
    if question_id is not None and question_id in QWEN_BLOOM_DEMOTION_OVERRIDES:
        return QWEN_BLOOM_DEMOTION_OVERRIDES[question_id], True
    if original_level in R9_MCQ_ILLEGAL_LEVELS:
        return "Analisar", True
    if original_level not in LEVEL_ORDER:
        # Unrecognized/missing declared level: default to the most common
        # legal level in this dataset rather than guessing at random.
        return "Analisar", True
    return original_level, False


# --------------------------------------------------------------------------
# 5. Data loading & candidate pool
# --------------------------------------------------------------------------
def load_original_dataset() -> pd.DataFrame:
    from datasets import load_dataset

    ds = load_dataset(HF_DATASET_ID)
    split_name = "train" if "train" in ds else list(ds.keys())[0]
    if split_name != "train":
        logger.info("Dataset has no 'train' split; using '%s' instead.", split_name)
    return ds[split_name].to_pandas()


def build_candidate_pool(pool_size: Optional[int] = None,
                          exclude_ids: Optional[set[int]] = None) -> pd.DataFrame:
    """Merges flaw_summary.csv (from the EDA pass) with the original
    dataset on question_id, ranks by structural_flaw_count descending
    (ties broken deterministically by question_id), and returns the
    ranked candidate pool the orchestrator will work through.
    `exclude_ids` drops already-approved question_ids from a prior partial
    run (e.g. one interrupted by an API-key/quota switch) before applying
    pool_size, so a resumed run doesn't re-spend quota re-processing items
    that already have an approved deliverable row."""
    if not FLAW_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"{FLAW_SUMMARY_PATH} not found. Run WAPLA_EDA.ipynb first -- "
            f"this engine consumes its structural-flaw diagnosis, it does "
            f"not recompute it."
        )
    flaws = pd.read_csv(FLAW_SUMMARY_PATH)
    original = load_original_dataset()

    merged = original.merge(
        flaws[["question_id", "structural_flaw_count", "flag_position_bias",
               "flag_verbosity_outlier", "flag_bloom_mismatch", "flag_r9_violation",
               "inferred_taxonomy_level_full"]],
        on="question_id", how="inner", validate="one_to_one",
    )
    if len(merged) != len(original):
        logger.warning(
            "flaw_summary.csv covers %d/%d original items; %d could not be "
            "matched and are excluded from the candidate pool.",
            len(merged), len(original), len(original) - len(merged),
        )

    merged = merged.sort_values(
        ["structural_flaw_count", "question_id"], ascending=[False, True]
    ).reset_index(drop=True)

    if exclude_ids:
        before = len(merged)
        merged = merged[~merged["question_id"].isin(exclude_ids)].reset_index(drop=True)
        logger.info("Excluded %d already-approved question_id(s) from a prior partial run; "
                    "%d candidates remain (was %d).", before - len(merged), len(merged), before)

    if pool_size is not None:
        merged = merged.head(pool_size)
    logger.info("Candidate pool built: %d items (flaw_count range %d-%d).",
                len(merged), merged["structural_flaw_count"].max(), merged["structural_flaw_count"].min())
    return merged


def assign_target_letters(n: int) -> list[str]:
    """Constitution R21 (position bias): the correct answer's slot is
    assigned PROGRAMMATICALLY by the orchestrator, not left to the
    generator LLM's own (documented, unreliable) sense of randomness --
    R2-Reasoner/GREEN-style 'control the radical, let the model handle the
    surface realization'. A balanced multiset of A-E, shuffled once with
    the global seed, guarantees a near-uniform correct_option distribution
    in the output by construction rather than by hope."""
    letters = (OPTION_LETTERS * ((n // len(OPTION_LETTERS)) + 1))[:n]
    RNG.shuffle(letters)
    return letters


def assign_assertion_reason_patterns(n: int) -> list[dict]:
    templates = (ASSERTION_REASON_TEMPLATES * ((n // len(ASSERTION_REASON_TEMPLATES)) + 1))[:n]
    RNG.shuffle(templates)
    return templates


def get_assertion_reason_distractors(true_pattern: dict) -> list[str]:
    return [t["text"] for t in ASSERTION_REASON_TEMPLATES if t["pattern"] != true_pattern["pattern"]]


def build_complex_mc_combination(rng: random.Random) -> dict:
    """Multipla Escolha Complexa (see WAPLA_EDA.ipynb Section 4.1): the
    option_a-e texts observed in this dataset are combinatorial phrases
    over the four roman-numeral statements ('I e III estão corretas', ...),
    not free-content distractors. Generating them programmatically --
    rather than asking the LLM to author five paraphrase-style options --
    structurally guarantees mutual exclusivity (R12/R13: each option names
    a distinct statement subset, so at most one can be true) and removes
    the verbosity-bias surface entirely (R22): every option is built from
    the same template, so there is no free-text length to skew. Returns the
    true subset plus four distractor subsets/texts, UNPLACED -- the caller
    assigns letters (see place_options_at_letters) using the corpus-wide
    balanced target_letter, not a per-call shuffle."""
    from itertools import combinations

    numerals = ["I", "II", "III", "IV"]
    all_subsets = [c for size in (2, 3, 4) for c in combinations(numerals, size)]
    true_subset = tuple(rng.sample(all_subsets, 1)[0])
    distractor_pool = [s for s in all_subsets if s != true_subset]
    distractor_subsets = rng.sample(distractor_pool, 4)

    def subset_to_text(subset: tuple) -> str:
        if len(subset) == 1:
            return f"{subset[0]} está correta"
        return f"{', '.join(subset[:-1])} e {subset[-1]} estão corretas"

    return {
        "true_subset": true_subset,
        "true_text": subset_to_text(true_subset),
        "distractor_texts": [subset_to_text(s) for s in distractor_subsets],
    }


def place_options_at_letters(target_letter: str, true_text: str,
                              distractor_texts: list[str], rng: random.Random) -> dict[str, str]:
    """Shared placement logic for both orchestrator-templated formats
    (Multipla Escolha Complexa, Assercao-Razao): the TRUE option goes at
    the corpus-wide-balanced target_letter (R21); the four distractors fill
    the remaining letters in a locally shuffled order (their relative order
    carries no signal, but shuffling avoids any accidental alphabetical
    correlation with subset size/pattern index)."""
    remaining_letters = [l for l in OPTION_LETTERS if l != target_letter]
    shuffled_distractors = list(distractor_texts)
    rng.shuffle(shuffled_distractors)
    placement = {target_letter: true_text}
    placement.update(dict(zip(remaining_letters, shuffled_distractors)))
    return placement


def apply_position_shuffle(item: "GeneratedItem", target_letter: str, item_rng: random.Random) -> None:
    """Decouples content correctness from position (R21) for the 'standard'
    question formats (Multipla Escolha Simples / Afirmacao Incompleta) --
    the generator no longer places the correct answer at TARGET_LETTER
    itself; it always writes the correct answer as option_a (by prompt
    convention) and focuses entirely on making it the genuinely correct
    one. This mechanically relocates already-generated, already-correct
    content to TARGET_LETTER afterward, a pure string-swap on values that
    exist already -- not a generation constraint. Root-cause fix for the
    judge-disagreement pattern diagnosed in calibration (items 63/392/457):
    the generator was reliably satisfying the position requirement without
    reliably ensuring the content placed there was actually correct.
    No-op if the item is already at target_letter (complex_mc/
    assertion_reason formats place correctness at generation time via
    place_options_at_letters already, in generator_agent())."""
    current_correct = item.correct_option.strip().upper()
    if current_correct == target_letter or current_correct not in LETTER_TO_COL:
        return
    true_text = getattr(item, LETTER_TO_COL[current_correct])
    distractor_texts = [getattr(item, LETTER_TO_COL[l]) for l in OPTION_LETTERS if l != current_correct]
    placement = place_options_at_letters(target_letter, true_text, distractor_texts, item_rng)
    for letter, text in placement.items():
        setattr(item, LETTER_TO_COL[letter], text)
    item.correct_option = target_letter


# --------------------------------------------------------------------------
# 6. LLM I/O schemas (validated with pydantic; never trust free-text parsing
#    of a "yes it's fine" reply -- constitution R8/R13: no self-report
#    without independent, structured verification).
# --------------------------------------------------------------------------
from pydantic import BaseModel, Field, ValidationError


class GeneratedItem(BaseModel):
    base_text: Optional[str] = None
    stem: str
    statement_i: Optional[str] = None
    statement_ii: Optional[str] = None
    statement_iii: Optional[str] = None
    statement_iv: Optional[str] = None
    assertion_i: Optional[str] = None
    assertion_ii: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    option_e: str
    generator_notes: Optional[str] = Field(
        default=None,
        description="Brief self-explanation from the Generator Agent -- logged for the "
                     "audit trail, never treated as validation evidence.",
    )
    correct_option: str


class JudgeVerdict(BaseModel):
    blind_solve_reasoning: str
    blind_solve_shuffled_label: str = Field(description="Which shuffled option label "
                                             "(e.g. 'Option 3') the judge independently "
                                             "believes is correct, solving blind.")
    mutual_exclusivity_ok: bool
    length_bias_ok: bool
    bloom_alignment_ok: bool
    factual_soundness_ok: bool
    reasons: list[str] = Field(default_factory=list)
    verdict: Literal["approve", "reject"]


# --------------------------------------------------------------------------
# 7. Mechanical Pre-Filter (spec.md Section 4.2 step 1 analogue) -- cheap,
#    deterministic, non-LLM checks. Runs BEFORE the expensive LLM Judge
#    call so malformed candidates never reach it (spec.md Section 4.2:
#    "the expensive judge only sees pre-filtered candidates").
# --------------------------------------------------------------------------
@dataclass
class PrefilterResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _option_lengths_words(item: GeneratedItem) -> dict[str, int]:
    return {letter: len(getattr(item, col).split())
            for letter, col in LETTER_TO_COL.items()}


def check_position(item: GeneratedItem, target_letter: str) -> Optional[str]:
    """R21: the generator was told exactly which letter must be correct.
    A mismatch is a hard, unambiguous generation failure."""
    if item.correct_option.strip().upper() != target_letter:
        return (f"correct_option must be '{target_letter}' as instructed, "
                f"got '{item.correct_option}'.")
    return None


def check_verbosity(item: GeneratedItem, target_letter: str,
                     max_cv: float = 0.35) -> Optional[str]:
    """R16/R22: the correct option must not be a length outlier. Flags if
    it is the strict max/min among the five, or if the overall coefficient
    of variation of option lengths is unusually high (a proxy for one
    option being conspicuously different in scale from the rest)."""
    lengths = _option_lengths_words(item)
    values = list(lengths.values())
    mean_len = sum(values) / len(values)
    std_len = (sum((v - mean_len) ** 2 for v in values) / len(values)) ** 0.5
    cv = std_len / mean_len if mean_len > 0 else 0.0
    correct_len = lengths[target_letter]

    reasons = []
    if correct_len == max(values) and max(values) != min(values):
        reasons.append(f"Correct option ({target_letter}) is the LONGEST option "
                        f"({correct_len} words vs. mean {mean_len:.1f}).")
    if correct_len == min(values) and max(values) != min(values):
        reasons.append(f"Correct option ({target_letter}) is the SHORTEST option "
                        f"({correct_len} words vs. mean {mean_len:.1f}).")
    if cv > max_cv:
        reasons.append(f"Option-length coefficient of variation is {cv:.2f} "
                        f"(threshold {max_cv}) -- normalize option lengths.")
    return " ".join(reasons) if reasons else None


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(strip_accents(a.lower()).split()), set(strip_accents(b.lower()).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def check_mutual_exclusivity(item: GeneratedItem, max_similarity: float = 0.6) -> Optional[str]:
    """R12/R13: rubric/option mutual exclusivity must be mechanically
    verified, never trusted from the generator's self-report. Uses a
    cheap Jaccard-similarity heuristic over the five options; anything
    above threshold is flagged for the generator to differentiate further."""
    flagged = []
    for i, li in enumerate(OPTION_LETTERS):
        for lj in OPTION_LETTERS[i + 1:]:
            sim = _jaccard(getattr(item, LETTER_TO_COL[li]), getattr(item, LETTER_TO_COL[lj]))
            if sim > max_similarity:
                flagged.append(f"{li}/{lj} (similarity={sim:.2f})")
    if flagged:
        return "Options too similar to be mutually exclusive: " + ", ".join(flagged)
    return None


def check_bloom_verb(item: GeneratedItem, target_level: str) -> Optional[str]:
    """R10: verifies the required level's verb bank is actually present in
    the item's cognitive text (stem + assertions/statements), rather than
    trusting the generator claimed to follow the template."""
    cognitive_text = build_cognitive_text(item.model_dump())
    detected = extract_bloom_levels(cognitive_text)
    if target_level not in detected:
        verb_bank = ", ".join(BLOOM_VERBS_PT[target_level][:5])
        return (f"No '{target_level}'-level verb detected in the item's cognitive "
                f"text. Use one of: {verb_bank}, ...")
    return None


def run_mechanical_prefilter(item: GeneratedItem, target_letter: str,
                              target_level: str, question_type: str) -> PrefilterResult:
    fmt = QUESTION_FORMAT.get(question_type, "standard")
    checks = [
        check_position(item, target_letter),
        check_verbosity(item, target_letter),
        check_bloom_verb(item, target_level),
    ]
    if fmt == "standard":
        # Mutual exclusivity is only a meaningful, checkable risk for
        # free-text options; complex_mc/assertion_reason options are
        # templated and exclusive by construction (see QUESTION_FORMAT
        # docstring above).
        checks.append(check_mutual_exclusivity(item))
    reasons = [c for c in checks if c]
    return PrefilterResult(passed=not reasons, reasons=reasons)


# --------------------------------------------------------------------------
# 8. LLM client abstraction -- litellm preferred (uniform interface across
#    providers, per the user's request to "swap models/endpoints easily"),
#    falling back to the plain `openai` package (also endpoint-swappable via
#    base_url) if litellm is unavailable in the runtime environment, and a
#    deterministic offline mock for --dry-run testing without API costs/keys.
# --------------------------------------------------------------------------
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

DRY_RUN = False  # set by main() from --dry-run; read by call_llm()

# Local Ollama server (litellm provider "ollama_chat" or "ollama") or a
# locally-served vLLM instance ("vllm_local", this pipeline's own provider
# string -- see _parse_vllm_model_string/_vllm_direct_chat below) has no
# API rate limits or per-day token quotas -- unlike the hosted providers
# this pipeline was originally calibrated against (Groq, Gemini), so both
# the TPM inter-item pacing (_inter_item_pacing_seconds, already gated on
# provider == "groq") and the TPD daily-quota guard (DailyTokenBudget,
# gated below in main_async) should not apply to either.
_LOCAL_PROVIDERS = {"ollama_chat", "ollama", "vllm_local"}


def _is_local_model(model: str) -> bool:
    return model.split("/")[0].lower() in _LOCAL_PROVIDERS


# --------------------------------------------------------------------------
# 7c. Local Ollama calls BYPASS litellm entirely (see _ollama_direct_chat
#     below) rather than going through litellm.acompletion(). Root-cause
#     history, so a future reader doesn't re-litigate this:
#
#     1. A real run aborted mid-load ("client connection closed before
#        llama-server finished loading, aborting load") around ~300-400s,
#        even after explicitly setting litellm.request_timeout=600 (the
#        one lever litellm 1.55.0's ollama_chat handler actually reads for
#        its total request timeout -- confirmed by reading main.py: unlike
#        e.g. its "triton" branch, the ollama_chat branch never passes a
#        per-call `timeout=` kwarg into ollama_chat.get_ollama_response()
#        at all; only the GLOBAL litellm.request_timeout attribute reaches
#        `aiohttp.ClientTimeout(total=litellm.request_timeout)` inside
#        ollama_acompletion()).
#     2. Hypothesized a hardcoded aiohttp sub-timeout (sock_read/
#        sock_connect) shorter than `total` -- checked directly against
#        aiohttp 3.14.1's ClientTimeout dataclass and litellm's
#        construction of it: litellm passes ONLY `total=`, leaving
#        connect/sock_read/sock_connect at their attrs default of `None`
#        (aiohttp semantics: None means no separate sub-timeout, `total`
#        alone governs the whole request). Also checked for any internal
#        `asyncio.wait_for`/wrapper timeout around completion()/
#        acompletion() -- litellm ships a `timeout()` decorator
#        (litellm/timeout.py) but it is only ever exported for external
#        use, never applied internally to the ollama_chat code path.
#        Conclusion: litellm's OWN source does not explain the ~300-400s
#        cutoff -- the exact mechanism (a different internal path, a
#        cluster-side network/proxy layer, or NFS cache-state variance
#        between attempts) could not be pinned down further without
#        reproducing it live on the cluster, which this environment has no
#        access to.
#     3. A direct `curl` against Ollama's /api/chat endpoint for the same
#        model succeeded end-to-end (~172s total, per Ollama's own
#        load_duration field) -- proving Ollama, the network, and the
#        cluster are NOT the problem; whatever litellm-side mechanism is
#        truncating the request, bypassing litellm's abstraction entirely
#        for local calls and issuing the same request shape ourselves
#        (full control over aiohttp.ClientTimeout, not mediated by
#        anything internal to litellm) is the pragmatic fix, matching the
#        proven-working curl shape exactly. This ALSO fixes the `keep_alive`
#        caveat noted below for free, since our own request body puts it
#        at the correct top-level field Ollama's API actually expects,
#        rather than however litellm's ollama_chat handler would place it.
#
#     Groq calls are entirely unaffected: they never enter
#     _ollama_direct_chat (gated on _is_local_model) and keep using
#     litellm's groq branch, which passes its own per-call `timeout` kwarg
#     through a separate code path that never reads litellm.request_timeout.
# --------------------------------------------------------------------------

# Ollama's own /api/chat default keep_alive is 5 minutes of idle; an
# unlucky combination of judge retries/backoff could exceed that between
# one item's last call and the next item's first call, forcing an
# avoidable reload (confirmed ~168s on this project's NFS-backed /home for
# the first load; subsequent warm calls are <1s). Overridable via
# --ollama-keep-alive for a longer-running batch. Sent as a genuine
# top-level field in our own request body (see _ollama_direct_chat) --
# unlike the now-abandoned litellm-mediated attempt, this one actually
# reaches the field Ollama's API documents, but still verify with
# `ollama ps` during a real run since it hasn't been confirmed live.
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"

# Passed as aiohttp.ClientTimeout(total=...) on our OWN ClientSession in
# _ollama_direct_chat -- full control, not mediated by litellm's internal
# (and, per the investigation above, not fully explained) timeout
# behavior. ROOT CAUSE CONFIRMED (2026-08, live curl testing on
# cluster-node7): NOT a code bug -- the *same* curl command against the
# *same* model measured 172s, >300s (failed), and 7.8s (warm cache) across
# three attempts, purely from this shared cluster's NFS storage-contention
# variability. 900s (15 min) leaves generous margin above the observed
# worst case while still bounded -- a genuinely hung request eventually
# gets classified as TransientLLMError and retried (see process_item's
# generator/judge call-error handling) rather than hanging forever.
DEFAULT_OLLAMA_LOAD_TIMEOUT = 900

# Sent as options.num_ctx in our own request body (see _ollama_direct_chat)
# -- this was already a genuine, correctly-forwarded OllamaChatConfig field
# under litellm too, so bypassing litellm for local calls doesn't change
# its correctness, only where it's constructed. Default sized generously
# above this pipeline's actual worst-case prompt: the longest base_text in
# the full 239-item candidate pool (question_id 772) produces a ~1660-token
# generator prompt and ~730-token judge prompt (litellm.token_counter,
# cl100k approximation) -- 8192 leaves roughly 5x headroom over that
# worst case even after adding a generous completion-token budget, while
# still shrinking the KV-cache allocation well below the model's default
# 262,144-token context window.
DEFAULT_OLLAMA_NUM_CTX = 8192

DEFAULT_OLLAMA_HOST = "http://localhost:11434"

_LITELLM = None
_OPENAI_ASYNC_CLIENT = None
try:
    import litellm
    _LITELLM = litellm
    litellm.suppress_debug_info = True
except ImportError:
    try:
        from openai import AsyncOpenAI
        _OPENAI_ASYNC_CLIENT = AsyncOpenAI()
    except ImportError:
        pass  # fine in --dry-run; enforced at startup otherwise (see main())


class TransientLLMError(RuntimeError):
    """Raised for retryable failures: rate limits, timeouts, 5xx."""


# --------------------------------------------------------------------------
# 7b. Daily token-quota guard -- Groq's free/on-demand tier enforces a
#     tokens-per-DAY (TPD) cap (200,000 observed for this account) on top of
#     the per-minute (TPM) limit already handled by the pacing/retry-after
#     logic below. Burning through TPD mid-batch means every remaining item
#     for the rest of the day fails with repeated 429s -- confirmed the hard
#     way in the 2026-07-18 run (see aig_audit_trail.jsonl). Rather than
#     grinding into that wall, this tracks real per-call token usage
#     (from each response's `.usage.total_tokens`), persists it to disk so
#     it survives across separate `python WAPLA_AIG_Engine.py` invocations
#     on the same day, and stops the run BEFORE the next call once a
#     configurable soft cap is reached -- leaving headroom under the real
#     TPD limit instead of discovering it via failures.
# --------------------------------------------------------------------------
class DailyTokenBudget:
    """Persists cumulative token usage for the current calendar day to
    `path`, resetting automatically when the date rolls over (matching
    Groq's TPD reset). Not process-safe across truly concurrent processes,
    but sufficient for this pipeline's single-process, --concurrency 1
    usage pattern -- the lock only serializes concurrent coroutines within
    one run."""

    def __init__(self, path: Path, soft_cap: int):
        self.path = path
        self.soft_cap = soft_cap
        self._lock = asyncio.Lock()
        self.date, self.cumulative_tokens = self._load()

    @staticmethod
    def _today() -> str:
        return datetime.now().date().isoformat()

    def _load(self) -> tuple[str, int]:
        today = self._today()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("date") == today:
                    return today, int(data.get("cumulative_tokens", 0))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                logger.warning("Could not parse %s; starting today's token count at 0.", self.path)
        return today, 0

    def _save(self) -> None:
        self.path.write_text(
            json.dumps({"date": self.date, "cumulative_tokens": self.cumulative_tokens}, indent=2),
            encoding="utf-8",
        )

    def _roll_over_if_new_day(self) -> None:
        today = self._today()
        if today != self.date:
            logger.info("Daily token budget rolled over (%s -> %s); cumulative usage reset to 0.",
                        self.date, today)
            self.date, self.cumulative_tokens = today, 0
            self._save()

    async def record(self, tokens: int) -> None:
        async with self._lock:
            self._roll_over_if_new_day()
            self.cumulative_tokens += max(0, tokens)
            self._save()

    async def would_exceed(self, estimate: int) -> bool:
        async with self._lock:
            self._roll_over_if_new_day()
            return (self.cumulative_tokens + estimate) > self.soft_cap


# Conservative per-call estimate used only for the PRE-call would_exceed()
# check -- actual usage recorded post-call is exact (from response.usage).
# Calibrated against real Groq 429 "Requested" token counts observed live
# during the 2026-07-18 run (range ~1800-3700 per single generator/judge
# call on this pipeline's prompts).
DEFAULT_PRE_CALL_TOKEN_ESTIMATE = 4000
DEFAULT_DAILY_TOKEN_SOFT_CAP = 180_000

# Set by main_async() before the pipeline runs (None in --dry-run, where no
# real tokens are spent and the persisted real counter must stay untouched).
_daily_budget: Optional["DailyTokenBudget"] = None


# Precise 5xx match on word boundaries -- e.g. "code': 503" or "Error 502" --
# replaces a bare "5" substring check, which false-positives on any message
# containing an unrelated digit 5 (a date, a count, part of an unrelated
# number). Confirmed live against a real Gemini 503 "high demand" response
# during setup validation.
_HTTP_5XX_RE = re.compile(r"\b(500|502|503|504)\b")

# Groq's rate-limit error body includes the exact wait time in prose, in one
# of three observed formats: "Please try again in 970ms" (sub-second),
# "...in 4.1325s" (seconds), or "...in 19m14.304s" (the much longer
# daily-quota variant) -- all three confirmed live during calibration. The
# "ms" alternative is tried first so "...970ms" isn't misread as an "m"
# (minutes) prefix with no seconds digits following it.
_RETRY_AFTER_RE = re.compile(
    r"try again in (?:(?P<ms>\d+(?:\.\d+)?)ms|(?:(?P<min>\d+(?:\.\d+)?)m)?(?P<sec>\d+(?:\.\d+)?)s)",
    re.IGNORECASE,
)


def _parse_retry_after_seconds(exc: BaseException, safety_margin: float = 2.0) -> Optional[float]:
    """Extracts Groq's actual reported rate-limit reset time so a retry can
    sleep the EXACT duration requested instead of guessing via a generic
    backoff schedule -- process_item()'s outer attempt loop uses this after
    a generator_call_error, since guessing (fixed inter-item pacing alone)
    left retries 2-4 within the same item colliding with the same tight TPM
    budget (confirmed: 40/60 attempts still rate-limited in that trial,
    concentrated in retries, not first attempts). Prefers an HTTP
    Retry-After response header when the exception chain exposes one
    (litellm's typed exceptions carry `.response` via openai.APIStatusError);
    falls back to parsing Groq's message text, the only signal actually
    observed in practice so far."""
    seen: Optional[BaseException] = exc
    for _ in range(5):
        if seen is None:
            break
        response = getattr(seen, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        if headers:
            header = headers.get("retry-after") or headers.get("Retry-After")
            if header:
                try:
                    return float(header) + safety_margin
                except ValueError:
                    pass
        seen = getattr(seen, "__cause__", None)

    match = _RETRY_AFTER_RE.search(str(exc))
    if match:
        if match.group("ms") is not None:
            return float(match.group("ms")) / 1000.0 + safety_margin
        minutes = float(match.group("min")) if match.group("min") else 0.0
        seconds = float(match.group("sec"))
        return minutes * 60 + seconds + safety_margin
    return None


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(TransientLLMError),
)
def _reasoning_effort_for_model(model: str) -> Optional[str]:
    """Groq's OpenAI-compatible endpoint -- and, identically, a local Ollama
    server via litellm's ollama_chat/ollama providers -- accepts and honors
    `reasoning_effort` for reasoning-capable models of these two vendor
    families (litellm 1.55.0 has no special-cased support for this param,
    it just forwards unrecognized kwargs through, and the underlying
    inference server itself applies it). Without it, Qwen3.6 emits a full
    <think>...</think> block before its answer on this pipeline's generator
    prompt (measured: 7110 chars of reasoning vs. 1517 chars of clean,
    complete JSON with reasoning_effort='none' on an identical prompt) --
    this is the actual fix for the JSON-parsing failures that model
    produced, not a prompt-wording issue. GPT-OSS models also support it;
    'low' was confirmed clean (no <think>, no trailing commentary) on this
    pipeline's judge prompt shape. Vendor detection (by model-name prefix,
    after stripping the provider prefix / an "openai/" vendor-directory
    prefix / an Ollama ":tag" suffix) mirrors _model_family()'s -- both
    functions need to key off the same underlying vendor regardless of
    which of these two multi-vendor providers is hosting it, and this one
    was originally left Groq-only when _model_family() was generalized for
    R26, silently reproducing the same <think>-block JSON-parsing failure
    on an ollama_chat/qwen3.6 run. Unset (None) for every other vendor/
    provider, since passing an unrecognized param to a provider/model that
    doesn't support it is an unnecessary risk this pipeline hasn't tested.

    Deliberately gated on the NARROWER _REASONING_EFFORT_PROVIDERS, not
    _model_family()'s _MULTI_VENDOR_PROVIDERS -- vllm_local is excluded on
    purpose (see _REASONING_EFFORT_PROVIDERS' own comment): vLLM's
    OpenAI-compatible server has no CONFIRMED equivalent request-level
    param, and the intended lever there is server-side (`--reasoning-parser
    qwen3` at launch time), not a per-request field this function would
    supply. Returning None for vllm_local is a deliberate "don't send an
    untested field" choice, not a gap to fill in later without checking
    vLLM's actual behavior first."""
    provider, _, rest = model.partition("/")
    provider_lower = provider.lower()
    if provider_lower not in _REASONING_EFFORT_PROVIDERS or not rest:
        return None
    name = rest[len("openai/"):] if rest.startswith("openai/") else rest
    name_lower = name.split(":")[0].lower()
    if name_lower.startswith("qwen"):
        return "none"
    if name_lower.startswith("gpt-oss"):
        return "low"
    return None


async def _record_usage(resp) -> None:
    """Feeds a completion response's exact token usage into the daily
    budget tracker, if one is active (real, non-dry-run run). Both litellm
    and the plain openai SDK expose `.usage.total_tokens` on the same
    response shape, so this one helper covers both call_llm backends."""
    if _daily_budget is None:
        return
    usage = getattr(resp, "usage", None)
    total = getattr(usage, "total_tokens", None) if usage is not None else None
    if isinstance(total, (int, float)) and total > 0:
        await _daily_budget.record(int(total))


# Set by main_async() from --ollama-keep-alive/--ollama-load-timeout/
# --ollama-num-ctx; read by call_llm(). All three only apply to
# ollama_chat/ollama models (see _is_local_model). NOTE keep_alive is kept
# here (harmless if it's a no-op -- see the CAVEAT on DEFAULT_OLLAMA_
# KEEP_ALIVE above) but, unlike num_ctx and the litellm.request_timeout
# global set in call_llm() below, it is NOT confirmed to actually reach
# Ollama on litellm 1.55.0 -- verify with `ollama ps` during a real run.
_OLLAMA_KEEP_ALIVE = DEFAULT_OLLAMA_KEEP_ALIVE
_OLLAMA_LOAD_TIMEOUT = DEFAULT_OLLAMA_LOAD_TIMEOUT
_OLLAMA_NUM_CTX = DEFAULT_OLLAMA_NUM_CTX


class _LocalHTTPError(Exception):
    """Raised for a non-200 response from a direct local-backend call
    (Ollama or vLLM). Deliberately NOT a RuntimeError subclass --
    call_llm()'s `except RuntimeError: raise` is reserved for permanent
    config errors (e.g. "no backend available"), and this needs to flow
    into the generic `except Exception` branch below so status_code-based
    TransientLLMError classification still applies."""

    def __init__(self, backend: str, status_code: int, body: str):
        super().__init__(f"{backend} HTTP {status_code}: {body[:500]}")
        self.status_code = status_code


# --------------------------------------------------------------------------
# 7d. Local vLLM calls -- a SECOND local backend alongside Ollama, added
#     once NFS storage-contention on the shared cluster made per-request
#     model (re)loading via Ollama unreliable (see the "Local Ollama calls
#     BYPASS litellm entirely" block above). vLLM instead runs as a
#     long-lived, already-warm OpenAI-compatible server per model (weights
#     on local /tmp, not NFS-backed $HOME), so there is no load-timeout
#     concern analogous to Ollama's -- only a per-request generation
#     timeout, sized much tighter than Ollama's 900s as a result.
#
#     Model string format: "vllm_local/<served-model-name>@<port>", e.g.
#     "vllm_local/gpt-oss-20b@8000". The port is REQUIRED and always
#     explicit -- each vLLM server here is a single-model instance on its
#     own port, and silently guessing/defaulting a port would risk routing
#     a judge call to the generator's server (or vice versa) with no error
#     until the wrong model's response shape or content looks obviously
#     wrong. <served-model-name> is sent verbatim as the request's "model"
#     field AND is what _model_family()'s vendor-prefix matching keys off
#     of (via the shared _MULTI_VENDOR_PROVIDERS/_HOSTED_MODEL_VENDOR_
#     PREFIXES machinery -- "gpt-oss-20b@8000".startswith("gpt-oss") is
#     still True, so the "@port" suffix doesn't interfere with vendor
#     detection) -- use `vllm serve ... --served-model-name <short-name>`
#     when launching the server so this stays a short, clean, vendor-
#     prefixed name (e.g. "gpt-oss-20b") rather than the full weights path,
#     which would NOT match any vendor prefix and would fall back to the
#     conservative "same family" default, incorrectly blocking a legitimate
#     generator/judge pairing under R26.
# --------------------------------------------------------------------------
DEFAULT_VLLM_REQUEST_TIMEOUT = 120  # seconds; a warm vLLM server has no Ollama-style
                                      # load-time concern, just generation latency --
                                      # generous margin over this pipeline's few-thousand-
                                      # token prompts, tightened well below Ollama's 900s.
_VLLM_REQUEST_TIMEOUT = DEFAULT_VLLM_REQUEST_TIMEOUT


def _parse_vllm_model_string(rest: str) -> tuple[str, int]:
    """`rest` is everything after the 'vllm_local/' prefix. Port is
    required (see the module comment above for why silently defaulting one
    is actively dangerous here, not just inconvenient)."""
    if "@" not in rest:
        raise ValueError(
            f"vllm_local model string must be 'vllm_local/<served-model-name>@<port>' "
            f"(e.g. 'vllm_local/gpt-oss-20b@8000'); got 'vllm_local/{rest}' with no '@<port>'."
        )
    name, _, port_str = rest.rpartition("@")
    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(
            f"vllm_local model string has a non-integer port ('{port_str}' from "
            f"'vllm_local/{rest}')."
        ) from None
    return name, port


def _vllm_api_base(port: int) -> str:
    host = os.environ.get("VLLM_HOST", "localhost")
    return f"http://{host}:{port}/v1/chat/completions"


async def _vllm_direct_chat(messages: list[dict], model: str, temperature: float,
                             response_format_json: bool) -> str:
    """vLLM's OpenAI-compatible /v1/chat/completions endpoint -- standard
    request/response shape (unlike Ollama's own /api/chat), so this is
    simpler than _ollama_direct_chat and reuses aiohttp directly rather
    than needing a bespoke payload shape. No reasoning_effort equivalent
    is sent -- see _reasoning_effort_for_model's docstring for why that's
    deliberate, not an oversight, and UNCONFIRMED without cluster access:
    check a raw judge response for a stray <think> block during the
    calibration trial; if present, vLLM's `--reasoning-parser` flag
    (already passed at server-launch time per this run's setup) not fully
    separating reasoning from content would be the next thing to check."""
    _, _, rest = model.partition("/")
    served_name, port = _parse_vllm_model_string(rest)
    payload: dict = {
        "model": served_name,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    timeout = aiohttp.ClientTimeout(total=_VLLM_REQUEST_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_vllm_api_base(port), json=payload) as resp:
                body_text = await resp.text()
                if resp.status != 200:
                    raise _LocalHTTPError("vLLM", resp.status, body_text)
                data = json.loads(body_text)
    except asyncio.TimeoutError as exc:
        # Same "timeout" (not "timed out") wording requirement as
        # _ollama_direct_chat's identical handler -- call_llm()'s
        # classification matches the literal substring "timeout".
        raise TimeoutError(
            f"vLLM request hit the {_VLLM_REQUEST_TIMEOUT}s timeout "
            f"(model={served_name}, port={port})"
        ) from exc
    return data["choices"][0]["message"]["content"]


def _ollama_api_base() -> str:
    base = (
        os.environ.get("OLLAMA_HOST")
        or os.environ.get("OLLAMA_API_BASE")
        or DEFAULT_OLLAMA_HOST
    ).rstrip("/")
    return base if base.endswith("/api/chat") else f"{base}/api/chat"


async def _ollama_direct_chat(messages: list[dict], model: str, temperature: float,
                               response_format_json: bool,
                               reasoning_effort: Optional[str]) -> str:
    """Bypasses litellm entirely for ollama_chat/ollama models -- see the
    "Local Ollama calls BYPASS litellm entirely" comment block above
    DEFAULT_OLLAMA_KEEP_ALIVE for why. Mirrors the exact request shape a
    direct `curl` already confirmed working end-to-end against this same
    /api/chat endpoint: a plain aiohttp POST with model/messages/options/
    keep_alive at the top level, and our OWN aiohttp.ClientTimeout (total=
    _OLLAMA_LOAD_TIMEOUT) -- not mediated by litellm's internal (and, per
    the investigation above, not fully explained) timeout handling.
    `reasoning_effort` is passed inside "options" on a best-effort basis --
    UNCONFIRMED whether Ollama's chat template for qwen3.6/gpt-oss actually
    honors that key the way Groq's hosted endpoint does; check the judge's
    raw response for a stray <think>...</think> block during the
    calibration trial, and if it's still there, Ollama's documented
    top-level `"think": false` field (for hybrid-reasoning models) is the
    more likely correct native lever to try next."""
    _, _, rest = model.partition("/")
    ollama_model = rest or model
    options: dict = {"num_ctx": _OLLAMA_NUM_CTX, "temperature": temperature}
    if reasoning_effort is not None:
        options["reasoning_effort"] = reasoning_effort

    payload: dict = {
        "model": ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": _OLLAMA_KEEP_ALIVE,
        "options": options,
    }
    if response_format_json:
        payload["format"] = "json"

    timeout = aiohttp.ClientTimeout(total=_OLLAMA_LOAD_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_ollama_api_base(), json=payload) as resp:
                body_text = await resp.text()
                if resp.status != 200:
                    raise _LocalHTTPError("Ollama", resp.status, body_text)
                data = json.loads(body_text)
    except asyncio.TimeoutError as exc:
        # aiohttp's own TimeoutError str is often empty -- re-raise with an
        # explicit message containing the literal substring "timeout" (not
        # "timed out") since that's exactly what call_llm()'s classification
        # matches on -- verified live: an earlier "timed out" wording here
        # silently failed to reclassify and leaked a bare TimeoutError.
        raise TimeoutError(
            f"Ollama request hit the {_OLLAMA_LOAD_TIMEOUT}s timeout "
            f"(model={ollama_model})"
        ) from exc
    return data["message"]["content"]


async def call_llm(messages: list[dict], model: str, temperature: float = 0.4,
                    response_format_json: bool = True) -> str:
    """Single point of contact with the outside world. Wrapped in
    exponential-backoff retry for TRANSIENT failures (network/rate-limit) --
    distinct from the content-quality retry loop in process_item(), which
    handles the Generator/Judge disagreeing about substance, not the API
    being flaky."""
    if DRY_RUN:
        return _mock_llm_call(messages, model)

    reasoning_effort = _reasoning_effort_for_model(model)
    provider = model.split("/", 1)[0].lower()

    try:
        if provider == "vllm_local":
            return await _vllm_direct_chat(messages, model, temperature, response_format_json)
        if provider in ("ollama_chat", "ollama"):
            return await _ollama_direct_chat(
                messages, model, temperature, response_format_json, reasoning_effort,
            )
        if _LITELLM is not None:
            kwargs = {"model": model, "messages": messages, "temperature": temperature}
            if response_format_json:
                kwargs["response_format"] = {"type": "json_object"}
            if reasoning_effort is not None:
                kwargs["reasoning_effort"] = reasoning_effort
            resp = await _LITELLM.acompletion(**kwargs)
            await _record_usage(resp)
            return resp.choices[0].message.content
        elif _OPENAI_ASYNC_CLIENT is not None:
            kwargs = {"model": model, "messages": messages, "temperature": temperature}
            if response_format_json:
                kwargs["response_format"] = {"type": "json_object"}
            if reasoning_effort is not None:
                kwargs["reasoning_effort"] = reasoning_effort
            resp = await _OPENAI_ASYNC_CLIENT.chat.completions.create(**kwargs)
            await _record_usage(resp)
            return resp.choices[0].message.content
        else:
            raise RuntimeError(
                "No LLM backend available: install `litellm` or `openai`, "
                "or run with --dry-run."
            )
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 -- provider SDKs raise varied types
        message = str(exc).lower()
        # Prefer the exception's actual HTTP status_code when the provider
        # SDK exposes one (litellm's typed exceptions -- RateLimitError,
        # ServiceUnavailableError, InternalServerError, etc. -- all subclass
        # openai.APIStatusError, which sets this reliably); this is exact,
        # unlike matching digits inside a free-text message. Falls back to
        # a word-boundary regex on the message for any exception type that
        # doesn't carry status_code (e.g. bare connection failures).
        status_code = getattr(exc, "status_code", None)
        is_5xx_or_429 = status_code in (429, 500, 502, 503, 504) or bool(_HTTP_5XX_RE.search(message))
        if is_5xx_or_429 or any(tok in message for tok in ("rate limit", "timeout", "overloaded", "connection")):
            raise TransientLLMError(str(exc)) from exc
        raise


def extract_json(text: str) -> dict:
    """Strips markdown code fences and locates the first {...} block.
    LLMs frequently wrap JSON in ```json fences despite instructions not
    to; this is defensive parsing, not a substitute for response_format."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")
    return json.loads(match.group(0))


# --------------------------------------------------------------------------
# 9. Prompt builders
# --------------------------------------------------------------------------
GENERATOR_SYSTEM_PROMPT = """Você é o Generator Agent de um pipeline de \
Automated Item Generation (AIG). Sua tarefa é REESCREVER uma questão de \
múltipla escolha que foi REJEITADA por falhas estruturais, produzindo uma \
versão corrigida.

REGRAS OBRIGATÓRIAS (não negociáveis):
1. CONTROLE DE COMPRIMENTO POR CONTAGEM REGRESSIVA VISÍVEL (Design D -- \
substitui a normalização por faixa aproximada; evita viés de \
comprimento): as cinco opções (A-E) devem ter \
EXATAMENTE o mesmo número de palavras, informado abaixo como ALVO DE \
CONTAGEM REGRESSIVA -- não uma faixa aproximada. Para CADA uma das cinco \
opções, gere o texto intercalando marcadores de contagem regressiva \
visíveis com as palavras, em vez de apenas contar mentalmente:
   a. Para cada inteiro k do alvo até 1: escreva o marcador <k> \
imediatamente seguido de UMA palavra (pontuação pode ficar grudada à \
palavra; sem espaço interno dentro do marcador ou entre marcador e \
palavra).
   b. Após a palavra pareada com <1>, escreva <0> e finalize aquela \
opção -- nenhum texto depois de <0>.
   c. Marcadores e pontuação NÃO contam como palavra -- apenas as \
palavras em si contam para o alvo.
   d. Se estiver ficando com poucas palavras, NÃO termine com marcadores \
vazios em sequência -- adicione conteúdo novo e significativo até \
completar o alvo.
   e. Os números devem decrescer estritamente de 1 em 1 (sem pular, sem \
repetir), e nunca dois marcadores seguidos sem uma palavra entre eles.

EXEMPLO CORRETO (alvo=5): <5>Olá,<4>mundo!<3>Como<2>vai<1>você?<0>
ERROS TÍPICOS A EVITAR:
- Parar cedo / sem <0>: <5>Rápido<4>demo<3>termina<0>
- Marcador duplicado: <5>Errado<4>marcador<3>de novo<2>aqui<1>agora<0><0>
- Cauda só de marcadores: <7>Começa<6>bem<5>então<4>para.<3><2><1><0>

O sistema removerá os marcadores automaticamente depois de gerados -- sua \
única responsabilidade é produzir o número exato de marcadores e \
palavras por opção, para as cinco opções (A-E). Se nenhum ALVO DE \
CONTAGEM REGRESSIVA for informado abaixo (formato sem opções de texto \
livre), esta regra não se aplica.
2. CORREÇÃO COMO PRIORIDADE MÁXIMA (substitui a exigência de posição fixa \
-- o reposicionamento da resposta correta é feito mecanicamente por outro \
componente do sistema, depois da geração, então você NÃO precisa e NÃO deve se \
preocupar com em qual letra a resposta correta vai terminar): avalie cada \
alternativa com rigor factual e lógico antes de decidir qual é a \
genuinamente mais correta e melhor sustentada pelo cenário/definição \
apresentados -- não a mais conveniente ou a que "parece" certa \
superficialmente. ESCREVA SEMPRE a resposta correta como option_a, e as \
quatro alternativas claramente incorretas, parciais ou fora de contexto \
como option_b, option_c, option_d, option_e. O campo correct_option deve \
ser sempre "A".
3. VERBO DE BLOOM OBRIGATÓRIO: o texto cognitivo do item \
(stem, e quando aplicável, assertion_i/ii ou statement_i-iv) DEVE conter \
pelo menos um verbo do banco de verbos do nível TARGET_LEVEL fornecido \
abaixo -- não use verbos de outro nível taxonômico. EXEMPLO CONCRETO: se \
TARGET_LEVEL_VERB_BANK contiver "analisar", o stem deve abrir de forma \
semelhante a: "Ao analisar [cenário apresentado], é correto afirmar \
que..." -- o verbo do banco precisa aparecer LITERALMENTE no texto, não \
apenas de forma implícita. AUTOVERIFICAÇÃO OBRIGATÓRIA: antes de \
finalizar, releia o stem e confirme que ele contém literalmente uma das \
palavras do TARGET_LEVEL_VERB_BANK -- se não contiver, reescreva o stem \
antes de responder.
4. EXCLUSIVIDADE MÚTUA: as cinco opções devem ser mutuamente \
exclusivas -- nenhuma pode ser uma paráfrase de outra nem sobrepor-se em \
significado. REGRA VERIFICÁVEL: evite repetir as mesmas palavras de \
conteúdo (substantivos, verbos e adjetivos específicos do tema) em mais \
de uma opção -- cada opção deve usar vocabulário majoritariamente distinto \
das demais; reescrever a mesma ideia com sinônimos ou reordenar as mesmas \
palavras-chave NÃO satisfaz esta regra.
5. Preserve a disciplina e a essência do conteúdo original sempre que \
possível; o objetivo é CORRIGIR falhas estruturais, não trocar de assunto.

Responda SOMENTE com um objeto JSON válido, sem markdown, com exatamente \
estes campos, NESTA ORDEM (justifique antes de \
declarar a resposta): base_text, stem, statement_i, statement_ii, \
statement_iii, statement_iv, assertion_i, assertion_ii, option_a, \
option_b, option_c, option_d, option_e, generator_notes, correct_option. \
Escreva generator_notes ANTES de correct_option -- explique seu raciocínio \
primeiro, só então declare a letra correta. Use null para campos não \
aplicáveis ao formato da questão."""


def build_generator_messages(row: pd.Series, target_letter: str, target_level: str,
                              demoted: bool, question_type: str,
                              feedback: Optional[list[str]] = None,
                              forced_options: Optional[list[dict]] = None,
                              assertion_pattern: Optional[dict] = None,
                              target_word_count: Optional[int] = None) -> list[dict]:
    flaws = []
    if row.get("flag_position_bias"):
        flaws.append("Position Bias: a resposta correta original estava na letra A.")
    if row.get("flag_verbosity_outlier"):
        flaws.append("Verbosity Bias: a opção correta original era a mais longa.")
    if row.get("flag_bloom_mismatch"):
        flaws.append(f"Bloom Mismatch: o nível declarado ({row['taxonomy_level']}) não "
                      f"correspondia ao verbo usado no item original.")
    if row.get("flag_r9_violation"):
        flaws.append(f"R9 Violation: nível '{row['taxonomy_level']}' (Avaliar/Criar) não "
                      f"pode ser avaliado em formato de múltipla escolha.")

    task_params = [
        f"TARGET_LEVEL: {target_level}",
        f"TARGET_LEVEL_VERB_BANK: {', '.join(BLOOM_VERBS_PT[target_level])}",
        f"QUESTION_TYPE: {question_type}",
        f"DISCIPLINE: {row['discipline']}",
    ]
    if demoted:
        task_params.append(
            f"NOTA: nível original '{row['taxonomy_level']}' foi rebaixado para "
            f"'{target_level}' por violar R9 (MCQ ilegal para Avaliar/Criar)."
        )
    if target_word_count is not None and forced_options is None and assertion_pattern is None:
        task_params.append(
            f"ALVO DE CONTAGEM REGRESSIVA (Design D, constitution R45 -- mesmo alvo EXATO para as "
            f"cinco opções, veja o formato de marcadores na Regra 1 do system "
            f"prompt): {target_word_count} palavras por opção, EXATAS -- gere "
            f"option_a, option_b, option_c, option_d e option_e cada uma com a "
            f"sequência completa de marcadores <{target_word_count}> ... <1> <0>, "
            f"contendo exatamente {target_word_count} palavras."
        )
    if forced_options is not None:
        opts_desc = "; ".join(f"{o['text']}" for o in forced_options)
        task_params.append(
            "ESTRUTURA DE OPÇÕES OBRIGATÓRIA (Múltipla Escolha Complexa): as cinco "
            "opções DEVEM ser exatamente estas frases combinatórias, mantendo a "
            "ordem dada (a correspondência com as letras A-E será feita pelo "
            f"orquestrador): {opts_desc}. Sua tarefa é reescrever statement_i-iv "
            "de modo que a combinação verdadeira seja consistente com estas opções."
        )
    if assertion_pattern is not None:
        task_params.append(
            "PADRÃO LÓGICO OBRIGATÓRIO (Asserção-Razão): reescreva assertion_i e "
            f"assertion_ii de modo que o padrão lógico seja exatamente "
            f"'{assertion_pattern['pattern']}' (correspondente à opção correta: "
            f"\"{assertion_pattern['text']}\"). As cinco opções de resposta serão "
            "fixadas pelo orquestrador -- não as gere."
        )

    original_context = {
        "base_text": row.get("base_text"),
        "stem": row.get("stem"),
        "statement_i": row.get("statement_i"), "statement_ii": row.get("statement_ii"),
        "statement_iii": row.get("statement_iii"), "statement_iv": row.get("statement_iv"),
        "assertion_i": row.get("assertion_i"), "assertion_ii": row.get("assertion_ii"),
        "option_a": row.get("option_a"), "option_b": row.get("option_b"),
        "option_c": row.get("option_c"), "option_d": row.get("option_d"),
        "option_e": row.get("option_e"), "correct_option": row.get("correct_option"),
    }
    original_context = {k: v for k, v in original_context.items() if pd.notna(v)}

    user_content = (
        "ITEM ORIGINAL (rejeitado, para reescrita):\n"
        f"{json.dumps(original_context, ensure_ascii=False, indent=2)}\n\n"
        "FALHAS DETECTADAS NO ITEM ORIGINAL:\n"
        + ("\n".join(f"- {f}" for f in flaws) if flaws else "- Nenhuma falha específica sinalizada.")
        + "\n\nPARÂMETROS DA TAREFA:\n" + "\n".join(task_params)
    )
    if feedback:
        user_content += (
            "\n\nFEEDBACK DA TENTATIVA ANTERIOR (corrija estes pontos):\n"
            + "\n".join(f"- {r}" for r in feedback)
        )

    return [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


JUDGE_SYSTEM_PROMPT = """Você é o Synthetic Judge Agent de um pipeline de \
AIG, arquiteturalmente independente do Generator Agent -- nunca o mesmo \
modelo do gerador. Sua tarefa é avaliar de forma \
independente e cética um item candidato.

PROTOCOLO OBRIGATÓRIO:
1. BLIND SOLVE (decorrelação de viés de posição): as cinco opções \
abaixo estão rotuladas 'Option 1'..'Option 5' em ORDEM EMBARALHADA, não na \
ordem A-E original. Resolva a questão você mesmo, de forma independente, \
ANTES de considerar qualquer alegação sobre qual seria a correta. Informe \
seu próprio veredito em blind_solve_shuffled_label. Você NÃO receberá a \
resposta alegada como correta -- isso é intencional e faz parte do \
protocolo. NÃO rejeite um item apenas por não ter recebido essa \
informação; sua tarefa é resolver a questão de forma independente e \
reportar sua própria resposta em blind_solve_shuffled_label. A comparação \
com a resposta alegada é feita por outro componente do sistema, fora do \
seu escopo.
2. Verifique MUTUAL EXCLUSIVITY: as cinco opções representam alternativas \
genuinamente distintas e não sobrepostas?
3. Verifique LENGTH BIAS: alguma opção é visivelmente mais longa/curta que \
as demais de forma que denuncie a resposta certa sem conhecimento de \
conteúdo?
4. Verifique BLOOM ALIGNMENT: o verbo/demanda cognitiva do item corresponde \
genuinamente ao nível declarado?
5. Verifique FACTUAL SOUNDNESS: o conteúdo é correto e coerente?

Reporte sua resposta independente em blind_solve_shuffled_label. Você NÃO \
deve comparar com nenhuma resposta alegada -- essa comparação é feita \
externamente, fora do seu escopo. Sua aprovação depende APENAS dos \
critérios de qualidade acima (mutual exclusivity, length bias, Bloom \
alignment, factual soundness), não de concordância com uma resposta que \
você não recebe.

Aprove (verdict='approve') SOMENTE se todas as verificações de qualidade \
acima forem satisfatórias. Em caso de dúvida sobre qualquer critério de \
qualidade, REJEITE -- não é sua função dar o benefício da dúvida ao \
gerador.

Responda SOMENTE com um objeto JSON válido, sem markdown, com exatamente \
estes campos, NESTA ORDEM (raciocine antes de \
declarar o veredito): blind_solve_reasoning, blind_solve_shuffled_label, \
mutual_exclusivity_ok, length_bias_ok, bloom_alignment_ok, \
factual_soundness_ok, reasons (lista de strings), verdict. Escreva \
blind_solve_reasoning ANTES de blind_solve_shuffled_label, e reasons ANTES \
de verdict -- explique seu raciocínio antes de declarar cada veredito, \
nunca depois. Responda APENAS com o objeto JSON. Não adicione nenhum \
texto, comentário ou explicação antes ou depois do JSON."""


def build_judge_messages(item: GeneratedItem, target_level: str,
                          shuffled_labels: dict[str, str]) -> list[dict]:
    """shuffled_labels maps 'Option 1'..'Option 5' -> real letter (A-E),
    already shuffled by the caller -- the judge never sees the real
    A-E ordering, decorrelating its verdict from the generator's assigned
    target_letter (a cheap, single-call adaptation of spec.md 4.2.1 step 1's
    10-reordering majority vote -- see module docstring)."""
    shuffled_view = {
        label: getattr(item, LETTER_TO_COL[letter])
        for label, letter in shuffled_labels.items()
    }
    cognitive_text = build_cognitive_text(item.model_dump())
    user_content = (
        f"NÍVEL DE BLOOM DECLARADO: {target_level}\n"
        f"TEXTO COGNITIVO (stem + assertions/statements):\n{cognitive_text}\n\n"
        f"OPÇÕES (ordem embaralhada, rótulos neutros):\n"
        f"{json.dumps(shuffled_view, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# --------------------------------------------------------------------------
# 10. Dry-run mock (no network, no API key) -- deterministic given SEED,
#     exercises the real retry/backfill/parsing machinery so the whole
#     orchestration can be validated offline before spending API budget.
# --------------------------------------------------------------------------
def _mock_llm_call(messages: list[dict], model: str) -> str:
    system, user = messages[0]["content"], messages[1]["content"]
    # NOTE: check the Judge marker FIRST -- JUDGE_SYSTEM_PROMPT itself
    # contains the substring "Generator Agent" (in "...independente do
    # Generator Agent..."), so a naive "Generator Agent" in system check
    # (checked first) would misroute every judge call to the generator mock.
    if "Synthetic Judge Agent" in system:
        return _mock_judge_response(user)
    if "Generator Agent" in system:
        return _mock_generator_response(user)
    raise ValueError("Unrecognized mock LLM call (unknown system prompt).")


_CORRECT_MARKER = "considera adequadamente"


def _mock_generator_response(user_content: str) -> str:
    """Bug fix (2026-08-20): this used to read a TARGET_LETTER field out of
    the prompt, but build_generator_messages() (position-content
    decoupling -- see Rule 2 in GENERATOR_SYSTEM_PROMPT) never puts
    TARGET_LETTER in the prompt anymore -- the generator always writes the
    correct answer as option_a, and apply_position_shuffle() relocates it
    mechanically afterward, outside the prompt entirely. The old regex
    crashed with 'NoneType has no attribute group' on every call, so
    --dry-run was silently 0%-approval-broken. Fixed to match the real
    architecture: always place the correct content at 'A', exactly as
    Rule 2 instructs a real generator to do."""
    target_level = re.search(r"TARGET_LEVEL: (\w+)", user_content).group(1)
    discipline = re.search(r"DISCIPLINE: (.+)", user_content).group(1).strip()
    has_feedback = "FEEDBACK DA TENTATIVA ANTERIOR" in user_content
    verb = BLOOM_VERBS_PT[target_level][0]
    # No TARGET_LETTER available anymore (see docstring) -- hash the
    # ORIGINAL item content (everything before any appended feedback
    # section) instead, so the bucket is stable across retries for the
    # same item, not just on the first attempt.
    base_content = user_content.split("FEEDBACK DA TENTATIVA ANTERIOR")[0]
    bucket = hash(base_content) % 20

    # Three deterministic, non-overlapping simulated scenarios (only on the
    # FIRST attempt, i.e. before any feedback exists) so the dry run
    # exercises every retry path at least once without any single item
    # hitting two failure modes at once (which would confound which check
    # actually fired):
    #   ~15% -- pure verbosity flaw: caught by the MECHANICAL pre-filter,
    #           never reaches the judge; clean on the retry (feedback seen).
    #   ~10% -- content the mock JUDGE will reject (factual_soundness_ok
    #           False), independent of any mechanical check; clean on retry.
    #   ~4%  -- "cursed" item that never improves even with feedback, to
    #           exercise the exhausted-retries -> backfill path.
    is_cursed = bucket == 19
    simulate_verbosity_flaw = (not has_feedback) and bucket < 3
    simulate_judge_flaw = ((not has_feedback) and 3 <= bucket < 5) or is_cursed

    # Fixed-length templates (manually verified during development to have
    # equal word count regardless of discipline length; not covered by an
    # automated test) so the CLEAN mock path passes check_verbosity by
    # construction; only the deliberately simulated-flaw branch below
    # should ever trip that check.
    base_texts = {
        "A": f"{_CORRECT_MARKER} os princípios centrais relativos a {discipline}.",
        "B": f"ignora por completo um aspecto central de {discipline}.",
        "C": f"aplica de forma parcial um critério sobre {discipline}.",
        "D": f"inverte a relação causal central prevista em {discipline}.",
        "E": f"generaliza de forma indevida um caso sobre {discipline}.",
    }
    # Rule 2 (position-content decoupling): the generator ALWAYS writes the
    # correct answer as option_a -- apply_position_shuffle() relocates it
    # mechanically afterward, exactly like a real generator call.
    options = dict(base_texts)
    correct_option = "A"

    if simulate_verbosity_flaw:
        options["A"] = options["A"] + " " + (
            "Este trecho adicional torna a opção correta visivelmente mais longa "
            "que as demais, simulando um item malformado a ser pego pelo filtro mecânico."
        )

    stem = f"Ao {verb} o cenário apresentado sobre {discipline}, é correto afirmar que a alternativa"
    if simulate_judge_flaw:
        # Marker survives into the judge's cognitive_text (stem is included
        # there) even though generator_notes/extra JSON keys do not --
        # pydantic silently drops unknown fields on parse, so any signal
        # for the mock judge must live inside a real schema field.
        stem += " [MOCK_JUDGE_FLAW]"

    payload = {
        "base_text": None,
        "stem": stem,
        "statement_i": f"O princípio de {discipline} é analisado com rigor ({verb}).",
        "statement_ii": f"Uma exceção pouco relevante para {discipline} é ignorada.",
        "statement_iii": f"A investigação de {discipline} considera o contexto histórico.",
        "statement_iv": f"O critério adotado para {discipline} é insuficiente.",
        "assertion_i": f"I. Ao {verb} o tema de {discipline}, observa-se um padrão consistente.",
        "assertion_ii": f"II. PORQUE o referencial teórico de {discipline} sustenta essa leitura.",
        "option_a": options["A"],
        "option_b": options["B"],
        "option_c": options["C"],
        "option_d": options["D"],
        "option_e": options["E"],
        "generator_notes": (
            "mock generation"
            + (" (simulated verbosity flaw)" if simulate_verbosity_flaw else "")
            + (" (simulated judge-rejectable content)" if simulate_judge_flaw and not is_cursed else "")
            + (" (cursed -- never converges)" if is_cursed else "")
        ),
        "correct_option": correct_option,
    }
    return json.dumps(payload, ensure_ascii=False)


def _mock_judge_response(user_content: str) -> str:
    """KNOWN MOCK LIMITATION: blind-solve here keys off _CORRECT_MARKER,
    which only appears in 'standard'-format mock option text. For
    complex_mc/assertion_reason items the real options are orchestrator-
    templated canonical text (see place_options_at_letters) that never
    contains the marker, so this falls back to an arbitrary (deterministic
    but effectively ~20%-chance) guess for those two formats in --dry-run
    only. This does not affect production behavior -- a real judge model
    reads and solves the canonical text correctly -- it only means those
    two formats see a noisier, more retry-heavy dry-run than 'standard'
    ones, which is a harmless (if slightly pessimistic) stress-test of the
    retry/backfill path, not a bug."""
    options_block = json.loads(re.search(r"\{[\s\S]*\}", user_content).group(0))
    correct_label = next((label for label, text in options_block.items()
                           if _CORRECT_MARKER in text), None)
    simulate_judge_flaw = "[MOCK_JUDGE_FLAW]" in user_content

    if simulate_judge_flaw:
        verdict_payload = {
            "blind_solve_reasoning": "mock judge: content flagged as factually unsound (simulated).",
            "blind_solve_shuffled_label": correct_label or next(iter(options_block)),
            "mutual_exclusivity_ok": True,
            "length_bias_ok": True,
            "bloom_alignment_ok": True,
            "factual_soundness_ok": False,
            "reasons": ["Simulated factual-soundness rejection (mock judge test path)."],
            "verdict": "reject",
        }
        return json.dumps(verdict_payload, ensure_ascii=False)

    verdict_payload = {
        "blind_solve_reasoning": f"mock blind solve: option containing '{_CORRECT_MARKER}' identified as correct.",
        "blind_solve_shuffled_label": correct_label or next(iter(options_block)),
        "mutual_exclusivity_ok": True,
        "length_bias_ok": True,
        "bloom_alignment_ok": True,
        "factual_soundness_ok": True,
        "reasons": [],
        "verdict": "approve",
    }
    return json.dumps(verdict_payload, ensure_ascii=False)


# --------------------------------------------------------------------------
# 11. Generator Agent
# --------------------------------------------------------------------------

async def generator_agent(row: pd.Series, target_letter: str, target_level: str,
                           demoted: bool, generator_model: str,
                           feedback: Optional[list[str]] = None,
                           item_rng: Optional[random.Random] = None,
                           target_word_count: Optional[int] = None,
                           ) -> tuple[GeneratedItem, list[str]]:
    question_type = row["question_type"]
    fmt = QUESTION_FORMAT.get(question_type, "standard")
    item_rng = item_rng or random.Random(f"{row['question_id']}-{target_letter}")

    forced_options = assertion_pattern = None
    if fmt == "complex_mc":
        combo = build_complex_mc_combination(item_rng)
        forced_options = [{"text": combo["true_text"]}] + [{"text": t} for t in combo["distractor_texts"]]
        placement = place_options_at_letters(target_letter, combo["true_text"],
                                              combo["distractor_texts"], item_rng)
    elif fmt == "assertion_reason":
        true_pattern = ASSERTION_REASON_TEMPLATES[hash(row["question_id"]) % len(ASSERTION_REASON_TEMPLATES)]
        assertion_pattern = true_pattern
        distractor_texts = get_assertion_reason_distractors(true_pattern)
        placement = place_options_at_letters(target_letter, true_pattern["text"],
                                              distractor_texts, item_rng)
    else:
        placement = None

    messages = build_generator_messages(
        row, target_letter, target_level, demoted, question_type,
        feedback=feedback, forced_options=forced_options, assertion_pattern=assertion_pattern,
        target_word_count=target_word_count,
    )
    raw = await call_llm(messages, model=generator_model, temperature=0.5)
    parsed = extract_json(raw)
    item = GeneratedItem.model_validate(parsed)

    # Design D (constitution R45): validate the RAW countdown-marker
    # sequence (diagnostic only -- never gates acceptance) THEN strip it
    # to produce the clean text that check_verbosity() and the judge will
    # actually see. Only meaningful for 'standard' format -- complex_mc/
    # assertion_reason option text is orchestrator-templated below, never
    # LLM-authored, so it never carries countdown markers.
    countdown_issues: list[str] = []
    if fmt == "standard" and target_word_count is not None:
        for col in ("option_a", "option_b", "option_c", "option_d", "option_e"):
            raw_option_text = getattr(item, col)
            issue = describe_countdown_malformation(raw_option_text, target_word_count)
            if issue:
                countdown_issues.append(f"{col}: {issue}")
            setattr(item, col, strip_countdown_markers(raw_option_text))

    if placement is not None:
        # Orchestrator-templated formats: option_a-e are NEVER taken from the
        # LLM (see build_complex_mc_combination / ASSERTION_REASON_TEMPLATES
        # docstrings) -- only the supporting statement/assertion content is.
        for letter, text in placement.items():
            setattr(item, LETTER_TO_COL[letter], text)
        item.correct_option = target_letter

    return item, countdown_issues


# --------------------------------------------------------------------------
# 12. Synthetic Judge Agent (spec.md Section 4.2.1)
# --------------------------------------------------------------------------
@dataclass
class JudgeOutcome:
    approved: bool
    reasons: list[str]
    raw_verdict: Optional[JudgeVerdict] = None


async def judge_agent(item: GeneratedItem, target_letter: str, target_level: str,
                       judge_model: str, item_rng: Optional[random.Random] = None,
                       n_reorderings: int = 1) -> JudgeOutcome:
    """n_reorderings=1 (default): single-shuffle blind-solve decorrelation.
    n_reorderings=10: full spec.md 4.2.1-step-1 majority vote (--rigorous
    -position-check) -- every reordering must agree with target_letter or
    the item is rejected, matching "declare a tie on disagreement, never
    silently pick one direction"."""
    item_rng = item_rng or random.Random(f"judge-{target_letter}-{target_level}")
    votes_for_target = 0
    last_verdict: Optional[JudgeVerdict] = None
    all_reasons: list[str] = []

    for _ in range(n_reorderings):
        shuffled_letters = list(OPTION_LETTERS)
        item_rng.shuffle(shuffled_letters)
        shuffled_labels = {f"Option {i + 1}": letter for i, letter in enumerate(shuffled_letters)}
        label_to_letter = {v: k for k, v in shuffled_labels.items()}  # letter -> label, for lookup below
        letter_of_label = shuffled_labels  # label -> letter

        messages = build_judge_messages(item, target_level, shuffled_labels)
        raw = await call_llm(messages, model=judge_model, temperature=0.0)
        verdict = JudgeVerdict.model_validate(extract_json(raw))
        last_verdict = verdict

        blind_solve_letter = letter_of_label.get(verdict.blind_solve_shuffled_label)
        agrees_with_target = blind_solve_letter == target_letter
        if agrees_with_target:
            votes_for_target += 1
        else:
            all_reasons.append(
                f"Judge blind-solve picked '{blind_solve_letter}' "
                f"(shuffled as {verdict.blind_solve_shuffled_label}), disagreeing with "
                f"claimed correct_option '{target_letter}'."
            )

    # R23: a single agreeing vote is enough for the default single-shuffle
    # mode; in rigorous mode ALL reorderings must agree (majority-vote ties
    # are treated as reject, per spec.md 4.2.1 step 1 -- "declare a tie...
    # never silently pick one direction").
    position_ok = votes_for_target == n_reorderings

    checks_ok = (
        last_verdict is not None
        and last_verdict.verdict == "approve"
        and last_verdict.mutual_exclusivity_ok
        and last_verdict.length_bias_ok
        and last_verdict.bloom_alignment_ok
        and last_verdict.factual_soundness_ok
        and position_ok
    )
    reasons = list(last_verdict.reasons) if last_verdict else []
    reasons += all_reasons
    if not checks_ok and not reasons:
        reasons.append("Judge rejected without a specific reason (defensive fallback).")

    return JudgeOutcome(approved=checks_ok, reasons=reasons, raw_verdict=last_verdict)


# --------------------------------------------------------------------------
# 13. Judge verbosity-confound audit (spec.md 4.2.1 step 2) -- a ONE-TIME,
#     model-version-tagged calibration run before the batch starts, not a
#     per-item check. Uses a small paired same-content-different-length
#     probe set; logs direction/magnitude, tagged to the judge model.
# --------------------------------------------------------------------------
async def run_verbosity_confound_audit(judge_model: str) -> dict:
    short_stem = "Analise o gráfico e identifique a tendência principal apresentada."
    long_stem = (
        "Considerando cuidadosamente todos os elementos apresentados no gráfico em "
        "questão, e levando em conta as diversas nuances metodológicas envolvidas "
        "na sua construção, identifique, de maneira exaustiva e pormenorizada, a "
        "tendência principal que nele se apresenta."
    )
    probe_options = {
        "option_a": "A tendência é de crescimento constante ao longo do período observado.",
        "option_b": "A tendência é de queda constante ao longo do período observado.",
        "option_c": "A tendência é de estabilidade ao longo do período observado.",
        "option_d": "A tendência é de oscilação irregular ao longo do período observado.",
        "option_e": "Não há dados suficientes para determinar uma tendência.",
    }

    async def probe(stem_text: str) -> Optional[str]:
        item = GeneratedItem(stem=stem_text, correct_option="A", **probe_options)
        shuffled_labels = {f"Option {i + 1}": l for i, l in enumerate(OPTION_LETTERS)}
        messages = build_judge_messages(item, "Analisar", shuffled_labels)
        try:
            raw = await call_llm(messages, model=judge_model, temperature=0.0)
            verdict = JudgeVerdict.model_validate(extract_json(raw))
            return verdict.verdict
        except Exception as exc:  # noqa: BLE001
            logger.warning("Verbosity-confound probe call failed: %s", exc)
            return None

    short_verdict = await probe(short_stem)
    long_verdict = await probe(long_stem)
    result = {
        "judge_model": judge_model,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "short_stem_verdict": short_verdict,
        "long_stem_verdict": long_verdict,
        "length_confound_detected": short_verdict != long_verdict,
    }
    if result["length_confound_detected"]:
        logger.warning(
            "R22/R25: judge model '%s' verdict CHANGED between a short and a long "
            "probe stem of identical content -- possible verbosity confound. "
            "Logged to %s for review.", judge_model, JUDGE_BIAS_AUDIT_PATH,
        )
    else:
        logger.info("Judge verbosity-confound audit: no length-driven verdict change detected "
                    "for model '%s' on this probe pair.", judge_model)
    return result


# --------------------------------------------------------------------------
# 13b. Inter-item pacing -- empirically observed Groq per-model TPM
#      (tokens-per-minute) limits for this account's on-demand tier
#      (discovered live from 429 error messages during calibration, not
#      published anywhere reusable). At --concurrency 1, back-to-back items
#      fire their generator calls close enough together to immediately burn
#      through a tight TPM budget before any real content is produced
#      (confirmed: 3/5 items lost both attempts to rate limiting with no
#      pacing). This sleeps BEFORE burning the budget rather than relying
#      solely on tenacity's retry-after-failure to recover from it.
# --------------------------------------------------------------------------
_KNOWN_GROQ_TPM_LIMITS = {
    "qwen/qwen3.6-27b": 8000,
    "openai/gpt-oss-20b": 8000,
    "openai/gpt-oss-120b": 8000,  # untested directly; same vendor tier, conservative assumption
    "llama-3.3-70b-versatile": 12000,
}
_DEFAULT_CONSERVATIVE_TPM = 8000
_PACING_TPM_THRESHOLD = 8000  # only pace when the active model's TPM is at or below this
_PACING_TOKENS_PER_CALL_ESTIMATE = 2000  # observed range ~1000-2000 tokens/call for these models


def _inter_item_pacing_seconds(generator_model: str, concurrency: int) -> Optional[float]:
    if concurrency != 1:
        return None
    provider, _, rest = generator_model.partition("/")
    if provider.lower() != "groq":
        return None
    tpm = _KNOWN_GROQ_TPM_LIMITS.get(rest, _DEFAULT_CONSERVATIVE_TPM)
    if tpm > _PACING_TPM_THRESHOLD:
        return None
    calls_per_minute = tpm / _PACING_TOKENS_PER_CALL_ESTIMATE
    return 60.0 / calls_per_minute if calls_per_minute > 0 else 15.0


# --------------------------------------------------------------------------
# 14. Per-item orchestration (spec.md Section 4.3 routing, applied to one
#     candidate): Generator -> Mechanical Pre-Filter -> [pass?] -> LLM
#     Judge -> Accept/Regenerate, up to MAX_RETRIES attempts, with the
#     judge/pre-filter's reasons fed back into the next generation attempt.
# --------------------------------------------------------------------------
@dataclass
class ProcessedResult:
    question_id: int
    original_row: dict
    target_letter: str
    target_level: str
    demoted: bool
    approved: bool
    attempts: int
    final_item: Optional[GeneratedItem] = None
    failure_reason: Optional[str] = None
    audit_entries: list[dict] = field(default_factory=list)
    quota_stopped: bool = False  # True: never attempted this session -- the daily
                                   # token-quota guard stopped the run before this
                                   # item's first call. Distinct from `approved=False`
                                   # after genuinely exhausting max_retries.
    exhaustion_category: Optional[str] = None  # set only when approved=False and NOT
                                   # quota_stopped -- "infrastructure_flakiness" (every
                                   # attempt failed on a transient call/timeout error,
                                   # zero content-quality signal), "content_quality"
                                   # (generator/judge genuinely disagreed or the item
                                   # failed a format check), or "mixed". Lets the
                                   # technical report's Green AI section separate
                                   # "infrastructure wasn't reliable" from "the
                                   # generator/judge pair couldn't agree" -- two very
                                   # different findings that a flat approved/failed
                                   # count would conflate.


_INFRA_FAILURE_STAGES = {"generator_call_error", "judge_call_error"}
_CONTENT_FAILURE_STAGES = {"generator_parse_error", "judge_parse_error", "mechanical_reject"}


def _classify_exhaustion(audit_entries: list[dict]) -> str:
    """Scans one item's own audit_entries (already scoped to just this
    question_id's attempts) and buckets each attempt as infra-caused or
    content-caused, per the ProcessedResult.exhaustion_category docstring.
    An attempt that reached judge_outcome without an explicit `stage` (the
    normal "judge ran and rejected on content grounds" shape -- see
    judge_agent's call site, which only sets `stage` on the parse-error/
    call-error paths) counts as content-caused."""
    saw_infra = saw_content = False
    for entry in audit_entries:
        stage = entry.get("stage")
        if stage in _INFRA_FAILURE_STAGES:
            saw_infra = True
        elif stage in _CONTENT_FAILURE_STAGES or "judge_outcome" in entry:
            saw_content = True
    if saw_infra and saw_content:
        return "mixed"
    if saw_infra:
        return "infrastructure_flakiness"
    return "content_quality"


async def _daily_quota_guard_hit(question_id: int, target_letter: str, target_level: str,
                                  demoted: bool, attempt: int, audit_entries: list[dict]) -> bool:
    """Checked right before every generator call. Returns True (and logs +
    records an audit entry) if calling would push today's cumulative Groq
    token usage past the configured soft cap -- the caller must stop this
    item (and, since pool items are processed in priority order under
    --concurrency 1, every remaining item in the pool) without spending
    quota on it."""
    if _daily_budget is None:
        return False
    if not await _daily_budget.would_exceed(DEFAULT_PRE_CALL_TOKEN_ESTIMATE):
        return False
    note = (f"Daily token soft cap reached (cumulative={_daily_budget.cumulative_tokens}, "
            f"soft_cap={_daily_budget.soft_cap}) -- stopping before spending more quota. "
            f"Resume in a later session.")
    audit_entries.append({
        "question_id": question_id, "attempt": attempt, "target_letter": target_letter,
        "target_level": target_level, "demoted": demoted,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "quota_guard_stop", "note": note,
    })
    logger.warning("[%d] DAILY TOKEN QUOTA GUARD: %s", question_id, note)
    return True


async def process_item(row: pd.Series, target_letter: str, generator_model: str,
                        judge_model: str, max_retries: int, rigorous_position_check: bool,
                        semaphore: asyncio.Semaphore,
                        pacing_seconds: Optional[float] = None) -> ProcessedResult:
    question_id = int(row["question_id"])
    target_level, demoted = determine_target_level(row["taxonomy_level"], question_id=question_id)
    item_rng = random.Random(f"{question_id}-{SEED}")
    n_reorderings = 10 if rigorous_position_check else 1
    fmt = QUESTION_FORMAT.get(row["question_type"], "standard")
    # Design C: computed ONCE per item (not per attempt) from the original
    # item's own option lengths, and only meaningful for the 'standard'
    # format -- complex_mc/assertion_reason never have LLM-authored option
    # text (see place_options_at_letters), so a length target is moot there.
    target_word_count = compute_target_word_count(row) if fmt == "standard" else None

    feedback: Optional[list[str]] = None
    audit_entries: list[dict] = []

    async with semaphore:
        if await _daily_quota_guard_hit(question_id, target_letter, target_level, demoted, 0, audit_entries):
            return ProcessedResult(
                question_id=question_id, original_row=row.to_dict(),
                target_letter=target_letter, target_level=target_level, demoted=demoted,
                approved=False, attempts=0, quota_stopped=True,
                failure_reason="daily_token_quota_guard_stop", audit_entries=audit_entries,
            )
        if pacing_seconds:
            await asyncio.sleep(pacing_seconds)
        for attempt in range(1, max_retries + 1):
            if await _daily_quota_guard_hit(question_id, target_letter, target_level, demoted, attempt, audit_entries):
                return ProcessedResult(
                    question_id=question_id, original_row=row.to_dict(),
                    target_letter=target_letter, target_level=target_level, demoted=demoted,
                    approved=False, attempts=attempt - 1, quota_stopped=True,
                    failure_reason="daily_token_quota_guard_stop", audit_entries=audit_entries,
                )
            entry = {
                "question_id": question_id, "attempt": attempt,
                "target_letter": target_letter, "target_level": target_level,
                "demoted": demoted, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                item, countdown_issues = await generator_agent(
                    row, target_letter, target_level, demoted, generator_model,
                    feedback=feedback, item_rng=item_rng,
                    target_word_count=target_word_count,
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("[%d] attempt %d: generator output failed to parse (%s).",
                                question_id, attempt, exc)
                feedback = [f"Sua resposta anterior não era um JSON válido no schema exigido: {exc}"]
                entry["stage"] = "generator_parse_error"
                entry["error"] = str(exc)
                audit_entries.append(entry)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.error("[%d] attempt %d: generator call failed: %s", question_id, attempt, exc)
                entry["stage"] = "generator_call_error"
                entry["error"] = str(exc)
                audit_entries.append(entry)
                retry_after = _parse_retry_after_seconds(exc)
                if retry_after is not None:
                    logger.info(
                        "[%d] attempt %d: waiting %.1fs (Groq-reported rate-limit "
                        "reset) before the next attempt for this item.",
                        question_id, attempt, retry_after,
                    )
                    await asyncio.sleep(retry_after)
                continue

            apply_position_shuffle(item, target_letter, item_rng)
            entry["generated_item"] = item.model_dump()
            entry["countdown_issues"] = countdown_issues

            prefilter = run_mechanical_prefilter(item, target_letter, target_level, row["question_type"])
            entry["mechanical_prefilter"] = {"passed": prefilter.passed, "reasons": prefilter.reasons}
            if not prefilter.passed:
                logger.info("[%d] attempt %d: REJECTED by mechanical pre-filter: %s",
                            question_id, attempt, "; ".join(prefilter.reasons))
                # Design C/D: thread the EXACT numeric miss against this
                # item's own target_word_count into next attempt's feedback,
                # additive to (never replacing) check_verbosity()'s own
                # reasons above -- run_mechanical_prefilter's pass/fail logic
                # and its audit-trail record are both untouched. Design D
                # targets an EXACT count (tolerance=0), not Design C's +-2 band.
                word_count_feedback = (
                    describe_word_count_violations(item, target_word_count, tolerance=0)
                    if target_word_count is not None else []
                )
                feedback = list(prefilter.reasons) + word_count_feedback + countdown_issues
                entry["stage"] = "mechanical_reject"
                audit_entries.append(entry)
                continue

            try:
                judge_outcome = await judge_agent(
                    item, target_letter, target_level, judge_model,
                    item_rng=item_rng, n_reorderings=n_reorderings,
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("[%d] attempt %d: judge output failed to parse (%s).",
                                question_id, attempt, exc)
                feedback = ["A verificação do julgador falhou por erro técnico; tente novamente."]
                entry["stage"] = "judge_parse_error"
                entry["error"] = str(exc)
                audit_entries.append(entry)
                continue
            except Exception as exc:  # noqa: BLE001
                # CRITICAL: without this handler, a transient judge-call
                # failure (Groq rate-limit, or an Ollama load-timeout under
                # NFS storage contention -- see DEFAULT_OLLAMA_LOAD_TIMEOUT)
                # propagated all the way out of process_item and into
                # run_pipeline's bare `asyncio.gather(*tasks)` (no
                # return_exceptions=True), crashing the ENTIRE session and
                # losing every already-approved item's audit trail/CSV
                # write for this run -- confirmed by tracing the call graph,
                # not merely suspected. Mirrors the generator's handler
                # immediately above it in shape.
                logger.error("[%d] attempt %d: judge call failed: %s", question_id, attempt, exc)
                entry["stage"] = "judge_call_error"
                entry["error"] = str(exc)
                audit_entries.append(entry)
                retry_after = _parse_retry_after_seconds(exc)
                if retry_after is not None:
                    logger.info(
                        "[%d] attempt %d: waiting %.1fs (Groq-reported rate-limit "
                        "reset) before the next attempt for this item.",
                        question_id, attempt, retry_after,
                    )
                    await asyncio.sleep(retry_after)
                continue

            entry["judge_outcome"] = {
                "approved": judge_outcome.approved, "reasons": judge_outcome.reasons,
                "raw_verdict": judge_outcome.raw_verdict.model_dump() if judge_outcome.raw_verdict else None,
            }
            audit_entries.append(entry)

            if judge_outcome.approved:
                logger.info("[%d] attempt %d: APPROVED (target=%s, level=%s%s).",
                            question_id, attempt, target_letter, target_level,
                            ", demoted from R9-illegal level" if demoted else "")
                return ProcessedResult(
                    question_id=question_id, original_row=row.to_dict(),
                    target_letter=target_letter, target_level=target_level, demoted=demoted,
                    approved=True, attempts=attempt, final_item=item, audit_entries=audit_entries,
                )

            logger.info("[%d] attempt %d: REJECTED by judge: %s",
                        question_id, attempt, "; ".join(judge_outcome.reasons))
            feedback = judge_outcome.reasons

    exhaustion_category = _classify_exhaustion(audit_entries)
    logger.warning("[%d] exhausted %d attempts without approval (%s) -- moving to backfill pool.",
                    question_id, max_retries, exhaustion_category)
    return ProcessedResult(
        question_id=question_id, original_row=row.to_dict(),
        target_letter=target_letter, target_level=target_level, demoted=demoted,
        approved=False, attempts=max_retries,
        failure_reason=feedback[-1] if feedback else "Unknown failure.",
        audit_entries=audit_entries, exhaustion_category=exhaustion_category,
    )


async def run_pipeline(pool: pd.DataFrame, generator_model: str, judge_model: str,
                        max_retries: int, concurrency: int,
                        rigorous_position_check: bool) -> list[ProcessedResult]:
    semaphore = asyncio.Semaphore(concurrency)
    target_letters = assign_target_letters(len(pool))

    pacing_seconds = _inter_item_pacing_seconds(generator_model, concurrency)
    if pacing_seconds:
        logger.info(
            "Inter-item pacing enabled: sleeping %.1fs before each item's first "
            "attempt (concurrency=1, generator model's TPM budget is tight) to "
            "avoid burning retry budget on immediate rate limits.", pacing_seconds,
        )

    tasks = [
        process_item(row, target_letters[i], generator_model, judge_model,
                     max_retries, rigorous_position_check, semaphore, pacing_seconds)
        for i, (_, row) in enumerate(pool.iterrows())
    ]
    results = await asyncio.gather(*tasks)

    n_quota_stopped = sum(1 for r in results if r.quota_stopped)
    if n_quota_stopped:
        logger.warning(
            "Daily token quota guard stopped this session before %d/%d pool item(s) "
            "were even attempted. Resume in a later session (once the TPD quota "
            "resets) -- previously approved items are auto-excluded from the pool.",
            n_quota_stopped, len(results),
        )

    attempted = [r for r in results if not r.quota_stopped]
    if attempted:
        discard_rate = 1 - sum(r.approved for r in attempted) / len(attempted)
        if discard_rate > 0.5:
            # spec.md Section 4.3: "flag dataset for regeneration before
            # proceeding, not silently accepted at a lower volume".
            logger.warning(
                "Discard rate across attempted items this session is %.1f%% (>50%%) -- "
                "this signals a systemic generation/judge problem, not isolated item "
                "flaws. Review prompts and judge-model calibration before trusting the "
                "output batch.", discard_rate * 100,
            )
    return results


# --------------------------------------------------------------------------
# 15. Output: select final 100, write competition CSV + audit trail
# --------------------------------------------------------------------------
def item_to_row(result: ProcessedResult) -> dict:
    item = result.final_item
    orig = result.original_row
    return {
        "question_id": result.question_id,
        "question_type": orig["question_type"],
        "discipline": orig["discipline"],
        "taxonomy_level": result.target_level,
        "base_text": item.base_text if item.base_text else orig.get("base_text"),
        "stem": item.stem,
        "assertion_i": item.assertion_i,
        "assertion_ii": item.assertion_ii,
        "statement_i": item.statement_i,
        "statement_ii": item.statement_ii,
        "statement_iii": item.statement_iii,
        "statement_iv": item.statement_iv,
        "option_a": item.option_a,
        "option_b": item.option_b,
        "option_c": item.option_c,
        "option_d": item.option_d,
        "option_e": item.option_e,
        "correct_option": item.correct_option,
    }


def select_final_100(results: list[ProcessedResult], target_n: int,
                      existing_df: Optional[pd.DataFrame] = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (cumulative_df, new_approved_df): `new_approved_df` is what
    THIS session approved; `cumulative_df` is that merged with `existing_df`
    (a prior session's already-written deliverable, if any), deduplicated by
    question_id (existing rows win -- they're already-approved, immutable
    once shipped) and capped at target_n. Merging here (rather than
    overwriting the deliverable CSV every run) is what makes --exclude-ids-
    based multi-session resumption actually accumulate toward target_n
    instead of each session's file replacing the last one's."""
    approved = [r for r in results if r.approved]
    new_rows = [item_to_row(r) for r in approved]
    new_df = pd.DataFrame(new_rows, columns=COMPETITION_SCHEMA)

    if existing_df is not None and len(existing_df):
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset="question_id", keep="first").reset_index(drop=True)
    else:
        combined = new_df

    if len(combined) < target_n:
        logger.warning(
            "Only %d/%d items approved cumulatively (this session: +%d). Writing %d "
            "items -- resume in a later session (see the daily token quota guard) or "
            "widen --pool-size to reach the full target.",
            len(combined), target_n, len(new_df), len(combined),
        )
    else:
        logger.info("%d cumulative approved candidates (+%d this session); capping "
                    "at target_n=%d.", len(combined), len(new_df), target_n)
    final = combined.head(target_n).reset_index(drop=True)
    return final, new_df


def write_audit_trail(results: list[ProcessedResult], path: Path, append: bool = True) -> None:
    """Appends by default -- the audit trail is a full historical record
    across every session (spec.md 2.8: "every review decision... required
    for accreditation/challengeability"), so a resumed session's entries
    must accumulate, not replace, prior sessions' entries for different
    question_ids. Callers that genuinely want a from-scratch file (e.g.
    --dry-run's separate dryrun path) can pass append=False."""
    mode = "a" if (append and path.exists()) else "w"
    n_new = sum(len(r.audit_entries) for r in results)
    with open(path, mode, encoding="utf-8") as f:
        for r in results:
            for entry in r.audit_entries:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    verb = "appended to" if mode == "a" else "written to"
    logger.info("Audit trail %s %s (+%d entries this session).", verb, path, n_new)


def print_run_summary(results: list[ProcessedResult], final_df: pd.DataFrame,
                       audit_result: Optional[dict], *, new_approved_df: pd.DataFrame,
                       target_n: int, deliverable_path: Path, audit_trail_path: Path) -> None:
    approved = [r for r in results if r.approved]
    attempted = [r for r in results if not r.quota_stopped]
    n_quota_stopped = len(results) - len(attempted)
    n_demoted = sum(1 for r in approved if r.demoted)
    letter_dist = final_df["correct_option"].value_counts(normalize=True).reindex(OPTION_LETTERS).fillna(0)
    attempts_hist = pd.Series([r.attempts for r in approved]).value_counts().sort_index()

    approved_this_session = len(new_approved_df)
    cumulative_approved = len(final_df)
    approval_rate = approved_this_session / len(attempted) if attempted else None
    remaining_needed = max(0, target_n - cumulative_approved)

    print("\n" + "=" * 70)
    print("WAPLA AIG ENGINE -- RUN SUMMARY (this session)")
    print("=" * 70)
    print(f"Candidates attempted this session:   {len(attempted)}")
    print(f"Approved this session:                {approved_this_session}")
    print(f"Exhausted retries (failed) this session: {len(attempted) - approved_this_session}")
    exhausted = [r for r in attempted if not r.approved]
    if exhausted:
        cat_counts = pd.Series([r.exhaustion_category for r in exhausted]).value_counts()
        n_infra = cat_counts.get("infrastructure_flakiness", 0)
        n_content = cat_counts.get("content_quality", 0)
        n_mixed = cat_counts.get("mixed", 0)
        print(f"  breakdown -- infrastructure_flakiness: {n_infra}, "
              f"content_quality: {n_content}, mixed: {n_mixed}")
        if n_infra:
            print(f"  ({n_infra} item(s) exhausted retries on transient call/timeout "
                  f"errors alone, with zero content-quality signal -- an infrastructure "
                  f"reliability data point for the Green AI section, not evidence the "
                  f"generator/judge pair disagrees on these items. See stage="
                  f"'generator_call_error'/'judge_call_error' audit entries.)")
    if n_quota_stopped:
        print(f"Skipped by daily token quota guard (not attempted): {n_quota_stopped}")
    print(f"Items demoted Avaliar/Criar -> Analisar (R9): {n_demoted}")
    print(f"\nCUMULATIVE approved (all sessions, capped at target_n={target_n}): "
          f"{cumulative_approved}/{target_n}")
    print(f"Still needed to reach target_n: {remaining_needed}")
    if attempted:
        print(f"This session's approval rate (approved/attempted): {approval_rate:.1%}")
    if remaining_needed == 0:
        print("Target reached -- no further sessions needed.")
    elif approval_rate:
        est_items_needed = remaining_needed / approval_rate
        est_sessions = math.ceil(est_items_needed / len(attempted)) if len(attempted) else None
        if est_sessions is not None:
            print(f"Estimated remaining sessions needed (at this session's rate and "
                  f"throughput): ~{est_sessions}")
    elif attempted:
        print("This session approved 0/{} attempted -- cannot estimate remaining "
              "sessions from a 0% rate; investigate the judge/generator before "
              "continuing.".format(len(attempted)))
    else:
        print("No items attempted this session (quota guard stopped before the first "
              "call) -- cannot estimate remaining sessions; resume tomorrow.")
    print("\ncorrect_option distribution in cumulative output (target: ~20% each):")
    for letter, prop in letter_dist.items():
        print(f"  {letter}: {prop:.1%}")
    print("\nAttempts-to-approval histogram (this session):")
    for n_attempts, count in attempts_hist.items():
        print(f"  {n_attempts} attempt(s): {count} items")
    if audit_result:
        print(f"\nJudge verbosity-confound audit ({audit_result['judge_model']}): "
              f"{'CONFOUND DETECTED -- see log' if audit_result['length_confound_detected'] else 'clean'}")
    if _daily_budget is not None:
        print(f"\nDaily token usage today: {_daily_budget.cumulative_tokens}/{_daily_budget.soft_cap} "
              f"(soft cap; hard TPD limit is higher -- see {TOKEN_USAGE_LOG_PATH})")
    print("\nKNOWN GAP (spec.md 4.2.1 step 5): this run has no human-SME "
          "leniency-baseline comparison -- judge accept-rate above should be "
          "validated against a human-reviewed sample before treating this "
          "batch as final/deployment-ready (constitution R24).")
    print(f"\nOutputs:\n  {deliverable_path}\n  {audit_trail_path}\n  {LOG_PATH}")
    if cumulative_approved:
        approved_ids = sorted(int(x) for x in final_df["question_id"].tolist())
        print(f"\nCumulative approved question_ids ({len(approved_ids)}): {approved_ids}")
    print("=" * 70)


# --------------------------------------------------------------------------
# 16. Entrypoint
# --------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="WAPLA 2026 AIG Refinement Engine")
    p.add_argument("--dry-run", action="store_true",
                    help="Use a deterministic offline mock instead of real LLM calls.")
    p.add_argument("--generator-model", default="gpt-4o-mini",
                    help="litellm/openai model string for the Generator Agent.")
    p.add_argument("--judge-model", default="gemini/gemini-flash-latest",
                    help="litellm/openai model string for the Judge Agent. Must differ "
                         "in provider/family from --generator-model (constitution R26) "
                         "unless --allow-same-model-judge is set. NOTE: gemini-2.5-flash "
                         "returns 404 'no longer available to new users' on freshly issued "
                         "API keys (verified against Google's API directly); "
                         "gemini-flash-latest is a confirmed-working substitute. Its "
                         "'-latest' alias can silently resolve to a different underlying "
                         "model over time -- per constitution R25 (bias-mitigation config "
                         "is tied to a specific judge model version and must be re-audited "
                         "on every upgrade, never assumed transferable), the per-call "
                         "resolved model should be logged into the audit trail rather than "
                         "just the requested alias string, so a future alias drift is "
                         "detectable after the fact instead of silently invalidating past "
                         "judge-bias-audit results. Not yet implemented -- flagged here as "
                         "the concrete gap.")
    p.add_argument("--allow-same-model-judge", action="store_true",
                    help="Override the R26 same-provider-family hard-fail (debugging only).")
    p.add_argument("--target-n", type=int, default=100)
    p.add_argument("--pool-size", type=int, default=None,
                    help="Cap the candidate pool (default: all items in flaw_summary.csv).")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--rigorous-position-check", action="store_true",
                    help="Full spec.md 4.2.1-step-1 10-reordering majority vote instead "
                         "of the default single-shuffle blind-solve (10x judge calls).")
    p.add_argument("--exclude-ids", type=str, default=None,
                    help="Comma-separated question_ids to drop from the candidate pool "
                         "before processing -- for resuming a run interrupted by a "
                         "quota/API-key switch without re-spending quota on items "
                         "already approved in entregavel_2_100_questoes.csv from the "
                         "interrupted run. E.g. --exclude-ids 13,22,63,457,559,623,779. "
                         "This is a BELT-AND-SUSPENDERS option -- question_ids already "
                         "present in entregavel_2_100_questoes.csv are auto-excluded "
                         "regardless of this flag, so forgetting to pass it can no longer "
                         "cause re-spending quota on an already-approved item.")
    p.add_argument("--daily-token-cap", type=int, default=DEFAULT_DAILY_TOKEN_SOFT_CAP,
                    help=f"Soft cap on cumulative real LLM tokens spent per calendar day "
                         f"(default {DEFAULT_DAILY_TOKEN_SOFT_CAP}, leaving headroom under "
                         f"Groq's observed 200,000 TPD hard limit). Checked before every "
                         f"generator/judge call; once crossed, the run stops the remaining "
                         f"pool gracefully (no more spend) instead of grinding into repeated "
                         f"429s. Usage persists across sessions in the same calendar day at "
                         f"{TOKEN_USAGE_LOG_PATH}. Ignored in --dry-run (no real tokens spent) "
                         f"and skipped entirely when both --generator-model and --judge-model "
                         f"are local ollama_chat/ollama models -- local inference has no API "
                         f"rate limit or daily token quota to guard against.")
    p.add_argument("--ollama-keep-alive", type=str, default=DEFAULT_OLLAMA_KEEP_ALIVE,
                    help=f"Sent as the top-level 'keep_alive' field on every direct Ollama "
                         f"request for ollama_chat/ollama models only (default "
                         f"'{DEFAULT_OLLAMA_KEEP_ALIVE}') -- keeps the model resident in memory "
                         f"across this run's sequential per-item calls instead of falling back "
                         f"to Ollama's default 5-minute idle unload, which would force a slow "
                         f"reload if a retry/backoff gap between calls runs long. Local models "
                         f"bypass litellm entirely (see _ollama_direct_chat) precisely because "
                         f"litellm 1.55.0's ollama_chat handler was found NOT to forward this "
                         f"field to the location Ollama's API actually reads it from -- this "
                         f"flag's value now reaches the real field, but still verify with "
                         f"`ollama ps` during a real run.")
    p.add_argument("--ollama-load-timeout", type=int, default=DEFAULT_OLLAMA_LOAD_TIMEOUT,
                    help=f"Request timeout in seconds for ollama_chat/ollama models only "
                         f"(default {DEFAULT_OLLAMA_LOAD_TIMEOUT}). Local models bypass litellm "
                         f"entirely (_ollama_direct_chat) and set this directly as "
                         f"aiohttp.ClientTimeout(total=...) on our own request -- full control, "
                         f"not mediated by litellm. Sized with generous headroom above observed "
                         f"load-time variance (172s / >300s-failed / 7.8s-warm-cache across three "
                         f"identical curl attempts) confirmed to be pure NFS storage-contention "
                         f"variability on this shared cluster, not a code bug -- raise further if "
                         f"a busier day needs it. A hung request still eventually raises and gets "
                         f"retried like any other transient failure (see process_item's generator/ "
                         f"judge call-error handling) rather than hanging forever. Does not affect "
                         f"Groq calls, which never enter this local-only code path.")
    p.add_argument("--ollama-num-ctx", type=int, default=DEFAULT_OLLAMA_NUM_CTX,
                    help=f"Ollama context-window size (num_ctx) for ollama_chat/ollama models "
                         f"only (default {DEFAULT_OLLAMA_NUM_CTX}), sent as options.num_ctx on "
                         f"our own direct request. Smaller than a model's default max context "
                         f"(e.g. 262,144 for gpt-oss:20b) reduces KV-cache memory allocation and "
                         f"load time; {DEFAULT_OLLAMA_NUM_CTX} leaves ~5x headroom over this "
                         f"pipeline's worst-case measured prompt (~1660 generator / ~730 judge "
                         f"tokens on the longest item in the 239-item pool) -- re-measure before "
                         f"lowering it further.")
    p.add_argument("--vllm-request-timeout", type=int, default=DEFAULT_VLLM_REQUEST_TIMEOUT,
                    help=f"Request timeout in seconds for vllm_local models only (default "
                         f"{DEFAULT_VLLM_REQUEST_TIMEOUT}), set directly as aiohttp.ClientTimeout"
                         f"(total=...) on our own request to each vLLM server's /v1/chat/"
                         f"completions endpoint. Deliberately much tighter than --ollama-load-"
                         f"timeout's {DEFAULT_OLLAMA_LOAD_TIMEOUT}s: a vLLM server here is already "
                         f"warm and long-running (weights loaded once at server-launch time from "
                         f"local /tmp, not per-request from NFS-backed storage), so there is no "
                         f"Ollama-style load-time variance to budget for -- only generation "
                         f"latency for this pipeline's few-thousand-token prompts.")
    p.add_argument("--fresh-start", action="store_true",
                    help="Ignore any existing deliverable CSV for auto-exclude purposes and "
                         "reprocess the FULL candidate pool from scratch, as if no prior session "
                         "had ever run (an explicitly-passed --exclude-ids/--pool-size is still "
                         "honored). Intended for a clean, from-scratch comparison run (e.g. a new "
                         "backend) without being auto-excluded by items a DIFFERENT backend "
                         "already approved. Pair with --output-tag so the clean run's results "
                         "don't overwrite the prior partial run's deliverable/audit trail.")
    p.add_argument("--output-tag", type=str, default=None,
                    help="Suffix inserted before the file extension of both the deliverable CSV "
                         "and the audit trail JSONL -- e.g. --output-tag vllm writes "
                         "entregavel_2_100_questoes_vllm.csv and aig_audit_trail_vllm.jsonl "
                         "instead of the default (untagged) files, keeping this run's output "
                         "fully separate from a prior backend's accumulated results. A SECOND "
                         "run with the same --output-tag (without --fresh-start) resumes/"
                         "auto-excludes from its OWN tagged file, same as the untagged default "
                         "does -- the tag doesn't disable multi-session accumulation, just scopes "
                         "it to a separate file.")
    return p.parse_args()


# Both Groq and a local Ollama server host multiple distinct model vendors
# (Qwen/Alibaba, GPT-OSS/OpenAI, Llama/Meta, Gemma/Google, Mistral/Mistral
# AI, Phi/Microsoft, DeepSeek/DeepSeek...) under a single litellm provider
# prefix ("groq/" or "ollama_chat/") -- the plain provider-prefix check
# below would treat any two same-provider models as "the same family"
# regardless of vendor. Confirmed hit in practice for BOTH providers: Groq
# hosting Qwen/GPT-OSS/Llama/Gemma side by side, and two different
# Ollama-hosted models (e.g. qwen2.5:7b vs. llama3.1:8b) both resolving to
# the bare provider string "ollama_chat" with the old logic. Mapping is by
# model-name prefix, checked for both of these providers; every other
# provider keeps the original prefix-based logic unchanged.
_HOSTED_MODEL_VENDOR_PREFIXES = {
    "qwen": "alibaba",
    "gpt-oss": "openai",
    "llama": "meta",
    "codellama": "meta",
    "gemma": "google",
    "mistral": "mistralai",
    "mixtral": "mistralai",
    "phi": "microsoft",
    "deepseek": "deepseek",
}
_MULTI_VENDOR_PROVIDERS = {"groq", "ollama_chat", "ollama", "vllm_local"}

# Deliberately narrower than _MULTI_VENDOR_PROVIDERS above: vllm_local is
# EXCLUDED here even though it needs the same vendor-prefix detection for
# R26 (_model_family). _reasoning_effort_for_model's `reasoning_effort`
# passthrough is a Groq/Ollama-specific mechanism -- vLLM's OpenAI-
# compatible endpoint has no confirmed equivalent request-level param, and
# unlike litellm's known-permissive kwarg forwarding, an unrecognized field
# sent to vLLM's server could be silently ignored OR rejected outright
# depending on version/strictness, which hasn't been tested. The intended
# fix for vLLM is server-side (`--reasoning-parser qwen3` at launch time,
# already part of this run's setup), not a request-level lever -- see
# _reasoning_effort_for_model's docstring.
_REASONING_EFFORT_PROVIDERS = {"groq", "ollama_chat", "ollama"}


def _model_family(model_name: str) -> str:
    provider, _, rest = model_name.partition("/")
    provider_lower = provider.lower()
    if provider_lower in _MULTI_VENDOR_PROVIDERS and rest:
        name = rest[len("openai/"):] if rest.startswith("openai/") else rest
        # Ollama tags a specific quantization/size after ':' (e.g.
        # "qwen2.5:7b") -- irrelevant to vendor identity, so it's stripped
        # before prefix matching.
        name_lower = name.split(":")[0].lower()
        for prefix, vendor in _HOSTED_MODEL_VENDOR_PREFIXES.items():
            if name_lower.startswith(prefix):
                return vendor
        # Unrecognized model on a multi-vendor provider: fall through to
        # the bare-provider-string default below (e.g. "groq", "ollama_chat")
        # -- the conservative choice, since it blocks pairing two
        # unrecognized same-provider models rather than silently assuming
        # they're different vendors. Add the vendor to
        # _HOSTED_MODEL_VENDOR_PREFIXES above once it's known, rather than
        # relying on --allow-same-model-judge as a permanent workaround.
    return model_name.split("/")[0].split("-")[0].lower()


def enforce_r26(generator_model: str, judge_model: str, allow_same: bool) -> None:
    if _model_family(generator_model) == _model_family(judge_model) and not allow_same:
        raise SystemExit(
            f"constitution R26 violation: Generator ('{generator_model}') and Judge "
            f"('{judge_model}') resolve to the same model family, and this pipeline has "
            f"no human-review step to fall back on. Pass --allow-same-model-judge to "
            f"override for local debugging, or choose models from different providers."
        )


def _tagged_path(path: Path, tag: Optional[str]) -> Path:
    """Inserts `_<tag>` before a path's extension, e.g. _tagged_path(
    Path("entregavel_2_100_questoes.csv"), "vllm") -> "entregavel_2_100_
    questoes_vllm.csv". Returns `path` unchanged if tag is falsy."""
    if not tag:
        return path
    return path.with_name(f"{path.stem}_{tag}{path.suffix}")


async def main_async() -> None:
    args = parse_args()
    global DRY_RUN, _daily_budget, _OLLAMA_KEEP_ALIVE, _OLLAMA_LOAD_TIMEOUT, _OLLAMA_NUM_CTX, _VLLM_REQUEST_TIMEOUT
    DRY_RUN = args.dry_run
    _OLLAMA_KEEP_ALIVE = args.ollama_keep_alive
    _OLLAMA_LOAD_TIMEOUT = args.ollama_load_timeout
    _OLLAMA_NUM_CTX = args.ollama_num_ctx
    _VLLM_REQUEST_TIMEOUT = args.vllm_request_timeout
    _attach_file_logging()

    # --dry-run writes to separate *.dryrun.* files so a mock/plumbing test
    # can never overwrite or append into the real, multi-session
    # accumulated deliverable/audit-trail (see path constants' docstring).
    # --output-tag (non-dry-run only) additionally scopes a real run's
    # output to its own separate pair of files -- e.g. a clean vLLM
    # comparison run's results never mix with or overwrite a prior Groq/
    # Ollama partial run's accumulated deliverable/audit trail.
    if DRY_RUN:
        deliverable_path = DRYRUN_DELIVERABLE_PATH
        audit_trail_path = DRYRUN_AUDIT_TRAIL_PATH
    else:
        deliverable_path = _tagged_path(DELIVERABLE_PATH, args.output_tag)
        audit_trail_path = _tagged_path(AUDIT_TRAIL_PATH, args.output_tag)

    logger.info("WAPLA AIG Engine starting. SEED=%d, DRY_RUN=%s", SEED, DRY_RUN)
    if not DRY_RUN:
        enforce_r26(args.generator_model, args.judge_model, args.allow_same_model_judge)
        if _LITELLM is None and _OPENAI_ASYNC_CLIENT is None:
            raise SystemExit(
                "No LLM backend available. Install `litellm` (preferred) or `openai`, "
                "set the relevant API key environment variable(s), or pass --dry-run."
            )
        logger.info("Generator model: %s | Judge model: %s", args.generator_model, args.judge_model)

        both_local = _is_local_model(args.generator_model) and _is_local_model(args.judge_model)
        if both_local:
            logger.info("Generator and judge are both local (Ollama/vLLM) models -- no API "
                        "rate limit or daily token quota applies, so the daily token-quota "
                        "guard is disabled for this run.")
            _daily_budget = None
        else:
            _daily_budget = DailyTokenBudget(TOKEN_USAGE_LOG_PATH, args.daily_token_cap)
            logger.info("Daily token quota guard active: soft cap=%d, already used today=%d (%s).",
                        _daily_budget.soft_cap, _daily_budget.cumulative_tokens, TOKEN_USAGE_LOG_PATH)

    # Auto-exclude question_ids already present in a prior session's
    # deliverable CSV, unioned with any --exclude-ids passed explicitly --
    # so a forgotten/stale --exclude-ids flag can no longer cause the
    # pipeline to re-spend quota re-generating an item that's already
    # approved and sitting in the shipped CSV. --fresh-start skips this
    # entirely -- a deliberate one-time "process the full pool as if
    # nothing had been approved before" run, independent of --output-tag
    # (which only decides WHERE this run's own results get written).
    exclude_ids: set[int] = set()
    if args.exclude_ids:
        exclude_ids |= {int(x.strip()) for x in args.exclude_ids.split(",") if x.strip()}
    existing_df: Optional[pd.DataFrame] = None
    if args.fresh_start:
        logger.info("--fresh-start: ignoring any existing %s for auto-exclude -- "
                    "reprocessing the full candidate pool from scratch.", deliverable_path)
    elif deliverable_path.exists():
        try:
            existing_df = pd.read_csv(deliverable_path)
            prior_ids = {int(x) for x in existing_df["question_id"].tolist()}
            newly_auto_excluded = prior_ids - exclude_ids
            if newly_auto_excluded:
                logger.info("Auto-excluding %d question_id(s) already in %s from a prior "
                            "session: %s", len(newly_auto_excluded), deliverable_path,
                            sorted(newly_auto_excluded))
            exclude_ids |= prior_ids
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read prior deliverable %s for auto-exclude (%s); "
                           "relying on --exclude-ids only.", deliverable_path, exc)

    already_approved = len(existing_df) if existing_df is not None else 0
    pool = build_candidate_pool(pool_size=args.pool_size, exclude_ids=exclude_ids or None)
    if already_approved + len(pool) < args.target_n:
        logger.warning("Cumulative approved so far (%d) + remaining candidate pool (%d) is "
                        "below target_n (%d); the target cannot be reached even if every "
                        "remaining candidate is approved.", already_approved, len(pool), args.target_n)

    audit_result = None
    if not DRY_RUN:
        logger.info("Running one-time judge verbosity-confound audit (spec.md 4.2.1 step 2)...")
        audit_result = await run_verbosity_confound_audit(args.judge_model)
        with open(JUDGE_BIAS_AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, ensure_ascii=False, indent=2)

    results = await run_pipeline(
        pool, args.generator_model, args.judge_model,
        args.max_retries, args.concurrency, args.rigorous_position_check,
    )

    final_df, new_approved_df = select_final_100(results, args.target_n, existing_df=existing_df)
    final_df.to_csv(deliverable_path, index=False, encoding="utf-8")
    logger.info("Deliverable written to %s (%d cumulative rows, +%d this session).",
                deliverable_path, len(final_df), len(new_approved_df))

    write_audit_trail(results, audit_trail_path, append=not DRY_RUN)
    print_run_summary(results, final_df, audit_result, new_approved_df=new_approved_df,
                      target_n=args.target_n, deliverable_path=deliverable_path,
                      audit_trail_path=audit_trail_path)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
