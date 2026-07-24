"""
Health Check Endpoint for Uptime Monitoring
Provides application status and health metrics
"""

from flask import Blueprint, jsonify
from datetime import datetime
import time
import os
from app import db

health_bp = Blueprint('health', __name__)

# Track application startup time
START_TIME = time.time()

@health_bp.route('/health')
def health_check():
    """
    Basic health check endpoint for uptime monitoring
    Returns 200 OK if application is healthy
    """
    try:
        # Calculate uptime
        uptime_seconds = time.time() - START_TIME
        uptime_hours = uptime_seconds / 3600
        uptime_days = uptime_hours / 24
        
        # Format uptime string
        if uptime_days >= 1:
            uptime_str = f"{uptime_days:.1f} days"
        elif uptime_hours >= 1:
            uptime_str = f"{uptime_hours:.1f} hours"
        else:
            uptime_str = f"{uptime_seconds:.0f} seconds"
        
        return jsonify({
            'status': 'healthy',
            'uptime': uptime_str,
            'uptime_seconds': round(uptime_seconds, 2),
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@health_bp.route('/health/detailed')
def detailed_health_check():
    """
    Detailed health check with database connectivity
    Use for internal monitoring or admin dashboards
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'uptime_seconds': round(time.time() - START_TIME, 2),
        'checks': {}
    }
    
    overall_healthy = True
    
    # Check database connectivity
    try:
        db.session.execute(db.text('SELECT 1'))
        health_status['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        overall_healthy = False
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': str(e)
        }
    
    # Check upload directory
    try:
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
        if os.path.exists(upload_dir) and os.access(upload_dir, os.W_OK):
            health_status['checks']['upload_directory'] = {
                'status': 'healthy',
                'message': 'Upload directory is writable'
            }
        else:
            overall_healthy = False
            health_status['checks']['upload_directory'] = {
                'status': 'unhealthy',
                'message': 'Upload directory does not exist or is not writable'
            }
    except Exception as e:
        overall_healthy = False
        health_status['checks']['upload_directory'] = {
            'status': 'unhealthy',
            'message': str(e)
        }
    
    # Check environment variables
    required_env_vars = ['SECRET_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        overall_healthy = False
        health_status['checks']['environment'] = {
            'status': 'unhealthy',
            'message': f'Missing required environment variables: {", ".join(missing_vars)}'
        }
    else:
        health_status['checks']['environment'] = {
            'status': 'healthy',
            'message': 'All required environment variables are set'
        }
    
    health_status['status'] = 'healthy' if overall_healthy else 'unhealthy'
    
    status_code = 200 if overall_healthy else 503
    return jsonify(health_status), status_code

@health_bp.route('/health/ready')
def readiness_check():
    """
    Readiness check - indicates if the app is ready to accept traffic
    Similar to basic health check but can be extended with more specific checks
    """
    try:
        # Quick database check
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503
