# Chilipad alarms

Disabled example. Choose your own target, time, temperature, and timezone before enabling through validated tools. This is a temperature routine, not an audible alarm.

```json
{
  "schema_version": 1,
  "items": [{
    "id": "example-weekday-wake",
    "enabled": false,
    "target": "my side",
    "action": "wake_temperature",
    "time": "06:30",
    "timezone": "America/Los_Angeles",
    "weekdays": [0, 1, 2, 3, 4],
    "temperature": 75,
    "unit": "F",
    "window_minutes": 0,
    "notification": "inbox"
  }]
}
```
