"""
Flask API Server for Email Cleanup Extension
Wraps existing Gmail and Outlook handlers with REST endpoints
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import argparse
import logging
from gmail_handler import GmailHandler
from outlook_handler import OutlookHandler

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for browser extension

# Store handler instances (in production, use proper session management)
handlers = {
    'gmail': None,
    'outlook': None
}


@app.route('/api/status', methods=['GET'])
def get_status():
    """Check if handlers are initialized and authenticated"""
    status = {
        'gmail': {
            'available': handlers['gmail'] is not None,
            'authenticated': False
        },
        'outlook': {
            'available': handlers['outlook'] is not None,
            'authenticated': False
        }
    }
    
    # Check Gmail authentication
    if handlers['gmail']:
        try:
            # Try to access Gmail service
            handlers['gmail'].service.users().getProfile(userId='me').execute()
            status['gmail']['authenticated'] = True
        except:
            status['gmail']['authenticated'] = False
    
    # Check Outlook authentication
    if handlers['outlook']:
        try:
            # Check if we have a valid access token
            status['outlook']['authenticated'] = handlers['outlook'].access_token is not None
        except:
            status['outlook']['authenticated'] = False
    
    return jsonify(status)


@app.route('/api/initialize/<provider>', methods=['POST'])
def initialize_handler(provider):
    """Initialize and authenticate Gmail or Outlook handler"""
    try:
        if provider == 'gmail':
            logger.info("Initializing Gmail handler...")
            handlers['gmail'] = GmailHandler(dry_run=True)
            handlers['gmail'].authenticate()  # ← ADDED THIS LINE!
            logger.info("Gmail handler authenticated successfully")
            return jsonify({
                'success': True,
                'message': 'Gmail handler initialized and authenticated',
                'provider': 'gmail'
            })
        
        elif provider == 'outlook':
            logger.info("Initializing Outlook handler...")
            handlers['outlook'] = OutlookHandler(dry_run=True)
            handlers['outlook'].authenticate()  # ← ADDED THIS LINE!
            logger.info("Outlook handler authenticated successfully")
            return jsonify({
                'success': True,
                'message': 'Outlook handler initialized and authenticated',
                'provider': 'outlook'
            })
        
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown provider: {provider}'
            }), 400
    
    except Exception as e:
        logger.error(f"Error initializing {provider} handler: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/preview/<provider>', methods=['GET'])
def preview_cleanup(provider):
    """Preview what would be cleaned up (dry-run mode)"""
    try:
        # Ensure handler is initialized
        if provider not in handlers or handlers[provider] is None:
            return jsonify({
                'success': False,
                'error': f'{provider} handler not initialized. Call /api/initialize/{provider} first.'
            }), 400
        
        handler = handlers[provider]
        
        # Ensure dry-run mode
        handler.dry_run = True
        
        logger.info(f"Running preview cleanup for {provider}...")
        stats = handler.process_emails()
        
        return jsonify({
            'success': True,
            'provider': provider,
            'dry_run': True,
            'stats': stats
        })
    
    except Exception as e:
        logger.error(f"Error previewing cleanup for {provider}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cleanup/<provider>', methods=['POST'])
def run_cleanup(provider):
    """Run actual email cleanup (live mode)"""
    try:
        # Ensure handler is initialized
        if provider not in handlers or handlers[provider] is None:
            return jsonify({
                'success': False,
                'error': f'{provider} handler not initialized. Call /api/initialize/{provider} first.'
            }), 400
        
        handler = handlers[provider]
        
        # Get dry_run flag from request
        data = request.get_json() or {}
        dry_run = data.get('dry_run', True)  # Default to dry-run for safety
        
        handler.dry_run = dry_run
        
        logger.info(f"Running cleanup for {provider} (dry_run={dry_run})...")
        stats = handler.process_emails()
        
        return jsonify({
            'success': True,
            'provider': provider,
            'dry_run': dry_run,
            'stats': stats
        })
    
    except Exception as e:
        logger.error(f"Error running cleanup for {provider}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Email Cleanup API is running'
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Email Cleanup API Server')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to listen on (default: 5000)'
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Log file path (optional)'
    )
    
    args = parser.parse_args()
    
    handlers = [logging.StreamHandler()]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file))
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    if args.debug:
        logger.debug("Debug logging enabled")
    
    logger.info("Starting Email Cleanup API Server...")
    logger.info(f"Server will run on http://{args.host}:{args.port}")
    logger.info("Make sure your browser extension points to this URL")
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug  # Disable in production
    )
