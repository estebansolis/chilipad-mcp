# Markdown definitions and scheduler semantics

The local data directory contains `devices.md`, `alarms.md`, and `routines.md`. Each uses exactly one `json` fenced block containing `{"schema_version":1,"items":[...]}`. Surrounding prose is ignored and cannot authorize or execute anything. JSON must be valid; duplicate IDs/aliases and unknown fields are rejected. Files are stored outside Git with user-only permissions, atomic rename, and interprocess locks. Assistant-facing tools validate edits before writing. Invalid manual edits suspend all schedules, retain the previous valid snapshot for repair, and surface an error.

Mapping items: `id`, `alias`, optional `group`, `position`, `confirmed_at`. Only confirmed claimed IDs may be saved. Mapping rows are not instructions or a permission boundary.

Routine/alarm fields:

| Field | Meaning |
| --- | --- |
| id | Unique 1–64 lowercase letters, numbers, or hyphens |
| enabled | Boolean; samples are false |
| target | Confirmed alias; no implicit all-device selection |
| action | prepare_bed, wake_temperature, water_check, or reminder |
| time | Local action time HH:MM; set earlier than bedtime for preconditioning |
| timezone | Saved IANA zone, independent of device/report zones |
| weekdays | List 0–6, Monday–Sunday; weekly cadence supported |
| date | Exact YYYY-MM-DD for one-time actions, takes precedence over weekdays |
| temperature / unit | Required for temperature actions; validated normal limits |
| on | Optional boolean power change, only for temperature actions |
| window_minutes | 0–180 catch-up minutes for prepare_bed; wake_temperature requires 0 |
| notification | inbox; the only implemented destination |
| reminder_hours | 1–8760, default 24; interval for repeated unresolved water warnings |
| overrides | Optional map of occurrence date to replacement HH:MM, or null to skip |

`update_routine(row=..., confirmed=true)` creates or replaces a validated definition; `alarm=true` puts a new row in alarms.md. Existing rows stay in their canonical file. A missing alias or unavailable notification channel does not prevent listing, pausing, or deleting a structurally valid definition. Set enabled false/true to pause/resume; `delete_id=..., confirmed=true` deletes. Edits become active within the runner's 15-second poll. To move tomorrow's occurrence only, add its explicit local date to overrides rather than changing the recurring time.

The runner starts separately from MCP. One file lock owns execution per profile. Each id/local-date occurrence receives a durable claim before side effects. Restart does not retry a completed or interrupted occurrence; `claimed_unknown` needs human inspection. This prioritizes avoiding duplicate temperature actions over guaranteed delivery. Definitions changed after execution do not rerun the same local date; use a deliberate immediate command for another action. If a temperature rule is paused, deleted, or changed after its occurrence was claimed, that occurrence is skipped instead of executing a changed definition. The claim remains recorded; use an explicit immediate command if another action is wanted that day. A slow earlier action or device-status read cannot extend a later temperature routine beyond its allowed dispatch window. History is unbounded in this release; stop the runner before archiving it manually.

Repeated autumn clock time uses fold 0 once; nonexistent spring time is marked missed. A late wake routine skips after its scheduled minute. Bed preparation may catch up only inside window_minutes. Water checks coalesce missed dates into one recovery check. Calendar reminders late by a minute or more are missed. On first start the runner considers today since midnight in each routine's saved timezone; after downtime it evaluates at most 31 days and does not enumerate older misses. One-time dates must be in the future when configuring them. No schedule runs while the computer or required services are unavailable.

Explicit commands suppress automatic writes to that controller for 12 hours, visible in status. This fixed safety window is a v0.1 simplification of the PRD's per-routine-window rule. `resume_automation(target=..., confirmed=true)` clears it. Subsequent automatic writes compare against the previous automatic settings; a mismatch pauses writes instead of fighting the user. The cloud API has no conditional PATCH, so manual changes racing a read/write cannot be fully prevented.

Low-water observations produce side-specific inbox messages; unchanged healthy conditions stay quiet, unresolved warnings repeat only after reminder_hours, and a transition to not_low is reported. Failed/offline reads are errors or unknown, never healthy. Messages persist in `inbox.json` and are available through get_routine_status or CLI inbox. A local inbox is not proactive push delivery. `retry-notifications` delivers pending/failed history messages without repeating actions. It may produce a duplicate message if the process died between inbox delivery and history save.

Only weekly/one-time triggers are supported. Arbitrary monthly maintenance intervals, computed bedtime lead-time fields, automatic profile/group expansion, audible alerts, and dot notifications are not implemented. Calendar reminders can be dated manually; they are not sensor findings.
