# Gmail Handler Update - Pagination Support

## What Changed

The original Gmail handler only fetched the first 100 emails per query due to API pagination limits. For accounts with 50,000+ emails, this meant only a tiny fraction was being processed.

## Updates Made

### 1. **Pagination Support**
- Now processes ALL matching emails, not just the first 100
- Fetches up to 500 messages per batch (Gmail API maximum)
- Automatically follows pagination tokens to get all results

### 2. **Progress Tracking**
- Shows progress every 100 messages processed
- Displays total found emails in real-time
- Better visibility into what's happening with large mailboxes

### 3. **Batch Processing**
- Processes emails in manageable batches of 500
- Prevents memory issues with huge result sets
- More efficient API usage

## How to Use

### Replace Your Old File

```bash
cd ~/email-manager

# Backup the old version (optional)
cp gmail_handler.py gmail_handler.py.backup

# Download the new version (it's in the outputs)
# Just replace the file with the updated one
```

### Test It

```bash
# Activate your virtual environment
source venv/bin/activate

# Test in dry-run mode (safe)
python email_manager.py --provider gmail

# You'll see output like:
#   Searching for old promotional emails...
#   Processing batch of 500 messages (total found so far: 500)...
#   Progress: 100 messages processed...
#   Progress: 200 messages processed...
#   Processing batch of 500 messages (total found so far: 1000)...
#   ...
```

## Performance Notes

### Processing Time
- **50,000 emails**: Could take 10-30 minutes depending on your internet speed
- **Gmail API Rate Limits**: 250 quota units per user per second
  - Most operations cost 5 quota units
  - So roughly 50 operations/second max
  - For 10,000 emails ≈ 3-5 minutes

### Recommendations

1. **First run**: Use dry-run mode to see totals without making changes
2. **Large mailboxes**: Run during off-hours (less likely to hit rate limits)
3. **Monitor progress**: Watch the log file for detailed progress
4. **Be patient**: With 50,000+ emails, this WILL take time

## What You'll See Now

### Before (Limited):
```
Gmail Processing Summary:
  Promotions deleted: 100  ← Only first page!
  Job alerts deleted: 100   ← Only first page!
  Rejections archived: 100  ← Only first page!
```

### After (Complete):
```
Gmail Processing Summary:
  Promotions deleted: 8,547   ← ALL matching emails!
  Job alerts deleted: 2,341    ← ALL matching emails!
  Rejections archived: 156     ← ALL matching emails!
```

## API Rate Limit Handling

If you hit rate limits, the Gmail API will return an error. The current implementation will:
- Stop processing that category
- Log the error
- Continue with other categories

### Future Enhancement (If Needed)
We can add automatic retry with exponential backoff if you consistently hit rate limits.

## Important Notes

⚠️ **Calendar Events Limited to 100**
- Even if you have 500 important emails, only 100 calendar events will be created
- This prevents calendar spam
- You can adjust this in the code if needed

⚠️ **Dry-Run First!**
- With 50,000 emails, ALWAYS test in dry-run mode first
- Make sure the filters are catching what you want
- Verify the date ranges make sense

⚠️ **Trash vs Permanent Delete**
- Emails are moved to Trash, not permanently deleted
- You can still recover them from Trash if needed
- Gmail auto-deletes trash after 30 days

## Troubleshooting

### "Quota exceeded" errors
- Wait a few minutes and try again
- Process one category at a time (modify code to comment out others)
- Run during off-peak hours

### Taking too long
- This is normal for large mailboxes!
- Check the log file to see progress
- Each batch of 500 should take 30-60 seconds

### Want to limit the number processed
Modify the query date ranges:
```python
# In gmail_handler.py

# For promotions - change from 30 days to 60 days
cutoff_date = datetime.now() - timedelta(days=60)  # Process older emails

# Or limit to MORE recent
cutoff_date = datetime.now() - timedelta(days=15)  # Only last 15 days
```

## Summary

With these updates, the Gmail handler can now:
- ✅ Process ALL matching emails, not just 100
- ✅ Handle mailboxes with 50,000+ emails
- ✅ Show progress in real-time
- ✅ Work efficiently with batch processing
- ✅ Prevent memory issues

Your 50,000+ email Gmail account will now be fully processed! 🎉
