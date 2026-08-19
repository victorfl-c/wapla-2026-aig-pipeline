#!/bin/bash
#SBATCH --job-name=wapla_calib
#SBATCH --partition=short-simple
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=02:00:00

cd ~/meu_projeto_mestrado
ollama serve > ~/ollama_server.log 2>&1 &
sleep 5

python3 WAPLA_AIG_Engine.py --generator-model ollama_chat/gpt-oss:20b --judge-model ollama_chat/qwen3.6:27b --concurrency 1 --max-retries 4 --pool-size 10
