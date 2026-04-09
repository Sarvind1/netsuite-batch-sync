# NetSuite API Integration Tool

A Python-based toolkit for integrating with NetSuite ERP via OAuth 1.0 authentication, enabling batch operations on purchase orders and automated retrieval of saved search results. Includes RESTlet integration and Lambda function support for cloud deployment.

## Features

- **OAuth 1.0 Authentication**: Secure NetSuite API access with HMAC-SHA256 signatures
- **Batch Purchase Order Operations**: Push and validate purchase orders in bulk
- **Saved Search Retrieval**: Pull and process NetSuite saved search results
- **RESTlet Integration**: Custom RESTlet scripts for advanced NetSuite workflows
- **Lambda Support**: AWS Lambda function wrapper for serverless deployment
- **Data Validation & QC**: Built-in validation for purchase order quality checks

## Tech Stack

- **Python 3**: Core scripts using requests, authlib, oauthlib
- **NetSuite REST API / SuiteScript**: NetSuite backend integration
- **AWS Lambda**: Serverless execution
- **OAuth 1.0a**: Authentication protocol
- **CSV/JSON**: Data format support

## Setup

1. Clone the repository and set up a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure NetSuite credentials as environment variables:
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

client = NetsuiteClient(
    consumer_key=os.environ['NETSUITE_CONSUMER_KEY'],
    consumer_secret=os.environ['NETSUITE_CONSUMER_SECRET'],
    token_id=os.environ['NETSUITE_TOKEN_ID'],
    token_secret=os.environ['NETSUITE_TOKEN_SECRET'],
    account_id=os.environ['NETSUITE_ACCOUNT']
)

# Retrieve saved search results
results = client.get_saved_search(saved_search_id=123)
```

### Batch Push Purchase Orders
```python
from batch_push import NetsuiteClient

client = NetsuiteClient({
    'NETSUITE_CONSUMER_KEY': os.environ['NETSUITE_CONSUMER_KEY'],
    'NETSUITE_CONSUMER_SECRET': os.environ['NETSUITE_CONSUMER_SECRET'],
    'NETSUITE_TOKEN_ID': os.environ['NETSUITE_TOKEN_ID'],
    'NETSUITE_TOKEN_SECRET': os.environ['NETSUITE_TOKEN_SECRET'],
    'NETSUITE_ACCOUNT': os.environ['NETSUITE_ACCOUNT']
})

# Create and push purchase orders
response = client.create_purchase_order(purchase_order_data)
```

## Files

- **batch_push.py** / **batch_push_ns_working.py**: Batch purchase order creation and validation
- **pull_ss.py** / **pull_ss_2.py**: Retrieve saved search results from NetSuite
- **netsuite_test_po_qc.py**: Quality control tests for purchase orders
- **lambda_function_batch_push.py**: AWS Lambda wrapper for batch operations
- **rf_ss_restlet.js** / **scriptlet-nsssoull.js**: NetSuite RESTlet/SuiteScript implementations
- **requirements.txt**: Python dependencies

## License

Proprietary