"""Retrospective token-count RECONSTRUCTION for today's local-model sessions.

IMPORTANT -- this is NOT measured API usage. No per-call token telemetry was
ever recorded for any session that used vllm_local for both generator and
judge (see constitution.md R37 -- the daily-token-quota/_record_usage()
mechanism is a no-op whenever both agents are local models, which is true
for every real session run today). This script reconstructs an ESTIMATE by:

  - Re-tokenizing the actual stored `generated_item` / `judge_outcome.raw_verdict`
    content with each model's REAL tokenizer (phi-4 for the generator side,
    gpt-oss-20b for the judge side) -- this part is exact, since the stored
    content IS what was produced.
  - Reconstructing the PROMPT side by replaying build_generator_messages()/
    build_judge_messages() with the original dataset row (reloaded by
    question_id) and feedback recovered from the previous attempt's stored
    mechanical_prefilter/judge_outcome reasons -- then tokenizing that
    reconstructed prompt text.

Known, disclosed approximation: the CURRENT (Design D) system-prompt Rule 1
wording is used uniformly for all four sessions, including r42fix and
design_c_fix, which historically ran under earlier Rule-1 text (pre-Design-C
abstract wording, and Design-C's banded-target wording, respectively). This
adds a small, bounded overestimate to the system-prompt portion of those two
sessions' reconstructed generator prompts (on the order of 100-150 words out
of a much larger total prompt) -- disclosed here, not hidden.

Must run where /tmp/models/{phi-4,gpt-oss-20b} are present (cluster-node7).
"""
import json
import sys
from collections import defaultdict

import pandas as pd
from transformers import AutoTokenizer

sys.path.insert(0, "/home/CIN/vflc/meu_projeto_mestrado")
from WAPLA_AIG_Engine import (
    QUESTION_FORMAT, LETTER_TO_COL, OPTION_LETTERS,
    build_generator_messages, build_judge_messages,
    compute_target_word_count, build_complex_mc_combination,
    place_options_at_letters, ASSERTION_REASON_TEMPLATES,
    GeneratedItem, load_original_dataset,
)
import random

GEN_TOKENIZER = AutoTokenizer.from_pretrained("/tmp/models/phi-4")
JUDGE_TOKENIZER = AutoTokenizer.from_pretrained("/tmp/models/gpt-oss-20b")


def n_tokens(text, tokenizer):
    if not text:
        return 0
    return len(tokenizer.encode(text, add_special_tokens=False))


def messages_text(messages):
    return "\n".join(m["content"] for m in messages)


SESSIONS = {
    "r42fix": {"path": "output/aig_audit_trail_r42fix.jsonl", "target_word_count_enabled": False},
    "design_c_fix": {"path": "output/aig_audit_trail_design_c_fix.jsonl", "target_word_count_enabled": True},
    "design_d_fix": {"path": "output/aig_audit_trail_design_d_fix.jsonl", "target_word_count_enabled": True},
    "design_d_full": {"path": "output/aig_audit_trail_design_d_full.jsonl", "target_word_count_enabled": True},
}


def load_entries(path):
    entries = []
    with open(path) as f:
        for line in f:
            entries.append(json.loads(line))
    return entries


def build_row_cache(question_ids, original_df):
    cache = {}
    for qid in question_ids:
        match = original_df[original_df["question_id"] == qid]
        if len(match):
            cache[qid] = match.iloc[0]
    return cache


def reconstruct_feedback(prev_entry):
    if prev_entry is None:
        return None
    fb = []
    if "mechanical_prefilter" in prev_entry:
        fb += prev_entry["mechanical_prefilter"].get("reasons", [])
    if "countdown_issues" in prev_entry:
        fb += prev_entry["countdown_issues"]
    if "judge_outcome" in prev_entry:
        fb += prev_entry["judge_outcome"].get("reasons", [])
    return fb or None


def main():
    print("Loading original dataset (for row reconstruction)...")
    original_df = load_original_dataset()

    all_results = defaultdict(list)  # session -> list of per-attempt dicts

    for session_name, cfg in SESSIONS.items():
        print(f"\n=== {session_name} ===")
        entries = load_entries(cfg["path"])
        # design_d_full's audit trail spans two distinct runs (full-pool
        # first pass, 2026-08-17; targeted second pass over the backfilled
        # remainder, 2026-08-18) -- split by timestamp to report them
        # separately, matching how the rest of the report already presents
        # them (not because the reconstruction needs it; see the
        # timestamp-sort fix above for that).
        pass_tag = None
        if session_name == "design_d_full":
            pass_tag = lambda e: "design_d_full_pass1" if e["timestamp_utc"] < "2026-08-18" else "design_d_full_pass2"

        by_qid = defaultdict(list)
        for e in entries:
            key = (e["question_id"], e["question_id"] if pass_tag is None else pass_tag(e))
            by_qid[key].append(e)
        for key in by_qid:
            # Sort by TIMESTAMP, not attempt number: design_d_full's audit
            # trail spans two separate passes (first pass + targeted second
            # pass), and items reprocessed in the second pass restart their
            # own attempt numbering at 1 -- sorting by attempt alone would
            # interleave the two passes' attempt-1..4 sequences incorrectly.
            by_qid[key].sort(key=lambda e: e["timestamp_utc"])

        real_qids = list({k[0] for k in by_qid})
        row_cache = build_row_cache(real_qids, original_df)

        for (qid, bucket_suffix), attempts in by_qid.items():
            row = row_cache.get(qid)
            if row is None:
                continue
            bucket_name = bucket_suffix if pass_tag is not None else session_name
            question_type = row["question_type"]
            fmt = QUESTION_FORMAT.get(question_type, "standard")
            target_letter = attempts[0]["target_letter"]
            target_level = attempts[0]["target_level"]
            demoted = attempts[0]["demoted"]

            item_rng = random.Random(f"{qid}-tokrecon")
            target_word_count = None
            if cfg["target_word_count_enabled"] and fmt == "standard":
                target_word_count = compute_target_word_count(row)

            final_outcome = "approved" if any(
                a.get("judge_outcome", {}).get("approved") for a in attempts
            ) else "backfilled"

            prev_entry = None
            for a in attempts:
                # attempt==1 is always a fresh start (no feedback yet), even
                # if this qid also appears earlier in the file from a prior
                # pass -- see the timestamp-sort note above.
                feedback = None if a["attempt"] == 1 else reconstruct_feedback(prev_entry)

                forced_options = assertion_pattern = None
                if fmt == "complex_mc":
                    combo = build_complex_mc_combination(item_rng)
                    forced_options = [{"text": combo["true_text"]}] + [{"text": t} for t in combo["distractor_texts"]]
                elif fmt == "assertion_reason":
                    true_pattern = ASSERTION_REASON_TEMPLATES[hash(qid) % len(ASSERTION_REASON_TEMPLATES)]
                    assertion_pattern = true_pattern

                gen_messages = build_generator_messages(
                    row, target_letter, target_level, demoted, question_type,
                    feedback=feedback, forced_options=forced_options,
                    assertion_pattern=assertion_pattern, target_word_count=target_word_count,
                )
                gen_prompt_tokens = n_tokens(messages_text(gen_messages), GEN_TOKENIZER)

                gi = a.get("generated_item")
                gen_completion_tokens = n_tokens(json.dumps(gi, ensure_ascii=False), GEN_TOKENIZER) if gi else 0

                judge_prompt_tokens = 0
                judge_completion_tokens = 0
                if gi is not None and "mechanical_prefilter" in a and a["mechanical_prefilter"]["passed"] is False:
                    pass  # mechanical reject: no judge call this attempt
                elif "judge_outcome" in a or gi is not None:
                    if "judge_outcome" in a:
                        item = GeneratedItem.model_validate(gi)
                        shuffled_labels = {f"Option {i + 1}": l for i, l in enumerate(OPTION_LETTERS)}
                        judge_messages = build_judge_messages(item, target_level, shuffled_labels)
                        judge_prompt_tokens = n_tokens(messages_text(judge_messages), JUDGE_TOKENIZER)
                        raw_verdict = a["judge_outcome"].get("raw_verdict")
                        if raw_verdict:
                            judge_completion_tokens = n_tokens(json.dumps(raw_verdict, ensure_ascii=False), JUDGE_TOKENIZER)

                all_results[bucket_name].append({
                    "question_id": qid, "attempt": a["attempt"], "final_outcome": final_outcome,
                    "gen_prompt": gen_prompt_tokens, "gen_completion": gen_completion_tokens,
                    "judge_prompt": judge_prompt_tokens, "judge_completion": judge_completion_tokens,
                    "had_judge_call": judge_prompt_tokens > 0,
                })
                prev_entry = a

    # ---- Aggregate ----
    print("\n\n" + "=" * 70)
    print("RECONSTRUCTED TOKEN ESTIMATES (not measured -- see module docstring)")
    print("=" * 70)

    combined = []
    for session_name, rows in all_results.items():
        combined.extend(rows)
        df = pd.DataFrame(rows)
        gen_total = df["gen_prompt"] + df["gen_completion"]
        judge_calls = df[df["had_judge_call"]]
        judge_total = judge_calls["judge_prompt"] + judge_calls["judge_completion"]
        per_item = df.groupby("question_id").apply(
            lambda g: (g["gen_prompt"] + g["gen_completion"] + g["judge_prompt"] + g["judge_completion"]).sum()
        )
        per_item_outcome = df.groupby("question_id")["final_outcome"].first()

        print(f"\n--- {session_name} ({df['question_id'].nunique()} items, {len(df)} attempts) ---")
        print(f"  avg tokens/generator call: {gen_total.mean():.0f}  (prompt {df['gen_prompt'].mean():.0f} + completion {df['gen_completion'].mean():.0f})")
        if len(judge_calls):
            print(f"  avg tokens/judge call:     {judge_total.mean():.0f}  (prompt {judge_calls['judge_prompt'].mean():.0f} + completion {judge_calls['judge_completion'].mean():.0f})")
        approved_items = per_item_outcome[per_item_outcome == "approved"].index
        backfilled_items = per_item_outcome[per_item_outcome == "backfilled"].index
        if len(approved_items):
            print(f"  avg tokens/item (approved, incl. retries):   {per_item[approved_items].mean():.0f}")
        if len(backfilled_items):
            print(f"  avg tokens/item (backfilled, incl. retries): {per_item[backfilled_items].mean():.0f}")

    print("\n" + "=" * 70)
    print("COMBINED ACROSS ALL FOUR SESSIONS (today's real, non-dry-run work)")
    print("=" * 70)
    cdf = pd.DataFrame(combined)
    gen_total = cdf["gen_prompt"] + cdf["gen_completion"]
    judge_calls = cdf[cdf["had_judge_call"]]
    judge_total = judge_calls["judge_prompt"] + judge_calls["judge_completion"]
    print(f"Total attempts: {len(cdf)}")
    print(f"avg tokens/generator call: {gen_total.mean():.0f}  (prompt {cdf['gen_prompt'].mean():.0f} + completion {cdf['gen_completion'].mean():.0f})")
    print(f"avg tokens/judge call:     {judge_total.mean():.0f}  (prompt {judge_calls['judge_prompt'].mean():.0f} + completion {judge_calls['judge_completion'].mean():.0f})")
    print(f"Total reconstructed tokens across all sessions: {int(gen_total.sum() + judge_total.sum()):,}")


if __name__ == "__main__":
    main()
