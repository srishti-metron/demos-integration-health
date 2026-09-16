# LogForge demo — integration health (Google SecOps)

Local kit for the **100 vendors / weekly regression** demo video.  
No push required. Run on your machine first; optional GitHub Actions + Slack later.

## Time / cost

| Piece | Your time |
|-------|-----------|
| Install SecOps mock + copy creds | ~5 min |
| Green local run | ~1 min |
| Red local run (`SIMULATE_DRIFT=true`) | ~1 min |
| Slack webhook (optional) | ~3 min |
| Film | ~2 min take |

No paid infra. Python stdlib only.

## Slack webhook

I **cannot** create this for you — it lives in *your* Slack workspace.

1. Slack → Apps → **Incoming Webhooks** → Add to a channel  
2. Copy the webhook URL  
3. If you use Actions: repo → Settings → Secrets → `SLACK_WEBHOOK_URL`  
4. Or tell me the URL only if you want help wiring it (treat it as a secret)

Without Slack, the video still works: show the **red GitHub Actions / terminal** failure.

## Local green run

```bash
cd demos/integration-health

export SECOPS_BASE_URL='https://google-secops-YOURSUB.staging.logforge.net'
export SECOPS_CREDENTIALS_JSON='{"credentials":{...},"project":"...","location":"...","instance":"..."}'

python3 tests/test_secops_health.py
# expect PASS
```

## Local red run (the “bug”)

```bash
export SIMULATE_DRIFT=true
python3 tests/test_secops_health.py
# expect FAIL — wrong params timeRange.start vs timeRange.start_time
```

## On-screen diff (for the video)

```diff
- timeRange.start_time
- timeRange.end_time
+ timeRange.start
+ timeRange.end
```

## Optional: GitHub Actions

Copy this folder into [demos-integration-health](https://github.com/srishti-metron/demos-integration-health) when you want CI visuals, then add secrets:

- `SECOPS_BASE_URL`
- `SECOPS_CREDENTIALS_JSON`
- `SLACK_WEBHOOK_URL` (optional)

Run workflow twice: `simulate_drift=false` (green), then `true` (red + Slack).

## Film order

1. Catalog / “100 integrations”  
2. SecOps mock URL + creds  
3. Green run  
4. Diff slide  
5. Red run + Slack (if ready)  
6. “Same playbook for every vendor”
