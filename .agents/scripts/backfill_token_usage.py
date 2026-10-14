#!/usr/bin/env python3
"""
Backfill histórico de conversaciones locales de Antigravity hacia BigQuery.
"""
import os
import glob
import json
import re
import datetime
import subprocess
import tiktoken
from google.cloud import bigquery

def get_developer_user():
    try:
        user = subprocess.check_output(
            ["gcloud", "config", "get-value", "account"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if user and "@" in user:
            return user
    except Exception:
        pass
    return os.environ.get("USER", os.environ.get("USERNAME", "unknown_developer"))

def get_default_model():
    candidate_paths = [
        os.path.expanduser("~/.gemini/antigravity/settings.json"),
        os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
    ]
    for settings_path in candidate_paths:
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("model", "Gemini 3.8 Flash (High)")
            except Exception:
                pass
    return "Gemini 3.8 Flash (High)"

def backfill():
    project_id = os.environ.get("WORKLOAD_PROJECT_ID", "desa01-uip")
    dataset_name = os.environ.get("DATASET_NAME", "antigravity_telemetry")
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset_name}.antigravity_token_usage"
    
    enc = tiktoken.get_encoding("cl100k_base")
    
    candidate_dirs = [
        os.path.expanduser("~/.gemini/antigravity/brain"),
        os.path.expanduser("~/.gemini/antigravity-cli/brain")
    ]
    
    transcripts = []
    for conv_dir in candidate_dirs:
        if os.path.exists(conv_dir):
            found = glob.glob(os.path.join(conv_dir, "*", ".system_generated", "logs", "transcript.jsonl"))
            transcripts.extend(found)
            
    transcripts = sorted(list(set(transcripts)))
    
    print(f"Descubiertos {len(transcripts)} historiales de conversacion.")
    dev_user = get_developer_user()
    default_model = get_default_model()
    print(f"Desarrollador asignado: {dev_user}")
    print(f"Modelo por defecto: {default_model}")
    
    all_rows = []
    total_prompt_tokens = 0
    total_candidate_tokens = 0
    
    for t_path in transcripts:
        parts = os.path.normpath(t_path).split(os.sep)
        conv_id = parts[-4] if len(parts) >= 4 else "unknown_conversation"
        current_model = default_model
        running_prompt_tokens = 500
        
        try:
            with open(t_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        step = json.loads(line)
                    except Exception:
                        continue
                        
                    stype = step.get("type")
                    source = step.get("source")
                    content = step.get("content") or ""
                    thinking = step.get("thinking") or ""
                    tool_calls = step.get("tool_calls") or []
                    step_idx = step.get("step_index", 0)
                    created_at = step.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
                    
                    if "<USER_SETTINGS_CHANGE>" in content and "Model Selection" in content:
                        m = re.search(r"Model Selection(?:`|\s)*from\s+.*?\s+to\s+(.*?)\.(?:\s+No need|\s+If reporting|\n|</USER_SETTINGS_CHANGE>|$)", content)
                        if m:
                            current_model = m.group(1).strip()
                            
                    if stype in ["USER_INPUT", "GENERIC"] or source in ["USER_EXPLICIT", "SYSTEM"]:
                        running_prompt_tokens += len(enc.encode(str(content)))
                    elif stype == "PLANNER_RESPONSE" or source == "MODEL":
                        cand_text = str(content) + str(thinking) + (json.dumps(tool_calls) if tool_calls else "")
                        c_tok = len(enc.encode(cand_text)) if cand_text else 0
                        p_tok = running_prompt_tokens
                        
                        usage_date = created_at[:10] if len(created_at) >= 10 else datetime.date.today().isoformat()
                        
                        all_rows.append({
                            "timestamp": created_at,
                            "usage_date": usage_date,
                            "developer_user": dev_user,
                            "conversation_id": conv_id,
                            "step_index": step_idx,
                            "model_name": current_model,
                            "prompt_tokens": p_tok,
                            "candidates_tokens": c_tok,
                            "total_tokens": p_tok + c_tok,
                            "client_version": "antigravity/cli/1.2.14",
                            "project_id": os.environ.get("AI_PROJECT_ID", "desa01-uip"),
                            "workspace_path": os.getcwd()
                        })
                        
                        total_prompt_tokens += p_tok
                        total_candidate_tokens += c_tok
                        running_prompt_tokens += c_tok
        except Exception as e:
            print(f"Error procesando {t_path}: {e}")

    print(f"\nTotal interacciones extraidas: {len(all_rows)}")
    print(f"Tokens de Input: {total_prompt_tokens:,}")
    print(f"Tokens de Output: {total_candidate_tokens:,}")
    print(f"Total Tokens: {total_prompt_tokens + total_candidate_tokens:,}")
    
    state_dir = os.path.expanduser("~/.gemini/antigravity")
    if not os.path.exists(state_dir):
        state_dir = os.path.expanduser("~/.gemini/antigravity-cli")
    os.makedirs(state_dir, exist_ok=True)
    state_file = os.path.join(state_dir, ".telemetry_state.json")
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

    rows_to_insert = []
    for r in all_rows:
        cid = r["conversation_id"]
        sidx = r["step_index"]
        if sidx > state.get(cid, -1):
            rows_to_insert.append(r)

    if not rows_to_insert:
        print("Todas las interacciones historicas de este desarrollador ya fueron cargadas previamente.")
        return

    batch_size = 250
    inserted = 0
    for i in range(0, len(rows_to_insert), batch_size):
        batch = rows_to_insert[i:i+batch_size]
        err = client.insert_rows_json(table_id, batch)
        if err:
            print(f"Error en lote {i}: {err}")
        else:
            inserted += len(batch)
            for r in batch:
                cid = r["conversation_id"]
                if r["step_index"] > state.get(cid, -1):
                    state[cid] = r["step_index"]
            print(f"Cargado lote {i // batch_size + 1}/{(len(rows_to_insert) + batch_size - 1) // batch_size} ({inserted}/{len(rows_to_insert)} filas)")

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f)

    print(f"\n[OK] Backfill completado exitosamente: {inserted} filas insertadas en {table_id}")

if __name__ == "__main__":
    backfill()
