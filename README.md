# LogForge integration health (client-style demo layout)

```
integrations/           # one folder per vendor (placeholders OK)
  google-secops/
  crowdstrike/
  okta/

tests/
  health/               # shared create → test → purge harness
    runner.py
    logforge_client.py
    assertions.py
  connectors/           # per-connector checks
    test_google_secops.py
    test_crowdstrike.py
    test_okta.py
```

## Client flow (real)

1. Create mock (LogForge API) **or** use `demo_config.json` for the video  
2. Get URL + creds / bearer token  
3. Run connector checks  
4. Report findings  
5. Purge mock if this run created it  

## Demo-only drift flag

`DEMO_SIMULATE_DRIFT=true` (or Actions input `simulate_drift=true`) sends **wrong** query params on purpose for the marketing red run.  
Real client CI never sets this — failures come from real assertion mismatches.

## Run locally

```bash
# green (healthy)
python tests/connectors/test_google_secops.py

# red (demo drift)
DEMO_SIMULATE_DRIFT=true python tests/connectors/test_google_secops.py
```

Uses `demo_config.json` when present (no secrets). Token expires ~1h — regenerate if you get 401.

## Create/purge via API (later)

Unset / remove `demo_config.json` and set:

- `LOGFORGE_HOST`, `LOGFORGE_EMAIL`, `LOGFORGE_PASSWORD`
- `LOGFORGE_ORG_ID`, `LOGFORGE_PLATFORM_ID`

Then the harness will create → test → purge automatically.
