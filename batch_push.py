import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from urllib.parse import quote, parse_qsl
import requests
import uuid
import os
from datetime import datetime
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NetsuiteClient:
    def __init__(self, credentials=None):
        # Use provided credentials or get from environment variables
        if credentials:
            self.consumer_key = credentials['NETSUITE_CONSUMER_KEY']
            self.consumer_secret = credentials['NETSUITE_CONSUMER_SECRET']
            self.token_id = credentials['NETSUITE_TOKEN_ID']
            self.token_secret = credentials['NETSUITE_TOKEN_SECRET']
            self.account = credentials['NETSUITE_ACCOUNT']
        else:
            # Get credentials from environment variables with validation
            required_vars = ['NETSUITE_CONSUMER_KEY', 'NETSUITE_CONSUMER_SECRET',
                             'NETSUITE_TOKEN_ID', 'NETSUITE_TOKEN_SECRET', 'NETSUITE_ACCOUNT']
            
            self.credentials = {}
            for var in required_vars:
                value = os.environ.get(var)
                if not value:
                    raise ValueError(f"Missing required environment variable: {var}")
                self.credentials[var] = value
                
            self.consumer_key = self.credentials['NETSUITE_CONSUMER_KEY']
            self.consumer_secret = self.credentials['NETSUITE_CONSUMER_SECRET']
            self.token_id = self.credentials['NETSUITE_TOKEN_ID']
            self.token_secret = self.credentials['NETSUITE_TOKEN_SECRET']
            self.account = self.credentials['NETSUITE_ACCOUNT']
        
        # Build base URL using account number
        self.base_url = f"https://{self.account}.restlets.api.netsuite.com/app/site/hosting/restlet.nl"

    def generate_oauth_header(self, url, method, params=None, data=None):
        """Generate OAuth 1.0a header for NetSuite"""
        # Generate timestamp and nonce
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4()).replace('-', '')

        # Extract query parameters from URL if any
        url_parts = urllib.parse.urlparse(url)
        query_params = dict(parse_qsl(url_parts.query))

        # Base URL without query string
        base_url = f"{url_parts.scheme}://{url_parts.netloc}{url_parts.path}"

        # Start with required OAuth parameters
        oauth_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_token': self.token_id,
            'oauth_signature_method': 'HMAC-SHA256',
            'oauth_timestamp': timestamp,
            'oauth_nonce': nonce,
            'oauth_version': '1.0',
        }

        # Combine all parameters for signature base string
        all_params = {}
        all_params.update(oauth_params)

        # Add URL query parameters
        if query_params:
            all_params.update(query_params)

        # Add regular parameters if any
        if params:
            all_params.update(params)

        # Sort parameters alphabetically by key as required by OAuth
        sorted_params = sorted(all_params.items())

        # Construct normalized parameter string
        param_string = '&'.join([f"{self.encode_rfc3986(k)}={self.encode_rfc3986(v)}" for k, v in sorted_params])

        # Construct signature base string
        signature_base = f"{method.upper()}&{self.encode_rfc3986(base_url)}&{self.encode_rfc3986(param_string)}"

        # Create signing key
        signing_key = f"{self.encode_rfc3986(self.consumer_secret)}&{self.encode_rfc3986(self.token_secret)}"

        # Calculate signature
        signature = hmac.new(
            signing_key.encode('utf-8'),
            signature_base.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature).decode('utf-8')

        # Add signature to OAuth parameters
        oauth_params['oauth_signature'] = signature

        # Construct Authorization header
        auth_header = 'OAuth ' + ', '.join([
            f'realm="{self.encode_rfc3986(self.account)}"',
        ] + [
            f'{k}="{self.encode_rfc3986(v)}"' for k, v in oauth_params.items()
        ])

        return auth_header

    def encode_rfc3986(self, text):
        """Encode string according to RFC 3986"""
        if not isinstance(text, str):
            text = str(text)
        return quote(text, safe='~')

    def hit_api(self, script_id, deploy_id=1, method="GET", data=None, headers=None, additional_params=None):
        """
        Improved API method that accepts script_id and deploy_id directly
        
        Args:
            script_id (str): NetSuite script ID
            deploy_id (str/int): NetSuite deployment ID, defaults to 1
            method (str): HTTP method (GET, POST, etc)
            data (dict): Payload to send
            headers (dict): Additional headers
            additional_params (dict): Additional URL parameters
            
        Returns:
            dict: API response
        """
        # Build params dictionary
        params = {
            "script": str(script_id),
            "deploy": str(deploy_id)
        }
        
        # Add any additional parameters
        if additional_params:
            params.update(additional_params)
            
        # Build full URL
        url = self.base_url
        
        # Initialize headers if None
        if headers is None:
            headers = {}
            
        # Set default content type for data requests
        if data and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
            
        # Generate OAuth header
        auth_header = self.generate_oauth_header(url, method, params, data)
        headers['Authorization'] = auth_header

        # Log request details at DEBUG level
        logger.info(f"NetSuite API Request: {method} {url}")
        logger.info(f"Params: {params}")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Data: {data}")

        # Set timeout to avoid hanging requests
        timeout = 30  # seconds
        
        # Make the request with retry logic
        max_retries = 3
        retry_count = 0
        retry_delay = 5  # seconds
        
        while retry_count < max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=timeout
                )
                
                # Try to get JSON response
                try:
                    result = response.json()
                except ValueError:
                    result = {"raw_response": response.text}
                
                # Check for successful response
                if response.status_code == 200:
                    return result
                    
                # Handle rate limiting with exponential backoff
                elif response.status_code == 429:
                    wait_time = retry_delay * (2 ** retry_count)
                    logger.warning(f"Rate limited by NetSuite API. Waiting {wait_time} seconds before retry.")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                    
                # Log error details
                else:
                    logger.error(f"NetSuite API Error: Status Code {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return {
                        "error": response.text,
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timed out. Retry {retry_count + 1}/{max_retries}")
                retry_count += 1
                time.sleep(retry_delay)
                continue
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                return {"error": str(e), "status_code": 500}
        
        # If we've exhausted retries
        return {"error": "Maximum retries exceeded", "status_code": 500}


def parse_date_string(date_string):
    """
    Parse various date formats and return a datetime object
    
    Supported formats:
    - YYYY-MM-DD (e.g., "2025-05-27")
    - ISO 8601 with timezone (e.g., "2025-05-27T00:00:00.000Z")
    - ISO 8601 without timezone (e.g., "2025-05-27T00:00:00")
    - DD.MM.YYYY (already in target format)
    
    Args:
        date_string (str): Date string to parse
        
    Returns:
        datetime: Parsed datetime object or None if parsing fails
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    # Strip whitespace
    date_string = date_string.strip()
    
    # If already in DD.MM.YYYY format, don't parse it
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_string):
        logger.debug(f"Date already in DD.MM.YYYY format: {date_string}")
        return None
    
    # List of date formats to try
    date_formats = [
        '%Y-%m-%d',                    # 2025-05-27
        '%Y-%m-%dT%H:%M:%S.%fZ',      # 2025-05-27T00:00:00.000Z
        '%Y-%m-%dT%H:%M:%SZ',         # 2025-05-27T00:00:00Z
        '%Y-%m-%dT%H:%M:%S.%f',       # 2025-05-27T00:00:00.000
        '%Y-%m-%dT%H:%M:%S',          # 2025-05-27T00:00:00
        '%Y-%m-%d %H:%M:%S',          # 2025-05-27 00:00:00
        '%m/%d/%Y',                   # 05/27/2025
        '%d/%m/%Y',                   # 27/05/2025
    ]
    
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_string, fmt)
            logger.debug(f"Successfully parsed '{date_string}' using format '{fmt}'")
            return date_obj
        except ValueError:
            continue
    
    logger.warning(f"Could not parse date string: {date_string}")
    return None


def format_date_fields(payload):
    """
    Process payload to convert date fields from various formats to DD.MM.YYYY format
    
    Args:
        payload (dict): The payload to process
        
    Returns:
        dict: The processed payload
    """
    if not payload or not isinstance(payload, dict):
        return payload
        
    # Process date fields in the body if it exists and is a list
    if 'body' in payload and isinstance(payload['body'], list):
        for item in payload['body']:
            if (isinstance(item, dict) and 
                item.get('field_id') == 'custrecord_rg_scr_date' and 
                item.get('type') == 'date' and 
                'value' in item):
                
                original_value = item['value']
                
                # Try to parse the date
                date_object = parse_date_string(original_value)
                
                if date_object:
                    # Convert to DD.MM.YYYY format
                    formatted_date = date_object.strftime('%d.%m.%Y')
                    item['value'] = formatted_date
                    logger.info(f"Reformatted date from '{original_value}' to '{formatted_date}'")
                else:
                    logger.warning(f"Could not parse date: {original_value}. Leaving it as is.")
    
    # Also check for date fields in other parts of the payload
    # This is a recursive approach to handle nested structures
    def process_nested_dates(obj, path=""):
        """Recursively process date fields in nested structures"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check if this looks like a date field
                if (isinstance(value, str) and 
                    (key.lower().endswith('date') or 
                     key.lower().endswith('_date') or
                     'date' in key.lower())):
                    
                    date_object = parse_date_string(value)
                    if date_object:
                        formatted_date = date_object.strftime('%d.%m.%Y')
                        obj[key] = formatted_date
                        logger.info(f"Reformatted nested date at '{current_path}' from '{value}' to '{formatted_date}'")
                else:
                    # Recursively process nested objects
                    process_nested_dates(value, current_path)
                    
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                process_nested_dates(item, current_path)
    
    # Process the entire payload for nested date fields
    process_nested_dates(payload)
    
    return payload


def test_netsuite_api():
    """
    Main function to test NetSuite API locally
    """
    # Your credentials
    credentials = {
        'NETSUITE_ACCOUNT': '6979138',
        'NETSUITE_CONSUMER_KEY': 'b02dd038dd43bde3165aded85004a10e19ff5c0822427ba0e8a44828fef3e44f',
        'NETSUITE_CONSUMER_SECRET': 'd94fc02c8a1102a1ac5280bc2d6a21a8ae71117390949906bd44de5f87b46e35',
        'NETSUITE_TOKEN_ID': '42ed3e4149822cc96616b6301fc9d6f4f78c9f6301b5c96c38314ac988dc8951',
        'NETSUITE_TOKEN_SECRET': 'cc85608407dee778d090c68b6e5ae34ada3c4322230e285f3a61bca913fc0663'
    }
    
    try:
        # Initialize NetSuite client with credentials
        logger.info("Initializing NetSuite client...")
        ns = NetsuiteClient(credentials=credentials)
        
        # Try different payload structures for PO line update
        payloads_to_test = [
            {
                "name": "Using internal ID",
                "payload": {
                    "id": "63651160",  # Internal ID from PO
                    "type": "purchaseorder",
                    "line_id": 2,
                    "body": [
                        {
                            "field_id": "custcol_rg_trxln_quality_control_date",
                            "value": "2025-08-15",
                            "type": "date"
                        }
                    ]
                }
            },
            {
                "name": "Using recordtype structure",
                "payload": {
                    "recordtype": "purchaseorder",
                    "id": "63651160",
                    "line": 2,
                    "body": [
                        {
                            "field_id": "custcol_rg_trxln_quality_control_date",
                            "value": "2025-08-15",
                            "type": "date"
                        }
                    ]
                }
            },
            {
                "name": "Batch update (original working structure)",
                "payload": {
                    "tran_id": "BATCH0008467",
                    "type": "customrecord_po_batches",
                    "body": [
                        {
                            "field_id": "custrecord_rg_scr_date",
                            "value": "2025-03-29",
                            "type": "date"
                        }
                    ]
                }
            }
        ]
        
        # Test each payload
        for test in payloads_to_test:
            logger.info(f"\n=== Testing: {test['name']} ===")
            payload = test['payload']
            
            logger.info(f"Original payload: {json.dumps(payload, indent=2)}")
            
            # Process date fields
            processed_payload = format_date_fields(payload)
            logger.info(f"Processed payload: {json.dumps(processed_payload, indent=2)}")
            
            # Call the NetSuite RESTlet
            logger.info("Calling NetSuite API...")
            result = ns.hit_api(
                script_id="5633",  # Using your provided script ID
                deploy_id="1",
                method="POST",
                data=processed_payload
            )
            
            # Print the result
            logger.info("API Response:")
            print(json.dumps(result, indent=2))
            print("-" * 50)
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing NetSuite API: {str(e)}", exc_info=True)
        return {"error": str(e)}


def test_specific_scenarios():
    """
    Test specific scenarios with different payloads
    """
    credentials = {
        'NETSUITE_ACCOUNT': '6979138',
        'NETSUITE_CONSUMER_KEY': 'b02dd038dd43bde3165aded85004a10e19ff5c0822427ba0e8a44828fef3e44f',
        'NETSUITE_CONSUMER_SECRET': 'd94fc02c8a1102a1ac5280bc2d6a21a8ae71117390949906bd44de5f87b46e35',
        'NETSUITE_TOKEN_ID': '42ed3e4149822cc96616b6301fc9d6f4f78c9f6301b5c96c38314ac988dc8951',
        'NETSUITE_TOKEN_SECRET': 'cc85608407dee778d090c68b6e5ae34ada3c4322230e285f3a61bca913fc0663'
    }
    
    ns = NetsuiteClient(credentials=credentials)
    
    # Test 1: GET request (no payload)
    logger.info("\n=== Test 1: GET Request ===")
    result = ns.hit_api(
        script_id="5633",
        deploy_id="1",
        method="GET"
    )
    print(json.dumps(result, indent=2))
    
    # Test 2: POST with correct payload structure
    logger.info("\n=== Test 2: POST with Date Conversion ===")
    test_payload = {
        "tran_id": "BATCH0008467",
        "type": "customrecord_po_batches",
        "body": [
            {
                "field_id": "custrecord_rg_scr_date",
                "value": "2025-05-27T00:00:00.000Z",
                "type": "date"
            }
        ]
    }
    processed = format_date_fields(test_payload)
    result = ns.hit_api(
        script_id="5633",
        deploy_id="1",
        method="POST",
        data=processed
    )
    print(json.dumps(result, indent=2))
    
    # Test 3: POST with multiple fields
    logger.info("\n=== Test 3: POST with Multiple Fields ===")
    test_payload2 = {
        "tran_id": "BATCH0008468",
        "type": "customrecord_po_batches",
        "body": [
            {
                "field_id": "custrecord_rg_scr_date",
                "value": "2025-03-29",
                "type": "date"
            },
            {
                "field_id": "some_other_field",
                "value": "test value",
                "type": "text"
            }
        ]
    }
    processed2 = format_date_fields(test_payload2)
    result2 = ns.hit_api(
        script_id="5633",
        deploy_id="1",
        method="POST",
        data=processed2
    )
    print(json.dumps(result2, indent=2))


if __name__ == "__main__":
    # Run the main test
    logger.info("Starting NetSuite API test...")
    test_netsuite_api()
    
    # Uncomment to run additional scenario tests
    # test_specific_scenarios()