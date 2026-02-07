# Opportunities API

Pipeline and deal management.

## Python API

```python
from maxlevel.api import GHLClient

async with GHLClient.from_session() as ghl:
    # List pipelines
    pipelines = await ghl.opportunities.pipelines()
    for p in pipelines["pipelines"]:
        print(f"{p['name']}")
        for stage in p["stages"]:
            print(f"  - {stage['name']}")

    # List opportunities
    opps = await ghl.opportunities.list(pipeline_id=pipeline_id)

    # Create opportunity
    opp = await ghl.opportunities.create(
        pipeline_id=pipeline_id,
        stage_id=first_stage_id,
        contact_id=contact_id,
        name="New Deal",
        value=5000,
        status="open"
    )

    # Move to next stage
    await ghl.opportunities.move_stage(opp_id, next_stage_id)

    # Mark as won/lost
    await ghl.opportunities.mark_won(opp_id)
    await ghl.opportunities.mark_lost(opp_id)

    # Delete
    await ghl.opportunities.delete(opp_id)
```

## Opportunity Status

- `open` - Active deal
- `won` - Closed won
- `lost` - Closed lost
- `abandoned` - No longer pursuing
