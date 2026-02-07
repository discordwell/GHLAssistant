# Calendars API

Calendar and appointment booking operations.

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List calendars
    result = await ghl.calendars.list()
    for cal in result["calendars"]:
        print(f"{cal['name']} - {cal['eventType']}")

    # Get available slots
    slots = await ghl.calendars.get_slots(
        calendar_id,
        start_date="2024-01-15",
        end_date="2024-01-16",
        timezone="America/New_York"
    )

    # Book appointment
    await ghl.calendars.book(
        calendar_id,
        contact_id,
        slot_time="2024-01-15T10:00:00Z",
        title="Consultation",
        notes="Initial call"
    )

    # Get appointments
    appointments = await ghl.calendars.get_appointments(
        calendar_id=calendar_id,
        start_date="2024-01-01",
        end_date="2024-01-31"
    )

    # Reschedule
    await ghl.calendars.reschedule(
        appointment_id,
        new_slot_time="2024-01-16T14:00:00Z"
    )

    # Cancel
    await ghl.calendars.cancel(appointment_id)
```

## Calendar Types

- `RoundRobin_OptimizeForEqualDistribution` - Round robin assignment
- `RoundRobin_OptimizeForAvailability` - First available
- `Collective` - Group booking
- `ServiceCalendar` - Service-based
