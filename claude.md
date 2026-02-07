# MaxLevel Project Notes

## Default Ports
- **CRM Platform**: `8020` — `ghl crm serve` (default)
- **Hiring Tool**: `8021` — `ghl hiring serve` (default)

## Known GHL Platform Bugs

### Private Integrations - Security Risk Confirm Button (2026-02-05)
When creating a Private Integration with sensitive scopes (like `locations.write`), the "Security Risk" confirmation dialog's **Confirm button does not work**. This is a GHL platform bug - clicking the button has no effect, whether done manually or via automation. The dialog cannot be dismissed and the integration cannot be created with sensitive scopes.

**Workaround:** Unknown. May need to contact GHL support or wait for platform fix.

**Affected scopes:** Any scope marked as "sensitive" (shown with warning icon), including:
- `locations.write` (Edit Locations)
- `users.write`
- And other write/delete scopes

### Private Integrations - Create Button Not Working (2026-02-05)
When creating a Private Integration, the **Create button does not work**. This affects **both sub-account level AND agency level** Private Integrations. The bug affects both read-only and write scopes. The button can be clicked (via UI or JavaScript) but no API call is made and the integration is not created.

**Affected levels:**
- Sub-account level (Settings > Private Integrations within a location)
- Agency level (Agency View > Settings > Private Integrations)

**Steps to reproduce:**
1. Navigate to Settings > Private Integrations (at either level)
2. Click "Create new integration"
3. Enter a name (e.g., "Agency Read Only API")
4. Click Next to go to Scopes
5. Select any scope (e.g., locations.readonly)
6. Click Create - button does nothing, no API call is made

**Workaround:** None known. Cannot create Private Integrations via the GHL UI at this time. Contact GHL support.

**Locations tested:**
- Sub-account: Jet Diaz Consulting (ID: jwKsnxyQuvqtiSM7EZAk)
- Agency: Discorp (via Agency View)
