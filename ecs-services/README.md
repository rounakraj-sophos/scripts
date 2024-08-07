# ECS Service Resource Information Script

This script retrieves detailed information about ECS services running across multiple AWS accounts and regions, including the number of vCPUs and memory allocated to each service. It outputs the gathered data into a JSON file and a structured CSV file.

## Prerequisites

- Python 3.x
- Boto3 library

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/ecs-resource-info.git
   cd ecs-resource-info
   ```

2. **Install required Python packages:**

   Ensure you have `boto3` installed. You can install it using pip:

   ```bash
   pip install boto3
   ```

## Configuration

Update the `accounts` list in the script with the necessary AWS credentials and regions for each account:

```python
accounts = [
    {
        "accountNo": "", // AWS Account No. 
        "regions": ["us-west-2", "us-east-2", "eu-central-1", "eu-west-1"],
        "AWS_ACCESS_KEY_ID": "your_access_key_id",
        "AWS_SECRET_ACCESS_KEY": "your_secret_access_key",
        "AWS_SESSION_TOKEN": "your_session_token"
    },
    // Add additional accounts as needed
]
```

## Usage

1. **Run the script:**

   Before running the script, you need to set the `service_set`, this will create CSV for only those services that are present in the set.

   The script is divided into two main functions: `list_account_region()` and `read_data_and_create_csv()`. The `list_account_region()` function collects data from AWS, and the `read_data_and_create_csv()` function reads the JSON data and generates a CSV file. Ensure to uncomment `list_account_region()` during the initial run to fetch data.

   ```bash
   python service-details.py
   ```

2. **Output:**

   - `aws-prod.json`: A JSON file containing detailed information about ECS services, including CPU and memory allocation.
   - `services-list-prod.csv`: A CSV file listing selected services with their resource information.

## Script Details

- **Exponential Backoff:** The script handles throttling exceptions using exponential backoff for API calls.
- **Service Set Filtering:** The script filters services based on a predefined set of service names (`service_set`).
- **Resource Conversion:** CPU units are converted to vCPU, and memory units are converted to GB for better readability.
