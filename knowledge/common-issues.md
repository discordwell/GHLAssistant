# Common GoHighLevel Issues & Solutions

## SMS/Messaging Issues

### Messages Not Sending

**Symptoms**: Messages stuck in queue, showing as "pending" or "failed"

**Common Causes & Fixes**:

1. **10DLC Not Registered**
   - Check Settings → Phone Numbers → Compliance
   - Registration must show "Approved"
   - See `10dlc-complete-guide.md` for setup

2. **Number Not Linked to Campaign**
   - Even with approved brand/campaign, number must be linked
   - Go to Phone Number settings → Compliance → Link to campaign

3. **Low Balance**
   - Check Settings → Company Billing
   - SMS costs money; ensure sufficient credits

4. **Invalid Recipient Number**
   - Must be valid mobile number
   - Landlines can't receive SMS
   - Check for country code issues (+1 for US)

5. **Carrier Filtering**
   - Message content triggered spam filter
   - Avoid: ALL CAPS, multiple exclamation marks, spammy words
   - Try sending simpler message to test

### Messages Marked as Spam

**Prevention**:
- Always include opt-out language ("Reply STOP to unsubscribe")
- Don't send to cold lists
- Respect STOP requests immediately
- Warm up new numbers gradually

---

## Workflow Issues

### Workflow Not Triggering

**Check**:
1. Is workflow published (not draft)?
2. Is trigger event actually happening?
3. Are filters too restrictive?
4. Is contact enrolled in another conflicting workflow?

### Actions Not Executing

**Check**:
1. Wait step timing correct?
2. Required fields populated?
3. Integration connected (for third-party actions)?
4. Check workflow history for error messages

### Contact Stuck in Workflow

**Fix**:
- Go to Contact → Workflows tab
- See current workflow status
- Option to remove from workflow
- Check if waiting on condition that will never be met

---

## Calendar Issues

### Appointments Not Showing

**Check**:
1. Calendar synced with Google/Outlook?
2. Timezone settings correct?
3. Availability hours set?
4. Calendar enabled for booking?

### Double Bookings

**Fix**:
1. Enable "Check for conflicts" in calendar settings
2. Ensure calendar is synced both ways
3. Set buffer time between appointments

### Booking Widget Not Working

**Check**:
1. Embed code current version?
2. Domain whitelisted?
3. Calendar has available slots?
4. Browser console for JavaScript errors

---

## CRM/Contact Issues

### Duplicate Contacts

**Prevention**:
- Set up deduplication rules
- Use consistent phone format (+1XXXXXXXXXX)
- Use email as primary identifier

**Fix**:
- Merge duplicates manually
- Or use workflow to auto-merge

### Custom Fields Not Saving

**Check**:
1. Field type matches data
2. Required fields filled
3. Form connected to correct custom fields
4. Check for character limits

### Missing Contact Activity

**Possible Causes**:
- Activity from different location
- Filtered view active
- Conversation in different channel
- Contact merged (check merged contacts)

---

## Integration Issues

### Zapier/Make Not Triggering

**Check**:
1. Webhook URL correct in GHL?
2. Zap/Scenario turned on?
3. Test with manual trigger first
4. Check Zapier/Make history for errors

### API Authentication Failed

**Common Fixes**:
1. Token expired - regenerate
2. Wrong authorization type (Bearer vs API key)
3. Location ID missing for location-level endpoints
4. Check API version (v1 deprecated, use v2)

---

## Email Issues

### Emails Going to Spam

**Improvements**:
1. Verify sending domain (SPF, DKIM, DMARC)
2. Warm up new domain
3. Clean email list (remove bounces)
4. Avoid spammy words in subject

### Email Not Sending from Workflow

**Check**:
1. Email template exists and published?
2. Sending domain verified?
3. Contact has valid email?
4. Daily sending limits reached?

---

## Funnel/Website Issues

### Funnel Not Loading

**Check**:
1. Domain/subdomain configured?
2. SSL certificate valid?
3. Funnel published?
4. Browser cache (try incognito)

### Form Submissions Not Creating Contacts

**Check**:
1. Form connected to correct location?
2. Required fields mapped?
3. Thank you page configured?
4. Check form submission logs

---

## Quick Diagnostic Commands

For developers using GHL Assistant CLI:

```bash
# Check authentication status
ghl auth status

# Test API connection
ghl test connection

# View 10DLC status
ghl 10dlc status

# Check recent errors
ghl logs errors --last 24h
```

---

## When to Contact GHL Support

Escalate to support when:
- Account-level billing issues
- Unexplained feature outages
- API behavior not matching documentation
- 10DLC registration stuck for 7+ days
- Data integrity issues

**GHL Support**:
- In-app chat (fastest)
- support.gohighlevel.com
- Developer Slack (for API issues)
