#!/bin/bash
# GPU power-draw sampler for Green AI energy accounting (relatorio_tecnico.tex
# Secao "Medicao Real de Energia" -- constitution.md R37, spec.md Sec 5.6,
# literatura/mod_7_energy_measurement/).
#
# Samples `nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used`
# every SAMPLE_INTERVAL_SECONDS, timestamped, to OUTPUT_CSV. Intended to run
# for the exact duration of a WAPLA_AIG_Engine.py invocation: start it
# immediately before the engine process, kill it immediately after (e.g. on
# the process's exit code), so the sampled window matches the measured run.
#
# Post-processing (trapezoidal integration of power.draw over time -> total
# kWh, average/peak power, energy-per-approved-item) is NOT done by this
# script -- it only collects the raw samples. See the Design D full-run
# energy computation in this project's own working notes for the
# integration method (manual trapezoidal rule, no scipy dependency assumed).
#
# Usage:
#   tools/energy_sampler.sh [output_csv] [interval_seconds] &
#   SAMPLER_PID=$!
#   python3 -u WAPLA_AIG_Engine.py ...
#   kill "$SAMPLER_PID"
#
# Defaults match the run this script was extracted from (Design D full-pool
# calibration, 2026-08-17, cluster-node7): ~/energy_samples.csv, 2s interval.

set -u

OUTPUT_CSV="${1:-$HOME/energy_samples.csv}"
SAMPLE_INTERVAL_SECONDS="${2:-2}"

sample_loop() {
  echo "timestamp_unix,power_draw_w,utilization_gpu_pct,memory_used_mib" > "$OUTPUT_CSV"
  while true; do
    ts=$(date +%s.%N)
    sample=$(nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used --format=csv,noheader,nounits)
    echo "${ts},${sample}" >> "$OUTPUT_CSV"
    sleep "$SAMPLE_INTERVAL_SECONDS"
  done
}

# ---------------------------------------------------------------------------
# SUPERVISED MODE, added 2026-10-02 after the Design D full run.
#
# WHY. On 2026-08-17 this sampler was started by hand and outlived neither
# more nor less than it should have -- it stopped at 23:08:30 UTC while the
# engine ran until 05:39:23 UTC. The result: the window covered 775 of 918
# generation attempts (84.4%) and 5.14 h of an 11.50 h run. The energy
# figure itself is sound (1.4979 kWh, verified by re-integrating these
# samples) and so is the 16.1 Wh/approved-item rate, because the 93
# approvals the report divides by are exactly the ones inside the window.
# What was lost is COVERAGE: 143 attempts and 10 further approvals were
# never instrumented, so the run's true total is unknown.
#
# The header above already prescribed the remedy -- "start it immediately
# before the engine process, kill it immediately after (e.g. on the process's
# exit code)". The instrument was documented correctly and invoked otherwise.
# Prescribing a discipline is not the same as enforcing one, so this mode
# makes the window structurally unable to differ from the run.
#
# Usage:
#   tools/energy_sampler.sh OUT.csv 2 -- python3 -u WAPLA_AIG_Engine.py ...
#
# Samples for exactly the engine's lifetime and exits with ITS exit code, so
# a failed run is still a failed job. The legacy background form still works
# and is left in place so existing scripts do not break.
# ---------------------------------------------------------------------------
for arg in "$@"; do
  if [ "$arg" = "--" ]; then
    SUPERVISED=1
  fi
done

if [ "${SUPERVISED:-0}" = "1" ]; then
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do shift; done
  shift  # drop the -- itself
  if [ "$#" -eq 0 ]; then
    echo "energy_sampler.sh: --  given but no command followed it." >&2
    exit 2
  fi

  sample_loop &
  SAMPLER_PID=$!
  # Stop sampling however we leave: normal exit, Ctrl-C, or SLURM's TERM.
  trap 'kill "$SAMPLER_PID" 2>/dev/null || true' EXIT INT TERM

  "$@"
  ENGINE_RC=$?

  kill "$SAMPLER_PID" 2>/dev/null || true
  wait "$SAMPLER_PID" 2>/dev/null || true
  trap - EXIT INT TERM

  echo "energy_sampler.sh: engine exited ${ENGINE_RC}; samples in ${OUTPUT_CSV}" >&2
  exit "$ENGINE_RC"
fi

sample_loop
