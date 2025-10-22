"""
Enhanced data logging system for Vision Assistant
Logs structured data for analytics and caregiver monitoring
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import threading

class VisionDataLogger:
    def __init__(self, db_path: str = "vision_data.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration_seconds INTEGER,
                    total_detections INTEGER DEFAULT 0,
                    total_alerts INTEGER DEFAULT 0,
                    critical_alerts INTEGER DEFAULT 0
                )
            """)
            
            # Detections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    object_type VARCHAR(50) NOT NULL,
                    distance_category VARCHAR(20),
                    distance_score REAL,
                    direction VARCHAR(20),
                    bbox_x1 INTEGER,
                    bbox_y1 INTEGER,
                    bbox_x2 INTEGER,
                    bbox_y2 INTEGER,
                    confidence REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    object_type VARCHAR(50) NOT NULL,
                    distance_category VARCHAR(20),
                    direction VARCHAR(20),
                    alert_text TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # Voice commands table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    command TEXT NOT NULL,
                    response TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # Scene summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scene_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    summary_text TEXT NOT NULL,
                    object_count INTEGER,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            conn.commit()
    
    def start_session(self) -> int:
        """Start a new session and return session ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (start_time) VALUES (?)",
                (datetime.now(),)
            )
            conn.commit()
            return cursor.lastrowid
    
    def end_session(self, session_id: int):
        """End a session and calculate statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get session start time
            cursor.execute(
                "SELECT start_time FROM sessions WHERE id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            if not result:
                return
            
            start_time = datetime.fromisoformat(result[0])
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            
            # Get statistics
            cursor.execute(
                "SELECT COUNT(*) FROM detections WHERE session_id = ?",
                (session_id,)
            )
            total_detections = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE session_id = ?",
                (session_id,)
            )
            total_alerts = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE session_id = ? AND distance_category = 'critical'",
                (session_id,)
            )
            critical_alerts = cursor.fetchone()[0]
            
            # Update session
            cursor.execute("""
                UPDATE sessions 
                SET end_time = ?, duration_seconds = ?, 
                    total_detections = ?, total_alerts = ?, critical_alerts = ?
                WHERE id = ?
            """, (end_time, duration, total_detections, total_alerts, critical_alerts, session_id))
            
            conn.commit()
    
    def log_detection(self, session_id: int, detection: Dict):
        """Log an object detection"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detections 
                (session_id, timestamp, object_type, distance_category, distance_score,
                 direction, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(),
                detection['name'],
                detection['distance'],
                detection['distance_score'],
                detection['direction'],
                detection['bbox'][0],
                detection['bbox'][1],
                detection['bbox'][2],
                detection['bbox'][3],
                detection.get('confidence', 0.0)
            ))
            conn.commit()
    
    def log_alert(self, session_id: int, object_type: str, distance_category: str, 
                  direction: str, alert_text: str):
        """Log a proximity alert"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts 
                (session_id, timestamp, object_type, distance_category, direction, alert_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(),
                object_type,
                distance_category,
                direction,
                alert_text
            ))
            conn.commit()
    
    def log_voice_command(self, session_id: int, command: str, response: str):
        """Log a voice command and its response"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO voice_commands 
                (session_id, timestamp, command, response)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(),
                command,
                response
            ))
            conn.commit()
    
    def log_scene_summary(self, session_id: int, summary_text: str, object_count: int):
        """Log a scene summary"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scene_summaries 
                (session_id, timestamp, summary_text, object_count)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(),
                summary_text,
                object_count
            ))
            conn.commit()
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """Get recent alerts"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_session_stats(self, session_id: Optional[int] = None) -> Dict:
        """Get statistics for a session or all sessions"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT * FROM sessions WHERE id = ?
                """, (session_id,))
                session = dict(cursor.fetchone())
                
                # Get object distribution
                cursor.execute("""
                    SELECT object_type, COUNT(*) as count
                    FROM detections
                    WHERE session_id = ?
                    GROUP BY object_type
                    ORDER BY count DESC
                """, (session_id,))
                session['object_distribution'] = [dict(row) for row in cursor.fetchall()]
                
                # Get alert timeline
                cursor.execute("""
                    SELECT timestamp, object_type, distance_category, direction
                    FROM alerts
                    WHERE session_id = ?
                    ORDER BY timestamp
                """, (session_id,))
                session['alert_timeline'] = [dict(row) for row in cursor.fetchall()]
                
                return session
            else:
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sessions,
                        SUM(duration_seconds) as total_duration,
                        SUM(total_detections) as total_detections,
                        SUM(total_alerts) as total_alerts,
                        SUM(critical_alerts) as total_critical_alerts
                    FROM sessions
                """)
                return dict(cursor.fetchone())
    
    def get_current_session(self) -> Optional[int]:
        """Get the current active session ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM sessions 
                WHERE end_time IS NULL 
                ORDER BY start_time DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions 
                ORDER BY start_time DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def export_session_json(self, session_id: int, output_file: str):
        """Export session data to JSON"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get session info
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session = dict(cursor.fetchone())
            
            # Get detections
            cursor.execute("SELECT * FROM detections WHERE session_id = ?", (session_id,))
            session['detections'] = [dict(row) for row in cursor.fetchall()]
            
            # Get alerts
            cursor.execute("SELECT * FROM alerts WHERE session_id = ?", (session_id,))
            session['alerts'] = [dict(row) for row in cursor.fetchall()]
            
            # Get voice commands
            cursor.execute("SELECT * FROM voice_commands WHERE session_id = ?", (session_id,))
            session['voice_commands'] = [dict(row) for row in cursor.fetchall()]
            
            # Get scene summaries
            cursor.execute("SELECT * FROM scene_summaries WHERE session_id = ?", (session_id,))
            session['scene_summaries'] = [dict(row) for row in cursor.fetchall()]
            
            # Write to file
            with open(output_file, 'w') as f:
                json.dump(session, f, indent=2, default=str)

