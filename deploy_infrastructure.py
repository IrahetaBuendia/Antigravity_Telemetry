#!/usr/bin/env python3
"""
Despliegue de Infraestructura de BigQuery para Telemetría de Antigravity.
"""
import os
import sys
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

def deploy():
    project_id = os.environ.get("WORKLOAD_PROJECT_ID", "desa01-uip")
    dataset_name = os.environ.get("DATASET_NAME", "antigravity_telemetry")
    location = os.environ.get("BQ_LOCATION", "US")
    
    print(f"Iniciando despliegue de infraestructura en:")
    print(f"  - Proyecto: {project_id}")
    print(f"  - Dataset: {dataset_name}")
    print(f"  - Region: {location}")
    print("-" * 50)
    
    client = bigquery.Client(project=project_id)
    dataset_ref = bigquery.DatasetReference(project_id, dataset_name)
    
    # 1. Crear Dataset
    try:
        dataset = client.get_dataset(dataset_ref)
        print(f"[OK] Dataset '{dataset_name}' ya existe.")
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        dataset.description = "Almacen central de logs y metricas de consumo de Antigravity"
        dataset = client.create_dataset(dataset, timeout=30)
        print(f"[OK] Dataset '{dataset_name}' creado exitosamente en {location}.")
        
    # 2. Crear Tabla Particionada antigravity_token_usage
    table_id = f"{project_id}.{dataset_name}.antigravity_token_usage"
    table_ref = bigquery.TableReference(dataset_ref, "antigravity_token_usage")
    
    schema = [
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED", description="Marca temporal exacta en UTC"),
        bigquery.SchemaField("usage_date", "DATE", mode="REQUIRED", description="Fecha de particionamiento YYYY-MM-DD"),
        bigquery.SchemaField("developer_user", "STRING", mode="NULLABLE", description="Correo del desarrollador"),
        bigquery.SchemaField("conversation_id", "STRING", mode="REQUIRED", description="UUID de la sesion"),
        bigquery.SchemaField("step_index", "INTEGER", mode="REQUIRED", description="Indice ordinal del turno"),
        bigquery.SchemaField("model_name", "STRING", mode="NULLABLE", description="Nombre del modelo LLM utilizado"),
        bigquery.SchemaField("prompt_tokens", "INTEGER", mode="NULLABLE", description="Tokens de entrada (contexto + prompt)"),
        bigquery.SchemaField("candidates_tokens", "INTEGER", mode="NULLABLE", description="Tokens de salida generados"),
        bigquery.SchemaField("total_tokens", "INTEGER", mode="NULLABLE", description="Total tokens consumidos"),
        bigquery.SchemaField("client_version", "STRING", mode="NULLABLE", description="Version de cliente Antigravity"),
        bigquery.SchemaField("project_id", "STRING", mode="NULLABLE", description="Proyecto GCP destino de inferencia"),
        bigquery.SchemaField("workspace_path", "STRING", mode="NULLABLE", description="Ruta de trabajo local del desarrollador"),
    ]
    
    try:
        table = client.get_table(table_ref)
        print(f"[OK] Tabla '{table_id}' ya existe.")
    except NotFound:
        table = bigquery.Table(table_ref, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )
        table.description = "Metricas de tokens por interaccion, desarrollador y modelo en Antigravity"
        table = client.create_table(table)
        print(f"[OK] Tabla '{table_id}' creada exitosamente particionada por dia.")

    # 3. Crear Vista antigravity_developer_token_summary
    view_token_summary_id = f"{project_id}.{dataset_name}.antigravity_developer_token_summary"
    view_token_query = f"""
    SELECT
      usage_date,
      developer_user,
      model_name,
      SUM(prompt_tokens) AS input_tokens,
      SUM(candidates_tokens) AS output_tokens,
      SUM(total_tokens) AS total_tokens,
      COUNT(1) AS total_interactions,
      COUNT(DISTINCT conversation_id) AS active_conversations
    FROM
      `{table_id}`
    GROUP BY
      usage_date,
      developer_user,
      model_name
    """
    
    view_ref = bigquery.TableReference(dataset_ref, "antigravity_developer_token_summary")
    try:
        view = bigquery.Table(view_ref)
        view.view_query = view_token_query
        view.description = "Resumen analitico de consumo de tokens por desarrollador y modelo"
        client.delete_table(view_ref, not_found_ok=True)
        view = client.create_table(view)
        print(f"[OK] Vista analitica '{view_token_summary_id}' creada exitosamente.")
    except Exception as e:
        print(f"[ERROR] Error creando vista de tokens: {e}")

    # 4. Crear Vista antigravity_user_usage_summary (si la tabla de auditoria existe)
    audit_table_id = f"{project_id}.{dataset_name}.cloudaudit_googleapis_com_data_access"
    try:
        client.get_table(audit_table_id)
        view_audit_query = f"""
        SELECT
          DATE(timestamp) AS usage_date,
          protopayload_auditlog.authenticationInfo.principalEmail AS user_email,
          protopayload_auditlog.methodName AS api_method,
          COUNT(1) AS total_requests,
          MIN(timestamp) AS session_start,
          MAX(timestamp) AS session_end,
          ANY_VALUE(protopayload_auditlog.requestMetadata.callerSuppliedUserAgent) AS client_version
        FROM
          `{audit_table_id}`
        WHERE
          protopayload_auditlog.serviceName = 'businessaicode.googleapis.com'
        GROUP BY
          usage_date,
          user_email,
          api_method
        """
        view_audit_ref = bigquery.TableReference(dataset_ref, "antigravity_user_usage_summary")
        view_audit = bigquery.Table(view_audit_ref)
        view_audit.view_query = view_audit_query
        view_audit.description = "Resumen de auditoria de llamadas API desde Cloud Logging Sink"
        client.delete_table(view_audit_ref, not_found_ok=True)
        view_audit = client.create_table(view_audit)
        print(f"[OK] Vista de auditoria '{project_id}.{dataset_name}.antigravity_user_usage_summary' creada exitosamente.")
    except NotFound:
        print(f"[INFO] La tabla de auditoria '{audit_table_id}' se creara automaticamente cuando Cloud Logging emita el primer evento.")

    print("-" * 50)
    print("[OK] Despliegue de infraestructura completado con exito.")

if __name__ == "__main__":
    deploy()
