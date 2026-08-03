#!/usr/bin/env python3
"""
Examples of how to use site-specific client secret authentication with the SDS Middleware.

This file demonstrates various authentication scenarios with code examples.
"""

import requests
from typing import Dict, Optional

# Example configuration (replace with your actual values)
BASE_URL = "http://your-server.com"
DEFAULT_CLIENT_SECRET = "your-default-client-secret-here"
SITE_SECRETS = {
    "site1": "site1-secret-key-12345",
    "site2": "site2-secret-key-67890", 
    "site3": "site3-secret-key-abcde"
}

def make_request_with_auth(
    endpoint: str = "/", 
    site: Optional[str] = None,
    client_ip: str = "192.168.1.100",
    auth_method: str = "header"
) -> requests.Response:
    """
    Make a request with proper authentication based on site.
    
    Args:
        endpoint: API endpoint to call
        site: Site identifier (site1, site2, site3, etc.)
        client_ip: Client IP address (for testing)
        auth_method: Authentication method ('header', 'bearer', 'query')
    
    Returns:
        Response object
    """
    # Determine which secret to use
    if site and site in SITE_SECRETS:
        secret = SITE_SECRETS[site]
    else:
        secret = DEFAULT_CLIENT_SECRET
    
    # Set up headers
    headers = {"X-Forwarded-For": client_ip}
    
    # Add site header if specified
    if site:
        headers["X-Site"] = site
    
    # Add authentication based on method
    if auth_method == "bearer":
        headers["Authorization"] = f"Bearer {secret}"
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers)
    elif auth_method == "header":
        headers["X-Client-Secret"] = secret
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers)
    elif auth_method == "query":
        params = {"client_secret": secret}
        if site:
            params["site"] = site
        return requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params)
    else:
        raise ValueError(f"Unknown auth method: {auth_method}")


def example_requests():
    """Show examples of different authentication scenarios."""
    
    print("=== Site-Specific Authentication Examples ===\n")
    
    # Example 1: Default authentication (no site specified)
    print("1. Default authentication (no site):")
    print("   curl -H 'X-Client-Secret: your-default-client-secret-here' http://your-server.com/")
    print("   Python:")
    print("   response = make_request_with_auth()")
    print()
    
    # Example 2: Site1 authentication with header
    print("2. Site1 authentication with X-Client-Secret header:")
    print("   curl -H 'X-Site: site1' -H 'X-Client-Secret: site1-secret-key-12345' http://your-server.com/")
    print("   Python:")
    print("   response = make_request_with_auth(site='site1', auth_method='header')")
    print()
    
    # Example 3: Site2 authentication with Bearer token
    print("3. Site2 authentication with Bearer token:")
    print("   curl -H 'X-Site: site2' -H 'Authorization: Bearer site2-secret-key-67890' http://your-server.com/")
    print("   Python:")
    print("   response = make_request_with_auth(site='site2', auth_method='bearer')")
    print()
    
    # Example 4: Site3 authentication with query parameters
    print("4. Site3 authentication with query parameters:")
    print("   curl 'http://your-server.com/?site=site3&client_secret=site3-secret-key-abcde'")
    print("   Python:")
    print("   response = make_request_with_auth(site='site3', auth_method='query')")
    print()
    
    # Example 5: Localhost request (no auth needed)
    print("5. Localhost request (no authentication required):")
    print("   curl http://localhost:8080/")
    print("   Python:")
    print("   response = requests.get('http://localhost:8080/')")
    print()
    
    # Example 6: Using different site headers
    print("6. Alternative site header methods:")
    print("   # Using X-Site-ID header")
    print("   curl -H 'X-Site-ID: site1' -H 'X-Client-Secret: site1-secret-key-12345' http://your-server.com/")
    print()
    print("   # Using site query parameter")
    print("   curl 'http://your-server.com/?site=site1&client_secret=site1-secret-key-12345'")
    print()


def validation_scenarios():
    """Show validation scenarios and expected responses."""
    
    print("=== Validation Scenarios ===\n")
    
    scenarios = [
        {
            "description": "Valid site1 request with correct secret",
            "site": "site1",
            "secret": SITE_SECRETS["site1"],
            "expected": "200 OK"
        },
        {
            "description": "Site1 request with wrong secret",
            "site": "site1", 
            "secret": "wrong-secret",
            "expected": "401 Unauthorized"
        },
        {
            "description": "Site1 request with default secret",
            "site": "site1",
            "secret": DEFAULT_CLIENT_SECRET,
            "expected": "401 Unauthorized (if site1 has its own secret)"
        },
        {
            "description": "Unknown site with default secret",
            "site": "unknown_site",
            "secret": DEFAULT_CLIENT_SECRET,
            "expected": "200 OK"
        },
        {
            "description": "No site specified with default secret",
            "site": None,
            "secret": DEFAULT_CLIENT_SECRET,
            "expected": "200 OK"
        },
        {
            "description": "External request with no authentication",
            "site": None,
            "secret": None,
            "expected": "401 Unauthorized"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario['description']}")
        print(f"   Expected: {scenario['expected']}")
        
        # Build curl command
        curl_cmd = "curl"
        if scenario['site']:
            curl_cmd += f" -H 'X-Site: {scenario['site']}'"
        if scenario['secret']:
            curl_cmd += f" -H 'X-Client-Secret: {scenario['secret']}'"
        curl_cmd += " -H 'X-Forwarded-For: 192.168.1.100'"  # Simulate external request
        curl_cmd += " http://your-server.com/"
        
        print(f"   Command: {curl_cmd}")
        print()


def main():
    """Main function to run all examples."""
    example_requests()
    validation_scenarios()
    
    print("=== Configuration Reference ===")
    print("Make sure your .env file contains:")
    print("""
[webserver]
client_secret=your-default-client-secret-here

[site_site1]
client_secret=site1-secret-key-12345

[site_site2]
client_secret=site2-secret-key-67890

[site_site3]
client_secret=site3-secret-key-abcde
""")


if __name__ == "__main__":
    main()
