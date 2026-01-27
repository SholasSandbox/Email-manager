# Category-Based Stale Inbox Archiving

## The Structure

**Perfect balance of topical organization + time-based cleanup!**

```
Archive/
├── Work/
│   ├── Recent (4-18 months old)
│   └── Old (18+ months old)
├── Personal/
│   ├── Recent
│   └── Old
├── Finance/
│   ├── Recent
│   └── Old
├── Shopping/
│   ├── Recent
│   └── Old
├── Travel/
│   ├── Recent
│   └── Old
├── Healthcare/
│   ├── Recent
│   └── Old
├── Utilities/
│   ├── Recent
│   └── Old
├── Education/
│   ├── Recent
│   └── Old
└── Other/
    ├── Recent
    └── Old
```

---

## Why This Is Better ⭐

### Topical Organization
"Where's that Amazon order?" → Check `Archive/Shopping/Recent`  
"Need my tax receipts" → Check `Archive/Finance/Recent` and `Archive/Finance/Old`  
"Old work email from 2 years ago" → Check `Archive/Work/Old`

### Easy Bulk Cleanup
Delete ALL old stuff from 18+ months: Delete all `/Old` subfolders  
Keep categories but clear old data: Delete specific `*/Old` folders

### Intuitive Browsing
Gmail labels or Outlook categories group by type AND age

---

## How Categorization Works

The system automatically detects email categories based on:
1. **Sender domain**
2. **Subject keywords**
3. **Content analysis**

### Category Detection Rules

#### 1️⃣ Finance
**Keywords in subject:** invoice, payment, receipt, statement, transaction, bill, charge, refund, tax  
**Domains:** paypal.com, stripe.com, bank domains, chase.com, amex.com, visa.com, etc.

**Examples:**
- "Your PayPal receipt" → Finance
- "Invoice #12345 from Acme Corp" → Finance
- From chase.com → Finance

#### 2️⃣ Shopping
**Keywords:** order, shipped, delivery, tracking, purchase, confirmation  
**Domains:** amazon.com, ebay.com, etsy.com, walmart.com, target.com, shopify

**Examples:**
- "Your Amazon order has shipped" → Shopping
- "Order confirmation" → Shopping
- From ebay.com → Shopping

#### 3️⃣ Travel
**Keywords:** booking, reservation, flight, hotel, itinerary, confirmation  
**Domains:** booking.com, airbnb.com, expedia.com, uber.com, lyft.com

**Examples:**
- "Your flight confirmation" → Travel
- "Hotel reservation confirmed" → Travel
- From airbnb.com → Travel

#### 4️⃣ Healthcare
**Keywords:** appointment, prescription, medical, health, doctor, clinic, hospital, insurance  
**Domains:** health, medical, doctor, hospital, pharmacy

**Examples:**
- "Appointment reminder" → Healthcare
- "Prescription ready" → Healthcare
- From myhealthportal.com → Healthcare

#### 5️⃣ Utilities
**Keywords:** bill, account, service, subscription  
**Domains:** electric, gas, water, internet, phone, spectrum.com, att.com, verizon.com

**Examples:**
- "Your electric bill is ready" → Utilities
- From comcast.com → Utilities
- "Monthly subscription" → Utilities

#### 6️⃣ Education
**Keywords:** course, class, assignment, grade, school, university, student  
**Domains:** .edu, udemy.com, coursera.org, edx.org

**Examples:**
- "New course available" → Education
- From university.edu → Education
- "Assignment due tomorrow" → Education

#### 7️⃣ Work
**Detection:** Corporate email domains (NOT free email services)  
**Criteria:** Domain has a dot (.) AND is not gmail/yahoo/hotmail/outlook/aol/icloud

**Examples:**
- From john@techcorp.com → Work
- From hr@startupxyz.io → Work
- From team@company.co.uk → Work

#### 8️⃣ Personal
**Detection:** Free email services  
**Domains:** gmail.com, yahoo.com, hotmail.com, outlook.com, aol.com, icloud.com, protonmail.com

**Examples:**
- From friend@gmail.com → Personal
- From family@yahoo.com → Personal
- From buddy@hotmail.com → Personal

#### 9️⃣ Other
**Fallback:** Any email that doesn't match the above categories

---

## Timeline: Recent vs Old

| Age | Status |
|-----|--------|
| 4-18 months | **Recent** subfolder |
| 18+ months | **Old** subfolder |

**Why 18 months for "Old"?**
- ✅ 18 months is enough time for most reference needs
- ✅ Easy to bulk-delete after 2+ years
- ✅ Tax documents (7 years) stay in Finance/Old until you manually clean
- ✅ Clear delineation between "might need" vs "ancient history"

---

## What You'll See

### Console Output

```
Gmail Processing Summary:
  Promotions deleted: 22,658
  Job alerts deleted: 8,234
  Social media deleted: 3,847
  App acknowledgements archived: 145
  App acknowledgements deleted: 89
  Stale inbox archived (4+ months): 3,420
  Category breakdown:
    Finance/Recent: 245
    Finance/Old: 89
    Shopping/Recent: 412
    Shopping/Old: 156
    Work/Recent: 892
    Work/Old: 634
    Personal/Recent: 378
    Personal/Old: 234
    Other/Recent: 280
    Other/Old: 100
  Rejections archived: 296
  Important emails found: 100
  Calendar events created: 100
```

### Gmail Label Structure

After running, your Gmail will have:

```
Labels:
├── Inbox
├── Archive/
│   ├── Finance/
│   │   ├── Recent (245 emails)
│   │   └── Old (89 emails)
│   ├── Shopping/
│   │   ├── Recent (412 emails)
│   │   └── Old (156 emails)
│   ├── Work/
│   │   ├── Recent (892 emails)
│   │   └── Old (634 emails)
│   ├── Personal/
│   │   ├── Recent (378 emails)
│   │   └── Old (234 emails)
│   └── Other/
│       ├── Recent (280 emails)
│       └── Old (100 emails)
```

### Outlook Implementation

**Archive Folder + Categories:**
- All emails move to Archive folder
- Each email gets a category tag: "Finance-Recent", "Work-Old", etc.
- Categories show as colored tags in Outlook
- Filter/group by category to see organized view

**Why not nested folders in Outlook?**
- Microsoft Graph API makes nested folder creation complex
- Categories achieve the same goal with less API complexity
- Outlook's category system is powerful and well-integrated

---

## Real-World Usage Scenarios

### Scenario 1: Tax Time

**Need:** Find all financial documents from last year

**Action:**
1. Go to `Archive/Finance/Recent`
2. Search within that label/category
3. Export or review as needed

**Result:** All invoices, receipts, statements in one place!

### Scenario 2: Warranty Claim

**Need:** Find Amazon order from 8 months ago

**Action:**
1. Go to `Archive/Shopping/Recent`
2. Search "Amazon order #"
3. Find confirmation email

**Result:** Quick access to order details!

### Scenario 3: Spring Cleaning

**Need:** Delete old emails to free up space

**Action:**
1. Go to `Archive/*/Old` (all Old subfolders)
2. Review what's 18+ months old
3. Bulk delete categories you don't need
   - Delete `Shopping/Old` (old orders don't matter)
   - Keep `Finance/Old` (might need for taxes)
   - Delete `Personal/Old` (ancient personal emails)

**Result:** Freed up GBs of space, kept important stuff!

### Scenario 4: Job Search Reference

**Need:** Find old work emails from previous employer

**Action:**
1. Go to `Archive/Work/Old`
2. Filter by date range when you worked there
3. Search for specific projects

**Result:** Easy access to work history!

---

## Customization

### Add More Categories

Want to add "Legal" or "Family" categories?

**In both handlers, add to categorization logic:**

```python
# Add after Education check, before Work check

# Legal keywords and domains
legal_keywords = ['contract', 'agreement', 'legal', 'attorney', 'lawyer', 'court']
legal_domains = ['law', 'legal', 'attorney']

if any(kw in subject for kw in legal_keywords) or any(dom in domain for dom in legal_domains):
    return "Legal"
```

### Adjust Category Keywords

Think "Finance" should catch "wire transfer"?

```python
finance_keywords = ['invoice', 'payment', 'receipt', 'statement', 'transaction', 'bill', 'charge', 'refund', 'tax', 'wire transfer']  # Added!
```

### Change 18-Month Threshold

Want Old to be 24 months instead?

**In both handlers:**
```python
old_threshold = datetime.now() - timedelta(days=540)  # 18 months
# Change to:
old_threshold = datetime.now() - timedelta(days=730)  # 24 months (2 years)
```

### Exclude Specific Senders from Archiving

Don't want to archive emails from your boss?

**In Gmail handler:**
```python
query = f'in:inbox before:{date_str} -from:boss@company.com'
```

**In Outlook handler:**
```python
filter_query = (
    f"receivedDateTime lt {cutoff_date.isoformat()}Z "
    f"and not(contains(from/emailAddress/address, 'boss@company.com'))"
)
```

---

## Finding Archived Emails

### Gmail - Browse by Label

1. **Expand Archive section** in left sidebar
2. **Click category**, e.g., `Archive/Finance/Recent`
3. **Browse emails** in that category
4. **Search within category:** 
   ```
   label:archive/finance/recent invoice
   ```

### Gmail - Search All Archives

```
label:archive/*
label:archive/* amazon
label:archive/shopping/* order #12345
label:archive/work/old project alpha
```

### Outlook - Browse by Category

1. **Open Archive folder**
2. **Group by Categories** (View → Arrange By → Categories)
3. **Expand category**, e.g., "Finance-Recent"
4. **Browse emails**

### Outlook - Search with Categories

```
category:"Finance-Recent"
category:"Work-Old" project
folder:archive AND category:"Shopping-Recent"
```

---

## Bulk Operations

### Delete All Old Emails (18+ months)

**Gmail:**
```
label:archive/*/old
```
Select all → Delete permanently

**Or delete specific categories:**
```
label:archive/shopping/old
label:archive/personal/old
```

**Outlook:**
1. Archive folder → Group by Categories
2. Select all emails in "*-Old" categories
3. Delete

### Keep Only Recent Financial Records

**Gmail:**
1. Go to `Archive/Finance/Old`
2. Filter by date > 7 years ago (for tax purposes)
3. Delete older emails
4. Keep last 7 years

---

## What Happens on First Run

With a large inbox (e.g., 15,000 emails):

### Initial Archive

```
Stale inbox archived (4+ months): 11,420

Category breakdown:
  Work/Recent: 3,240
  Work/Old: 2,100
  Personal/Recent: 1,890
  Personal/Old: 1,200
  Shopping/Recent: 980
  Shopping/Old: 670
  Finance/Recent: 580
  Finance/Old: 360
  Other/Recent: 280
  Other/Old: 120
```

**This is NORMAL and GOOD!**
- Your inbox drops from 15,000 → 3,580 emails
- Everything is organized and searchable
- Easy to find what you need

### Monthly Maintenance (After First Run)

```
Stale inbox archived (4+ months): 147

Category breakdown:
  Work/Recent: 52
  Shopping/Recent: 38
  Personal/Recent: 29
  Finance/Recent: 18
  Other/Recent: 10
```

Much smaller numbers after initial cleanup!

---

## Testing the Categorization

### Dry-Run Mode Shows Categories

```bash
python email_manager.py
```

**Check the log:**
```
Category breakdown:
  Finance/Recent: 245
  Shopping/Recent: 412
  Work/Recent: 892
```

**If categories seem wrong:**
1. Check a few emails manually
2. Adjust keywords/domains in code
3. Re-run dry-run to verify

### Test with Small Sample

Want to test before processing thousands?

**Temporarily limit the query:**

**In Gmail handler:**
```python
results = self.service.users().messages().list(
    userId='me',
    q=query,
    maxResults=50,  # Test with just 50 emails
    pageToken=page_token
).execute()
```

**In Outlook handler:**
```python
params = {
    '$filter': filter_query,
    '$top': 50,  # Test with just 50 emails
    '$select': 'id,from,subject,receivedDateTime'
}
```

---

## Advantages Over Date-Based

| Feature | Date-Based | Category-Based |
|---------|------------|----------------|
| **Find by topic** | ❌ Hard - must remember when | ✅ Easy - browse category |
| **Bulk cleanup** | ✅ Delete by month | ✅ Delete by topic AND age |
| **Tax time** | ❌ Search across all months | ✅ Just check Finance/* |
| **Order lookup** | ❌ Which month was it? | ✅ Check Shopping/* |
| **Work reference** | ❌ When did I work there? | ✅ Check Work/* |
| **Storage management** | ✅ Delete old months | ✅ Delete specific */Old |

---

## Update Instructions

```bash
cd ~/email-manager

# Backup
cp gmail_handler.py gmail_handler.py.backup
cp outlook_handler.py outlook_handler.py.backup

# Update
cp /mnt/user-data/outputs/gmail_handler.py ~/email-manager/
cp /mnt/user-data/outputs/outlook_handler.py ~/email-manager/

# Test with dry-run
source venv/bin/activate
python email_manager.py

# Review category breakdown in output
# When satisfied:
python email_manager.py --live

# Check Gmail labels or Outlook categories
```

---

## FAQ

### Q: What if an email fits multiple categories?

**A:** First match wins. Order of checking:
1. Finance
2. Shopping  
3. Travel
4. Healthcare
5. Utilities
6. Education
7. Work
8. Personal
9. Other (fallback)

You can reorder these in the code if needed.

### Q: What about starred/important emails?

**A:** Currently they'll be archived. To exclude:

**Gmail:**
```python
query = f'in:inbox before:{date_str} -is:starred'
```

**Outlook:**
```python
filter_query = f"receivedDateTime lt {cutoff_date.isoformat()}Z and flag/flagStatus ne 'flagged'"
```

### Q: Can I move emails between categories later?

**Gmail:** Yes! Remove old label, add new label  
**Outlook:** Yes! Change the category

### Q: Will this slow down the app?

**A:** Slightly slower than date-based (needs to fetch full message for categorization), but worth it for organization!

### Q: What if a category is miscategorized?

**A:** 
1. Note the pattern (e.g., "XYZ Corp emails going to Personal")
2. Add XYZ Corp domain to Work check
3. Re-run on new emails (old ones stay miscategorized unless you manually fix)

---

## Summary

✅ **Topical organization** - Find emails by subject, not date  
✅ **Time-based subfolders** - Easy bulk cleanup of old stuff  
✅ **Automatic categorization** - No manual sorting needed  
✅ **Best of both worlds** - Category + age organization  
✅ **Intuitive browsing** - "Where's my Amazon order?" → Shopping/Recent  
✅ **Easy cleanup** - Delete all */Old to free space  
✅ **Smart defaults** - 9 categories cover most use cases  
✅ **Customizable** - Add categories, adjust keywords  

**This is professional-grade email organization!** 🎯✨
