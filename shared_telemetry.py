"""Shared telemetry storage for cross-process analytics using SQLite."""

import sqlite3
import json
import time
from typing import List, Dict, Any
from contextlib import contextmanager

class SharedTelemetry:
    """
    Shared telemetry storage using SQLite for safe multi-process access.
    Enables admin dashboard to view interactions from all components.
    SQLite provides built-in cross-process locking and ACID guarantees.
    """
    
    def __init__(self, db_file: str = "telemetry.db"):
        self.db_file = db_file
        self._initialize_db()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_file, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _initialize_db(self):
        """Initialize database schema if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT,
                    agent_original_response TEXT,
                    final_response TEXT,
                    status TEXT,
                    safety_result JSON,
                    processing_time REAL,
                    timestamp TEXT,
                    trace_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON interactions(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp)
            """)
            conn.commit()
    
    def log_interaction(self, interaction: Dict[str, Any]):
        """
        Log an interaction to shared storage with atomic SQLite operations.
        
        Args:
            interaction: Interaction dictionary with user_message, response, safety_result, etc.
        """
        # Add timestamp if not present
        if 'timestamp' not in interaction:
            interaction['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO interactions 
                (user_message, agent_original_response, final_response, status, 
                 safety_result, processing_time, timestamp, trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.get('user_message'),
                interaction.get('agent_original_response'),
                interaction.get('final_response'),
                interaction.get('status'),
                json.dumps(interaction.get('safety_result', {})),
                interaction.get('processing_time'),
                interaction.get('timestamp'),
                interaction.get('trace_id')
            ))
            conn.commit()
            
            # Keep last 1000 interactions
            conn.execute("""
                DELETE FROM interactions 
                WHERE id NOT IN (
                    SELECT id FROM interactions 
                    ORDER BY id DESC 
                    LIMIT 1000
                )
            """)
            conn.commit()
    
    def get_all_interactions(self) -> List[Dict[str, Any]]:
        """Get all interactions from storage."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM interactions 
                ORDER BY id ASC
            """)
            
            interactions = []
            for row in cursor.fetchall():
                interactions.append({
                    'user_message': row['user_message'],
                    'agent_original_response': row['agent_original_response'],
                    'final_response': row['final_response'],
                    'status': row['status'],
                    'safety_result': json.loads(row['safety_result']) if row['safety_result'] else {},
                    'processing_time': row['processing_time'],
                    'timestamp': row['timestamp'],
                    'trace_id': row['trace_id']
                })
            
            return interactions
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from all logged interactions using efficient SQL aggregations."""
        with self._get_connection() as conn:
            # Get counts and averages
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked,
                    SUM(CASE WHEN status = 'safe' THEN 1 ELSE 0 END) as safe,
                    AVG(processing_time) as avg_time
                FROM interactions
            """)
            row = cursor.fetchone()
            
            total = row['total']
            blocked = row['blocked']
            safe = row['safe']
            avg_time = row['avg_time'] or 0
            
            if total == 0:
                return {
                    'total_interactions': 0,
                    'blocked_count': 0,
                    'safe_count': 0,
                    'block_rate': 0.0,
                    'avg_similarity_score': 0.0,
                    'avg_processing_time': 0.0,
                    'blocked_interactions': [],
                    'category_counts': {}
                }
            
            # Get average similarity score
            cursor = conn.execute("""
                SELECT safety_result FROM interactions
            """)
            similarity_scores = []
            for row in cursor.fetchall():
                result = json.loads(row['safety_result']) if row['safety_result'] else {}
                if 'similarity_score' in result:
                    similarity_scores.append(result['similarity_score'])
            
            avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
            
            # Get recent blocked interactions
            cursor = conn.execute("""
                SELECT * FROM interactions 
                WHERE status = 'blocked'
                ORDER BY id DESC
                LIMIT 5
            """)
            
            blocked_interactions = []
            for row in cursor.fetchall():
                blocked_interactions.append({
                    'user_message': row['user_message'],
                    'agent_original_response': row['agent_original_response'],
                    'final_response': row['final_response'],
                    'status': row['status'],
                    'safety_result': json.loads(row['safety_result']) if row['safety_result'] else {},
                    'processing_time': row['processing_time'],
                    'timestamp': row['timestamp'],
                    'trace_id': row['trace_id']
                })
            
            # Get category counts
            category_counts = {}
            for interaction in blocked_interactions:
                category = interaction['safety_result'].get('matched_topic', 'Unknown')
                category_counts[category] = category_counts.get(category, 0) + 1
            
            return {
                'total_interactions': total,
                'blocked_count': blocked,
                'safe_count': safe,
                'block_rate': (blocked / total * 100) if total > 0 else 0,
                'avg_similarity_score': avg_similarity,
                'avg_processing_time': avg_time,
                'blocked_interactions': list(reversed(blocked_interactions)),
                'category_counts': category_counts
            }
    
    def clear_all(self):
        """Clear all interactions from storage."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM interactions")
            conn.commit()

# Global shared telemetry instance
_telemetry = None

def get_telemetry() -> SharedTelemetry:
    """Get or create the global telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = SharedTelemetry()
    return _telemetry
