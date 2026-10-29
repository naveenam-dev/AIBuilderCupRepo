# Provisions AlloyDB Omni on a small Compute Engine VM (~5 min). COSTS MONEY while running (~$50-60/month:
# e2-standard-2, two 20 GB disks, Cloud NAT); see teardown at the bottom.
# Omni licence: free for developing, testing, prototyping and demonstrating; production use needs a subscription.
# Access: the VM has no public IP. Cloud Run reaches it over Direct VPC egress; admins use an IAP TCP tunnel.
# The postgres password comes from OMNI_PASSWORD in backend/.env and is stored in Secret Manager only.
param(
  [string]$Project = "aibuildercupprj",
  [string]$Region = "us-central1",
  [string]$Zone = "us-central1-b",
  [string]$Vm = "omni-vm",
  [string]$Secret = "omni-postgres-password",
  [string]$RuntimeSa = "second-brain-sa"
)
$ErrorActionPreference = "Continue"   # gcloud writes progress to stderr
$Password = (Get-Content "$PSScriptRoot\..\backend\.env" | Where-Object { $_ -like "OMNI_PASSWORD=*" }) -replace "^OMNI_PASSWORD=", ""
if (-not $Password) { throw "OMNI_PASSWORD missing from backend/.env" }
$VmSa = "$Vm-sa@$Project.iam.gserviceaccount.com"

gcloud services enable compute.googleapis.com iap.googleapis.com secretmanager.googleapis.com --project $Project

# Outbound internet for the VM (Docker image pulls, apt) without a public IP.
gcloud compute routers create omni-router --network default --region $Region --project $Project
gcloud compute routers nats create omni-nat --router omni-router --region $Region --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges --project $Project

# Postgres is reachable only from the default subnet (Cloud Run Direct VPC egress) and from IAP (SSH + tunnel).
$Subnet = gcloud compute networks subnets describe default --region $Region --project $Project --format "value(ipCidrRange)"
gcloud compute firewall-rules create omni-allow-cloudrun --network default --direction INGRESS --allow tcp:5432 --source-ranges $Subnet --target-tags omni --project $Project
gcloud compute firewall-rules create omni-allow-iap --network default --direction INGRESS --allow tcp:22,tcp:5432 --source-ranges 35.235.240.0/20 --target-tags omni --project $Project

# Password in Secret Manager (no trailing newline), readable by the VM and the Cloud Run runtime.
$Tmp = New-TemporaryFile
[IO.File]::WriteAllText($Tmp, $Password)
gcloud secrets create $Secret --replication-policy automatic --data-file $Tmp --project $Project
Remove-Item $Tmp

gcloud iam service-accounts create "$Vm-sa" --display-name "AlloyDB Omni VM" --project $Project
foreach ($role in "roles/logging.logWriter", "roles/monitoring.metricWriter") {
  gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$VmSa" --role $role --condition=None --quiet | Out-Null
}
foreach ($sa in $VmSa, "$RuntimeSa@$Project.iam.gserviceaccount.com") {
  gcloud secrets add-iam-policy-binding $Secret --member "serviceAccount:$sa" --role roles/secretmanager.secretAccessor --project $Project --quiet | Out-Null
}

# Data on a separate disk that outlives the VM (auto-delete=no); omni_startup.sh installs Docker and runs Omni.
gcloud compute instances create $Vm --zone $Zone --machine-type e2-standard-2 `
  --image-family debian-12 --image-project debian-cloud --boot-disk-size 20GB --boot-disk-type pd-balanced `
  --create-disk "name=omni-data,size=20GB,type=pd-balanced,device-name=omni-data,auto-delete=no" `
  --no-address --tags omni --shielded-secure-boot `
  --service-account $VmSa --scopes cloud-platform `
  --metadata-from-file "startup-script=$PSScriptRoot\omni_startup.sh" --project $Project

Write-Host "Next: open a tunnel and load the corpus:"
Write-Host "  gcloud compute start-iap-tunnel $Vm 5432 --local-host-port=localhost:15432 --zone $Zone --project $Project"
Write-Host "  cd backend; .venv\Scripts\python -m scripts.init_alloydb --omni"

# Teardown (stops all Omni charges):
#   gcloud compute instances delete omni-vm --zone us-central1-b --project aibuildercupprj
#   gcloud compute disks delete omni-data --zone us-central1-b --project aibuildercupprj
#   gcloud compute routers delete omni-router --region us-central1 --project aibuildercupprj
#   gcloud secrets delete omni-postgres-password --project aibuildercupprj
