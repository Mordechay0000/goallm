"""
CRM Web Application for managing filtering policies.
Flask-based backend with modern frontend.
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.policy_processor.policy_database import (
    add_policy, update_policy, delete_policy,
    get_policy, get_all_policies, validate_policy
)

# Get the static folder path before creating Flask app
_static_folder = Path(__file__).resolve().parent / 'static'

app = Flask(__name__, static_folder=str(_static_folder), static_url_path='')
CORS(app)

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Serve the main CRM page."""
    return send_from_directory(str(_static_folder), 'index.html')


@app.route('/api/policies', methods=['GET'])
def list_policies():
    """Get all policies."""
    try:
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        policies = get_all_policies(enabled_only=enabled_only)
        return jsonify({"success": True, "policies": policies})
    except Exception as e:
        logger.exception("Error listing policies")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/policies', methods=['POST'])
def create_policy():
    """Create a new policy."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "לא התקבלו נתונים"}), 400
        
        domain = data.get('domain', '').strip()
        path = data.get('path', '').strip() or None
        policy_type = data.get('type', '*')
        state = data.get('state', 'block')
        description = data.get('description', '').strip() or None
        enabled = data.get('enabled', True)
        
        policy = add_policy(
            domain=domain,
            path=path,
            policy_type=policy_type,
            state=state,
            description=description,
            enabled=enabled
        )
        
        return jsonify({"success": True, "policy": policy}), 201
        
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Error creating policy")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/policies/<int:policy_id>', methods=['GET'])
def get_policy_by_id(policy_id):
    """Get a single policy by ID."""
    try:
        policy = get_policy(policy_id)
        if not policy:
            return jsonify({"success": False, "error": "כלל לא נמצא"}), 404
        return jsonify({"success": True, "policy": policy})
    except Exception as e:
        logger.exception("Error getting policy")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/policies/<int:policy_id>', methods=['PUT'])
def update_policy_by_id(policy_id):
    """Update an existing policy."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "לא התקבלו נתונים"}), 400
        
        # Only update provided fields
        update_data = {}
        if 'domain' in data:
            update_data['domain'] = data['domain'].strip()
        if 'path' in data:
            update_data['path'] = data['path'].strip() or None
        if 'type' in data:
            update_data['policy_type'] = data['type']
        if 'state' in data:
            update_data['state'] = data['state']
        if 'description' in data:
            update_data['description'] = data['description'].strip() or None
        if 'enabled' in data:
            update_data['enabled'] = data['enabled']
        
        policy = update_policy(policy_id, **update_data)
        return jsonify({"success": True, "policy": policy})
        
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Error updating policy")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/policies/<int:policy_id>', methods=['DELETE'])
def delete_policy_by_id(policy_id):
    """Delete a policy."""
    try:
        deleted = delete_policy(policy_id)
        if not deleted:
            return jsonify({"success": False, "error": "כלל לא נמצא"}), 404
        return jsonify({"success": True})
    except Exception as e:
        logger.exception("Error deleting policy")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/policies/validate', methods=['POST'])
def validate_policy_endpoint():
    """Validate policy fields without creating it."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "לא התקבלו נתונים"}), 400
        
        domain = data.get('domain', '').strip()
        path = data.get('path', '').strip() or None
        policy_type = data.get('type', '*')
        state = data.get('state', 'block')
        
        error = validate_policy(domain, path, policy_type, state)
        if error:
            return jsonify({"success": False, "error": error}), 400
        
        return jsonify({"success": True, "valid": True})
        
    except Exception as e:
        logger.exception("Error validating policy")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    
    # Setup logging (optional)
    try:
        from core.logger.logging_config import setup_logging
        setup_logging()
    except:
        print("Logging not configured")
    
    print("\n" + "="*60)
    print("CRM Server starting on http://127.0.0.1:5000")
    print("="*60)
    print("\nOpen your browser at: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server\n")
    
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
