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
            NetSuite account ID (e.g., '6979138')
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token_id = token_id
        self.token_secret = token_secret
        self.account = account_id
        self.oauth_signature_method = "HMAC-SHA256"
        self.restlet_api_root = "https://6979138.restlets.api.netsuite.com"

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

            # Print response details
            print(f"\nStatus Code: {response.status_code}")
            print(f"Content Length: {len(response.content)}")

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

    def fetch_saved_search(self, script_id, deploy_id, search_id, result_type="object", search_type=None):
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
        result_type : str, optional
            Result format ('object' or 'array'), default 'object'
        search_type : str, optional
            The search type/record type (e.g., 'transaction')

        Returns:
        --------
        dict
            Response data or error information
        """
        # Construct RESTlet URL
        url = f"{self.restlet_api_root}/app/site/hosting/restlet.nl"

        # Set up parameters
        params = {
            "script": script_id,
            "deploy": deploy_id,
            "search_id": search_id,
            "result": result_type
        }

        # Add search_type if provided
        if search_type:
            params["search_type"] = search_type

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
                # Handle list of dicts
                if isinstance(value, list) and value and isinstance(value[0], dict):
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

        # Write to CSV with UTF-8 BOM for Excel compatibility with Chinese characters
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened_records)

        print(f"Successfully converted {len(flattened_records)} records to {csv_filename}")
        return True

    except Exception as e:
        print(f"Error converting JSON to CSV: {str(e)}")
        return False


if __name__ == "__main__":
    # Replace with your credentials
    CONSUMER_KEY = 'b02dd038dd43bde3165aded85004a10e19ff5c0822427ba0e8a44828fef3e44f'
    CONSUMER_SECRET = 'd94fc02c8a1102a1ac5280bc2d6a21a8ae71117390949906bd44de5f87b46e35'
    TOKEN_ID = '42ed3e4149822cc96616b6301fc9d6f4f78c9f6301b5c96c38314ac988dc8951'
    TOKEN_SECRET = 'cc85608407dee778d090c68b6e5ae34ada3c4322230e285f3a61bca913fc0663'
    ACCOUNT_ID = '6979138'

    # RESTlet configuration from your URL:
    # /app/site/hosting/restlet.nl?script=3078&deploy=1&search_id=115452&result=true&search_type=transaction
    SCRIPT_ID = '3078'
    DEPLOY_ID = '1'
    SEARCH_ID = '115452'
    RESULT_TYPE = 'object'  # or 'array'
    SEARCH_TYPE = 'transaction'

    # Create NetSuite client
    client = NetsuiteClient(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        token_id=TOKEN_ID,
        token_secret=TOKEN_SECRET,
        account_id=ACCOUNT_ID
    )

    # Fetch the saved search
    result = client.fetch_saved_search(
        script_id=SCRIPT_ID,
        deploy_id=DEPLOY_ID,
        search_id=SEARCH_ID,
        result_type=RESULT_TYPE,
        search_type=SEARCH_TYPE
    )

    # Print the result
    if "error" not in result:
        print("\n=== Saved Search Results ===")

        # Generate filenames
        safe_filename = f"search_{SEARCH_ID}_{SEARCH_TYPE}"
        json_filename = f"{safe_filename}.json"
        csv_filename = f"{safe_filename}.csv"

        # Save to JSON file with proper Unicode handling
        with open(json_filename, "w", encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
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
