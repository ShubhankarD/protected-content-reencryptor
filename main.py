"""
Main entry point for the Microsoft Graph API Demo Project.
Demonstrates authentication, file generation, labeling, and upload.
"""

import json
from src.auth import AuthManager
from src.data_generation import DataGenerator
from src.labeling import Labeler
from src.storage import StorageManager

# Load configuration
with open('config.json') as f:
    config = json.load(f)

# Initialize modules
auth_manager = AuthManager(config)
data_generator = DataGenerator(output_dir='output')
labeler = Labeler(config)
storage_manager = StorageManager(config)

# Example flow (placeholders for real logic)

def main():
    # 1. Authenticate only questtest06@qa0.honeywell.com using interactive browser flow
    # Set scopes as needed for your app registration
    scopes = ["User.Read", "Files.ReadWrite.All"]
    print("Authenticating questtest06@qa0.honeywell.com ...")
    auth_manager.login(scopes=scopes)
    print("Access token:", auth_manager.get_token()[:40], "...")  # Print first 40 chars for confirmation

    # The rest of the flow can be enabled as needed
    # csv_file = 'output/sample.csv'
    # docx_file = 'output/sample.docx'
    # txt_file = 'output/sample.txt'
    # data_generator.generate_csv(csv_file)
    # data_generator.generate_docx(docx_file)
    # data_generator.generate_txt(txt_file)
    # labeler.apply_label(csv_file, config['sensitivity_label_id'])
    # labeler.apply_label(docx_file, config['sensitivity_label_id'])
    # labeler.apply_label(txt_file, config['sensitivity_label_id'])
    # storage_manager.upload_to_sharepoint(csv_file, config['sharepoint_library'])
    # storage_manager.upload_to_onedrive(docx_file, config['onedrive_folder'])
    # storage_manager.upload_to_onedrive(txt_file, config['onedrive_folder'])

if __name__ == '__main__':
    main()
