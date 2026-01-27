"""
Outlook Handler
Handles authentication and email processing for Outlook/Microsoft 365 accounts
"""

import os
import json
import logging
import html
import re
from datetime import datetime, timedelta
import msal
import requests

logger = logging.getLogger(__name__)

# Microsoft Graph API endpoints
GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'

# Required scopes (permissions)
SCOPES = [
    'Mail.ReadWrite',      # Read and write email
    'Calendars.ReadWrite', # Create calendar events
    'User.Read'            # Read basic profile (needed for /me)
]


class OutlookHandler:
    """Handles all Outlook/Microsoft 365 operations"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.access_token = None
        self.user_email = None
        self.app = None
        self.archive_folder_id = None
        # Microsoft Graph $batch limit is 20 requests per batch
        self.batch_size = 20
        
    def authenticate(self):
        """
        Authenticate with Microsoft Graph API using OAuth 2.0
        
        AUTHENTICATION FLOW:
        1. Check for cached token
        2. If token exists and valid, use it
        3. If no token or expired, start OAuth flow
        
        Setup required:
        1. Go to Azure Portal (portal.azure.com)
        2. Register an application in Azure AD
        3. Add 'Mobile and desktop applications' platform
        4. Set redirect URI to: http://localhost
        5. Add API permissions: Mail.ReadWrite, Calendars.ReadWrite
        6. Create outlook_credentials.json with:
           {
               "client_id": "your-client-id",
               "authority": "https://login.microsoftonline.com/common"
           }
        """
        
        # Load credentials
        if not os.path.exists('outlook_credentials.json'):
            raise FileNotFoundError(
                "outlook_credentials.json not found. "
                "Create this file with your Azure AD app credentials."
            )
        
        with open('outlook_credentials.json', 'r') as f:
            config = json.load(f)
        
        # Create persistent token cache
        token_cache_file = 'outlook_token_cache.json'
        cache = msal.SerializableTokenCache()
        
        # Load existing cache if available
        if os.path.exists(token_cache_file):
            with open(token_cache_file, 'r') as cache_file:
                cache.deserialize(cache_file.read())
        
        # Create MSAL application with persistent cache
        self.app = msal.PublicClientApplication(
            config['client_id'],
            authority=config.get('authority', 'https://login.microsoftonline.com/common'),
            token_cache=cache
        )
        
        # Check cache for existing token
        accounts = self.app.get_accounts()
        result = None
        
        if accounts:
            # Try to get token silently
            logger.info("Attempting silent token acquisition...")
            result = self.app.acquire_token_silent(SCOPES, account=accounts[0])
        
        if not result:
            # Need interactive login
            logger.info("Starting interactive Outlook authentication...")
            result = self.app.acquire_token_interactive(
                scopes=SCOPES,
                parent_window_handle=None  # Will open browser
            )
        
        if "access_token" in result:
            self.access_token = result['access_token']
            logger.info("Outlook authentication successful")
            
            # Save token cache to disk for persistence
            token_cache_file = 'outlook_token_cache.json'
            if self.app.token_cache.has_state_changed:
                with open(token_cache_file, 'w') as cache_file:
                    cache_file.write(self.app.token_cache.serialize())
                logger.info(f"Token cache saved to {token_cache_file}")
            
            # Get user info
            self._get_user_info()
        else:
            error = result.get("error")
            error_desc = result.get("error_description")
            raise Exception(f"Authentication failed: {error} - {error_desc}")
    
    def _get_user_info(self):
        """Get authenticated user's information"""
        headers = {'Authorization': f'Bearer {self.access_token}'}
        response = requests.get(f'{GRAPH_API_ENDPOINT}/me', headers=headers)
        
        if response.status_code == 200:
            user_data = self._safe_json(response, "get user info")
            if not user_data:
                return
            self.user_email = user_data.get('mail') or user_data.get('userPrincipalName')
            logger.info(f"Authenticated as: {self.user_email}")
        else:
            logger.error(f"Failed to get user info: {response.status_code}")

    def _safe_json(self, response, context):
        """Parse JSON safely and log useful diagnostics on failure."""
        try:
            return response.json()
        except ValueError as error:
            text = response.text or ""
            snippet = text[:500].replace("\n", " ")
            logger.error(
                f"Invalid JSON from {context}: {error}; status={response.status_code}; "
                f"body_len={len(text)}; body_snippet={snippet}"
            )
            return None

    def _chunk_ids(self, ids, size):
        """Yield chunks of IDs for batch operations."""
        for i in range(0, len(ids), size):
            yield ids[i:i + size]

    def _batch_request(self, requests_payload):
        """Send a Graph $batch request and return responses list or None on failure."""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        response = requests.post(
            f'{GRAPH_API_ENDPOINT}/$batch',
            headers=headers,
            json={'requests': requests_payload}
        )
        if response.status_code != 200:
            logger.debug(f"Batch request failed: {response.status_code}")
            return None
        data = self._safe_json(response, "batch request")
        if not data:
            return None
        return data.get('responses', [])

    def _batch_delete_message_ids(self, ids):
        """Batch delete messages (moves to Deleted Items). Returns count deleted."""
        deleted = 0
        for chunk in self._chunk_ids(ids, self.batch_size):
            if not chunk:
                continue
            requests_payload = []
            for i, msg_id in enumerate(chunk):
                requests_payload.append({
                    'id': str(i),
                    'method': 'DELETE',
                    'url': f'/me/messages/{msg_id}'
                })
            responses = self._batch_request(requests_payload)
            if responses is None:
                # Fallback to per-message
                for msg_id in chunk:
                    resp = requests.delete(
                        f"{GRAPH_API_ENDPOINT}/me/messages/{msg_id}",
                        headers={'Authorization': f'Bearer {self.access_token}'}
                    )
                    if resp.status_code == 204:
                        deleted += 1
                continue
            # Count successes
            for resp in responses:
                if resp.get('status') == 204:
                    deleted += 1
                else:
                    logger.debug(f"Batch delete failed for request {resp.get('id')}: {resp.get('status')}")
        return deleted

    def _batch_move_message_ids(self, ids, destination_id):
        """Batch move messages to a folder. Returns count moved."""
        moved = 0
        for chunk in self._chunk_ids(ids, self.batch_size):
            if not chunk:
                continue
            requests_payload = []
            for i, msg_id in enumerate(chunk):
                requests_payload.append({
                    'id': str(i),
                    'method': 'POST',
                    'url': f'/me/messages/{msg_id}/move',
                    'headers': {'Content-Type': 'application/json'},
                    'body': {'destinationId': destination_id}
                })
            responses = self._batch_request(requests_payload)
            if responses is None:
                # Fallback to per-message
                for msg_id in chunk:
                    resp = requests.post(
                        f"{GRAPH_API_ENDPOINT}/me/messages/{msg_id}/move",
                        headers={
                            'Authorization': f'Bearer {self.access_token}',
                            'Content-Type': 'application/json'
                        },
                        json={'destinationId': destination_id}
                    )
                    if resp.status_code == 201:
                        moved += 1
                continue
            for resp in responses:
                if resp.get('status') == 201:
                    moved += 1
                else:
                    logger.debug(f"Batch move failed for request {resp.get('id')}: {resp.get('status')}")
        return moved

    def _batch_set_categories(self, id_to_categories):
        """Batch set categories for messages. Returns count updated."""
        updated = 0
        items = list(id_to_categories.items())
        for chunk in self._chunk_ids(items, self.batch_size):
            requests_payload = []
            for i, (msg_id, categories) in enumerate(chunk):
                requests_payload.append({
                    'id': str(i),
                    'method': 'PATCH',
                    'url': f'/me/messages/{msg_id}',
                    'headers': {'Content-Type': 'application/json'},
                    'body': {'categories': categories}
                })
            responses = self._batch_request(requests_payload)
            if responses is None:
                # Fallback to per-message
                for msg_id, categories in chunk:
                    resp = requests.patch(
                        f"{GRAPH_API_ENDPOINT}/me/messages/{msg_id}",
                        headers={
                            'Authorization': f'Bearer {self.access_token}',
                            'Content-Type': 'application/json'
                        },
                        json={'categories': categories}
                    )
                    if resp.status_code == 200:
                        updated += 1
                continue
            for resp in responses:
                if resp.get('status') == 200:
                    updated += 1
                else:
                    logger.debug(f"Batch category update failed for request {resp.get('id')}: {resp.get('status')}")
        return updated

    def _batch_mark_read_message_ids(self, ids):
        """Batch mark messages as read. Returns count updated."""
        updated = 0
        for chunk in self._chunk_ids(ids, self.batch_size):
            if not chunk:
                continue
            requests_payload = []
            for i, msg_id in enumerate(chunk):
                requests_payload.append({
                    'id': str(i),
                    'method': 'PATCH',
                    'url': f'/me/messages/{msg_id}',
                    'headers': {'Content-Type': 'application/json'},
                    'body': {'isRead': True}
                })
            responses = self._batch_request(requests_payload)
            if responses is None:
                for msg_id in chunk:
                    resp = requests.patch(
                        f"{GRAPH_API_ENDPOINT}/me/messages/{msg_id}",
                        headers={
                            'Authorization': f'Bearer {self.access_token}',
                            'Content-Type': 'application/json'
                        },
                        json={'isRead': True}
                    )
                    if resp.status_code == 200:
                        updated += 1
                continue
            for resp in responses:
                if resp.get('status') == 200:
                    updated += 1
                else:
                    logger.debug(f"Batch mark read failed for request {resp.get('id')}: {resp.get('status')}")
        return updated

    def _normalize_text(self, text):
        """Normalize text for matching (strip HTML, collapse whitespace, lowercase)."""
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()

    def _fetch_message(self, message_id, select_fields=None):
        """Fetch a single message by ID with optional select fields."""
        headers = {'Authorization': f'Bearer {self.access_token}'}
        params = {}
        if select_fields:
            params['$select'] = select_fields
        response = requests.get(
            f'{GRAPH_API_ENDPOINT}/me/messages/{message_id}',
            headers=headers,
            params=params or None
        )
        if response.status_code == 200:
            return self._safe_json(response, f"fetch message {message_id}")
        logger.error(f"Failed to fetch message {message_id}: {response.status_code}")
        return None

    def _message_matches_phrases(self, message, phrases):
        """Check if any phrase appears in subject or body."""
        subject = message.get('subject', '')
        body = message.get('body', {}).get('content', '')
        haystack = self._normalize_text(f"{subject} {body}")
        return any(phrase in haystack for phrase in phrases)

    def _collect_messages_by_search(self, phrases, select_fields=None):
        """
        Use Graph $search to collect candidate messages that match phrases
        in subject or body. Returns a list or None on failure.
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'ConsistencyLevel': 'eventual'
        }
        collected = {}

        for phrase in phrases:
            params = {
                '$search': f'"{phrase}"',
                '$top': 100
            }
            if select_fields:
                params['$select'] = select_fields

            next_link = None
            while True:
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    response = requests.get(
                        f'{GRAPH_API_ENDPOINT}/me/messages',
                        headers=headers,
                        params=params
                    )

                if response.status_code != 200:
                    logger.warning(f"Search failed for phrase '{phrase}': {response.status_code}")
                    return None
                
                data = self._safe_json(response, f"search messages for phrase '{phrase}'")
                if not data:
                    return None
                for msg in data.get('value', []):
                    collected[msg['id']] = msg

                next_link = data.get('@odata.nextLink')
                if not next_link:
                    break

        return list(collected.values())

    def _get_archive_folder_id(self):
        """Resolve the real Archive folder ID (Graph requires ID, not name)."""
        if self.archive_folder_id:
            return self.archive_folder_id
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # Try well-known folder name first
        response = requests.get(f'{GRAPH_API_ENDPOINT}/me/mailFolders/Archive', headers=headers)
        if response.status_code == 200:
            data = response.json()
            self.archive_folder_id = data.get('id')
            return self.archive_folder_id
        
        # Fallback: find by displayName
        response = requests.get(f'{GRAPH_API_ENDPOINT}/me/mailFolders', headers=headers)
        if response.status_code == 200:
            data = response.json()
            for folder in data.get('value', []):
                if folder.get('displayName', '').lower() == 'archive':
                    self.archive_folder_id = folder.get('id')
                    return self.archive_folder_id
        
        logger.warning("Could not resolve Archive folder ID; falling back to 'archive'")
        return 'archive'
    
    def process_emails(self):
        """Main processing function for all email operations"""
        stats = {
            'promotions_deleted': 0,
            'job_alerts_deleted': 0,
            'social_media_deleted': 0,
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
        
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Outlook doesn't have Gmail's category system, so we use keyword matching
        # Common promotional sender patterns
        promo_keywords = [
            'noreply',
            'newsletter',
            'marketing',
            'promotions',
            'offers',
            'unsubscribe'
        ]
        
        deleted = 0
        
        for keyword in promo_keywords:
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and (from/emailAddress/address eq '{keyword}' or "
                f"contains(from/emailAddress/address, '{keyword}'))"
            )
            deleted += self._delete_emails_by_filter(filter_query, f"promotions ({keyword})")
        
        return deleted
    
    def _delete_old_job_alerts(self):
        """Delete job alert emails older than 14 days (2 weeks)"""
        logger.info("Searching for old job alerts...")
        
        cutoff_date = datetime.now() - timedelta(days=14)
        
        # Job alert sender domains and keywords
        job_sources = [
            'linkedin.com',
            'indeed.com',
            'glassdoor.com',
            'monster.com',
            'careerbuilder.com',
            'ziprecruiter.com',
            'simplyhired.com',
            'dice.com'
        ]
        
        job_keywords = [
            'job alert',
            'career opportunity',
            'new jobs',
            'job recommendations',
            'recommended jobs',
            'jobs you may like',
            'job matches',
            'new opportunity',
            'new opportunities'
        ]
        
        deleted = 0
        
        # Search by sender domain
        for source in job_sources:
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and contains(from/emailAddress/address, '{source}')"
            )
            deleted += self._delete_emails_by_filter(filter_query, f"job alerts from {source}")
        
        # Search by subject keywords
        for keyword in job_keywords:
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and contains(subject, '{keyword}')"
            )
            deleted += self._delete_emails_by_filter(filter_query, f"job alerts: {keyword}")
        
        return deleted
    
    def _delete_old_social_media(self):
        """Delete social media notification emails older than 14 days (2 weeks)"""
        logger.info("Searching for old social media notifications...")
        
        cutoff_date = datetime.now() - timedelta(days=14)
        
        # Social media platforms
        social_platforms = [
            'facebookmail.com',
            'facebook.com',
            'twitter.com',
            'x.com',
            'instagram.com',
            'mail.instagram.com',
            'tiktok.com',
            'reddit.com',
            'pinterest.com',
            'snapchat.com',
        ]
        
        deleted = 0
        
        # Search by sender domain
        for platform in social_platforms:
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and contains(from/emailAddress/address, '{platform}')"
            )
            deleted += self._delete_emails_by_filter(filter_query, f"social media from {platform}")
        
        # LinkedIn social notifications (exclude job-related)
        # LinkedIn job alerts are handled in job_alerts category
        filter_query = (
            f"receivedDateTime lt {cutoff_date.isoformat()}Z "
            f"and contains(from/emailAddress/address, 'linkedin.com') "
            f"and not(contains(subject, 'job')) "
            f"and not(contains(subject, 'career')) "
            f"and not(contains(subject, 'opportunity'))"
        )
        deleted += self._delete_emails_by_filter(filter_query, "LinkedIn social notifications")
        
        return deleted
    
    def _archive_rejections(self):
        """Archive job rejection emails"""
        logger.info("Searching for rejection emails...")
        
        rejection_phrases = [
            'regret to inform',
            'not moving forward',
            'not move forward',
            'other candidates',
            'other candidate',
            'not been successful',
            'not successful',
            'position has been filled',
            'position is filled',
            'after careful consideration',
            'decided to move forward with other',
            'decided to pursue other',
            'we will not be moving forward',
            'we are unable to move forward',
            'not selected',
            'declined to move forward',
            'we have chosen another',
            'no longer under consideration'
        ]
        
        archived = 0
        phrases = [p.lower() for p in rejection_phrases]
        
        # Use Graph $search to match subject/body for better quality
        candidates = self._collect_messages_by_search(
            phrases,
            select_fields='id,subject,from,receivedDateTime'
        )
        
        if candidates is None:
            logger.warning("Falling back to subject-only filtering for rejections")
            for phrase in phrases:
                filter_query = f"contains(subject, '{phrase}')"
                archived += self._archive_emails_by_filter(filter_query, f"rejections: {phrase}")
            return archived
        
        ids_to_move = []
        ids_to_mark_read = []
        for msg in candidates:
            msg_id = msg['id']
            full_msg = self._fetch_message(msg_id, select_fields='id,subject,from,receivedDateTime,body,importance')
            if not full_msg:
                continue
            if self._message_matches_phrases(full_msg, phrases):
                ids_to_move.append(msg_id)
                if (full_msg.get('importance') or '').lower() != 'high':
                    ids_to_mark_read.append(msg_id)
        
        if not self.dry_run:
            self._batch_mark_read_message_ids(ids_to_mark_read)
            archive_id = self._get_archive_folder_id()
            archived += self._batch_move_message_ids(ids_to_move, archive_id)
        else:
            archived += len(ids_to_move)
        
        logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} rejection emails")
        return archived
    
    def _archive_application_acknowledgements(self):
        """
        Archive application acknowledgement emails after 7 days
        Step 1 of 2-step process: Archive (move to archive folder, keep searchable)
        Only targets automated noreply emails, NOT emails from real people
        """
        logger.info("Searching for application acknowledgements to archive (7+ days old)...")
        
        cutoff_date = datetime.now() - timedelta(days=7)
        
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
        
        # Noreply/automated email patterns
        noreply_patterns = [
            'noreply',
            'no-reply',
            'donotreply',
            'do-not-reply',
            'notifications@',
            'automated@',
            'system@',
            'bot@'
        ]
        
        phrases = [p.lower() for p in ack_phrases]
        sender_patterns = [p.lower() for p in noreply_patterns]
        
        # Use Graph $search to match subject/body, then filter by sender + date
        candidates = self._collect_messages_by_search(
            phrases,
            select_fields='id,subject,from,receivedDateTime'
        )
        
        if candidates is None:
            logger.warning("Falling back to subject-only filtering for application acknowledgements")
            phrase_conditions = ' or '.join([
                f"contains(subject, '{phrase}')"
                for phrase in phrases
            ])
            sender_conditions = ' or '.join([
                f"contains(from/emailAddress/address, '{pattern}')"
                for pattern in sender_patterns
            ])
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and ({phrase_conditions}) "
                f"and ({sender_conditions})"
            )
            archived = self._archive_emails_by_filter(
                filter_query,
                "automated app acks (combined query)"
            )
            return archived
        
        archived = 0
        ids_to_move = []
        ids_to_mark_read = []
        for msg in candidates:
            msg_id = msg['id']
            full_msg = self._fetch_message(msg_id, select_fields='id,subject,from,receivedDateTime,body,importance')
            if not full_msg:
                continue
            
            from_addr = full_msg.get('from', {}).get('emailAddress', {}).get('address', '').lower()
            received_str = full_msg.get('receivedDateTime', '')
            try:
                received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                continue
            
            if received_date >= cutoff_date:
                continue
            if not any(pat in from_addr for pat in sender_patterns):
                continue
            if not self._message_matches_phrases(full_msg, phrases):
                continue
            ids_to_move.append(msg_id)
            if (full_msg.get('importance') or '').lower() != 'high':
                ids_to_mark_read.append(msg_id)
        
        if not self.dry_run:
            self._batch_mark_read_message_ids(ids_to_mark_read)
            archive_id = self._get_archive_folder_id()
            archived += self._batch_move_message_ids(ids_to_move, archive_id)
        else:
            archived += len(ids_to_move)
        
        logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} automated application acknowledgements (7+ days)")
        return archived
    
    def _delete_old_application_acknowledgements(self):
        """
        Delete application acknowledgement emails after 30 days
        Step 2 of 2-step process: Delete old acknowledgements from archive
        Only targets automated noreply emails, NOT emails from real people
        Note: In Outlook, we delete directly since there's no easy way to filter by folder
        """
        logger.info("Searching for old application acknowledgements to delete (30+ days old)...")
        
        cutoff_date = datetime.now() - timedelta(days=30)
        
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
        
        # Noreply/automated email patterns
        noreply_patterns = [
            'noreply',
            'no-reply',
            'donotreply',
            'do-not-reply',
            'notifications@',
            'automated@',
            'system@',
            'bot@'
        ]
        
        phrases = [p.lower() for p in ack_phrases]
        sender_patterns = [p.lower() for p in noreply_patterns]
        
        # Use Graph $search to match subject/body, then filter by sender + date
        candidates = self._collect_messages_by_search(
            phrases,
            select_fields='id,subject,from,receivedDateTime'
        )
        
        if candidates is None:
            logger.warning("Falling back to subject-only filtering for old application acknowledgements")
            phrase_conditions = ' or '.join([
                f"contains(subject, '{phrase}')"
                for phrase in phrases
            ])
            sender_conditions = ' or '.join([
                f"contains(from/emailAddress/address, '{pattern}')"
                for pattern in sender_patterns
            ])
            filter_query = (
                f"receivedDateTime lt {cutoff_date.isoformat()}Z "
                f"and ({phrase_conditions}) "
                f"and ({sender_conditions})"
            )
            deleted = self._delete_emails_by_filter(
                filter_query,
                "old automated app acks (combined query)"
            )
            return deleted
        
        deleted = 0
        ids_to_delete = []
        ids_to_mark_read = []
        for msg in candidates:
            msg_id = msg['id']
            full_msg = self._fetch_message(msg_id, select_fields='id,subject,from,receivedDateTime,body,importance')
            if not full_msg:
                continue
            
            from_addr = full_msg.get('from', {}).get('emailAddress', {}).get('address', '').lower()
            received_str = full_msg.get('receivedDateTime', '')
            try:
                received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                continue
            
            if received_date >= cutoff_date:
                continue
            if not any(pat in from_addr for pat in sender_patterns):
                continue
            if not self._message_matches_phrases(full_msg, phrases):
                continue
            ids_to_delete.append(msg_id)
            if (full_msg.get('importance') or '').lower() != 'high':
                ids_to_mark_read.append(msg_id)
        
        if not self.dry_run:
            self._batch_mark_read_message_ids(ids_to_mark_read)
            deleted += self._batch_delete_message_ids(ids_to_delete)
        else:
            deleted += len(ids_to_delete)
        
        logger.info(f"  {'Deleted' if not self.dry_run else 'Would delete'} {deleted} automated application acknowledgements (30+ days)")
        return deleted
    
    def _archive_stale_inbox(self):
        """
        Archive emails that have been in inbox for 4+ months
        Organizes by category (Work, Personal, Finance, etc.) with Recent/Old subfolders
        Recent: 4-18 months old
        Old: 18+ months old
        Note: Outlook API makes folder creation complex, so we use simpler Archive folder with categories as secondary approach
        """
        logger.info("Searching for stale inbox items (4+ months old)...")
        
        cutoff_date = datetime.now() - timedelta(days=120)  # 4 months = ~120 days
        old_threshold = datetime.now() - timedelta(days=540)  # 18 months = ~540 days
        
        # Filter: older than 4 months
        filter_query = f"receivedDateTime lt {cutoff_date.isoformat()}Z"
        
        archived = 0
        next_link = None
        total_found = 0
        category_counts = {}
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000  # Max 1000 batches = 100,000 emails
        iteration_count = 0
        processed_ids = set()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            url = f'{GRAPH_API_ENDPOINT}/me/messages'
            
            while True:
                # Safety check
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations ({max_iterations * 100} emails max)")
                    logger.error("Stopping to prevent infinite loop. Your inbox may have more emails to process.")
                    break
                
                # Use nextLink if available, otherwise construct initial request
                if next_link:
                    response = requests.get(next_link, headers={'Authorization': f'Bearer {self.access_token}'})
                else:
                    params = {
                        '$filter': filter_query,
                        '$top': 100,  # Max per page for Outlook
                        '$select': 'id,from,subject,receivedDateTime,importance'
                    }
                    response = requests.get(url, headers={'Authorization': f'Bearer {self.access_token}'}, params=params)
                
                if response.status_code == 200:
                    data = self._safe_json(response, f"stale inbox list page {iteration_count}")
                    if not data:
                        break
                    messages = data.get('value', [])
                    
                    if not messages:
                        break
                    
                    total_found += len(messages)
                    logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                    
                    ids = []
                    ids_mark_read = []
                    id_to_categories = {}
                    for msg in messages:
                        msg_id = msg['id']
                        
                        # Safety: Skip duplicates
                        if msg_id in processed_ids:
                            logger.warning(f"Skipping duplicate message ID: {msg_id}")
                            continue
                        processed_ids.add(msg_id)
                        
                        # Categorize the email
                        category = self._categorize_email_outlook(msg)
                        
                        # Determine if Recent or Old
                        received_str = msg.get('receivedDateTime', '')
                        try:
                            received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00'))
                            age_subfolder = "Old" if received_date < old_threshold else "Recent"
                        except:
                            age_subfolder = "Recent"
                        
                        ids.append(msg_id)
                        if (msg.get('importance') or '').lower() != 'high':
                            ids_mark_read.append(msg_id)
                        id_to_categories[msg_id] = [f"{category}-{age_subfolder}"]
                        
                        # Track category counts
                        full_category = f"{category}/{age_subfolder}"
                        category_counts[full_category] = category_counts.get(full_category, 0) + 1
                        
                    if not self.dry_run:
                        self._batch_mark_read_message_ids(ids_mark_read)
                        archive_id = self._get_archive_folder_id()
                        archived += self._batch_move_message_ids(ids, archive_id)
                        self._batch_set_categories(id_to_categories)
                    else:
                        archived += len(ids)
                    
                    # Log progress every 100 messages with category breakdown
                    if archived % 100 == 0:
                        logger.info(f"    Progress: {archived} messages processed...")
                        # Show current category distribution
                        logger.info(f"    Current category breakdown:")
                        for cat, count in sorted(category_counts.items()):
                            logger.info(f"      {cat}: {count}")
                    
                    # Check for next page
                    next_link = data.get('@odata.nextLink')
                    if not next_link:
                        break
                else:
                    logger.error(f"Error fetching stale inbox items: {response.status_code}")
                    break
            
            if total_found == 0:
                logger.info(f"  No stale inbox items found")
            else:
                logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} stale inbox items to Archive folder")
                logger.info(f"  Category breakdown:")
                for cat, count in sorted(category_counts.items()):
                    logger.info(f"    {cat}: {count}")
                
        except Exception as error:
            logger.error(f"Error archiving stale inbox: {error}")
        
        return archived
    
    def _categorize_email_outlook(self, message):
        """
        Categorize an Outlook email into: Work, Personal, Finance, Shopping, Travel, Healthcare, Utilities, Education, or Other
        """
        from_email = (message.get('from', {}).get('emailAddress', {}).get('address') or '').lower()
        subject = (message.get('subject') or '').lower()
        
        # Extract domain
        domain = ""
        if '@' in from_email:
            domain = from_email.split('@')[-1]
        
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
    
    def _set_outlook_category(self, message_id, category_name):
        """
        Set an Outlook category on a message
        This adds a colored category tag for organization within Archive folder
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            url = f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}"
            body = {
                'categories': [category_name]
            }
            
            response = requests.patch(url, headers=headers, json=body)
            # Don't log success/failure for each category - too verbose
            
        except Exception as error:
            # Silently fail - categories are nice-to-have, not critical
            pass
    
    def _find_important_emails(self):
        """
        Find important emails directly addressed to the user
        
        Criteria:
        - Received in last 7 days
        - Directly addressed to user (in To field)
        - Not from no-reply addresses
        - Not bulk/list mail
        - Importance is high OR unread
        """
        logger.info("Searching for important emails...")
        
        # Safety: Skip if user_email not available (403 on /me endpoint)
        if not self.user_email:
            logger.warning("Skipping important emails - user email not available (missing User.Read permission?)")
            return []
        
        cutoff_date = datetime.now() - timedelta(days=7)
        
        # Filter for potentially important emails
        filter_query = (
            f"receivedDateTime gt {cutoff_date.isoformat()}Z "
            f"and isRead eq false "
            f"and not(contains(from/emailAddress/address, 'noreply')) "
            f"and not(contains(from/emailAddress/address, 'no-reply'))"
        )
        
        important_emails = []
        next_link = None
        
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            # Limit to Inbox to reduce noise
            url = f'{GRAPH_API_ENDPOINT}/me/mailFolders/Inbox/messages'
            
            while len(important_emails) < 50:  # Limit to 50 important emails for calendar events
                # Use nextLink if available, otherwise construct initial request
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    params = {
                        '$filter': filter_query,
                        '$top': 100,
                        '$select': 'id,subject,from,toRecipients,importance,receivedDateTime,isRead,inferenceClassification,internetMessageHeaders'
                    }
                    response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = self._safe_json(response, f"delete list for {description}")
                    if not data:
                        break
                    messages = data.get('value', [])
                    
                    if not messages:
                        break
                    
                    for msg in messages:
                        if len(important_emails) >= 100:
                            break
                        
                        # Check if directly addressed and not bulk/list mail
                        if self._is_directly_addressed(msg) and not self._is_bulk_or_marketing_outlook(msg):
                            # Require high importance OR unread (filter already prefers unread)
                            if msg.get('importance', '').lower() == 'low':
                                continue
                            important_emails.append(msg)
                            
                            # Mark as important if not already
                            if not self.dry_run:
                                self._mark_important(msg['id'])
                    
                    # Check for next page
                    next_link = data.get('@odata.nextLink')
                    if not next_link:
                        break
                else:
                    logger.error(f"Error fetching emails: {response.status_code}")
                    break
                
            logger.info(f"Found {len(important_emails)} important emails")
                
        except Exception as error:
            logger.error(f"Error finding important emails: {error}")
        
        return important_emails
    
    def _is_directly_addressed(self, message):
        """Check if email is directly addressed to user"""
        # Safety: Skip if user_email not set (403 on user info)
        if not self.user_email:
            return False
        
        to_recipients = message.get('toRecipients', [])
        
        # Check if user is in To field and there aren't too many recipients
        for recipient in to_recipients:
            if recipient.get('emailAddress', {}).get('address', '').lower() == self.user_email.lower():
                # Limit to emails with few recipients (not mass emails)
                return len(to_recipients) <= 2
        
        return False

    def _is_bulk_or_marketing_outlook(self, message):
        """Detect bulk/automated messages via headers and inference classification."""
        # Skip "Other" if focused inbox is enabled
        if message.get('inferenceClassification', '').lower() == 'other':
            return True
        
        headers = message.get('internetMessageHeaders', []) or []
        header_map = {h.get('name', '').lower(): h.get('value', '') for h in headers}
        
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
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            url = f'{GRAPH_API_ENDPOINT}/me/messages/{message_id}'
            body = {'importance': 'high'}
            
            response = requests.patch(url, headers=headers, json=body)
            
            if response.status_code != 200:
                logger.error(f"Error marking email as important: {response.status_code}")
                
        except Exception as error:
            logger.error(f"Error marking email as important: {error}")
    
    def _create_calendar_events(self, important_emails):
        """Create calendar reminders for important emails"""
        if not important_emails:
            return 0
        
        logger.info(f"Creating calendar events for {len(important_emails)} important emails...")
        events_created = 0
        
        for email in important_emails:
            try:
                subject = email.get('subject', 'Important Email')
                sender = email.get('from', {}).get('emailAddress', {}).get('name', 'Unknown')
                
                # Create event for tomorrow at 9 AM
                tomorrow = datetime.now() + timedelta(days=1)
                event_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
                end_time = event_time + timedelta(minutes=30)
                
                event = {
                    'subject': f'📧 Read: {subject[:50]}',
                    'body': {
                        'contentType': 'text',
                        'content': f'Important email from: {sender}\n\nReminder to read this email.'
                    },
                    'start': {
                        'dateTime': event_time.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'end': {
                        'dateTime': end_time.isoformat(),
                        'timeZone': 'UTC'
                    },
                    'reminderMinutesBeforeStart': 10
                }
                
                if not self.dry_run:
                    headers = {
                        'Authorization': f'Bearer {self.access_token}',
                        'Content-Type': 'application/json'
                    }
                    url = f'{GRAPH_API_ENDPOINT}/me/calendar/events'
                    
                    response = requests.post(url, headers=headers, json=event)
                    
                    if response.status_code == 201:
                        events_created += 1
                        logger.info(f"  Created event: {subject[:50]}")
                    else:
                        logger.error(f"  Error creating event: {response.status_code}")
                else:
                    logger.info(f"  [DRY RUN] Would create event: {subject[:50]}")
                    events_created += 1
                    
            except Exception as error:
                logger.error(f"Error creating calendar event: {error}")
        
        return events_created
    
    def _delete_emails_by_filter(self, filter_query, description):
        """Generic function to delete emails matching a filter with pagination"""
        deleted = 0
        next_link = None
        total_found = 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f'{GRAPH_API_ENDPOINT}/me/messages'
            
            while True:
                # Safety check
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                # Use nextLink if available, otherwise construct initial request
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    params = {
                        '$filter': filter_query,
                        '$top': 100,  # Max per page for Outlook
                        '$select': 'id,importance'
                    }
                    response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = self._safe_json(response, f"archive list for {description}")
                    if not data:
                        break
                    messages = data.get('value', [])
                    
                    if not messages:
                        break
                    
                    total_found += len(messages)
                    logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                    
                    ids = []
                    ids_mark_read = []
                    for msg in messages:
                        msg_id = msg['id']
                        
                        # Skip duplicates
                        if msg_id in processed_ids:
                            continue
                        processed_ids.add(msg_id)
                        ids.append(msg_id)
                        if (msg.get('importance') or '').lower() != 'high':
                            ids_mark_read.append(msg_id)
                    
                    if not self.dry_run:
                        # Mark read before delete (skip important)
                        self._batch_mark_read_message_ids(ids_mark_read)
                        deleted += self._batch_delete_message_ids(ids)
                    else:
                        deleted += len(ids)
                    
                    # Log progress every 100 messages
                    if deleted % 100 == 0:
                        logger.info(f"    Progress: {deleted} messages processed...")
                    
                    # Check for next page
                    next_link = data.get('@odata.nextLink')
                    if not next_link:
                        break
                else:
                    logger.error(f"Error fetching {description}: {response.status_code}")
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found")
            else:
                logger.info(f"  {'Deleted' if not self.dry_run else 'Would delete'} {deleted} {description}")
                
        except Exception as error:
            logger.error(f"Error deleting {description}: {error}")
        
        return deleted
    
    def _archive_emails_by_filter(self, filter_query, description):
        """Generic function to archive emails matching a filter with pagination"""
        archived = 0
        next_link = None
        total_found = 0
        
        # Safety: Iteration counter and duplicate tracking
        max_iterations = 1000
        iteration_count = 0
        processed_ids = set()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            url = f'{GRAPH_API_ENDPOINT}/me/messages'
            
            while True:
                # Safety check
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.error(f"Safety limit reached: {max_iterations} iterations")
                    break
                
                # Use nextLink if available, otherwise construct initial request
                if next_link:
                    response = requests.get(next_link, headers={'Authorization': f'Bearer {self.access_token}'})
                else:
                    params = {
                        '$filter': filter_query,
                        '$top': 100,  # Max per page for Outlook
                        '$select': 'id,importance'
                    }
                    response = requests.get(url, headers={'Authorization': f'Bearer {self.access_token}'}, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get('value', [])
                    
                    if not messages:
                        break
                    
                    total_found += len(messages)
                    logger.info(f"  Processing batch of {len(messages)} messages (total found so far: {total_found})...")
                    
                    ids = []
                    ids_mark_read = []
                    for msg in messages:
                        msg_id = msg['id']
                        
                        # Skip duplicates
                        if msg_id in processed_ids:
                            continue
                        processed_ids.add(msg_id)
                        ids.append(msg_id)
                        if (msg.get('importance') or '').lower() != 'high':
                            ids_mark_read.append(msg_id)
                    
                    if not self.dry_run:
                        # Mark read before move (skip important)
                        self._batch_mark_read_message_ids(ids_mark_read)
                        archive_id = self._get_archive_folder_id()
                        archived += self._batch_move_message_ids(ids, archive_id)
                    else:
                        archived += len(ids)
                    
                    # Log progress every 100 messages
                    if archived % 100 == 0:
                        logger.info(f"    Progress: {archived} messages processed...")
                    
                    # Check for next page
                    next_link = data.get('@odata.nextLink')
                    if not next_link:
                        break
                else:
                    logger.error(f"Error fetching {description}: {response.status_code}")
                    break
            
            if total_found == 0:
                logger.info(f"  No {description} found")
            else:
                logger.info(f"  {'Archived' if not self.dry_run else 'Would archive'} {archived} {description}")
                
        except Exception as error:
            logger.error(f"Error archiving {description}: {error}")
        
        return archived
