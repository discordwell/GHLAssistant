# 10DLC Complete Guide for GoHighLevel Users

## What is 10DLC?

**10DLC** stands for **10-Digit Long Code**. It's a system that allows businesses to send Application-to-Person (A2P) SMS messages using standard 10-digit phone numbers (like 555-123-4567) instead of short codes (like 12345).

### Why Does 10DLC Exist?

Before 2021, anyone could buy a phone number from Twilio, GHL, or similar providers and blast thousands of text messages. This led to massive spam problems. US mobile carriers (AT&T, T-Mobile, Verizon) cracked down by requiring all business SMS to go through a registration system managed by **The Campaign Registry (TCR)**.

### What Happens Without 10DLC Registration?

- Messages silently filtered (never delivered)
- Messages blocked entirely
- Severely throttled throughput (1 msg/second instead of 100/second)
- Number flagged as spam
- Account suspension

---

## How 10DLC Registration Works

### The Two-Step Process

```
Step 1: BRAND REGISTRATION
Register your business identity with TCR
↓
Step 2: CAMPAIGN REGISTRATION
Register what you're texting about and to whom
↓
Step 3: CARRIER APPROVAL
Carriers review and approve (1-7 business days)
↓
Step 4: LINK TO GHL
Connect approved campaign to your GHL number
```

---

## Step 1: Brand Registration

### Required Information

| Field | Description | Common Mistakes |
|-------|-------------|-----------------|
| Legal Business Name | Exactly as registered with IRS/state | Not matching EIN records |
| DBA (if applicable) | "Doing Business As" name | Using DBA when EIN is under legal name |
| EIN (Tax ID) | 9-digit employer ID number | Typos, using SSN instead |
| Business Type | Sole Prop, LLC, Corp, etc. | Selecting wrong entity type |
| Business Address | Physical address | Using PO Box (not allowed) |
| Website | Your business website | Website down or doesn't match business |
| Vertical | Industry category | Selecting wrong category |
| Contact Info | Email and phone | Using personal email |

### Brand Trust Scores

After registration, TCR assigns a "Trust Score" that affects your messaging limits:

| Score | Daily Message Limit | Typical For |
|-------|-------------------|-------------|
| Low | 2,000/day | New/unverified businesses |
| Medium | 10,000/day | Verified small businesses |
| High | 200,000/day | Established enterprises |

### Brand Vetting (Optional but Recommended)

For higher limits, you can pay for "External Vetting" ($40-44 one-time):
- Verifies your business against official records
- Can significantly increase trust score
- Usually takes 1-2 business days

---

## Step 2: Campaign Registration

### Campaign Types (Use Cases)

| Use Case | Description | Examples |
|----------|-------------|----------|
| Marketing | Promotional messages | Sales, offers, newsletters |
| Customer Care | Support-related | Order updates, help responses |
| Account Notifications | Transactional | Appointment reminders, confirmations |
| 2FA | Security codes | Login verification |
| Mixed | Combination of above | Most common for GHL users |

### Required for Campaign Registration

1. **Campaign Description** (min 40 chars)
   - Be specific about what you're sending
   - BAD: "Sending texts to customers"
   - GOOD: "Appointment reminders and follow-up messages for dental patients who book through our website"

2. **Sample Messages** (2-5 samples)
   - Must represent actual messages you'll send
   - Must include opt-out language
   - Must match your campaign description

3. **Message Volume Estimate**
   - Daily/monthly expected volume
   - Be realistic, not aspirational

4. **Opt-in Method**
   - How do contacts consent to receive texts?
   - Website form, paper form, verbal, etc.
   - Must have documented consent process

5. **Opt-in Keywords** (if applicable)
   - e.g., "Text START to 555-1234"

6. **Opt-out Keywords**
   - Standard: STOP, UNSUBSCRIBE, CANCEL, END, QUIT
   - These are automatically honored

---

## Common Rejection Reasons & Fixes

### 1. Business Name Mismatch

**Problem**: Legal name doesn't match EIN records exactly.

**Fix**:
- Check IRS records (Letter 147C or SS-4 confirmation)
- Use EXACT legal name including punctuation
- Example: "Smith & Co., LLC" not "Smith and Co LLC"

### 2. Website Issues

**Problem**: Website doesn't match business or is down.

**Fixes**:
- Ensure website is live and accessible
- Business name should appear on website
- Add privacy policy and terms of service
- Remove "under construction" pages

### 3. Vague Campaign Description

**Problem**: Description doesn't clearly explain use case.

**Fix Example**:
- BAD: "Customer communications"
- GOOD: "Appointment reminder texts sent 24 hours before scheduled HVAC service appointments. Customers opt-in when booking online at example.com/book."

### 4. Missing Opt-out Language

**Problem**: Sample messages don't include unsubscribe option.

**Fix**: Every sample should include something like:
- "Reply STOP to unsubscribe"
- "Text STOP to opt-out"

### 5. Sample Message Mismatch

**Problem**: Samples don't match declared campaign type.

**Fix**: If you selected "Appointment Reminders", samples should be... appointment reminders, not marketing offers.

### 6. Invalid Phone Number

**Problem**: Contact phone is VOIP or invalid.

**Fix**: Use a real mobile or landline, not Google Voice.

---

## GoHighLevel-Specific 10DLC Steps

### In GHL Sub-Account Settings

1. Navigate to **Settings → Phone Numbers**
2. Click on your phone number
3. Go to **Compliance** tab
4. Click **Start Registration**

### GHL Registration Flow

```
1. Select "Register New Brand"
   - Fill business details exactly
   - Submit for TCR review

2. Wait for Brand Approval (usually minutes)

3. Register Campaign
   - Select use case(s)
   - Write description
   - Add sample messages
   - Describe opt-in process

4. Wait for Campaign Approval (1-7 days)

5. Link Approved Campaign to Number
   - Done automatically in most cases
```

### GHL-Specific Gotchas

1. **Agency vs Location**: Registration happens at the LOCATION (sub-account) level, not agency level

2. **Multiple Numbers**: Each number needs to be linked to an approved campaign, but one campaign can cover multiple numbers

3. **White-label**: If you white-label GHL, clients see your branding but TCR sees GHL as the provider

4. **Toll-Free Alternative**: GHL also supports toll-free numbers which have a simpler verification process

---

## Carrier-Specific Notes

### AT&T
- Strictest filtering
- Blocks messages with certain keywords
- "Free" or excessive caps can trigger filters

### T-Mobile
- Moderate filtering
- Focuses on consent verification
- URL shorteners may be blocked

### Verizon
- Generally more lenient
- Still requires proper registration
- Delays common during high-volume periods

---

## Best Practices After Registration

1. **Warm Up Your Number**
   - Start with low volume
   - Gradually increase over 2-4 weeks
   - Don't blast 10,000 messages day one

2. **Monitor Delivery Rates**
   - Track delivered vs. sent
   - If delivery drops, stop and investigate
   - Check for carrier feedback

3. **Maintain Opt-in Records**
   - Keep proof of consent
   - Timestamp when consent given
   - How consent was collected

4. **Handle STOP Requests Immediately**
   - Auto-processed by carrier
   - Don't message after STOP
   - Honor for 30 days minimum

5. **Keep Content Clean**
   - Avoid SHAFT content (Sex, Hate, Alcohol, Firearms, Tobacco)
   - No loan/debt collection language
   - No misleading claims

---

## Troubleshooting

### Messages Not Delivering

1. Check 10DLC registration status
2. Verify number is linked to approved campaign
3. Check for carrier filtering (try different message content)
4. Verify recipient number is valid mobile
5. Check if recipient has blocked you
6. Review GHL conversation logs for error codes

### Registration Stuck in Pending

1. Most approvals take 1-7 business days
2. "Pending" for 7+ days = contact support
3. Check for rejection email/notification
4. Verify all required fields are complete

### Trust Score Too Low

1. Complete brand vetting ($40-44)
2. Ensure business is verifiable online
3. Fix any mismatched information
4. Wait - score can improve over time

---

## Glossary

| Term | Definition |
|------|------------|
| A2P | Application-to-Person messaging (business SMS) |
| P2P | Person-to-Person messaging (personal texts) |
| TCR | The Campaign Registry - manages 10DLC registration |
| CSP | Campaign Service Provider (like GHL, Twilio) |
| MNO | Mobile Network Operator (carriers) |
| Throughput | Messages per second allowed |
| Trust Score | TCR rating affecting message limits |
| SHAFT | Sex, Hate, Alcohol, Firearms, Tobacco (prohibited) |

---

## Quick Reference Card

### Registration Checklist

- [ ] Legal business name (exact match to EIN)
- [ ] EIN number verified
- [ ] Business address (no PO Box)
- [ ] Working website with business name visible
- [ ] Campaign description (40+ chars, specific)
- [ ] Sample messages (2-5) with opt-out language
- [ ] Documented opt-in process
- [ ] Contact email and phone

### Sample Message Template

```
Hi [Name], this is [Business] confirming your appointment on [Date] at [Time].

Reply YES to confirm or call us at [Phone] to reschedule.

Reply STOP to unsubscribe.
```

### Emergency Contacts

- GHL Support: In-app chat or support.gohighlevel.com
- TCR Status: tcr.statuspage.io
- Carrier Issues: Contact through GHL support
