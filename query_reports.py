#!/usr/bin/env python3
"""
Reportes y Consultas de Validación para Telemetría de Antigravity en BigQuery.
"""
import os
from google.cloud import bigquery

def run_reports():
    project_id = os.environ.get("WORKLOAD_PROJECT_ID", "desa01-uip")
    dataset_name = os.environ.get("DATASET_NAME", "antigravity_telemetry")
    client = bigquery.Client(project=project_id)
    
    print("=" * 115)
    print("REPORTE 1: CONSOLIDADO GENERAL POR DESARROLLADOR Y MODELO")
    print("=" * 115)
    
    query1 = f"""
    SELECT
      developer_user,
      model_name,
      SUM(input_tokens) AS grand_input_tokens,
      SUM(output_tokens) AS grand_output_tokens,
      SUM(total_tokens) AS grand_total_tokens,
      SUM(total_interactions) AS grand_interactions
    FROM
      `{project_id}.{dataset_name}.antigravity_developer_token_summary`
    GROUP BY
      developer_user,
      model_name
    ORDER BY
      grand_total_tokens DESC
    """
    
    results1 = list(client.query(query1).result())
    header1 = f"{'Desarrollador':<20} | {'Modelo':<28} | {'Input Tokens':>14} | {'Output Tokens':>14} | {'Total Tokens':>14} | {'Interacciones':>13}"
    print(header1)
    print("-" * len(header1))
    for row in results1:
        print(f"{str(row.developer_user):<20} | {str(row.model_name):<28} | {row.grand_input_tokens:>14,d} | {row.grand_output_tokens:>14,d} | {row.grand_total_tokens:>14,d} | {row.grand_interactions:>13,d}")
        
    print("\n" + "=" * 115)
    print("REPORTE 2: CONSUMO DIARIO (ÚLTIMOS 15 DÍAS)")
    print("=" * 115)
    
    query2 = f"""
    SELECT
      usage_date,
      developer_user,
      model_name,
      input_tokens,
      output_tokens,
      total_tokens,
      total_interactions
    FROM
      `{project_id}.{dataset_name}.antigravity_developer_token_summary`
    ORDER BY
      usage_date DESC,
      total_tokens DESC
    LIMIT 15
    """
    
    results2 = list(client.query(query2).result())
    header2 = f"{'Fecha':<12} | {'Desarrollador':<18} | {'Modelo':<28} | {'Input Tokens':>14} | {'Output Tokens':>14} | {'Total Tokens':>14}"
    print(header2)
    print("-" * len(header2))
    for row in results2:
        print(f"{str(row.usage_date):<12} | {str(row.developer_user):<18} | {str(row.model_name):<28} | {row.input_tokens:>14,d} | {row.output_tokens:>14,d} | {row.total_tokens:>14,d}")

if __name__ == "__main__":
    run_reports()
