# Builds the container remotely with Cloud Build and deploys to Cloud Run (no local Docker needed).
# With -Firebase (default): Firestore state, Firebase Auth and FCM push. Run backend/scripts/setup_firebase.py once first.
param(
  [string]$Project = "aibuildercupprj",
  [string]$Region = "us-central1",
  [string]$Service = "second-brain",
  [ValidateSet("memory", "alloydb")][string]$Store = "alloydb",
  [string]$AlloyDbInstanceUri = "projects/aibuildercupprj/locations/us-central1/clusters/second-brain/instances/primary",
  [bool]$Firebase = $true,
  [int]$MaxInstances = 3,
  [ValidateSet("adk", "native")][string]$AgentRuntime = "adk"
)
$ErrorActionPreference = "Continue"   # gcloud writes progress to stderr
$Root = Split-Path $PSScriptRoot -Parent
$SaName = "$Service-sa"
$Sa = "$SaName@$Project.iam.gserviceaccount.com"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com --project $Project

if (-not (gcloud iam service-accounts list --project $Project --filter "email=$Sa" --format "value(email)")) {
  gcloud iam service-accounts create $SaName --display-name "Second Brain runtime" --project $Project
}
# Least privilege: Vertex AI, AlloyDB connector/IAM login, Firestore, FCM; signs its own Firebase custom tokens.
foreach ($role in "roles/aiplatform.user", "roles/alloydb.client", "roles/alloydb.databaseUser", "roles/serviceusage.serviceUsageConsumer",
                  "roles/datastore.user", "roles/firebasecloudmessaging.admin") {
  gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$Sa" --role $role --condition=None --quiet | Out-Null
}
gcloud iam service-accounts add-iam-policy-binding $Sa --member "serviceAccount:$Sa" --role roles/iam.serviceAccountTokenCreator --project $Project --quiet | Out-Null

$JwtSecret = -join ((1..48) | ForEach-Object { [char](Get-Random -Minimum 65 -Maximum 90) })
$Vars = @("GCP_PROJECT=$Project", "VECTOR_STORE=$Store", "JWT_SECRET=$JwtSecret", "AGENT_RUNTIME=$AgentRuntime")
if ($Store -eq "alloydb") {
  # Passwordless: the service account authenticates to Postgres as an IAM database user.
  $Vars += @("ALLOYDB_INSTANCE_URI=$AlloyDbInstanceUri", "ALLOYDB_IAM_AUTH=true", "ALLOYDB_USER=$SaName@$Project.iam")
}
if ($Firebase) {
  # The public Firebase web config is read from backend/.env (kept out of git).
  $WebConfig = (Get-Content "$Root\backend\.env" | Where-Object { $_ -like "FIREBASE_WEB_CONFIG=*" }) -replace "^FIREBASE_WEB_CONFIG=", ""
  if (-not $WebConfig) { throw "FIREBASE_WEB_CONFIG missing from backend/.env" }
  $Vars += @("STATE_STORE=firestore", "AUTH_PROVIDER=firebase", "CHAT_ADAPTER=firebase", "FIREBASE_SIGNER_SA=$Sa", "FIREBASE_WEB_CONFIG=$WebConfig")
  # The UI on Firebase Hosting streams /api/chat directly from Cloud Run (Hosting rewrites buffer SSE);
  # the backend allows this project's Hosting origins for CORS.
  $Url = gcloud run services describe $Service --region $Region --project $Project --format "value(status.url)" 2>$null
  if ($Url) { $Vars += "PUBLIC_API_URL=$Url" }
}
# Pass variables through a YAML file: Windows PowerShell strips embedded quotes from native-command
# arguments, which would corrupt the JSON web config.
$EnvFile = Join-Path $env:TEMP "second-brain-env.yaml"
$Yaml = foreach ($v in $Vars) {
  $k, $val = $v -split "=", 2
  "${k}: '" + ($val -replace "'", "''") + "'"
}
Set-Content -Path $EnvFile -Value $Yaml -Encoding ascii

# State lives in Firestore, so several instances can serve traffic.
gcloud run deploy $Service --source $Root --region $Region --project $Project `
  --service-account $Sa --allow-unauthenticated --memory 1Gi --cpu 1 --max-instances $MaxInstances --timeout 300 `
  --env-vars-file $EnvFile
Remove-Item $EnvFile -ErrorAction SilentlyContinue
