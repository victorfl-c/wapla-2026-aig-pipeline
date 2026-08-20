"""One-off remediation pass, 2026-08-19: rebuild the 100-item deliverable
so every item passes qwen3.6-27b's judge (blind-solve + Bloom-alignment +
mutual-exclusivity + length-bias + factual-soundness), not just the
original gpt-oss-20b judge.

- 50 items already qwen-validated (output/reaudit_bloom_qwen_pool100.jsonl,
  approved=True) are kept as-is, unchanged.
- 7 context-incomplete items (base_text never actually contains the
  scenario/figure the stem references -- a source-data defect no generator
  can fix) go straight to the backfill pool, skipping wasted retries.
- 43 items (23 Bloom-demoted via QWEN_BLOOM_DEMOTION_OVERRIDES, 20 other
  defects) are regenerated from the ORIGINAL dataset row (never from the
  already-AI-rewritten delivered text) with gpt-oss-20b generator (Design D
  countdown-marker length control) + qwen3.6-27b judge.
- Anything that exhausts max_retries=4 cascades into the 136-item backfill
  pool (the 239-item production pool's tried-but-never-approved remainder),
  ordered easiest-first (ascending structural_flaw_count) on the theory
  those are likelier to succeed under a fresh model pairing. The 3
  already-gpt-oss-20b-approved-but-unused reserve items (368/418/505) are
  tried FIRST via a judge-only re-check (no regeneration needed) since
  that's nearly free if it works.
- Each slot keeps its ORIGINAL delivered item's correct_option letter, so
  the final correct_option distribution doesn't drift from a deliberate
  regeneration decision.

Writes a NEW file (does not touch entregavel_2_100_questoes_design_d_full.csv):
  output/entregavel_2_100_questoes_qwen_validated.csv
  output/aig_audit_trail_qwen_remediation.jsonl
  output/remediation_progress.log  (tailable progress, human-readable)
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/home/CIN/vflc/meu_projeto_mestrado")
from WAPLA_AIG_Engine import (  # noqa: E402
    COMPETITION_SCHEMA, GeneratedItem, ProcessedResult, build_candidate_pool,
    item_to_row, judge_agent, process_item, write_audit_trail,
)

GENERATOR_MODEL = "vllm_local/gpt-oss-20b@8000"
JUDGE_MODEL = "vllm_local/qwen3.6-27b@8001"
MAX_RETRIES = 4
CONCURRENCY = 1

CURRENT_CSV = "output/entregavel_2_100_questoes_design_d_full.csv"
REAUDIT_JSONL = "output/reaudit_bloom_qwen_pool100.jsonl"
OUT_CSV = Path("output/entregavel_2_100_questoes_qwen_validated.csv")
AUDIT_TRAIL_PATH = Path("output/aig_audit_trail_qwen_remediation.jsonl")
PROGRESS_LOG = Path("output/remediation_progress.log")

SKIP_TO_BACKFILL_QIDS = [43, 193, 293, 343, 508, 690, 750]
RESERVE_QIDS = [368, 418, 505]  # already gpt-oss-20b-approved, unused, try judge-only first

TOTAL_SLOTS = 50


def log_progress(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} | {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def row_from_csv(row: pd.Series) -> GeneratedItem:
    def s(col):
        v = row.get(col)
        return None if pd.isna(v) else str(v)
    return GeneratedItem(
        base_text=s("base_text"), stem=s("stem"),
        statement_i=s("statement_i"), statement_ii=s("statement_ii"),
        statement_iii=s("statement_iii"), statement_iv=s("statement_iv"),
        assertion_i=s("assertion_i"), assertion_ii=s("assertion_ii"),
        option_a=s("option_a"), option_b=s("option_b"), option_c=s("option_c"),
        option_d=s("option_d"), option_e=s("option_e"), correct_option=s("correct_option"),
    )


async def main():
    current_df = pd.read_csv(CURRENT_CSV)
    assert len(current_df) == 100

    reaudit = [json.loads(l) for l in open(REAUDIT_JSONL, encoding="utf-8").read().splitlines()]
    keep_qids = sorted(r["question_id"] for r in reaudit if r.get("approved") is True)
    failed_qids = sorted(r["question_id"] for r in reaudit if r.get("approved") is False)
    assert len(keep_qids) == 50 and len(failed_qids) == 50

    regen_qids = [q for q in failed_qids if q not in SKIP_TO_BACKFILL_QIDS]
    assert len(regen_qids) == 43

    keep_df = current_df[current_df["question_id"].isin(keep_qids)].copy()
    target_letter_for_qid = dict(zip(current_df["question_id"], current_df["correct_option"]))

    delivered_qids = set(current_df["question_id"])
    all_pool = build_candidate_pool(pool_size=None)  # full merged original+flaw_summary
    all_pool_by_qid = all_pool.set_index("question_id", drop=False)

    tried_239 = sorted(set(all_pool_by_qid.index) & set(
        json.loads(l)["question_id"]
        for l in open("output/aig_audit_trail_design_d_full.jsonl", encoding="utf-8")
    ))
    backfill_136 = [q for q in tried_239 if q not in delivered_qids and q not in RESERVE_QIDS]
    backfill_pool_df = all_pool_by_qid.loc[backfill_136].sort_values(
        "structural_flaw_count", ascending=True
    )
    backfill_queue = list(backfill_pool_df.itertuples(index=False))
    backfill_cols = list(backfill_pool_df.columns)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    results_final: dict[int, ProcessedResult] = {}
    all_attempts: list[ProcessedResult] = []
    resolved = 0
    total_generation_attempts = 0
    total_generation_approved = 0

    def record(result: ProcessedResult):
        nonlocal total_generation_attempts, total_generation_approved
        all_attempts.append(result)
        total_generation_attempts += result.attempts if result.attempts else 1
        if result.approved:
            total_generation_approved += 1

    async def try_backfill_for_slot(orig_qid: int, slot_letter: str) -> bool:
        nonlocal resolved
        while backfill_queue:
            cand_tuple = backfill_queue.pop(0)
            cand_row = pd.Series(dict(zip(backfill_cols, cand_tuple)))
            cand_qid = int(cand_row["question_id"])
            log_progress(f"  backfill candidate qid={cand_qid} (flaw_count="
                         f"{cand_row['structural_flaw_count']}) attempting for slot orig_qid={orig_qid}")
            result = await process_item(cand_row, slot_letter, GENERATOR_MODEL, JUDGE_MODEL,
                                         MAX_RETRIES, False, semaphore)
            record(result)
            if result.approved:
                results_final[orig_qid] = result
                resolved += 1
                log_progress(f"[{resolved}/{TOTAL_SLOTS}] slot orig_qid={orig_qid} FILLED via "
                             f"backfill (new content from qid={cand_qid}), rate so far: "
                             f"{total_generation_approved}/{total_generation_attempts} attempts approved")
                return True
            log_progress(f"  backfill candidate qid={cand_qid} exhausted, trying next")
        log_progress(f"BACKFILL POOL EXHAUSTED -- could not fill slot orig_qid={orig_qid}")
        return False

    # --- Step 0: try the 3 free reserve items via judge-only re-check ---
    log_progress("=== Step 0: judge-only re-check of 3 unused reserve items (368/418/505) ===")
    reserve_hist = {}
    for l in open("output/aig_audit_trail_design_d_full.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["question_id"] in RESERVE_QIDS and (d.get("judge_outcome") or {}).get("approved"):
            reserve_hist[d["question_id"]] = d
    reserve_available = list(reserve_hist.keys())
    reserve_ptr = 0

    # --- Step 1: 7 context-incomplete items, straight to backfill ---
    log_progress(f"=== Step 1: {len(SKIP_TO_BACKFILL_QIDS)} context-incomplete items -> backfill directly ===")
    for qid in SKIP_TO_BACKFILL_QIDS:
        slot_letter = target_letter_for_qid[qid]
        filled = False
        if reserve_ptr < len(reserve_available):
            r_qid = reserve_available[reserve_ptr]
            d = reserve_hist[r_qid]
            gi = d["generated_item"]
            item = GeneratedItem(**{k: gi.get(k) for k in GeneratedItem.model_fields})
            # IMPORTANT: judge with the item's OWN historically-recorded
            # target_letter, not the failing slot's letter -- this item's
            # correct content already lives at ITS letter; re-judging it
            # under a different target_letter would check the wrong option
            # and either spuriously fail or (worse) spuriously pass an
            # actually-wrong answer key. The overall corpus only needs
            # reasonable A-E balance across all 100 rows, not a fixed
            # letter per replaced slot, so keeping the reserve item's own
            # letter is safe and correct.
            own_letter = d["target_letter"]
            outcome = await judge_agent(item, own_letter, d["target_level"], JUDGE_MODEL)
            record(ProcessedResult(question_id=r_qid, original_row={}, target_letter=own_letter,
                                    target_level=d["target_level"], demoted=d["demoted"],
                                    approved=outcome.approved, attempts=1))
            if outcome.approved:
                row_for_item = pd.Series({"question_type": all_pool_by_qid.loc[r_qid, "question_type"],
                                           "discipline": all_pool_by_qid.loc[r_qid, "discipline"],
                                           "base_text": gi.get("base_text")})
                pr = ProcessedResult(question_id=r_qid, original_row=row_for_item.to_dict(),
                                      target_letter=own_letter, target_level=d["target_level"],
                                      demoted=d["demoted"], approved=True, attempts=1, final_item=item)
                results_final[qid] = pr
                resolved += 1
                reserve_ptr += 1
                log_progress(f"[{resolved}/{TOTAL_SLOTS}] slot orig_qid={qid} FILLED via free reserve "
                             f"(qid={r_qid}, judge-only re-check passed at its own letter '{own_letter}')")
                filled = True
        if not filled:
            filled = await try_backfill_for_slot(qid, slot_letter)

    # --- Step 2: regenerate the 43 ---
    log_progress(f"=== Step 2: regenerating {len(regen_qids)} items (Bloom-demoted + other-defect) ===")
    for qid in regen_qids:
        row = all_pool_by_qid.loc[qid]
        slot_letter = target_letter_for_qid[qid]
        log_progress(f"  regenerating qid={qid} (target_level input='{row['taxonomy_level']}', "
                     f"demotion override applies: {qid in [26,29,106,132,138,246,364,374,392,457,483,489,516,519,528,559,623,745,779,794,808,830,840]})")
        result = await process_item(row, slot_letter, GENERATOR_MODEL, JUDGE_MODEL,
                                     MAX_RETRIES, False, semaphore)
        record(result)
        if result.approved:
            results_final[qid] = result
            resolved += 1
            log_progress(f"[{resolved}/{TOTAL_SLOTS}] slot orig_qid={qid} REGENERATED successfully "
                         f"({result.attempts} attempt(s)), rate so far: "
                         f"{total_generation_approved}/{total_generation_attempts} attempts approved")
        else:
            log_progress(f"  qid={qid} exhausted {MAX_RETRIES} retries -- cascading to backfill")
            await try_backfill_for_slot(qid, slot_letter)

    # --- Rebuild final CSV ---
    new_rows = [item_to_row(r) for r in results_final.values()]
    new_df = pd.DataFrame(new_rows, columns=COMPETITION_SCHEMA)
    final_df = pd.concat([keep_df[COMPETITION_SCHEMA], new_df], ignore_index=True)

    log_progress("=== Integrity check ===")
    log_progress(f"Total rows: {len(final_df)} (expect 100)")
    dupes = final_df["question_id"].duplicated().sum()
    log_progress(f"Duplicate question_ids: {dupes} (expect 0)")
    unresolved = TOTAL_SLOTS - resolved
    log_progress(f"Resolved slots: {resolved}/{TOTAL_SLOTS} (unresolved: {unresolved})")

    final_df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    write_audit_trail(all_attempts, AUDIT_TRAIL_PATH, append=False)
    log_progress(f"Wrote {OUT_CSV} and {AUDIT_TRAIL_PATH}")
    log_progress(f"FINAL: {len(final_df)} rows, {dupes} duplicates, "
                 f"{total_generation_approved}/{total_generation_attempts} total generation attempts approved "
                 f"({total_generation_approved/max(total_generation_attempts,1)*100:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
