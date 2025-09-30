# Microsoft Graph API Demo Project

## Overview
This project demonstrates:
- Authentication with multiple Microsoft accounts (MSAL)
- Dummy file generation (CSV, DOCX, TXT)
- (Mock) application of Microsoft Purview sensitivity labels
- Uploading files to SharePoint and OneDrive via Microsoft Graph API

## Structure
- `src/auth.py`: Authentication logic
- `src/data_generation.py`: Dummy file generation
- `src/labeling.py`: Sensitivity label application (mock/Graph API)
- `src/storage.py`: File upload to SharePoint/OneDrive
- `config.json` or `.env`: Configuration and secrets

## Setup
1. Clone the repo and navigate to the project folder.
2. Install dependencies:
   ```
pip install -r requirements.txt
   ```
3. Fill in `config.json` or `.env` with your Azure/Graph details.
   - Copy `.env.example` to `.env` and fill in `CLIENT_ID` and optionally `CLIENT_SECRET`.
   - `CLIENT_SECRET` enables app-only (client credentials) flows; omit it to use interactive delegated flows.

## Usage
- Implement the TODOs in each module for real API integration.
- Run your main script to test authentication, file generation, labeling, and upload.

## Notes
- This is a scaffolding project. Real secrets and API calls must be implemented.
- See comments in each module for integration points.
