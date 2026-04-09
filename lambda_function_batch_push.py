import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from urllib.parse import quote, parse_qsl
import requests
import uuid

class NetsuiteClient:
    def __init__(self):
        # Replace with your credentials
        self.consumer_key = 'a0046767571ceccbb340ac5305c84a0694ce1a833df67fdf20f1c2015ea3e5a2'
        self.consumer_secret = 'b3f582b9051c60b3e6d5b2efa5a6f98b124cb594c3f8138e8eefbd7ef962a36a'
        self.token_id = 'e350228e9a78a26e0ecb697deb305b946629118d997dd7b4a494a280fae93c49'
        self.token_secret = '92f9dfa04c2ee4dd6c0bd0ae996ba21f34c532a2876ae0de17bc6756c64e0180'
        self.account = '6979138_SB1'
        self.rest_api_root = f"https://{self.account.lower().replace('_','-')}.suitetalk.api.netsuite.com"
        
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
    
    def hit_api(self, url, method, params=None, data=None, headers=None):
        if url.startswith("/"):
            url = self.rest_api_root + url
            
        if headers is None:
            headers = {}
            
        # Generate OAuth header
        auth_header = self.generate_oauth_header(url, method, params, data)
        headers['Authorization'] = auth_header
        
        if data and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
            
        # For debugging
        print(f"URL: {url}")
        print(f"Method: {method}")
        print(f"Headers: {headers}")
        print(f"Data: {data}")
        
        # Make the request
        response = requests.request(
            method=method, 
            url=url, 
            json=data, 
            params=params, 
            headers=headers
        )
        
        try:
            result = response.json()
        except:
            result = {"raw_response": response.text}
            
        if response.status_code == 200:
            return result
        elif response.status_code == 429:
            time.sleep(10)
            return self.hit_api(url, method, params, data, headers)
        else:
            return {"error": response.text, "status_code": response.status_code, "headers": dict(response.headers)}


def lambda_handler(event, context):
    try:
        # For testing directly
        ns = NetsuiteClient()
        
        # Define payload
        payload = {
            'tran_id': 'BATCH0006541',
            'type': 'customrecord_po_batches',
            'body': [
                {
                    'field_id': 'custrecord_rg_scr_date',
                    'value': '25.03.2025',
                    'type': 'date'
                }
            ]
        }
        
        # Use the specific RESTlet URL
        url = "https://6979138-sb1.restlets.api.netsuite.com/app/site/hosting/restlet.nl"
        params = {
            "script": "5328",
            "deploy": "1"
        }
        
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }
        
        # Make API call
        result = ns.hit_api(url, method, params=params, data=payload, headers=headers)
        
        # If we're called from API Gateway
        if event and 'body' in event:
            try:
                # Get payload from the event
                api_payload = json.loads(event['body'])
                # Use it instead of our test payload
                result = ns.hit_api(url, method, params=params, data=api_payload, headers=headers)
            except Exception as e:
                print(f"Error processing API Gateway request: {str(e)}")
                # Continue with test payload
        
        return {
            "statusCode": 200 if "error" not in result else result.get("status_code", 500),
            "body": json.dumps(result)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }