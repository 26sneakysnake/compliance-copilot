# Deployment

The API is a single container (FastAPI + Uvicorn). The pipeline is:

```
push to main -> ci (tests, data contracts, eval gate, governance, docker smoke test)
             -> deploy: build image -> ghcr.io/<owner>/compliance-copilot:<sha> -> Azure Container Apps revision
```

## Azure Container Apps (free grant)

1. Check that your subscription is eligible. Container Apps on the consumption plan includes a
   monthly free grant per subscription (180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million
   requests when this was written: https://learn.microsoft.com/azure/container-apps/billing).
   With `--min-replicas 0` an idle demo consumes nothing. A pay-as-you-go subscription is still
   required (Azure for Students works without a card if you are eligible).
2. Run CI once on `main` so the deploy workflow publishes `ghcr.io/<owner>/compliance-copilot:latest`,
   then make the package public (GitHub > Packages > compliance-copilot > Package settings).
3. `az login` then `./infra/azure_setup.sh`. It creates the resource group, the Container Apps
   environment and app, and a managed identity trusted by GitHub Actions through OIDC (no long-lived secret in GitHub, no tenant admin rights needed).
4. Add the secrets and variables printed by the script. The next push to `main` deploys
   automatically, then smoke-tests `/health`.

Demo keys (`demo-analyst`, `demo-claims`, `demo-auditor`) are enabled on the demo app with
`CCP_DEMO_KEYS=1`. For anything beyond a demo, set `CCP_API_KEYS` from a secret store instead.

To use Claude instead of the offline extractive generator:

```bash
az containerapp secret set -n compliance-copilot -g rg-compliance-copilot --secrets anthropic-key=<key>
az containerapp update -n compliance-copilot -g rg-compliance-copilot \
  --set-env-vars CCP_GENERATOR=anthropic ANTHROPIC_API_KEY=secretref:anthropic-key
```

## Tracing to Langfuse

Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (and `LANGFUSE_HOST` for a self-hosted or EU
instance) as container secrets. The app then exports its OpenTelemetry spans to Langfuse's OTLP
endpoint. Any other OTLP backend works with `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Local

```bash
docker build -t compliance-copilot .
docker run -p 8000:8000 -e CCP_DEMO_KEYS=1 compliance-copilot
open http://localhost:8000/docs
```
