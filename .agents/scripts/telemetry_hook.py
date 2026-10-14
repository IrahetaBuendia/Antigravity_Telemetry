#!/usr/bin/env python3
"""
Antigravity Telemetry Hook: Captura tokens por interacción y envía streaming a BigQuery.
"""
import sys
import json
import os
import re
import datetime
import subprocess

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

def get_active_ai_project():
    if os.environ.get("AI_PROJECT_ID"):
        return os.environ.get("AI_PROJECT_ID")
    try:
        proj = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if proj and proj != "(unset)":
            return proj
    except Exception:
        pass
    return "pro-gemini-enterprise-uip-mh"

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

def main():
    response_payload = {"injectSteps": []}
    
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return
            
        data = json.loads(input_data)
        conv_id = data.get("conversationId")
        transcript_path = data.get("transcriptPath")
        model_name = data.get("modelName") or get_default_model()
        workspace_paths = data.get("workspacePaths", [])
        workspace_path = workspace_paths[0] if workspace_paths else os.getcwd()
        
        if not transcript_path or not os.path.exists(transcript_path):
            return
            
        import tiktoken
        from google.cloud import bigquery
        
        enc = tiktoken.get_encoding("cl100k_base")
        
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
                
        last_processed_step = state.get(conv_id, -1)
        
        rows_to_insert = []
        running_prompt_tokens = 500
        max_step_seen = last_processed_step
        ai_project = get_active_ai_project()
        dev_user = get_developer_user()
        
        with open(transcript_path, "r", encoding="utf-8") as f:
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
                
                # Detectar cambios explícitos de modelo durante la conversación en el chat
                if "<USER_SETTINGS_CHANGE>" in content and "Model Selection" in content:
                    m = re.search(r"Model Selection(?:`|\s)*from\s+.*?\s+to\s+(.*?)\.(?:\s+No need|\s+If reporting|\n|</USER_SETTINGS_CHANGE>|$)", content)
                    if m:
                        model_name = m.group(1).strip()
                
                if stype in ["USER_INPUT", "GENERIC"] or source in ["USER_EXPLICIT", "SYSTEM"]:
                    running_prompt_tokens += len(enc.encode(str(content)))
                elif stype == "PLANNER_RESPONSE" or source == "MODEL":
                    cand_text = str(content) + str(thinking) + (json.dumps(tool_calls) if tool_calls else "")
                    c_tok = len(enc.encode(cand_text)) if cand_text else 0
                    
                    if step_idx > last_processed_step:
                        usage_date = created_at[:10] if len(created_at) >= 10 else datetime.date.today().isoformat()
                        p_tok = running_prompt_tokens
                        rows_to_insert.append({
                            "timestamp": created_at,
                            "usage_date": usage_date,
                            "developer_user": dev_user,
                            "conversation_id": conv_id,
                            "step_index": step_idx,
                            "model_name": model_name,
                            "prompt_tokens": p_tok,
                            "candidates_tokens": c_tok,
                            "total_tokens": p_tok + c_tok,
                            "client_version": "antigravity/cli/1.2.14",
                            "project_id": ai_project,
                            "workspace_path": workspace_path
                        })
                        if step_idx > max_step_seen:
                            max_step_seen = step_idx
                            
                    running_prompt_tokens += c_tok
                    
        if rows_to_insert:
            client = bigquery.Client(project=os.environ.get("WORKLOAD_PROJECT_ID", "desa01-uip"))
            dataset_name = os.environ.get("DATASET_NAME", "antigravity_telemetry")
            table_id = f"{client.project}.{dataset_name}.antigravity_token_usage"
            client.insert_rows_json(table_id, rows_to_insert)
            
            state[conv_id] = max_step_seen
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
                
    except Exception as e:
        err_log = os.path.expanduser("~/.gemini/antigravity/telemetry_hook.log")
        with open(err_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] Error: {str(e)}\n")
    finally:
        print(json.dumps(response_payload))

if __name__ == "__main__":
    main()
