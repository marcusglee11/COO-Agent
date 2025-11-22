import sqlite3

def snapshot_query(conn: sqlite3.Connection, mission_id: str, task_id: str) -> list[tuple[str, bytes, str]]:
    """
    Returns a list of (file_path, content_bytes, created_at_iso) representing the snapshot
    for mission_id + task_id per spec v0.9.
    
    Uses the normative SQL query with ROW_NUMBER() CTE and required_artifact_ids overrides.
    """
    query = """
    WITH snapshot_artifacts AS (
      SELECT a.file_path, a.content, a.is_deleted, a.created_at
      FROM artifacts a
      JOIN mission_tasks t ON t.mission_id = a.mission_id
      WHERE t.id = :task_id
        AND a.mission_id = :mission_id
        AND a.file_path IS NOT NULL
        AND a.created_at <= t.started_at
        AND a.version_number = (
          SELECT MAX(a2.version_number)
          FROM artifacts a2
          WHERE a2.mission_id = a.mission_id
            AND a2.file_path = a.file_path
            AND a2.created_at <= t.started_at
        )
    ),
    required_artifacts AS (
      SELECT a.file_path, a.content, a.created_at
      FROM artifacts a
      WHERE a.mission_id = :mission_id
        AND a.id IN (
          SELECT value
          FROM json_each(
            (
              SELECT required_artifact_ids
              FROM mission_tasks
              WHERE id = :task_id
                AND required_artifact_ids IS NOT NULL
                AND json_valid(required_artifact_ids) = 1
            )
          )
        )
        AND a.is_deleted = 0
    )
    SELECT file_path, content, created_at
    FROM required_artifacts
    UNION
    SELECT file_path, content, created_at
    FROM snapshot_artifacts
    WHERE is_deleted = 0
      AND file_path NOT IN (SELECT file_path FROM required_artifacts)
    ORDER BY file_path ASC;
    """
    
    cur = conn.execute(query, {"mission_id": mission_id, "task_id": task_id})
    return cur.fetchall()
