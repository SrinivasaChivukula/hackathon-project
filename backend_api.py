"""
Flask REST API for Vision Assistant Dashboard
Serves detection data, analytics, and live stream
"""

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from data_logger import VisionDataLogger
import cv2
import json
import threading
import time
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)  # Enable CORS for frontend

# Initialize data logger
logger = VisionDataLogger()

# Global variable for current frame (shared with vision assistant)
current_frame = None
frame_lock = threading.Lock()

def set_current_frame(frame):
    """Update the current frame (called from vision assistant)"""
    global current_frame
    with frame_lock:
        current_frame = frame.copy() if frame is not None else None

def generate_mjpeg():
    """Generate MJPEG stream for dashboard"""
    while True:
        frame_to_encode = None
        with frame_lock:
            if current_frame is not None:
                frame_to_encode = current_frame.copy()
        
        if frame_to_encode is not None:
            ret, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.033)  # ~30 FPS

@app.route('/')
def index():
    """Serve dashboard frontend"""
    return send_from_directory('frontend', 'index.html')

@app.route('/api/video_feed')
def video_feed():
    """MJPEG video stream endpoint"""
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0'})

@app.route('/api/frame_status')
def frame_status():
    """Check if frames are being received"""
    with frame_lock:
        has_frame = current_frame is not None
        shape = current_frame.shape if has_frame else None
    return jsonify({
        'has_frame': has_frame,
        'frame_shape': str(shape) if shape is not None else None
    })

@app.route('/api/status')
def get_status():
    """Get current system status"""
    current_session = logger.get_current_session()
    
    return jsonify({
        'status': 'active' if current_session else 'inactive',
        'current_session_id': current_session,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/sessions')
def get_sessions():
    """Get all sessions"""
    sessions = logger.get_all_sessions()
    return jsonify(sessions)

@app.route('/api/sessions/<int:session_id>')
def get_session(session_id):
    """Get detailed session data"""
    session_data = logger.get_session_stats(session_id)
    return jsonify(session_data)

@app.route('/api/sessions/<int:session_id>/export')
def export_session(session_id):
    """Export session data as JSON"""
    filename = f'session_{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    logger.export_session_json(session_id, filename)
    return send_from_directory('.', filename, as_attachment=True)

@app.route('/api/alerts/recent')
def get_recent_alerts():
    """Get recent alerts"""
    limit = request.args.get('limit', 50, type=int)
    alerts = logger.get_recent_alerts(limit)
    return jsonify(alerts)

@app.route('/api/stats/overview')
def get_overview_stats():
    """Get overview statistics"""
    overall_stats = logger.get_session_stats()
    
    # Get current session info if active
    current_session = logger.get_current_session()
    if current_session:
        current_session_data = logger.get_session_stats(current_session)
    else:
        current_session_data = None
    
    return jsonify({
        'overall': overall_stats,
        'current_session': current_session_data
    })

@app.route('/api/stats/objects')
def get_object_stats():
    """Get object detection statistics"""
    with sqlite3.connect(logger.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Most common objects
        cursor.execute("""
            SELECT object_type, COUNT(*) as count
            FROM detections
            GROUP BY object_type
            ORDER BY count DESC
            LIMIT 10
        """)
        common_objects = [dict(row) for row in cursor.fetchall()]
        
        # Objects by distance category
        cursor.execute("""
            SELECT distance_category, COUNT(*) as count
            FROM detections
            WHERE distance_category IS NOT NULL
            GROUP BY distance_category
        """)
        distance_distribution = [dict(row) for row in cursor.fetchall()]
        
        # Objects by direction
        cursor.execute("""
            SELECT direction, COUNT(*) as count
            FROM detections
            WHERE direction IS NOT NULL
            GROUP BY direction
        """)
        direction_distribution = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'common_objects': common_objects,
            'distance_distribution': distance_distribution,
            'direction_distribution': direction_distribution
        })

@app.route('/api/stats/timeline')
def get_timeline():
    """Get detection timeline for charts"""
    hours = request.args.get('hours', 24, type=int)
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    with sqlite3.connect(logger.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Detections over time (grouped by hour)
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                COUNT(*) as count
            FROM detections
            WHERE timestamp > ?
            GROUP BY hour
            ORDER BY hour
        """, (cutoff_time,))
        detections_timeline = [dict(row) for row in cursor.fetchall()]
        
        # Alerts over time
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                distance_category,
                COUNT(*) as count
            FROM alerts
            WHERE timestamp > ?
            GROUP BY hour, distance_category
            ORDER BY hour
        """, (cutoff_time,))
        alerts_timeline = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'detections': detections_timeline,
            'alerts': alerts_timeline
        })

@app.route('/api/stats/safety')
def get_safety_metrics():
    """Get safety metrics"""
    with sqlite3.connect(logger.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Critical alerts in last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM alerts
            WHERE distance_category = 'critical'
            AND timestamp > ?
        """, (cutoff_time,))
        critical_24h = cursor.fetchone()['count']
        
        # Warning alerts in last 24 hours
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM alerts
            WHERE distance_category = 'warning'
            AND timestamp > ?
        """, (cutoff_time,))
        warning_24h = cursor.fetchone()['count']
        
        # Most dangerous times (hour of day)
        cursor.execute("""
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as count
            FROM alerts
            WHERE distance_category IN ('critical', 'warning')
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 5
        """)
        dangerous_hours = [dict(row) for row in cursor.fetchall()]
        
        # Most dangerous objects
        cursor.execute("""
            SELECT 
                object_type,
                COUNT(*) as count
            FROM alerts
            WHERE distance_category = 'critical'
            GROUP BY object_type
            ORDER BY count DESC
            LIMIT 5
        """)
        dangerous_objects = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'critical_alerts_24h': critical_24h,
            'warning_alerts_24h': warning_24h,
            'dangerous_hours': dangerous_hours,
            'dangerous_objects': dangerous_objects
        })

@app.route('/api/voice_commands')
def get_voice_commands():
    """Get voice command history"""
    limit = request.args.get('limit', 50, type=int)
    
    with sqlite3.connect(logger.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM voice_commands
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        commands = [dict(row) for row in cursor.fetchall()]
        
        return jsonify(commands)

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

def run_api_server(host='0.0.0.0', port=5001):
    """Run the Flask API server"""
    print(f"Starting Flask API server on http://{host}:{port}")
    print(f"Dashboard will be available at: http://localhost:{port}")
    app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_api_server()

