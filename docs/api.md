# API mapping and provenance

Frozen collection revision: `42f4f72a9ecc435d31dfaf0099e3b69b44e60b93` from [estebansolis/sleepme-postman](https://github.com/estebansolis/sleepme-postman). Expanded Postman v2.1 JSON, equivalent CLI v3 YAML request files, and Sleep.me OpenAPI **v1.1** are under `reference/`. The reference source was retrieved October 5, 2026. The expanded JSON removes scripts and saved responses and keeps credentials and device selection blank. No private environment is bundled.

Fixed origin: `https://api.developer.sleep.me/v1`; bearer token from explicit OS vault backend; HTTPS, Accept JSON, JSON content type on PATCH. Redirects and environment proxies are disabled. Responses and exception bodies never appear in errors. No user-defined upstream URL is accepted.

| Operation | Postman recipes | MCP tools |
| --- | --- | --- |
| GET /devices | List Devices | list_devices; mapping validation; identification selection |
| GET /devices/{id} | Get Device Status | get_device_status; check_water_status; model guard; recovery |
| PATCH /devices/{id} | Update Device Status, On, Off, F target, C target, Maximum Cooling, Maximum Heating, Display F, Display C, Time Zone | set_power; set_temperature; update_device_settings; prepare_bed; identify_devices |
| GET /sleep-reports/ | List Sleep Reports, Today Sleep Reports | get_sleep_reports |

Four operations, fourteen saved recipes. No cloud alarm/routine endpoint exists. Schedules and aliases are local application features. A general recipe with 69°F/standby is never an implicit runtime default.

| Writable top-level property | Validation |
| --- | --- |
| thermal_control_status | active or standby |
| set_temperature_f | integer 55–115; -1/999 only through explicit named mode or recovery |
| set_temperature_c | 13–48 in half-degree increments; documented sentinels are accepted only in trusted recovery snapshots |
| display_temperature_unit | f or c |
| time_zone | valid IANA identifier |

PATCH requires at least one allowlisted property and never both temperature fields. Settings preserve power/temperature. Target changes preserve power. Combined preparation includes power only if explicitly saved. Writes require connected Dock Pro status; unrecognized model strings fail closed rather than inferring support from field presence.

Status retains optional/unknown status and control data. `about` is filtered to model/firmware to avoid disclosing serial numbers and network addresses. Discovery preserves IDs, names, and attachments. Readouts include observation timestamps. A missing or null low-water boolean is unknown; water_level has no documented scale and cannot imply a percentage or maintenance diagnosis. Cleaning/replacement reminders are calendar-based.

Reports accept optional YYYY-MM-DD start_date, integer days_back 0–6, and IANA time_zone (explicit UTC default). Blank dates fail; omitted dates remain omitted so Sleepme resolves today in the query timezone. Data remains account scoped; no device_id is sent or invented side association. Scores, sessions, nullable minute metrics, and hypnogram offsets/stages including NO_DATA pass through without fabricating values. The source interval direction is inconsistent; inspect actual returned dates before promising a range.

400/401/403/404 yield safe actionable errors. Other non-2xx statuses yield a generic service error. 429 saves a shared blocked-until deadline using Retry-After (seconds or HTTP date); GET retries at most twice for short delays. PATCH never retries automatically, including network timeouts or 429. Read status before a deliberate subsequent write. A PATCH 2xx means request accepted; unconstrained/empty responses do not establish actual target or readiness.

The local per-profile file-lock budget permits at most 10 requests per discrete minute across server processes, setup validation, recovery, and runner. Exhaustion fails promptly rather than blocking an MCP call for a full minute. Other consumers and separate profiles still share Sleepme's upstream account limit.
