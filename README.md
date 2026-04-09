# NetSuite API Integration

A Python integration framework for NetSuite ERP that provides OAuth 1.0 authenticated access to NetSuite REST APIs and RESTlets. Includes utilities for batch data operations, saved search extraction, and AWS Lambda deployment.

## Features

- **OAuth 1.0 Authentication** - Secure NetSuite API authentication with HMAC-SHA256 signing
- **Saved Search Export** - Pull and export NetSuite saved search results to CSV/JSON
- **Batch Operations** - Push and manage purchase orders and transaction data in bulk
- **Quality Control Testing** - Validate purchase orders and transaction data before NetSuite submission
- **Lambda Support** - AWS Lambda-compatible batch push operations for serverless deployment
- **SuiteScript Integration** - Custom NetSuite RESTlets and scriptlets for advanced operations

## Tech Stack

- Python 3.x
- NetSuite REST API & SuiteScript
- OAuth 1.0 (via authlib/oauthlib)
- AWS Lambda
- CSV/JSON data handling

## Setup

### Prerequisites
- NetSuite account with REST API access enabled
- OAuth credentials (consumer key/secret, token ID/secret)
- Python 3.7+

### Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Set up NetSuite credentials as environment variables:
```bash
export NETSUITE_CONSUMER_KEY="your_consumer_key"
export NETSUITE_CONSUMER_SECRET="your_consumer_secret"
export NETSUITE_TOKEN_ID="your_token_id"
export NETSUITE_TOKEN_SECRET="your_token_secret"
export NETSUITE_ACCOUNT="your_account_id"
```

## Usage

### Pull Saved Search Results
```python
from pull_ss import NetsuiteClient

client = NetsuiteClient(consumer_key, consumer_secret, token_id, token_secret, account_id)
results = client.get_saved_search(search_id)
```

### Batch Push Purchase Orders
```python
from batch_push import NetsuiteClient

client = NetsuiteClient()
response = client.push_purchase_orders(po_data)
```

### AWS Lambda Deployment
Deploy `lambda_function_batch_push.py` to AWS Lambda for scheduled or event-driven batch operations.

## Files

- `batch_push.py` - Main batch push implementation
- `pull_ss.py`, `pull_ss_2.py` - Saved search extraction utilities
- `netsuite_test_po_qc.py` - Purchase order quality checks
- `lambda_function_batch_push.py` - AWS Lambda handler
- `rf_ss_restlet.js`, `scriptlet-nsssoull.js` - NetSuite-side custom code (SuiteScript)