# Builds the container remotely with Cloud Build and deploys to Cloud Run (no local Docker needed).
param(
  [string]$Project = "aibuildercupprj",
  [string]$Region = "us-central1",
  [string]$Service = "second-brain",
  [ValidateSet("memory", "alloydb")][string]$Store = "alloydb",
  [string]$AlloyDbInstanceUri = "projects/aibuildercupprj/locations/us-central1/clusters/second-brain/instances/primary"
)
$ErrorActionPreference = "Continue"   # gcloud writes progress to stderr
$Root = Split-Path $PSScriptRoot -Parent
$SaName = "$Service-sa"
$Sa = "$SaName@$Project.iam.gserviceaccount.com"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com --project $Project

if (-not (gcloud iam service-accounts list --project $Project --filter "email=$Sa" --format "value(email)")) {
  gcloud iam service-accounts create $SaName --display-name "Second Brain runtime" --project $Project
}
# Least privilege: Vertex AI calls + AlloyDB connector/IAM login.
foreach ($role in "roles/aiplatform.user", "roles/alloydb.client", "roles/alloydb.databaseUser", "roles/serviceusage.serviceUsageConsumer") {
  gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$Sa" --role $role --condition=None --quiet | Out-Null
}

$JwtSecret = -join ((1..48) | ForEach-Object { [char](Get-Random -Minimum 65 -Maximum 90) })
$EnvVars = "GCP_PROJECT=$Project,VECTOR_STORE=$Store,JWT_SECRET=$JwtSecret"
if ($Store -eq "alloydb") {
  # Passwordless: the service account authenticates to Postgres as an IAM database user.
  $EnvVars += ",ALLOYDB_INSTANCE_URI=$AlloyDbInstanceUri,ALLOYDB_IAM_AUTH=true,ALLOYDB_USER=$SaName@$Project.iam"
}

# max-instances=1: the approval queue and audit log are in-process for the prototype.
gcloud run deploy $Service --source $Root --region $Region --project $Project `
  --service-account $Sa --allow-unauthenticated --memory 1Gi --cpu 1 --max-instances 1 --timeout 300 `
  --set-env-vars $EnvVars
