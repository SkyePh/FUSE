import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib.parse

BASE_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals"

#identifier parts
PROGRAM = "HORIZON"
CLUSTER = "CL4"
YEAR = "2024"
CALL_TYPE = "TWIN-TRANSITION"
CALL_NUMBER = "01"

#build the call identifier
call_identifier = f"{PROGRAM}-{CLUSTER}-{YEAR}-{CALL_TYPE}-{CALL_NUMBER}"

#params
CALL_PARAMS = {
    "order": "DESC",
    "pageNumber": 1,
    "pageSize": 50,
    "sortBy": "startDate",
    "isExactMatch": "true",
    "status": "31094501,31094502,31094503",
    "callIdentifier": call_identifier
}

def construct_call_url(base_url, params):
    # Construct the URL by encoding the parameters
    query_string = urllib.parse.urlencode(params, doseq=True)
    return f"{base_url}?{query_string}"

def getCalls(url, params, pageNumber=None):
    
    params["pageNumber"] = pageNumber
    
    # Send a GET request
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch page {pageNumber}. Status code: {response.status_code}")
        return None

#final url
call_url = construct_call_url(BASE_URL, CALL_PARAMS)

print(call_url)
# Example: Fetch the first page
html_content = getCalls(call_url, CALL_PARAMS)
#print(html_content)  # For testing
