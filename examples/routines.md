# Chilipad routines

Disabled weekly water check. No sensor can establish water quality or a cleaning requirement.

```json
{
  "schema_version": 1,
  "items": [{
    "id": "example-weekly-water",
    "enabled": false,
    "target": "my side",
    "action": "water_check",
    "time": "18:00",
    "timezone": "America/Los_Angeles",
    "weekdays": [6],
    "notification": "inbox",
    "reminder_hours": 24
  }]
}
```
