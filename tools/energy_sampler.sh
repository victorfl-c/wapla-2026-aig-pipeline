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

echo "timestamp_unix,power_draw_w,utilization_gpu_pct,memory_used_mib" > "$OUTPUT_CSV"

while true; do
  ts=$(date +%s.%N)
  sample=$(nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used --format=csv,noheader,nounits)
  echo "${ts},${sample}" >> "$OUTPUT_CSV"
  sleep "$SAMPLE_INTERVAL_SECONDS"
done
