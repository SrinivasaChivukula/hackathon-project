// API base URL
const API_BASE = '';

// Chart instances
let objectChart = null;
let timelineChart = null;

// Update intervals
const UPDATE_INTERVAL = 2000; // 2 seconds
const CHARTS_UPDATE_INTERVAL = 10000; // 10 seconds

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initializeCharts();
    updateDashboard();
    
    // Set up periodic updates
    setInterval(updateStatus, UPDATE_INTERVAL);
    setInterval(updateStats, UPDATE_INTERVAL);
    setInterval(updateAlerts, UPDATE_INTERVAL);
    setInterval(updateCharts, CHARTS_UPDATE_INTERVAL);
    setInterval(updateSafetyMetrics, UPDATE_INTERVAL);
    setInterval(updateCommands, 5000);
    setInterval(updateSessions, 5000);
    
    // Handle video feed errors
    const videoFeed = document.getElementById('videoFeed');
    videoFeed.onerror = () => {
        document.getElementById('videoStatus').textContent = 'Video feed unavailable';
    };
    videoFeed.onload = () => {
        document.getElementById('videoStatus').style.display = 'none';
    };
});

// Update all dashboard components
async function updateDashboard() {
    await updateStatus();
    await updateStats();
    await updateAlerts();
    await updateCharts();
    await updateSafetyMetrics();
    await updateCommands();
    await updateSessions();
}

// Update system status
async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();
        
        const statusBadge = document.getElementById('statusBadge');
        const statusText = document.getElementById('statusText');
        
        if (data.status === 'active') {
            statusBadge.classList.remove('inactive');
            statusText.textContent = 'Active';
        } else {
            statusBadge.classList.add('inactive');
            statusText.textContent = 'Inactive';
        }
        
        document.getElementById('lastUpdate').textContent = 
            `Last updated: ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Update statistics cards
async function updateStats() {
    try {
        const [overviewRes, safetyRes] = await Promise.all([
            fetch(`${API_BASE}/api/stats/overview`),
            fetch(`${API_BASE}/api/stats/safety`)
        ]);
        
        const overview = await overviewRes.json();
        const safety = await safetyRes.json();
        
        // Update stat cards
        document.getElementById('criticalAlerts').textContent = safety.critical_alerts_24h || 0;
        document.getElementById('warningAlerts').textContent = safety.warning_alerts_24h || 0;
        
        if (overview.current_session) {
            document.getElementById('totalDetections').textContent = 
                overview.current_session.total_detections || 0;
            
            const duration = overview.current_session.duration_seconds || 0;
            const minutes = Math.floor(duration / 60);
            const hours = Math.floor(minutes / 60);
            
            if (hours > 0) {
                document.getElementById('sessionDuration').textContent = 
                    `${hours}h ${minutes % 60}m`;
            } else {
                document.getElementById('sessionDuration').textContent = `${minutes}m`;
            }
        } else {
            document.getElementById('totalDetections').textContent = 
                overview.overall?.total_detections || 0;
            document.getElementById('sessionDuration').textContent = '0m';
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Update recent alerts
async function updateAlerts() {
    try {
        const response = await fetch(`${API_BASE}/api/alerts/recent?limit=20`);
        const alerts = await response.json();
        
        const alertsList = document.getElementById('alertsList');
        
        if (alerts.length === 0) {
            alertsList.innerHTML = '<div class="loading">No alerts yet</div>';
            return;
        }
        
        alertsList.innerHTML = alerts.map(alert => `
            <div class="alert-item ${alert.distance_category}">
                <div class="alert-content">
                    <div class="alert-text">${escapeHtml(alert.alert_text)}</div>
                    <div class="alert-meta">
                        ${alert.object_type} - ${alert.direction}
                    </div>
                </div>
                <div class="alert-time">
                    ${formatTime(alert.timestamp)}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error updating alerts:', error);
    }
}

// Initialize charts
function initializeCharts() {
    // Object distribution chart
    const objectCtx = document.getElementById('objectChart').getContext('2d');
    objectChart = new Chart(objectCtx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#6366f1',
                    '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#84cc16'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });
    
    // Timeline chart
    const timelineCtx = document.getElementById('timelineChart').getContext('2d');
    timelineChart = new Chart(timelineCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Detections',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Update charts
async function updateCharts() {
    try {
        const [objectsRes, timelineRes] = await Promise.all([
            fetch(`${API_BASE}/api/stats/objects`),
            fetch(`${API_BASE}/api/stats/timeline?hours=24`)
        ]);
        
        const objects = await objectsRes.json();
        const timeline = await timelineRes.json();
        
        // Update object chart
        if (objects.common_objects && objects.common_objects.length > 0) {
            objectChart.data.labels = objects.common_objects.map(o => o.object_type);
            objectChart.data.datasets[0].data = objects.common_objects.map(o => o.count);
            objectChart.update();
        }
        
        // Update timeline chart
        if (timeline.detections && timeline.detections.length > 0) {
            timelineChart.data.labels = timeline.detections.map(d => 
                new Date(d.hour).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            );
            timelineChart.data.datasets[0].data = timeline.detections.map(d => d.count);
            timelineChart.update();
        }
    } catch (error) {
        console.error('Error updating charts:', error);
    }
}

// Update safety metrics
async function updateSafetyMetrics() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/safety`);
        const safety = await response.json();
        
        const metricsContainer = document.getElementById('safetyMetrics');
        
        metricsContainer.innerHTML = `
            <div class="safety-metrics-grid">
                <div class="safety-item">
                    <h3>Most Dangerous Hours</h3>
                    <ul class="danger-list">
                        ${safety.dangerous_hours.map(h => `
                            <li>
                                <span>${h.hour}:00</span>
                                <strong>${h.count} alerts</strong>
                            </li>
                        `).join('') || '<li>No data</li>'}
                    </ul>
                </div>
                <div class="safety-item">
                    <h3>Most Dangerous Objects</h3>
                    <ul class="danger-list">
                        ${safety.dangerous_objects.map(o => `
                            <li>
                                <span>${o.object_type}</span>
                                <strong>${o.count} critical</strong>
                            </li>
                        `).join('') || '<li>No data</li>'}
                    </ul>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error updating safety metrics:', error);
    }
}

// Update voice commands
async function updateCommands() {
    try {
        const response = await fetch(`${API_BASE}/api/voice_commands?limit=10`);
        const commands = await response.json();
        
        const commandsList = document.getElementById('commandsList');
        
        if (commands.length === 0) {
            commandsList.innerHTML = '<div class="loading">No voice commands yet</div>';
            return;
        }
        
        commandsList.innerHTML = commands.map(cmd => `
            <div class="command-item">
                <div class="command-text"><span class="material-icons inline-icon">mic</span> "${escapeHtml(cmd.command)}"</div>
                ${cmd.response ? `<div class="command-response">Response: ${escapeHtml(cmd.response)}</div>` : ''}
                <div class="command-time">${formatTime(cmd.timestamp)}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error updating commands:', error);
    }
}

// Update sessions list
async function updateSessions() {
    try {
        const response = await fetch(`${API_BASE}/api/sessions`);
        const sessions = await response.json();
        
        const sessionsList = document.getElementById('sessionsList');
        
        if (sessions.length === 0) {
            sessionsList.innerHTML = '<div class="loading">No sessions yet</div>';
            return;
        }
        
        sessionsList.innerHTML = sessions.slice(0, 10).map(session => {
            const isActive = !session.end_time;
            const duration = session.duration_seconds || 0;
            const minutes = Math.floor(duration / 60);
            
            return `
                <div class="session-item ${isActive ? 'active' : ''}">
                    <div class="session-header">
                        <div class="session-id">Session #${session.id}</div>
                        ${isActive ? '<div class="session-badge">ACTIVE</div>' : ''}
                    </div>
                    <div class="session-stats">
                        <div class="session-stat">
                            <div class="session-stat-value">${session.total_detections || 0}</div>
                            <div class="session-stat-label">Detections</div>
                        </div>
                        <div class="session-stat">
                            <div class="session-stat-value">${session.total_alerts || 0}</div>
                            <div class="session-stat-label">Alerts</div>
                        </div>
                        <div class="session-stat">
                            <div class="session-stat-value">${minutes}m</div>
                            <div class="session-stat-label">Duration</div>
                        </div>
                    </div>
                    <div class="command-time">${formatDateTime(session.start_time)}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error updating sessions:', error);
    }
}

// Utility functions
function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return date.toLocaleDateString();
}

function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

