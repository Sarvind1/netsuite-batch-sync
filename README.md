# NetSuite API Integration Tools

Tools for batch pushing data to NetSuite and pulling saved search results using OAuth 1.0a authentication. Includes quality control utilities, Lambda support, and RESTlet integration for enterprise ERP workflows.

## Features

- **Batch Push Operations**: Upload purchase orders and data to NetSuite via RESTlets
- **Saved Search Extraction**: Pull search results from NetSuite saved searches as CSV/JSON
- **OAuth 1.0a Authentication**: Secure API access using HMAC-SHA256 signatures
- **Quality Control**: PO validation and data consistency checking
- **AWS Lambda Support**: Deploy batch operations as serverless functions
- **Server-Side Scripts**: NetSuite RESTlet and scriptlet implementations

## Tech Stack

- Python 3 with `requests`, `authlib`, `oauthlib`
- NetSuite RESTlets API (HTTPS/OAuth 1.0a)
- JavaScript for NetSuite server-side scripts
- AWS Lambda for cloud deployment

## Setup

1. **Install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure credentials** (do NOT commit credentials):
   Create a `.env` file with your NetSuite OAuth credentials:
   ```
   NETSUITE_CONSUMER_KEY=<your-consumer-key>
   NETSUITE_CONSUMER_SECRET=<your-consumer-secret>
   NETSUITE_TOKEN_ID=<your-token-id>
   NETSUITE_TOKEN_SECRET=<your-token-secret>
   NETSUITE_ACCOUNT=<your-account-id>
   ```

3. **Load environment variables** before running scripts:
   ```bash
   source .env
   ```

## Usage

**Batch push to NetSuite:**
```python
from batch_push import NetsuiteClient

client = NetsuiteClient()
# Push purchase order data to NetSuite
response = client.push_data(url, data)
```

**Pull saved search results:**
```python
from pull_ss import NetsuiteClient

client = NetsuiteClient(
    consumer_key, consumer_secret, 
    token_id, token_secret, account_id
)
results = client.get_saved_search(saved_search_id)
```

**Run PO quality checks:**
```bash
python netsuite_test_po_qc.py
```

## Notes

- Always use environment variables for credentials—never hardcode them
- Large data files (CSV/JSON) are ignored by `.gitignore` and should not be committed
- Test PO QC script before running batch operations
- Refer to NetSuite SuiteScript documentation for server-side script modifications