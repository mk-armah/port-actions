import argparse
import json
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description='Send POST request with JSON data.')
    parser.add_argument('--data', required=True, help='JSON string containing the data to be sent.')
    args = parser.parse_args()
  
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError:
        logging.error("Invalid JSON input.")
        return

    url = "https://api.getport.io/v1/blueprints/doraMetrics/entities"

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raises a HTTPError for bad responses
        logging(f"Response Status Code:  {response.status_code}")
        print(f"Response Body: {response.json()}")
    except requests.RequestException as e:
        logging.error(f"An error occurred while making the POST request: {e}")

if __name__ == "__main__":
    main()
