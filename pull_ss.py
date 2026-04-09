import json
import csv
import requests
from time import sleep
from authlib.integrations.requests_client import OAuth1Auth
from authlib.oauth1.rfc5849.client_auth import ClientAuth
from authlib.oauth1.rfc5849.signature import generate_signature_base_string
from oauthlib.oauth1.rfc5849.signature import sign_hmac_sha256

class NetsuiteClient:
    """
    NetSuite client using OAuth 1.0 authentication for accessing NetSuite RESTlets and APIs
    """
    
    def __init__(self, consumer_key, consumer_secret, token_id, token_secret, account_id):
        """
        Initialize the NetSuite client with OAuth credentials
        
        Parameters:
        -----------
        consumer_key : str
            Consumer key for the NetSuite integration
        consumer_secret : str
            Consumer secret for the NetSuite integration
        token_id : str
            Token ID for the NetSuite integration
        token_secret : str
            Token secret for the NetSuite integration
        account_id : str
            NetSuite account ID (e.g., '6979138_SB1')
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token_id = token_id
        self.token_secret = token_secret
        self.account = account_id
        self.oauth_signature_method = "HMAC-SHA256"
        self.account_domain = account_id.lower().replace('_', '-')
        self.rest_api_root = f"https://{self.account_domain}.suitetalk.api.netsuite.com"
        self.restlet_api_root = f"https://{self.account_domain}.restlets.api.netsuite.com"
        
        # Set up the session with OAuth authentication
        self.setup_session()

    def authlib_hmac_sha256_sign_method(self, client, request):
        """
        Custom signature method for HMAC-SHA256
        """
        base_string = generate_signature_base_string(request)
        return sign_hmac_sha256(base_string, client.client_secret, client.token_secret)

    def setup_session(self):
        """
        Set up a requests session with OAuth 1.0 authentication
        """
        # Register the HMAC-SHA256 signature method
        ClientAuth.register_signature_method(
            "HMAC-SHA256", self.authlib_hmac_sha256_sign_method
        )
        
        # Create OAuth authentication object
        auth = OAuth1Auth(
            client_id=self.consumer_key,
            client_secret=self.consumer_secret,
            token=self.token_id,
            token_secret=self.token_secret,
            realm=self.account,
            signature_method=self.oauth_signature_method,
        )
        
        # Create and configure session
        self.session = requests.Session()
        self.session.auth = auth

    def hit_api(self, url, method, params=None, data=None, headers=None):
        """
        Make an API request to NetSuite
        
        Parameters:
        -----------
        url : str
            The URL to request
        method : str
            HTTP method (GET, POST, etc.)
        params : dict, optional
            Query parameters
        data : dict, optional
            JSON data for the request body
        headers : dict, optional
            HTTP headers
            
        Returns:
        --------
        dict
            Response data or error information
        """
        if url.startswith("/"):
            url = self.rest_api_root + url
            
        # Default headers if none provided
        if headers is None:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
        
        try:
            # Make the request
            response = self.session.request(
                method=method, url=url, json=data, params=params, headers=headers
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                print("Rate limited. Waiting 10 seconds before retrying...")
                sleep(10)
                return self.hit_api(url, method, params, data, headers)

            # Print raw response details
            print(f"\n=== RAW RESPONSE DEBUG ===")
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Raw Text: {response.text}")
            print(f"Raw Content Length: {len(response.content)}")
            print(f"=== END RAW RESPONSE ===\n")

            # Try to parse JSON response
            try:
                result = response.json()
            except json.JSONDecodeError:
                # If not JSON, return text
                result = {"content": response.text}

            # Add status code to result
            if response.status_code != 200:
                result = {"error": result if isinstance(result, dict) else {"content": result},
                          "status_code": response.status_code}

            return result
            
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status_code": 500}

    def get_saved_search_metadata(self, search_id):
        """
        Get saved search metadata including the name

        Parameters:
        -----------
        search_id : str
            The internal ID of the saved search

        Returns:
        --------
        dict
            Saved search metadata or error information
        """
        url = f"/services/rest/record/v1/savedsearch/{search_id}"

        print(f"Fetching metadata for saved search {search_id}...")
        result = self.hit_api(url, "GET")

        # Extract name if successful
        if "error" not in result and isinstance(result, dict):
            return {
                "id": result.get("id"),
                "title": result.get("title"),
                "scriptid": result.get("scriptid")
            }

        return result

    def fetch_saved_search(self, script_id, deploy_id, search_id, additional_params=None):
        """
        Fetch data from a saved search using a RESTlet

        Parameters:
        -----------
        script_id : str
            The script ID of the RESTlet
        deploy_id : str
            The deployment ID of the RESTlet
        search_id : str
            The internal ID of the saved search
        additional_params : dict, optional
            Additional parameters to include in the request

        Returns:
        --------
        dict
            Response data or error information
        """
        # Construct RESTlet URL
        url = f"{self.restlet_api_root}/app/site/hosting/restlet.nl"

        # Set up parameters - using searchid (no underscore) as query param like the browser URL
        params = {
            "script": script_id,
            "deploy": deploy_id,
            "searchid": search_id  # Changed from sending in POST body to query param
        }

        # Add any additional parameters
        if additional_params:
            params.update(additional_params)

        # Make the request using GET like the browser does
        print(f"Fetching saved search {search_id} using script {script_id}...")
        print(f"URL: {url}")
        print(f"Params: {params}")

        return self.hit_api(url, "GET", params=params)


def json_to_csv(json_data, csv_filename):
    """
    Convert NetSuite JSON response to CSV format

    Parameters:
    -----------
    json_data : dict or list
        The JSON response from NetSuite (expects {"success": true, "data": [...]})
    csv_filename : str
        Output CSV filename

    Returns:
    --------
    bool
        True if successful, False otherwise
    """
    try:
        # Extract the data array
        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"]
        elif isinstance(json_data, list):
            records = json_data
        else:
            print("Error: Unexpected JSON format")
            return False

        if not records:
            print("No records to convert")
            return False

        # Flatten nested structures and collect all unique keys
        flattened_records = []
        all_keys = set()

        for record in records:
            flattened = {}
            for key, value in record.items():
                # Handle list of dicts (like item, custcol_rg_marketplace, etc.)
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    # Join multiple values or take first value
                    if len(value) == 1:
                        flattened[f"{key}_value"] = value[0].get("value", "")
                        flattened[f"{key}_text"] = value[0].get("text", "")
                    else:
                        # Multiple values - join them
                        flattened[f"{key}_value"] = "|".join(str(v.get("value", "")) for v in value)
                        flattened[f"{key}_text"] = "|".join(str(v.get("text", "")) for v in value)
                elif isinstance(value, list):
                    # Empty list or list of primitives
                    flattened[key] = "|".join(str(v) for v in value) if value else ""
                elif isinstance(value, dict):
                    # Single dict
                    flattened[f"{key}_value"] = value.get("value", "")
                    flattened[f"{key}_text"] = value.get("text", "")
                elif isinstance(value, bool):
                    flattened[key] = str(value).lower()
                else:
                    flattened[key] = str(value) if value is not None else ""

            flattened_records.append(flattened)
            all_keys.update(flattened.keys())

        # Sort keys for consistent column order
        fieldnames = sorted(all_keys)

        # Write to CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened_records)

        print(f"Successfully converted {len(flattened_records)} records to {csv_filename}")
        return True

    except Exception as e:
        print(f"Error converting JSON to CSV: {str(e)}")
        return False


def fetch_netsuite_saved_search(consumer_key, consumer_secret, token_id, token_secret,
                              account_id, script_id, deploy_id, search_id, search_name=None):
    """
    Standalone function to fetch a NetSuite saved search

    Parameters:
    -----------
    consumer_key : str
        Consumer key for the NetSuite integration
    consumer_secret : str
        Consumer secret for the NetSuite integration
    token_id : str
        Token ID for the NetSuite integration
    token_secret : str
        Token secret for the NetSuite integration
    account_id : str
        NetSuite account ID (e.g., '6979138_SB1')
    script_id : str
        The script ID of the RESTlet
    deploy_id : str
        The deployment ID of the RESTlet
    search_id : str
        The internal ID of the saved search
    search_name : str, optional
        The name of the saved search (used for naming output files)

    Returns:
    --------
    dict
        Response data or error information
    """
    # Create NetSuite client
    client = NetsuiteClient(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        token_id=token_id,
        token_secret=token_secret,
        account_id=account_id
    )

    # Use provided search name if available
    if search_name:
        print(f"Using provided search name: {search_name}")

    # Try multiple parameter variations if needed
    variations = [
        # Basic search_id parameter
        {},
            
        # Using searchId instead (some RESTlets use different naming)
        {"searchId": search_id, "search_id": None},
            
        # Add search type
        {"recordType": "customrecord_rg_automated_dto_plan"},
            
        # Using different parameter names
        {"id": search_id, "search_id": None},
            
        # Try with explicit type parameter
        {"type": "customrecord_rg_automated_dto_plan"}
    ]
    
    # Try each variation
    results = []
    for i, params in enumerate(variations):
        print(f"\nTrying parameter variation {i+1}: {params}")
        
        # Create a clean copy of parameters
        clean_params = {k: v for k, v in params.items() if v is not None}
        
        # Add search_id if not explicitly set to None
        if "search_id" not in params or params["search_id"] is not None:
            clean_params["search_id"] = search_id
            
        # Try the variation
        result = client.fetch_saved_search(script_id, deploy_id, search_id, clean_params)
        
        # Check if successful
        if "error" not in result:
            print("✅ Success!")
            # Add search name to result if available
            if search_name:
                result["search_name"] = search_name
            return result
            
        # Store the result for reporting
        results.append({"params": clean_params, "result": result})
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    # All variations failed
    print("\nAll parameter variations failed.")
    return {"error": "All parameter variations failed", "attempts": results}


if __name__ == "__main__":
    # Replace with your credentials
    CONSUMER_KEY = '8955874faedff2e01927c92830d7bc8facec9be50fa0de6bc9230e13c9f84ee3'
    CONSUMER_SECRET = 'e2197de50030cf186f3837038d810d07fdb40791c6f15e4f7feb032b8f5c1f7d'
    TOKEN_ID = '73b648858503d43b6bdb677acfb93bbb33435795aaca1d988e039fe5853b9b06'
    TOKEN_SECRET = 'bcc76dd07d05565a890f5d6e34424f4e949be1b0d5861d68327f701e56585f32'
    ACCOUNT_ID = '6979138_SB1'
    
    # Replace with your RESTlet script ID, deployment ID, and saved search ID
    SCRIPT_ID = '6573'
    DEPLOY_ID = '1'
    SEARCH_ID = '102684'
    SEARCH_NAME = None  # Optional: Set to the saved search name (e.g., "Purchase_Orders_Report")

    # Fetch the saved search
    result = fetch_netsuite_saved_search(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        token_id=TOKEN_ID,
        token_secret=TOKEN_SECRET,
        account_id=ACCOUNT_ID,
        script_id=SCRIPT_ID,
        deploy_id=DEPLOY_ID,
        search_id=SEARCH_ID,
        search_name=SEARCH_NAME
    )
    
    # Print the result
    if "error" not in result:
        print("\n=== Saved Search Results ===")

        # Determine filenames based on search_name from result
        search_name = result.get("search_name", "saved_search_results")
        # Sanitize filename
        safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in search_name)
        safe_filename = safe_filename.strip().replace(' ', '_')

        json_filename = f"{safe_filename}.json"
        csv_filename = f"{safe_filename}.csv"

        # Save to file for easier viewing
        with open(json_filename, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to {json_filename}")

        # Convert to CSV
        json_to_csv(result, csv_filename)

        # Print sample if it's a list
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            print(f"Retrieved {len(data)} records")
            for i, record in enumerate(data[:3]):  # Print first 3 records as preview
                print(f"\nRecord {i+1}:")
                for key, value in record.items():
                    print(f"  {key}: {value}")

            if len(data) > 3:
                print(f"\n... and {len(data) - 3} more records")
        elif isinstance(result, list):
            print(f"Retrieved {len(result)} records")
            for i, record in enumerate(result[:3]):  # Print first 3 records as preview
                print(f"\nRecord {i+1}:")
                for key, value in record.items():
                    print(f"  {key}: {value}")

            if len(result) > 3:
                print(f"\n... and {len(result) - 3} more records")
        else:
            # Just print the first part of the result if it's not a list
            print(json.dumps(result, indent=2)[:1000] + "...")
    else:
        print("\n=== Error Fetching Saved Search ===")
        print(json.dumps(result, indent=2))