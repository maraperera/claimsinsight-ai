import os
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "raw"
DATA_DIR = Path("data/raw")

CATEGORIES = ["medical_discharge", "physio_notes", "police_reports", "policy_schedules"]

blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

for category in CATEGORIES:
    category_path = DATA_DIR / category
    if not category_path.exists():
        continue
    
    print(f"Uploading files from category: {category}...")
    for pdf_file in category_path.glob("*.pdf"):
        blob_target_path = f"incoming_claims/{category}/{pdf_file.name}"
        blob_client = container_client.get_blob_client(blob_target_path)
        
        with open(pdf_file, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            print(f"  Uploaded -> {blob_target_path}")

print("All synthetic claim documents successfully uploaded to Azure Storage.")