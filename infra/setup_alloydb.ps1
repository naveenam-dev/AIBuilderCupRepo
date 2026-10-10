# Provisions AlloyDB for the prototype (~15-20 min). COSTS MONEY while running; see teardown at the bottom.
# Access: AlloyDB Python Connector over the instance's public IP (IAM-authorized mTLS, no VPC connector).
# Local bootstrap uses the postgres password from backend/.env; Cloud Run uses passwordless IAM database auth.
param(
  [string]$Project = "aibuildercupprj",
  [string]$Region = "us-central1",
  [string]$Cluster = "second-brain",
  [string]$Instance = "primary",
  [string]$RuntimeSa = "second-brain-sa"
)
$ErrorActionPreference = "Continue"   # gcloud writes progress to stderr
$Password = (Get-Content "$PSScriptRoot\..\backend\.env" | Where-Object { $_ -like "ALLOYDB_PASSWORD=*" }) -replace "^ALLOYDB_PASSWORD=", ""
if (-not $Password) { throw "ALLOYDB_PASSWORD missing from backend/.env" }

gcloud services enable alloydb.googleapis.com servicenetworking.googleapis.com compute.googleapis.com --project $Project

# Private services access (already done once for aibuildercupprj; these no-op with an 'already exists' error).
gcloud compute addresses create alloydb-psa-range --global --purpose=VPC_PEERING --prefix-length=20 --network=default --project $Project
gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com --ranges=alloydb-psa-range --network=default --project $Project

gcloud alloydb clusters create $Cluster --region=$Region --network=default --password=$Password --project $Project
gcloud alloydb instances create $Instance --cluster=$Cluster --region=$Region --instance-type=PRIMARY `
  --cpu-count=2 --availability-type=ZONAL --assign-inbound-public-ip=ASSIGN_IPV4 `
  --database-flags="alloydb.iam_authentication=on,password.enforce_complexity=on" --project $Project

# Passwordless database user for the Cloud Run service account.
if (-not (gcloud iam service-accounts list --project $Project --filter "email=$RuntimeSa@$Project.iam.gserviceaccount.com" --format "value(email)")) {
  gcloud iam service-accounts create $RuntimeSa --display-name "Second Brain runtime" --project $Project
}
gcloud alloydb users create "$RuntimeSa@$Project.iam" --cluster=$Cluster --region=$Region --type=IAM_BASED --project $Project

Write-Host "Next: cd backend; .venv\Scripts\python -m scripts.init_alloydb $RuntimeSa@$Project.iam"

# Teardown when done:
#   gcloud alloydb clusters delete second-brain --region=us-central1 --force --project aibuildercupprj
