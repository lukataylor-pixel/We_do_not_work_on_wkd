"""
Temporal Leak Detector - Cross-Session Information Disclosure Tracking

This module implements a novel defense against slow-extraction attacks where attackers
gradually extract sensitive information across multiple sessions, bypassing per-query filters.

Key Features:
- Tracks cumulative sensitive topic exposure per user_id across sessions
- Blocks users when cumulative exposure exceeds threshold (default: 60%)
- Monitors 5 sensitive topic categories (fraud rules, verification, architecture, etc.)
- SQLite-based persistent storage for cross-session tracking
- Graceful session_id handling for legacy and new block records

Author: Guardian Glass Agent Team
License: MIT
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import re


class SensitiveTopic:
    """Represents a category of sensitive information to track."""
    
    def __init__(self, topic_id: str, name: str, keywords: List[str], weight: float = 1.0):
        """
        Initialize a sensitive topic.
        
        Args:
            topic_id: Unique identifier for the topic
            name: Human-readable name
            keywords: List of keywords/patterns that indicate exposure
            weight: Importance weight (higher = more sensitive)
        """
        self.topic_id = topic_id
        self.name = name
        self.keywords = [kw.lower() for kw in keywords]
        self.weight = weight
    
    def matches(self, text: str) -> float:
        """
        Check if text contains this topic and return exposure score.
        
        Args:
            text: Text to analyze
            
        Returns:
            Exposure score (0.0 to 1.0)
        """
        text_lower = text.lower()
        matches = sum(1 for kw in self.keywords if kw in text_lower)
        if matches == 0:
            return 0.0
        
        # Score based on keyword coverage and weight
        coverage = min(matches / len(self.keywords), 1.0)
        return coverage * self.weight


class TemporalLeakDetector:
    """
    Tracks cumulative information disclosure across sessions to prevent slow-extraction attacks.
    
    The detector monitors sensitive topic exposure per user over a lookback window.
    When cumulative exposure exceeds a threshold, the user is blocked.
    """
    
    def __init__(self, 
                 db_file: str = "temporal_leaks.db",
                 exposure_threshold: float = 0.6,
                 lookback_days: int = 30):
        """
        Initialize the temporal leak detector.
        
        Args:
            db_file: Path to SQLite database for persistence
            exposure_threshold: Block threshold (0.0 to 1.0)
            lookback_days: Number of days to look back for cumulative tracking
        """
        self.db_file = db_file
        self.exposure_threshold = exposure_threshold
        self.lookback_days = lookback_days
        
        # Define sensitive topics to monitor
        self.topics = [
            SensitiveTopic(
                "fraud_rules",
                "Fraud Detection Rules",
                ["fraud threshold", "transaction limit", "risk score", "fraud detection", "detection rule"],
                weight=1.0
            ),
            SensitiveTopic(
                "verification",
                "Verification Workflows",
                ["verification process", "verify customer", "card last", "postcode", "authentication flow"],
                weight=0.9
            ),
            SensitiveTopic(
                "architecture",
                "System Architecture",
                ["database schema", "system architecture", "internal process", "backend system", "infrastructure"],
                weight=0.8
            ),
            SensitiveTopic(
                "security",
                "Security Protocols",
                ["encryption", "api key", "secret", "security protocol", "authentication method"],
                weight=1.0
            ),
            SensitiveTopic(
                "pii_detection",
                "PII Detection Methods",
                ["similarity threshold", "embedding model", "detection method", "safety classifier"],
                weight=0.7
            )
        ]
        
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
        """Initialize database schema for leak tracking."""
        with self._get_connection() as conn:
            # Table for tracking topic exposure per user
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_exposures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    topic_id TEXT NOT NULL,
                    topic_name TEXT NOT NULL,
                    exposure_score REAL NOT NULL,
                    matched_keywords TEXT,
                    interaction_context TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_topic 
                ON topic_exposures(user_id, topic_id, timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_timestamp 
                ON topic_exposures(user_id, timestamp)
            """)
            
            # Table for tracking blocks due to excessive leakage
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leak_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    total_exposure REAL NOT NULL,
                    topics_exposed TEXT,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add session_id column if it doesn't exist (for migration)
            try:
                conn.execute("ALTER TABLE leak_blocks ADD COLUMN session_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            conn.commit()
    
    def analyze_interaction(self, 
                           user_id: Optional[str],
                           session_id: Optional[str],
                           user_message: str,
                           agent_response: str) -> Dict[str, Any]:
        """
        Analyze an interaction for sensitive information disclosure.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            user_message: User's input message
            agent_response: Agent's response
            
        Returns:
            Analysis result with exposure scores and block decision
        """
        # Skip analysis if no user_id (anonymous interactions)
        if not user_id:
            return {
                'should_block': False,
                'total_exposure': 0.0,
                'new_exposures': {},
                'cumulative_exposure': {},
                'reason': None
            }
        
        # Analyze current interaction for topic exposure
        new_exposures = self._detect_topic_exposure(agent_response)
        
        # Record new exposures
        self._record_exposures(user_id, session_id, new_exposures, agent_response[:500])
        
        # Calculate cumulative exposure
        cumulative_exposure = self._get_cumulative_exposure(user_id)
        
        # Determine if we should block
        total_exposure = sum(cumulative_exposure.values())
        should_block = total_exposure >= self.exposure_threshold
        
        # Log block if needed
        if should_block:
            self._record_block(user_id, session_id, total_exposure, cumulative_exposure)
        
        return {
            'should_block': should_block,
            'total_exposure': total_exposure,
            'new_exposures': new_exposures,
            'cumulative_exposure': cumulative_exposure,
            'threshold': self.exposure_threshold,
            'reason': f'Cumulative information leakage ({total_exposure:.1%}) exceeds threshold ({self.exposure_threshold:.1%})' if should_block else None,
            'exposed_topics': [
                {'topic': tid, 'coverage': score}
                for tid, score in cumulative_exposure.items()
                if score > 0.3
            ]
        }
    
    def _detect_topic_exposure(self, text: str) -> Dict[str, Dict[str, Any]]:
        """
        Detect which sensitive topics are exposed in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary mapping topic_id to exposure data (score, topic_name, matched)
        """
        exposures = {}
        
        for topic in self.topics:
            score = topic.matches(text)
            if score > 0:
                exposures[topic.topic_id] = {
                    'score': score,
                    'topic_name': topic.name,
                    'matched': True
                }
        
        return exposures
    
    def _record_exposures(self, 
                         user_id: str,
                         session_id: Optional[str],
                         exposures: Dict[str, Dict[str, Any]],
                         context: str):
        """
        Record topic exposures to database.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            exposures: Dictionary of exposures from _detect_topic_exposure
            context: Interaction context (truncated response)
        """
        if not exposures:
            return
        
        with self._get_connection() as conn:
            for topic_id, data in exposures.items():
                conn.execute("""
                    INSERT INTO topic_exposures 
                    (user_id, session_id, topic_id, topic_name, exposure_score, interaction_context)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    session_id,
                    topic_id,
                    data['topic_name'],
                    data['score'],
                    context
                ))
            conn.commit()
    
    def _get_cumulative_exposure(self, user_id: str) -> Dict[str, float]:
        """
        Calculate cumulative exposure for a user over lookback period.
        
        Uses max exposure per topic (not sum) to avoid double-counting.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary mapping topic_id to cumulative exposure score
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT topic_id, MAX(exposure_score) as max_exposure
                FROM topic_exposures
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY topic_id
            """, (user_id, cutoff_date.isoformat()))
            
            rows = cursor.fetchall()
            
            return {row['topic_id']: row['max_exposure'] for row in rows}
    
    def _record_block(self, 
                     user_id: str,
                     session_id: Optional[str],
                     total_exposure: float,
                     topics: Dict[str, float]):
        """
        Record a block due to excessive leakage.
        
        Args:
            user_id: User identifier
            session_id: Session identifier where block occurred
            total_exposure: Total cumulative exposure score
            topics: Dictionary of topic exposures
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO leak_blocks
                (user_id, session_id, total_exposure, topics_exposed, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                session_id,
                total_exposure,
                json.dumps(topics),
                f"Cumulative exposure {total_exposure:.1%} exceeds threshold {self.exposure_threshold:.1%}"
            ))
            conn.commit()
    
    def get_user_exposure_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get exposure history for a specific user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of exposure records
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM topic_exposures
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 100
            """, (user_id, cutoff_date.isoformat()))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a summary of user's exposure status.
        
        Args:
            user_id: User identifier
            
        Returns:
            Summary dictionary with exposure stats
        """
        cumulative_exposure = self._get_cumulative_exposure(user_id)
        total_exposure = sum(cumulative_exposure.values())
        history = self.get_user_exposure_history(user_id)
        
        return {
            'user_id': user_id,
            'total_exposure': total_exposure,
            'threshold': self.exposure_threshold,
            'at_risk': total_exposure >= self.exposure_threshold * 0.8,
            'would_block': total_exposure >= self.exposure_threshold,
            'topics_exposed': cumulative_exposure,
            'interaction_count': len(history),
            'lookback_days': self.lookback_days
        }
    
    def get_all_users_at_risk(self) -> List[Dict[str, Any]]:
        """
        Get all users who are at risk of being blocked (>80% of threshold).
        
        Returns:
            List of user summaries for at-risk users
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT user_id, SUM(exposure_score) as total_exposure
                FROM (
                    SELECT user_id, topic_id, MAX(exposure_score) as exposure_score
                    FROM topic_exposures
                    WHERE timestamp >= ?
                    GROUP BY user_id, topic_id
                )
                GROUP BY user_id
                HAVING total_exposure >= ?
                ORDER BY total_exposure DESC
            """, (cutoff_date.isoformat(), self.exposure_threshold * 0.8))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'user_id': row['user_id'],
                    'total_exposure': row['total_exposure'],
                    'at_risk': True
                }
                for row in rows
            ]
    
    def get_leak_statistics(self) -> Dict[str, Any]:
        """
        Get overall leak detection statistics across all users.
        
        Returns:
            Dictionary with aggregate statistics including:
            - total_sessions: Total number of sessions tracked
            - blocked_sessions: Number of distinct sessions that triggered blocks
            - block_events: Total number of block events (can exceed blocked_sessions)
            - average_coverage: Average disclosure percentage
            - user_sessions: Per-user session data with max_coverage, session_count, blocked
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        
        with self._get_connection() as conn:
            # Get exposure statistics
            exposure_cursor = conn.execute("""
                SELECT 
                    user_id,
                    COUNT(DISTINCT session_id) as session_count,
                    MAX(total_exposure) as max_coverage
                FROM (
                    SELECT 
                        user_id,
                        session_id,
                        SUM(exposure_score) as total_exposure
                    FROM (
                        SELECT 
                            user_id, 
                            session_id,
                            topic_id, 
                            MAX(exposure_score) as exposure_score
                        FROM topic_exposures
                        WHERE timestamp >= ?
                        GROUP BY user_id, session_id, topic_id
                    )
                    GROUP BY user_id, session_id
                )
                GROUP BY user_id
                ORDER BY max_coverage DESC
            """, (cutoff_date.isoformat(),))
            
            exposure_rows = exposure_cursor.fetchall()
            exposure_by_user = {row['user_id']: row for row in exposure_rows}
            
            # Get block statistics with NULL handling for legacy blocks
            block_cursor = conn.execute("""
                SELECT 
                    user_id,
                    COUNT(DISTINCT COALESCE(session_id, 'legacy_' || id)) as blocked_session_count,
                    COUNT(*) as block_event_count
                FROM leak_blocks
                WHERE timestamp >= ?
                GROUP BY user_id
            """, (cutoff_date.isoformat(),))
            
            block_rows = block_cursor.fetchall()
            blocks_by_user = {row['user_id']: row for row in block_rows}
            
            # Merge data from both queries
            all_user_ids = set(exposure_by_user.keys()) | set(blocks_by_user.keys())
            
            total_sessions = 0
            total_blocked_sessions = 0
            total_block_events = 0
            total_coverage = 0.0
            user_sessions = {}
            
            for user_id in all_user_ids:
                exposure_data = exposure_by_user.get(user_id)
                block_data = blocks_by_user.get(user_id)
                
                session_count = exposure_data['session_count'] if exposure_data else 0
                max_coverage = exposure_data['max_coverage'] if exposure_data else 0.0
                blocked_session_count = block_data['blocked_session_count'] if block_data else 0
                block_event_count = block_data['block_event_count'] if block_data else 0
                
                total_sessions += session_count
                total_blocked_sessions += blocked_session_count
                total_block_events += block_event_count
                if max_coverage > 0:
                    total_coverage += max_coverage
                
                user_sessions[user_id] = {
                    'session_count': session_count,
                    'max_coverage': max_coverage,
                    'blocked': block_data is not None,
                    'blocked_session_count': blocked_session_count,
                    'block_event_count': block_event_count
                }
            
            user_count_with_coverage = len([u for u in exposure_by_user.values() if u['max_coverage'] > 0])
            average_coverage = (total_coverage / user_count_with_coverage) if user_count_with_coverage else 0.0
            
            return {
                'total_sessions': total_sessions,
                'blocked_sessions': total_blocked_sessions,
                'block_events': total_block_events,
                'average_coverage': average_coverage,
                'user_sessions': user_sessions
            }
