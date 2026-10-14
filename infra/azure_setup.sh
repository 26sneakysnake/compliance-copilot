#!/usr/bin/env bash
# One-time setup of Azure Container Apps for the demo API (consumption plan, scale to zero).
# Requires: az CLI logged in (`az login`), the containerapp extension, and the GHCR image
# ghcr.io/<owner>/compliance-copilot:latest published and set to public visibility.
# Cost: the consumption plan has a monthly free grant (180,000 vCPU-s, 360,000 GiB-s,
# 2M requests at the time of writing); with min replicas 0 an idle demo costs nothing.
set -euo pipefail

OWNER="${OWNER:-26sneakysnake}"
REPO="${REPO:-compliance-copilot}"
LOCATION="${LOCATION:-francecentral}"
RG="${RG:-rg-compliance-copilot}"
ENV_NAME="${ENV_NAME:-cae-compliance-copilot}"
APP="${APP:-compliance-copilot}"
IMAGE="ghcr.io/${OWNER}/${REPO}:latest"

az extension add --name containerapp --upgrade --only-show-errors
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

az group create -n "$RG" -l "$LOCATION" -o none
az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" -o none

az containerapp create -n "$APP" -g "$RG" --environment "$ENV_NAME" \
  --image "$IMAGE" --target-port 8000 --ingress external \
  --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 1 \
  --env-vars CCP_DEMO_KEYS=1 CCP_GENERATOR=extractive -o none

URL=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "API: https://$URL/docs"

# --- GitHub Actions OIDC (no secret stored in GitHub) -------------------------------
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name "gh-${REPO}-deploy" --query appId -o tsv)
az ad sp create --id "$APP_ID" -o none || true
az role assignment create --assignee "$APP_ID" --role Contributor \
  --scope "/subscriptions/$SUB/resourceGroups/$RG" -o none
az ad app federated-credential create --id "$APP_ID" --parameters "{
  \"name\": \"github-production\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${OWNER}/${REPO}:environment:production\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}" -o none

cat <<OUT

Add these in GitHub > Settings > Secrets and variables > Actions:
  secrets:   AZURE_CLIENT_ID=$APP_ID  AZURE_TENANT_ID=$TENANT  AZURE_SUBSCRIPTION_ID=$SUB
  variables: AZURE_DEPLOY=true  AZURE_RESOURCE_GROUP=$RG  AZURE_APP_NAME=$APP
and create an environment named "production".
OUT
