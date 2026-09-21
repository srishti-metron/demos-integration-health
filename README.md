# LogForge integration health (client-style layout)

```
integrations/                 # vendor-specific data + checks
  google_secops/
    manifest.json             # endpoint + expected params
    demo_env.json             # demo mock URL/token (optional)
    checks.py                 # what to call for this vendor
  crowdstrike/                # placeholder
  okta/                       # placeholder

tests/health/                 # shared ONLY: create → run → purge
  runner.py
  logforge_client.py
  assertions.py

tests/connectors/             # thin entrypoints
  test_google_secops.py       # calls integrations.google_secops.checks
```

## Rule of thumb
- **Vendor knowledge** → `integrations/<vendor>/`
- **Lifecycle plumbing** → `tests/health/`

## Run

```bash
python tests/connectors/test_google_secops.py
DEMO_SIMULATE_DRIFT=true python tests/connectors/test_google_secops.py
```

`DEMO_SIMULATE_DRIFT` is marketing-demo only.
