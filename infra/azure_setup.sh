#!/usr/bin/env bash
# One-time setup of Azure Container Apps for the demo API (consumption plan, scale to zero).
# Requires: az CLI logged in (`az login`), the containerapp extension, and the GHCR image
# ghcr.io/<owner>/compliance-copilot:latest published and set to public visibility.
# Cost: the consumption plan has a monthly free grant (180,000 vCPU-s, 360,000 GiB-s,
# 2M requests at the time of writing); with min replicas 0 an idle demo costs nothing.
set -euo pipefail

OWNER="${OWNER:-26sneakysnake}"
REPO="${REPO:-compliance-copilot}"
LOCATION="${LOCATION:-}"
RG="${RG:-rg-compliance-copilot}"
ENV_NAME="${ENV_NAME:-cae-compliance-copilot}"
APP="${APP:-compliance-copilot}"
IMAGE="ghcr.io/${OWNER}/${REPO}:latest"

az extension add --name containerapp --upgrade --only-show-errors

# Register resource providers only when needed: registering requires Owner/Contributor on the
# subscription, which school or company subscriptions often do not grant.
for ns in Microsoft.App Microsoft.OperationalInsights; do
  state=$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo Unknown)
  if [ "$state" != "Registered" ]; then
    if ! az provider register --namespace "$ns" --wait; then
      echo "ERROR: $ns is not registered and this account cannot register it on subscription $(az account show --query name -o tsv)."
      echo "Use a subscription where you are Owner (az account set --subscription <id>) or ask its admin to register $ns."
      exit 1
    fi
  fi
done

# Azure for Students and some company subscriptions restrict regions with an "allowed locations"
# policy. Pick the first allowed European region unless LOCATION is set.
if [ -z "$LOCATION" ]; then
  ALLOWED=$(az policy assignment list --query "[].parameters.listOfAllowedLocations.value[]" -o tsv 2>/dev/null | tr 'A-Z' 'a-z')
  LOCATION=francecentral
  if [ -n "$ALLOWED" ]; then
    LOCATION=$(echo "$ALLOWED" | head -1)
    for pref in francecentral westeurope northeurope germanywestcentral swedencentral switzerlandnorth \
                italynorth spaincentral polandcentral norwayeast uksouth; do
      if echo "$ALLOWED" | grep -qx "$pref"; then LOCATION=$pref; break; fi
    done
    echo "Allowed regions: $(echo $ALLOWED)"
  fi
fi
echo "Using region: $LOCATION"

if ! az group show -n "$RG" -o none 2>/dev/null; then
  az group create -n "$RG" -l "$LOCATION" -o none
fi
# No Log Analytics workspace: fewer resources, nothing billed, logs stay in the app (traces.jsonl, /metrics).
az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" --logs-destination none -o none

az containerapp create -n "$APP" -g "$RG" --environment "$ENV_NAME" \
  --image "$IMAGE" --target-port 8000 --ingress external \
  --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 1 \
  --env-vars CCP_DEMO_KEYS=1 CCP_GENERATOR=extractive -o none

URL=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "API: https://$URL/docs"

# --- GitHub Actions OIDC (no secret stored in GitHub) -------------------------------
# A user-assigned managed identity with a federated credential: unlike an app registration,
# it needs no Entra ID (tenant) rights, only rights on the subscription. Works in school tenants.
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
az identity create -n "id-${REPO}-deploy" -g "$RG" -l "$LOCATION" -o none
APP_ID=$(az identity show -n "id-${REPO}-deploy" -g "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n "id-${REPO}-deploy" -g "$RG" --query principalId -o tsv)
az identity federated-credential create --name github-production \
  --identity-name "id-${REPO}-deploy" --resource-group "$RG" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "repo:${OWNER}/${REPO}:environment:production" \
  --audiences "api://AzureADTokenExchange" -o none
for i in 1 2 3 4 5 6; do   # the new identity can take a few seconds to be visible
  az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
    --role Contributor --scope "/subscriptions/$SUB/resourceGroups/$RG" -o none && break
  sleep 10
done

cat <<OUT

Add these in GitHub > Settings > Secrets and variables > Actions:
  secrets:   AZURE_CLIENT_ID=$APP_ID  AZURE_TENANT_ID=$TENANT  AZURE_SUBSCRIPTION_ID=$SUB
  variables: AZURE_DEPLOY=true  AZURE_RESOURCE_GROUP=$RG  AZURE_APP_NAME=$APP
and create an environment named "production".
OUT
