"""
Gmail Handler
Handles authentication and email processing for Gmail accounts
"""

import os
import pickle
import logging
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes - what permissions we need
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # Read and modify emails
    'https://www.googleapis.com/auth/calendar'        # Create calendar events
]


class GmailHandler:
    """Handles all Gmail operations"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.service = None
        self.calendar_service = None
        self.user_email = None
        self._label_cache = {}
        self._labels_loaded = False
        # Gmail batchModify limit is 1000 message IDs per request
        self.batch_size = 1000
        
    def authenticate(self):
        """
        Authenticate with Gmail using OAuth 2.0
        
        AUTHENTICATION FLOW:
        1. Check if we have saved credentials (token.pickle)
        2. If credentials exist and are valid, use them
        3. If credentials are expired, refresh them
        4. If no credentials, start OAuth flow (opens browser)
        
        You'll need to:
        1. Go to Google Cloud Console (console.cloud.google.com)
        2. Create a project
        3. Enable Gmail API and Google Calendar API
        4. Create OAuth 2.0 credentials (Desktop app)
        5. Download credentials and save as 'gmail_credentials.json'
        """
        creds = None
        
        # Check for existing token
        if os.path.exists('gmail_token.pickle'):
            with open('gmail_token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Gmail credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists('gmail_credentials.json'):
                    raise FileNotFoundError(
                        "gmail_credentials.json not found. "
                        "Download OAuth credentials from Google Cloud Console."
                    )
                logger.info("Starting Gmail OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'gmail_credentials.json', SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open('gmail_token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        # Build service objects
        self.service = build('gmail', 'v1', credentials=creds)
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        
        # Get user's email address
        profile = self.service.users().getProfile(userId='me').execute()
        self.user_email = profile['emailAddress']
        logger.info(f"Authenticated as: {self.user_email}")
    
    def process_emails(self):
        """Main processing function for all email operations"""
        stats = {
            'promotions_deleted': 0,
            'job_alerts_deleted': 0,
            'social_media_deleted': 0,
            'updates_notifications_trashed': 0,
            'updates_attention_labeled': 0,
            'updates_attention_archived': 0,
            'updates_stale_archived': 0,
            'receipts_archived_recent': 0,
            'receipts_moved_old': 0,
            'app_acks_archived': 0,
            'app_acks_deleted': 0,
            'stale_inbox_archived': 0,
            'rejections_archived': 0,
            'important_found': 0,
            'events_created': 0
        }
        
        # Process old promotions (30+ days)
        stats['promotions_deleted'] = self._delete_old_promotions()
        
        # Process old job alerts (14+ days / 2 weeks)
        stats['job_alerts_deleted'] = self._delete_old_job_alerts()
        
        # Process old social media notifications (14+ days / 2 weeks)
        stats['social_media_deleted'] = self._delete_old_social_media()
        
        # Process updates: trash stale notifications, label attention, archive stale
        stats['updates_notifications_trashed'] = self._trash_stale_updates_notifications()
        stats['updates_attention_labeled'] = self._label_updates_attention()
        stats['updates_attention_archived'] = self._archive_aged_attention_updates()
        stats['updates_stale_archived'] = self._archive_stale_updates_general()
        
        # Process receipts
        self._ensure_receipt_labels()
        self._consolidate_receipt_labels()
        stats['receipts_archived_recent'] = self._archive_receipts_recent()
        stats['receipts_moved_old'] = self._move_receipts_old()
        
        # Process application acknowledgements - two-step process
        stats['app_acks_archived'] = self._archive_application_acknowledgements()
        stats['app_acks_deleted'] = self._delete_old_application_acknowledgements()
        
        # Archive stale inbox items (4+ months old)
        stats['stale_inbox_archived'] = self._archive_stale_inbox()
        
        # Process rejection emails
        stats['rejections_archived'] = self._archive_rejections()
        
        # Find and highlight important emails
        important_emails = self._find_important_emails()
        stats['important_found'] = len(important_emails)
        
        # Create calendar events for important emails
        stats['events_created'] = self._create_calendar_events(important_emails)
        
        return stats
    
    def _delete_old_promotions(self):
        """Delete promotional emails older than 30 days"""
        logger.info("Searching for old promotional emails...")
        
        # Calculate date 30 days ago
        cutoff_date = datetime.now() - timedelta(days=30)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Gmail query: category:promotions AND before:date, skip spam/trash
        query = f'category:promotions before:{date_str} -in:spam -in:trash'
        
        deleted = self._delete_emails_by_query(query, "old promotions")
        # Mark remaining promotions (archived) as read
        self._mark_read_by_query(query, "old promotions")
        return deleted
    
    def _delete_old_job_alerts(self):
        """Delete job alert emails older than 14 days (2 weeks)"""
        logger.info("Searching for old job alerts...")
        
        cutoff_date = datetime.now() - timedelta(days=14)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Common job alert patterns
        # Keep literal phrases quoted; keep Gmail operators unquoted.
        job_phrases = [
            'job alert',
            'job alerts',
            'career opportunity',
            'career opportunities',
            'new jobs',
            'job notification',
            'job recommendations',
            'recommended jobs',
            'jobs you may like',
            'job matches',
            'new opportunity',
            'new opportunities',
        ]
        job_queries = [
            'from:linkedin.com',
            'from:indeed.com',
            'from:glassdoor.com',
            'from:ziprecruiter.com',
            'from:monster.com',
            'from:careerbuilder.com',
            'from:simplyhired.com',
        ]
        
        # Build query with OR conditions for job alerts
        phrase_query = ' OR '.join([f'"{kw}"' for kw in job_phrases])
        query_parts = [phrase_query] + job_queries
        keyword_query = ' OR '.join([part for part in query_parts if part])
        query = f'({keyword_query}) before:{date_str} -in:spam -in:trash'
        
        deleted = self._delete_emails_by_query(query, "old job alerts")
        self._mark_read_by_query(query, "old job alerts")
        return deleted
    
    def _delete_old_social_media(self):
        """Delete social media notification emails older than 14 days (2 weeks)"""
        logger.info("Searching for old social media notifications...")
        
        cutoff_date = datetime.now() - timedelta(days=14)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Social media platforms
        # For LinkedIn: exclude job alerts (those have "job" in them and are handled separately)
        social_platforms = [
            'from:facebookmail.com',
            'from:facebook.com',
            'from:twitter.com',
            'from:x.com',
            'from:instagram.com',
            'from:mail.instagram.com',
            'from:tiktok.com',
            'from:reddit.com',
            'from:pinterest.com',
            'from:snapchat.com',
            '(from:linkedin.com -subject:job -subject:career -subject:opportunity)',  # LinkedIn social only
        ]
        
        # Build query with OR conditions for social media
        platform_query = ' OR '.join(social_platforms)
        query = f'({platform_query}) before:{date_str} -in:spam -in:trash'
        
        deleted = self._delete_emails_by_query(query, "old social media notifications")
        self._mark_read_by_query(query, "old social media notifications")
        return deleted

    def _trash_stale_updates_notifications(self):
        """Trash stale updates notifications after 60 days (tasks/AWS/OneDrive/Instagram)."""
        logger.info("Trashing stale Updates notifications (60+ days)...")
        
        cutoff = datetime.now() - timedelta(days=60)
        date_str = cutoff.strftime('%Y/%m/%d')
        
        # Task updates and notification sources
        task_sources = [
            'from:asana.com',
            'from:trello.com',
            'from:monday.com',
            'from:clickup.com',
            'from:todoist.com',
            'from:atlassian.net',
        ]
        task_keywords = [
            '"task update"',
            '"task assigned"',
            '"task completed"',
            '"due date"',
            '"commented on"',
        ]
        
        # AWS, OneDrive, Instagram notifications
        notif_sources = [
            'from:amazonaws.com',
            'from:aws.amazon.com',
            'subject:AWS',
            'from:onedrive.com',
            'from:storage.live.com',
            'from:instagram.com',
            'from:mail.instagram.com',
        ]
        
        query_parts = task_sources + task_keywords + notif_sources
        keyword_query = ' OR '.join(query_parts)
        query = f'in:updates ({keyword_query}) before:{date_str} -in:spam -in:trash'
        
        deleted = self._delete_emails_by_query(query, "stale updates notifications (60+ days)")
        self._mark_read_by_query(query, "stale updates notifications (60+ days)")
        return deleted

    def _label_updates_attention(self):
        """Label important or directly addressed Updates for attention (keep in inbox)."""
        logger.info("Labeling important or directed Updates for attention...")
        
        attention_label = "Attention/Updates"
        attention_label_id = self._get_or_create_label(attention_label)
        if not attention_label_id:
            return 0
        
        query = (
            f'in:updates in:inbox -in:spam -in:trash '
            f'(-list:* -has:unsubscribe) '
            f'(is:important OR to:{self.user_email} OR cc:{self.user_email})'
        )
        
        return self._modify_emails_by_query(
            query,
            "attention updates (label only)",
            add_label_ids=[attention_label_id],
            remove_label_ids=[]
        )

    def _archive_aged_attention_updates(self):
        """Archive attention-labeled updates after 14 days while keeping the label."""
        logger.info("Archiving aged attention Updates (14+ days)...")
        
        cutoff = datetime.now() - timedelta(days=14)
        date_str = cutoff.strftime('%Y/%m/%d')
        attention_label = "Attention/Updates"
        
        query = f'label:"{attention_label}" in:updates before:{date_str} -in:spam -in:trash'
        
        return self._modify_emails_by_query(
            query,
            "aged attention updates (archive)",
            add_label_ids=[],
            remove_label_ids=['INBOX']
        )

    def _archive_stale_updates_general(self):
        """Archive non-important Updates older than 60 days."""
        logger.info("Archiving stale Updates (60+ days)...")
        
        cutoff = datetime.now() - timedelta(days=60)
        date_str = cutoff.strftime('%Y/%m/%d')
        
        query = (
            f'in:updates before:{date_str} -in:spam -in:trash '
            f'-is:important -to:{self.user_email} -cc:{self.user_email} '
            f'-label:"Attention/Updates"'
        )
        
        return self._archive_emails_by_query(query, "stale updates (60+ days)")

    def _ensure_receipt_labels(self):
        """Ensure receipt labels exist."""
        self._get_or_create_label("Archive/Shopping/Receipts/Recent")
        self._get_or_create_label("Archive/Shopping/Receipts/Old")

    def _consolidate_receipt_labels(self):
        """Consolidate existing receipt labels into the new receipts path."""
        if not self._labels_loaded:
            self._get_or_create_label("Archive/Shopping/Receipts/Recent")
        receipt_labels = [
            name for name in self._label_cache.keys()
            if 'receipt' in name.lower() and not name.startswith("Archive/Shopping/Receipts/")
        ]
        if not receipt_labels:
            return
        
        recent_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Recent")
        old_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Old")
        
        # Split by age: 30+ days -> Old, otherwise Recent
        cutoff = datetime.now() - timedelta(days=30)
        date_str = cutoff.strftime('%Y/%m/%d')
        
        for label in receipt_labels:
            # Old
            old_query = f'label:"{label}" before:{date_str} -in:spam -in:trash'
            self._modify_emails_by_query(
                old_query,
                f"consolidate receipts old from {label}",
                add_label_ids=[old_label_id],
                remove_label_ids=[self._label_cache.get(label)]
            )
            # Recent
            recent_query = f'label:"{label}" after:{date_str} -in:spam -in:trash'
            self._modify_emails_by_query(
                recent_query,
                f"consolidate receipts recent from {label}",
                add_label_ids=[recent_label_id],
                remove_label_ids=[self._label_cache.get(label)]
            )

    def _archive_receipts_recent(self):
        """Archive receipts after 7 days into Receipts/Recent."""
        logger.info("Archiving receipts to Receipts/Recent (7+ days)...")
        
        cutoff = datetime.now() - timedelta(days=7)
        date_str = cutoff.strftime('%Y/%m/%d')
        
        receipt_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Recent")
        old_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Old")
        
        receipt_query = self._receipt_query()
        query = f'({receipt_query}) before:{date_str} -in:spam -in:trash'
        
        modified = self._modify_emails_by_query(
            query,
            "receipts to Recent (7+ days)",
            add_label_ids=[receipt_label_id],
            remove_label_ids=['INBOX', old_label_id]
        )
        self._mark_read_by_query(query, "receipts to Recent (7+ days)")
        return modified

    def _move_receipts_old(self):
        """Move receipts older than 30 days to Receipts/Old."""
        logger.info("Moving receipts to Receipts/Old (30+ days)...")
        
        cutoff = datetime.now() - timedelta(days=30)
        date_str = cutoff.strftime('%Y/%m/%d')
        
        receipt_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Recent")
        old_label_id = self._get_or_create_label("Archive/Shopping/Receipts/Old")
        
        receipt_query = self._receipt_query()
        query = f'({receipt_query}) before:{date_str} -in:spam -in:trash'
        
        modified = self._modify_emails_by_query(
            query,
            "receipts to Old (30+ days)",
            add_label_ids=[old_label_id],
            remove_label_ids=['INBOX', receipt_label_id]
        )
        self._mark_read_by_query(query, "receipts to Old (30+ days)")
        return modified

    def _receipt_query(self):
        """Build a query for receipt-like emails."""
        receipt_keywords = [
            '"receipt"',
            '"order confirmation"',
            '"order receipt"',
            '"purchase confirmation"',
            '"payment received"',
            '"your order"',
            '"order number"',
            '"pickup"',
            '"delivered"',
            '"shipped"',
        ]
        receipt_domains = [
            'from:amazon.com',
            'from:amazon.co.uk',
            'from:amazon.ca',
            'from:ebay.com',
            'from:orders@amazon.com',
            'from:ebay@ebay.com',
            'from:walmart.com',
            'from:target.com',
            'from:bestbuy.com',
            'from:homedepot.com',
            'from:lowes.com',
            'from:costco.com',
            'from:samsclub.com',
            'from:shopify.com',
            'from:squareup.com',
            'from:stripe.com',
            'from:paypal.com',
        ]
        parts = receipt_keywords + receipt_domains
        return ' OR '.join(parts)
    
    def _archive_rejections(self):
        """Archive job rejection emails"""
        logger.info("Searching for rejection emails...")
        
        # Common rejection phrases
        rejection_phrases = [
            'regret to inform',
            'not moving forward',
            'not move forward',
            'chosen to pursue other candidates',
            'decided to move forward with other',
            'decided to pursue other',
            'not been successful',
            'not successful',
            'will not be progressing',
            'we will not be moving forward',
            'we are unable to move forward',
            'position has been filled',
            'position is filled',
            'after careful consideration',
            'not selected',
            'declined to move forward',
            'we have chosen another',
            'no longer under consideration'
        ]
        
        # Build query
        phrase_query = ' OR '.join([f'"{phrase}"' for phrase in rejection_phrases])
        query = phrase_query
        
        return self._archive_emails_by_query(query, "rejection emails")
    
    def _archive_application_acknowledgements(self):
        """
        Archive application acknowledgement emails after 7 days
        Step 1 of 2-step process: Archive (remove from inbox, keep searchable)
        Only targets automated noreply emails, NOT emails from real people
        """
        logger.info("Searching for application acknowledgements to archive (7+ days old)...")
        
        cutoff_date = datetime.now() - timedelta(days=7)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Common acknowledgement phrases
        ack_phrases = [
            'thank you for applying',
            'application received',
            'we received your application',
            'received your application',
            'application confirmation',
            'application submitted',
            'thank you for your application',
            'application acknowledged',
            'confirmed receipt of your application',
            'your application has been received',
            'thanks for applying',
            'application submitted successfully',
            'application complete',
            'we have received your application',
            'your application was received'
        ]
        
        # Build query - must be in inbox, older than 7 days, AND from noreply addresses
        # This ensures we only archive automated acknowledgements, not real recruiter emails
        phrase_query = ' OR '.join([f'"{phrase}"' for phrase in ack_phrases])
        
        # Only target noreply/automated emails - NOT emails from real people
        noreply_filters = [
            'from:noreply',
            'from:no-reply',
            'from:donotreply',
            'from:do-not-reply',
            'from:notifications@',
            'from:automated@',
            'from:system@',
            'from:bot@'
        ]
        noreply_query = ' OR '.join(noreply_filters)
        
        query = f'in:inbox ({phrase_query}) ({noreply_query}) before:{date_str}'
        
        return self._archive_emails_by_query(query, "automated application acknowledgements (7+ days)")
    
    def _delete_old_application_acknowledgements(self):
        """
        Delete application acknowledgement emails after 30 days
        Step 2 of 2-step process: Delete archived acknowledgements that are 30+ days old
        Only targets automated noreply emails, NOT emails from real people
        """
        logger.info("Searching for old application acknowledgements to delete (30+ days old)...")
        
        cutoff_date = datetime.now() - timedelta(days=30)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Same acknowledgement phrases
        ack_phrases = [
            'thank you for applying',
            'application received',
            'we received your application',
            'received your application',
            'application confirmation',
            'application submitted',
            'thank you for your application',
            'application acknowledged',
            'confirmed receipt of your application',
            'your application has been received',
            'thanks for applying',
            'application submitted successfully',
            'application complete',
            'we have received your application',
            'your application was received'
        ]
        
        # Only target noreply/automated emails - NOT emails from real people
        noreply_filters = [
            'from:noreply',
            'from:no-reply',
            'from:donotreply',
            'from:do-not-reply',
            'from:notifications@',
            'from:automated@',
            'from:system@',
            'from:bot@'
        ]
        
        # Build query - must NOT be in inbox (already archived), from noreply, and older than 30 days
        phrase_query = ' OR '.join([f'"{phrase}"' for phrase in ack_phrases])
        noreply_query = ' OR '.join(noreply_filters)
        query = f'-in:inbox ({phrase_query}) ({noreply_query}) before:{date_str} -in:spam -in:trash'
        
        return self._delete_emails_by_query(query, "old automated application acknowledgements (30+ days)")
    
    def _archive_stale_inbox(self):
        """
        Archive emails that have been in inbox for 4+ months
        Organizes by category (Work, Personal, Finance, etc.) with Recent/Old subfolders
        Recent: 4-18 months old
        Old: 18+ months old
        """
        logger.info("Searching for stale inbox items (4+ months old)...")

        # Pre-create all archive labels up front to avoid per-message lookups
        self._ensure_archive_labels()
        attention_label_id = self._get_or_create_label("Attention/Updates")
        
        cutoff_date = datetime.now() - timedelta(days=120)  # 4 months = ~120 days
        old_threshold = datetime.now() - timedelta(days=540)  # 18 months = ~540 days
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Query: in inbox AND older than 4 months
        query = f'in:inbox before:{date_str}'
        
        archived = 0
        skipped_failed_precondition = 0
        page_token = None
        total_found = 0
        category_counts = {}
        
        # Safety: Track processed message IDs to prevent duplicates
        processed_ids = set()
        
        # Safety: Iteration counter to prevent infinite loops
        max_iterations = 1000  # Max 1000 batches = 500,000 emails
        iteration_count = 0
        
        try:
            while True:
                # Safety check: iteration limit
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations ({iteration_count * 500} emails max)")
                    logger.error("Stopping to prevent infinite loop. Your inbox may have more emails to process.")
                    break
                
                # Fetch up to 500 messages per batch
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    break
                
                total_found += len(messages)
                logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                
                # Group by archive label to batch operations
                label_to_ids_read = {}
                label_to_ids_keep = {}
                
                for msg in messages:
                    msg_id = msg['id']
                    
                    # Safety: Skip if already processed (shouldn't happen, but prevents duplicates)
                    if msg_id in processed_ids:
                        logger.warning(f"Skipping duplicate message ID: {msg_id}")
                        continue
                    
                    processed_ids.add(msg_id)
                    
                    # Get full message to categorize
                    message = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ).execute()
                    
                    labels = set(message.get('labelIds', []))
                    is_important = 'IMPORTANT' in labels
                    is_attention = attention_label_id in labels if attention_label_id else False
                    
                    # Categorize the email
                    category = self._categorize_email(message)
                    
                    # Determine if Recent or Old
                    received_date = self._get_email_date(message)
                    age_subfolder = "Old" if received_date and received_date < old_threshold else "Recent"
                    
                    # Create label name: Archive/{Category}/{Recent|Old}
                    archive_label_name = f"Archive/{category}/{age_subfolder}"
                    
                    # Get or create the label
                    archive_label_id = self._get_or_create_label(archive_label_name)
                    
                    if not archive_label_id:
                        logger.warning(f"Failed to get/create label {archive_label_name}, skipping")
                        continue
                    
                    # Collect IDs by label for batch archive
                    target = label_to_ids_keep if (is_important or is_attention) else label_to_ids_read
                    target.setdefault(archive_label_id, []).append(msg_id)
                    
                    # Track category counts
                    full_category = f"{category}/{age_subfolder}"
                    category_counts[full_category] = category_counts.get(full_category, 0) + 1
                    
                # Batch archive by label ID
                for label_id, ids in label_to_ids_read.items():
                    for chunk in self._chunk_ids(ids, self.batch_size):
                        if not self.dry_run:
                            try:
                                self.service.users().messages().batchModify(
                                    userId='me',
                                    body={
                                        'ids': chunk,
                                        'addLabelIds': [label_id],
                                        'removeLabelIds': ['INBOX', 'UNREAD']
                                    }
                                ).execute()
                                archived += len(chunk)
                            except HttpError as error:
                                # Fallback to per-message to isolate failures
                                for msg_id in chunk:
                                    try:
                                        self.service.users().messages().modify(
                                            userId='me',
                                            id=msg_id,
                                            body={
                                                'addLabelIds': [label_id],
                                                'removeLabelIds': ['INBOX', 'UNREAD']
                                            }
                                        ).execute()
                                        archived += 1
                                    except HttpError as error:
                                        if 'failedPrecondition' in str(error):
                                            skipped_failed_precondition += 1
                                            logger.debug(f"  Skipping message {msg_id}: {error}")
                                            continue
                                        logger.warning(f"  Error archiving message {msg_id}: {error}")
                                        continue
                        else:
                            archived += len(chunk)
                        
                        # Log progress every 100 messages
                        if archived % 100 == 0:
                            logger.info(f"    Progress: {archived} messages processed...")
                
                for label_id, ids in label_to_ids_keep.items():
                    for chunk in self._chunk_ids(ids, self.batch_size):
                        if not self.dry_run:
                            try:
                                self.service.users().messages().batchModify(
                                    userId='me',
                                    body={
                                        'ids': chunk,
                                        'addLabelIds': [label_id],
                                        'removeLabelIds': ['INBOX']
                                    }
                                ).execute()
                                archived += len(chunk)
                            except HttpError as error:
                                for msg_id in chunk:
                                    try:
                                        self.service.users().messages().modify(
                                            userId='me',
                                            id=msg_id,
                                            body={
                                                'addLabelIds': [label_id],
                                                'removeLabelIds': ['INBOX']
                                            }
                                        ).execute()
                                        archived += 1
                                    except HttpError as error:
                                        if 'failedPrecondition' in str(error):
                                            skipped_failed_precondition += 1
                                            logger.debug(f"  Skipping message {msg_id}: {error}")
                                            continue
                                        logger.warning(f"  Error archiving message {msg_id}: {error}")
                                        continue
                        else:
                            archived += len(chunk)
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if total_found == 0:
                logger.info(f"  No stale inbox items found")
            else:
                logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} stale inbox items")
                if skipped_failed_precondition:
                    logger.info(f"  Skipped {skipped_failed_precondition} messages due to failed precondition")
                logger.info(f"  Category breakdown:")
                for cat, count in sorted(category_counts.items()):
                    logger.info(f"    {cat}: {count}")
            
        except HttpError as error:
            logger.error(f"Error archiving stale inbox: {error}")
        
        return archived

    def _chunk_ids(self, ids, size):
        """Yield chunks of IDs for batch operations."""
        for i in range(0, len(ids), size):
            yield ids[i:i + size]

    def _ensure_archive_labels(self):
        """Pre-create all Archive/{Category}/{Recent|Old} labels."""
        categories = [
            "Work",
            "Personal",
            "Finance",
            "Shopping",
            "Travel",
            "Healthcare",
            "Utilities",
            "Education",
            "Other",
        ]
        age_groups = ["Recent", "Old"]

        for category in categories:
            for age in age_groups:
                label_name = f"Archive/{category}/{age}"
                self._get_or_create_label(label_name)
    
    def _categorize_email(self, message):
        """
        Categorize an email into: Work, Personal, Finance, Shopping, Travel, Healthcare, Utilities, Education, or Other
        """
        headers = message.get('payload', {}).get('headers', [])
        
        from_email = ""
        subject = ""
        
        for header in headers:
            if header['name'].lower() == 'from':
                from_email = header['value'].lower()
            elif header['name'].lower() == 'subject':
                subject = header['value'].lower()
        
        # Extract domain from email
        domain = ""
        if '@' in from_email:
            domain = from_email.split('@')[-1].split('>')[0].strip()
        
        # Finance keywords and domains
        finance_keywords = ['invoice', 'payment', 'receipt', 'statement', 'transaction', 'bill', 'charge', 'refund', 'tax']
        finance_domains = ['paypal.com', 'stripe.com', 'square.com', 'bank', 'chase.com', 'wellsfargo.com', 'bankofamerica.com', 'citi.com', 'discover.com', 'amex.com', 'americanexpress.com', 'visa.com', 'mastercard.com']
        
        # Shopping keywords and domains
        shopping_keywords = ['order', 'shipped', 'delivery', 'tracking', 'purchase', 'confirmation']
        shopping_domains = ['amazon.com', 'ebay.com', 'etsy.com', 'walmart.com', 'target.com', 'bestbuy.com', 'shopify']
        
        # Travel keywords and domains
        travel_keywords = ['booking', 'reservation', 'flight', 'hotel', 'itinerary', 'confirmation']
        travel_domains = ['booking.com', 'airbnb.com', 'expedia.com', 'hotels.com', 'uber.com', 'lyft.com', 'airline']
        
        # Healthcare keywords and domains
        health_keywords = ['appointment', 'prescription', 'medical', 'health', 'doctor', 'clinic', 'hospital', 'insurance']
        health_domains = ['health', 'medical', 'doctor', 'hospital', 'pharmacy']
        
        # Utilities keywords and domains
        utility_keywords = ['bill', 'account', 'service', 'subscription']
        utility_domains = ['electric', 'gas', 'water', 'internet', 'phone', 'cable', 'spectrum.com', 'att.com', 'verizon.com', 'tmobile.com']
        
        # Education keywords and domains
        education_keywords = ['course', 'class', 'assignment', 'grade', 'school', 'university', 'student']
        education_domains = ['.edu', 'udemy.com', 'coursera.org', 'edx.org']
        
        # Check Finance
        if any(kw in subject for kw in finance_keywords) or any(dom in domain for dom in finance_domains):
            return "Finance"
        
        # Check Shopping
        if any(kw in subject for kw in shopping_keywords) or any(dom in domain for dom in shopping_domains):
            return "Shopping"
        
        # Check Travel
        if any(kw in subject for kw in travel_keywords) or any(dom in domain for dom in travel_domains):
            return "Travel"
        
        # Check Healthcare
        if any(kw in subject for kw in health_keywords) or any(dom in domain for dom in health_domains):
            return "Healthcare"
        
        # Check Utilities
        if any(kw in subject for kw in utility_keywords) or any(dom in domain for dom in utility_domains):
            return "Utilities"
        
        # Check Education
        if any(kw in subject for kw in education_keywords) or any(dom in domain for dom in education_domains):
            return "Education"
        
        # Check Work (corporate domains, not free email services)
        free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com', 'protonmail.com']
        if domain and not any(free in domain for free in free_domains) and '.' in domain:
            # Corporate domain - likely work
            return "Work"
        
        # Check Personal (free email services)
        if any(free in domain for free in free_domains):
            return "Personal"
        
        # Default
        return "Other"
    
    def _get_email_date(self, message):
        """Get the date an email was received"""
        try:
            timestamp = int(message.get('internalDate', 0))
            if timestamp:
                return datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
        except:
            pass
        return None
    
    def _get_or_create_label(self, label_name):
        """
        Get existing label ID or create new label
        Returns label ID or None on failure
        """
        try:
            # Return cached ID if available
            if label_name in self._label_cache:
                return self._label_cache[label_name]
            
            # Load labels once per run
            if not self._labels_loaded:
                results = self.service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])
                for label in labels:
                    name = label.get('name')
                    label_id = label.get('id')
                    if name and label_id:
                        self._label_cache[name] = label_id
                self._labels_loaded = True
            
            # Check cache again after loading
            if label_name in self._label_cache:
                return self._label_cache[label_name]
            
            # Label doesn't exist, create it
            if not self.dry_run:
                label_object = {
                    'name': label_name,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
                created_label = self.service.users().labels().create(
                    userId='me',
                    body=label_object
                ).execute()
                logger.info(f"  Created new label: {label_name}")
                label_id = created_label.get('id')
                if label_id:
                    self._label_cache[label_name] = label_id
                return label_id
            else:
                # In dry-run mode, log once and cache a fake ID
                logger.info(f"  [DRY RUN] Would create label: {label_name}")
                fake_id = f"dry-run-{label_name}"
                self._label_cache[label_name] = fake_id
                return fake_id
                
        except HttpError as error:
            logger.error(f"Error getting/creating label {label_name}: {error}")
            return None
    
    def _find_important_emails(self):
        """
        Find important emails directly addressed to the user
        
        Criteria:
        - Addressed directly to user (in To: field, not CC or BCC)
        - Not in spam or trash
        - Received in last 7 days
        - Not from mailing lists
        - Marked as important OR unread and not bulk/automated
        """
        logger.info("Searching for important emails...")
        
        cutoff_date = datetime.now() - timedelta(days=7)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Query for potentially important emails
        # Tighten to primary inbox and exclude list/bulk mail.
        query = (
            f'in:inbox category:primary to:{self.user_email} after:{date_str} '
            f'-in:spam -in:trash -list:* -has:unsubscribe -from:noreply -from:no-reply'
        )
        
        important_emails = []
        page_token = None
        
        try:
            while len(important_emails) < 100:  # Limit to 100 important emails for calendar events
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=100,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    break
                
                for msg in messages:
                    if len(important_emails) >= 100:
                        break
                    
                    # Get full message details
                    message = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    # Check if directly addressed to user and not bulk
                    if self._is_directly_addressed(message) and not self._is_bulk_or_marketing(message):
                        important_emails.append(message)
                        
                        # Mark as important if not already
                        if not self.dry_run:
                            self._mark_important(msg['id'])
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"Found {len(important_emails)} important emails")
            
        except HttpError as error:
            logger.error(f"Error finding important emails: {error}")
        
        return important_emails
    
    def _is_directly_addressed(self, message):
        """Check if email is directly addressed to user (not CC'd)"""
        headers = message.get('payload', {}).get('headers', [])
        
        to_header = None
        for header in headers:
            if header['name'].lower() == 'to':
                to_header = header['value'].lower()
                break
        
        if to_header and self.user_email.lower() in to_header:
            # Make sure not a mass email (multiple recipients)
            recipient_count = to_header.count('@')
            # Also require the message be unread or marked important
            labels = message.get('labelIds', [])
            if 'IMPORTANT' not in labels and 'UNREAD' not in labels:
                return False
            return recipient_count <= 2  # Allow user + maybe one other
        
        return False

    def _is_bulk_or_marketing(self, message):
        """Detect bulk/automated messages using common list headers."""
        headers = message.get('payload', {}).get('headers', [])
        header_map = {h['name'].lower(): h.get('value', '') for h in headers}
        
        # Common bulk/list indicators
        if header_map.get('list-id'):
            return True
        if header_map.get('list-unsubscribe'):
            return True
        precedence = header_map.get('precedence', '').lower()
        if precedence in {'bulk', 'list', 'junk'}:
            return True
        x_precedence = header_map.get('x-precedence', '').lower()
        if x_precedence in {'bulk', 'list', 'junk'}:
            return True
        auto_submitted = header_map.get('auto-submitted', '').lower()
        if auto_submitted and auto_submitted != 'no':
            return True
        return False
    
    def _mark_important(self, message_id):
        """Mark an email as important"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['IMPORTANT']}
            ).execute()
        except HttpError as error:
            logger.error(f"Error marking email as important: {error}")
    
    def _create_calendar_events(self, important_emails):
        """Create calendar reminders for important emails"""
        if not important_emails:
            return 0
        
        logger.info(f"Creating calendar events for {len(important_emails)} important emails...")
        events_created = 0
        
        for email in important_emails:
            try:
                # Extract subject
                headers = email.get('payload', {}).get('headers', [])
                subject = "Important Email"
                sender = "Unknown"
                
                for header in headers:
                    if header['name'].lower() == 'subject':
                        subject = header['value']
                    elif header['name'].lower() == 'from':
                        sender = header['value']
                
                # Create event for tomorrow at 9 AM
                tomorrow = datetime.now() + timedelta(days=1)
                event_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
                
                event = {
                    'summary': f'📧 Read: {subject[:50]}',
                    'description': f'Important email from: {sender}\n\nReminder to read this email.',
                    'start': {
                        'dateTime': event_time.isoformat(),
                        'timeZone': 'UTC',
                    },
                    'end': {
                        'dateTime': (event_time + timedelta(minutes=30)).isoformat(),
                        'timeZone': 'UTC',
                    },
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'popup', 'minutes': 10},
                        ],
                    },
                }
                
                if not self.dry_run:
                    self.calendar_service.events().insert(
                        calendarId='primary',
                        body=event
                    ).execute()
                    events_created += 1
                    logger.info(f"  Created event: {subject[:50]}")
                else:
                    logger.info(f"  [DRY RUN] Would create event: {subject[:50]}")
                    events_created += 1
                
            except Exception as error:
                logger.error(f"Error creating calendar event: {error}")
        
        return events_created
    
    def _delete_emails_by_query(self, query, description):
        """Generic function to delete emails matching a query with pagination"""
        deleted = 0
        skipped_failed_precondition = 0
        page_token = None
        total_found = 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            # First, get total count
            logger.info(f"  Searching for {description}...")
            
            while True:
                # Safety check
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                # Fetch up to 500 messages per page (Gmail API max)
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    break
                
                total_found += len(messages)
                logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                
                ids = []
                for msg in messages:
                    msg_id = msg['id']
                    
                    # Skip duplicates
                    if msg_id in processed_ids:
                        continue
                    processed_ids.add(msg_id)
                    ids.append(msg_id)
                
                for chunk in self._chunk_ids(ids, self.batch_size):
                    if not self.dry_run:
                        # Batch move to trash (safer than permanent delete)
                        try:
                            self.service.users().messages().batchModify(
                                userId='me',
                                body={
                                    'ids': chunk,
                                    'addLabelIds': ['TRASH'],
                                    'removeLabelIds': ['INBOX']
                                }
                            ).execute()
                            deleted += len(chunk)
                        except HttpError:
                            # Fallback to per-message to isolate failures
                            for msg_id in chunk:
                                try:
                                    self.service.users().messages().trash(
                                        userId='me',
                                        id=msg_id
                                    ).execute()
                                    deleted += 1
                                except HttpError as error:
                                    if 'failedPrecondition' in str(error):
                                        skipped_failed_precondition += 1
                                    logger.debug(f"  Skipping message {msg_id}: {error}")
                    else:
                        deleted += len(chunk)
                    
                    # Log progress every 100 messages
                    if deleted % 100 == 0:
                        logger.info(f"    Progress: {deleted} messages processed...")
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found")
            else:
                logger.info(f"  {'Deleted' if not self.dry_run else 'Would delete'} {deleted} {description}")
                if skipped_failed_precondition:
                    logger.info(f"  Skipped {skipped_failed_precondition} messages due to failed precondition")
            
        except HttpError as error:
            logger.error(f"Error deleting {description}: {error}")
        
        return deleted

    def _mark_read_by_query(self, query, description):
        """Mark emails as read matching a query with pagination"""
        modified = 0
        page_token = None
        total_found = 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            safe_query = f'({query}) -is:important -label:"Attention/Updates"'
            logger.info(f"  Searching for {description} to mark as read...")
            
            while True:
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                results = self.service.users().messages().list(
                    userId='me',
                    q=safe_query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                total_found += len(messages)
                logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                
                ids = []
                for msg in messages:
                    msg_id = msg['id']
                    if msg_id in processed_ids:
                        continue
                    processed_ids.add(msg_id)
                    ids.append(msg_id)
                
                for chunk in self._chunk_ids(ids, self.batch_size):
                    if not self.dry_run:
                        try:
                            self.service.users().messages().batchModify(
                                userId='me',
                                body={
                                    'ids': chunk,
                                    'removeLabelIds': ['UNREAD']
                                }
                            ).execute()
                            modified += len(chunk)
                        except HttpError:
                            for msg_id in chunk:
                                try:
                                    self.service.users().messages().modify(
                                        userId='me',
                                        id=msg_id,
                                        body={'removeLabelIds': ['UNREAD']}
                                    ).execute()
                                    modified += 1
                                except HttpError as error:
                                    logger.debug(f"  Skipping message {msg_id}: {error}")
                    else:
                        modified += len(chunk)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found to mark as read")
            else:
                logger.info(f"  {'Marked' if not self.dry_run else 'Would mark'} {modified} {description} as read")
        
        except HttpError as error:
            logger.error(f"Error marking {description} as read: {error}")
        
        return modified
    
    def _archive_emails_by_query(self, query, description, preserve_important_unread=True):
        """Generic function to archive emails matching a query with pagination"""
        if preserve_important_unread:
            important_query = f'({query}) (is:important OR label:"Attention/Updates")'
            non_important_query = f'({query}) -is:important -label:"Attention/Updates"'
            archived = 0
            archived += self._archive_emails_by_query_core(
                important_query,
                f"{description} (important/attention)",
                remove_unread=False
            )
            archived += self._archive_emails_by_query_core(
                non_important_query,
                f"{description} (non-important)",
                remove_unread=True
            )
            return archived
        
        return self._archive_emails_by_query_core(query, description, remove_unread=True)

    def _archive_emails_by_query_core(self, query, description, remove_unread=True):
        """Archive emails matching a query with pagination (internal)."""
        archived = 0
        page_token = None
        total_found = 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            logger.info(f"  Searching for {description}...")
            
            while True:
                # Safety check
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                # Fetch up to 500 messages per page
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    break
                
                total_found += len(messages)
                logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                
                ids = []
                for msg in messages:
                    msg_id = msg['id']
                    
                    # Skip duplicates
                    if msg_id in processed_ids:
                        continue
                    processed_ids.add(msg_id)
                    ids.append(msg_id)
                
                remove_labels = ['INBOX']
                if remove_unread:
                    remove_labels.append('UNREAD')
                
                for chunk in self._chunk_ids(ids, self.batch_size):
                    if not self.dry_run:
                        try:
                            # Batch remove INBOX label (archives the email)
                            self.service.users().messages().batchModify(
                                userId='me',
                                body={'ids': chunk, 'removeLabelIds': remove_labels}
                            ).execute()
                            archived += len(chunk)
                        except HttpError:
                            # Fallback to per-message to isolate failures
                            for msg_id in chunk:
                                try:
                                    self.service.users().messages().modify(
                                        userId='me',
                                        id=msg_id,
                                        body={'removeLabelIds': remove_labels}
                                    ).execute()
                                    archived += 1
                                except HttpError as error:
                                    logger.debug(f"  Skipping message {msg_id}: {error}")
                    else:
                        archived += len(chunk)
                    
                    # Log progress every 100 messages
                    if archived % 100 == 0:
                        logger.info(f"    Progress: {archived} messages processed...")
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found")
            else:
                logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} {description}")
            
        except HttpError as error:
            logger.error(f"Error archiving {description}: {error}")
        
        return archived

    def _resolve_label_ids(self, labels):
        """Resolve label names/IDs into label IDs."""
        if not labels:
            return []
        resolved = []
        for label in labels:
            if not label:
                continue
            # System labels like INBOX/TRASH can be used as IDs
            if label in {'INBOX', 'TRASH', 'SPAM', 'IMPORTANT', 'STARRED', 'SENT', 'DRAFT', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_SOCIAL', 'CATEGORY_FORUMS'}:
                resolved.append(label)
                continue
            # If label is already an ID in cache, keep it
            if label in self._label_cache.values():
                resolved.append(label)
                continue
            # Treat as name
            label_id = self._get_or_create_label(label)
            if label_id:
                resolved.append(label_id)
        return resolved

    def _modify_emails_by_query(self, query, description, add_label_ids=None, remove_label_ids=None):
        """Generic function to add/remove labels for emails matching a query with pagination"""
        modified = 0
        page_token = None
        total_found = 0
        
        add_ids = self._resolve_label_ids(add_label_ids)
        remove_ids = self._resolve_label_ids(remove_label_ids)
        
        # Nothing to do
        if not add_ids and not remove_ids:
            return 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            logger.info(f"  Searching for {description}...")
            
            while True:
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                total_found += len(messages)
                logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                
                ids = []
                for msg in messages:
                    msg_id = msg['id']
                    if msg_id in processed_ids:
                        continue
                    processed_ids.add(msg_id)
                    ids.append(msg_id)
                
                for chunk in self._chunk_ids(ids, self.batch_size):
                    if not self.dry_run:
                        try:
                            self.service.users().messages().batchModify(
                                userId='me',
                                body={
                                    'ids': chunk,
                                    'addLabelIds': add_ids,
                                    'removeLabelIds': remove_ids
                                }
                            ).execute()
                            modified += len(chunk)
                        except HttpError:
                            # Fallback to per-message
                            for msg_id in chunk:
                                try:
                                    self.service.users().messages().modify(
                                        userId='me',
                                        id=msg_id,
                                        body={
                                            'addLabelIds': add_ids,
                                            'removeLabelIds': remove_ids
                                        }
                                    ).execute()
                                    modified += 1
                                except HttpError as error:
                                    logger.debug(f"  Skipping message {msg_id}: {error}")
                    else:
                        modified += len(chunk)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found")
            else:
                logger.info(f"  {'Modified' if not self.dry_run else 'Would modify'} {modified} {description}")
        
        except HttpError as error:
            logger.error(f"Error modifying {description}: {error}")
        
        return modified
