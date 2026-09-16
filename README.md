# Demo config for GitHub Actions / local film
#
# Uses a mock LogForge bearer token (expires ~1 hour).
# Regenerate before filming if the green run returns 401.

## Local check

```bash
python3 tests/test_secops_health.py                      # green / PASS
SIMULATE_DRIFT=true python3 tests/test_secops_health.py  # red / FAIL
```

## GitHub Actions

No secrets required for the health check.  
Run workflow → `simulate_drift=false` then `true`.

Optional: `SLACK_WEBHOOK_URL` secret for failure notify.
