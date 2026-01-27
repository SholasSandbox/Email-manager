#!/usr/bin/env python3
"""
Email Management Utility
Manages Gmail and Outlook emails with automated cleanup and organization
"""

import argparse
import logging
from datetime import datetime
from gmail_handler import GmailHandler
from outlook_handler import OutlookHandler

logger = logging.getLogger(__name__)

def configure_logging(log_file=None, debug=False):
    """Configure logging for console and optional file output."""
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


class EmailManager:
    """Main orchestrator for email management across providers"""
    
    def __init__(self, dry_run=True):
        """
        Initialize the email manager
        
        Args:
            dry_run (bool): If True, only simulate actions without making changes
        """
        self.dry_run = dry_run
        self.gmail_handler = None
        self.outlook_handler = None
        
    def setup_gmail(self):
        """Initialize and authenticate Gmail handler"""
        logger.info("Setting up Gmail handler...")
        try:
            self.gmail_handler = GmailHandler(dry_run=self.dry_run)
            self.gmail_handler.authenticate()
            logger.info("Gmail authentication successful")
            return True
        except Exception as e:
            logger.error(f"Gmail setup failed: {e}")
            return False
    
    def setup_outlook(self):
        """Initialize and authenticate Outlook handler"""
        logger.info("Setting up Outlook handler...")
        try:
            self.outlook_handler = OutlookHandler(dry_run=self.dry_run)
            self.outlook_handler.authenticate()
            logger.info("Outlook authentication successful")
            return True
        except Exception as e:
            logger.error(f"Outlook setup failed: {e}")
            return False
    
    def process_all_emails(self):
        """Process emails from all configured providers"""
        results = {
            'gmail': {'processed': False, 'stats': {}},
            'outlook': {'processed': False, 'stats': {}}
        }
        
        # Process Gmail
        if self.gmail_handler:
            logger.info("\n" + "="*50)
            logger.info("Processing Gmail emails...")
            logger.info("="*50)
            try:
                stats = self.gmail_handler.process_emails()
                results['gmail'] = {'processed': True, 'stats': stats}
                self._log_stats('Gmail', stats)
            except Exception as e:
                logger.error(f"Error processing Gmail: {e}")
        
        # Process Outlook
        if self.outlook_handler:
            logger.info("\n" + "="*50)
            logger.info("Processing Outlook emails...")
            logger.info("="*50)
            try:
                stats = self.outlook_handler.process_emails()
                results['outlook'] = {'processed': True, 'stats': stats}
                self._log_stats('Outlook', stats)
            except Exception as e:
                logger.error(f"Error processing Outlook: {e}")
        
        return results
    
    def _log_stats(self, provider, stats):
        """Log processing statistics"""
        logger.info(f"\n{provider} Processing Summary:")
        logger.info(f"  Promotions deleted: {stats.get('promotions_deleted', 0)}")
        logger.info(f"  Job alerts deleted: {stats.get('job_alerts_deleted', 0)}")
        logger.info(f"  Social media deleted: {stats.get('social_media_deleted', 0)}")
        logger.info(f"  Updates notifications trashed: {stats.get('updates_notifications_trashed', 0)}")
        logger.info(f"  Updates attention labeled: {stats.get('updates_attention_labeled', 0)}")
        logger.info(f"  Updates attention archived: {stats.get('updates_attention_archived', 0)}")
        logger.info(f"  Updates stale archived: {stats.get('updates_stale_archived', 0)}")
        logger.info(f"  Receipts archived (Recent): {stats.get('receipts_archived_recent', 0)}")
        logger.info(f"  Receipts moved to Old: {stats.get('receipts_moved_old', 0)}")
        logger.info(f"  App acknowledgements archived: {stats.get('app_acks_archived', 0)}")
        logger.info(f"  App acknowledgements deleted: {stats.get('app_acks_deleted', 0)}")
        logger.info(f"  Stale inbox archived (4+ months): {stats.get('stale_inbox_archived', 0)}")
        logger.info(f"  Rejections archived: {stats.get('rejections_archived', 0)}")
        logger.info(f"  Important emails found: {stats.get('important_found', 0)}")
        logger.info(f"  Calendar events created: {stats.get('events_created', 0)}")


def main():
    parser = argparse.ArgumentParser(description='Email Management Utility')
    parser.add_argument(
        '--provider',
        choices=['gmail', 'outlook', 'both'],
        default='both',
        help='Email provider to process'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Run in live mode (actually make changes). Default is dry-run.'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Log file path (optional)'
    )
    parser.add_argument(
        '--setup-only',
        action='store_true',
        help='Only run authentication setup'
    )
    
    args = parser.parse_args()
    
    configure_logging(log_file=args.log_file, debug=args.debug)
    if args.debug:
        logger.debug("Debug logging enabled")
    
    # Determine if we're in dry-run mode
    dry_run = not args.live
    
    if dry_run:
        logger.info("="*50)
        logger.info("RUNNING IN DRY-RUN MODE - No changes will be made")
        logger.info("Use --live flag to actually process emails")
        logger.info("="*50 + "\n")
    else:
        logger.warning("="*50)
        logger.warning("RUNNING IN LIVE MODE - Changes will be made!")
        logger.warning("="*50 + "\n")
    
    # Initialize manager
    manager = EmailManager(dry_run=dry_run)
    
    # Setup providers
    if args.provider in ['gmail', 'both']:
        manager.setup_gmail()
    
    if args.provider in ['outlook', 'both']:
        manager.setup_outlook()
    
    # If setup-only, exit here
    if args.setup_only:
        logger.info("Setup complete. Run without --setup-only to process emails.")
        return
    
    # Process emails
    results = manager.process_all_emails()
    
    logger.info("\n" + "="*50)
    logger.info("Processing complete!")
    logger.info("="*50)


if __name__ == '__main__':
    main()
