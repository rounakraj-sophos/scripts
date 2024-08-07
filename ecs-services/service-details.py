import boto3
import os
from botocore.config import Config
from botocore.exceptions import ClientError
import json
from datetime import datetime
import time
import csv

result = []
file_path = 'aws-prod.json'
csv_file_name = 'services-list-prod.csv'

accounts = [

    {
        "accountNo": "", # AWS Account No.
        "regions": ["us-west-2", "us-east-2", "eu-central-1", "eu-west-1"],
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": ""
    },

    {
        "accountNo": "",
        "regions": ["ca-central-1"],
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": ""
    },

]

service_set = ("service1Name", "service2Name")


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # or use any other string format
        return super().default(obj)


def describe_tasks_with_backoff(ecs_client, cluster_name, task_arns, max_attempts=5):
    attempt = 0
    while attempt < max_attempts:
        try:
            response = ecs_client.describe_tasks(
                cluster=cluster_name,
                tasks=task_arns
            )
            return response['tasks']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                attempt += 1
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Throttling exception occurred. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise  # Re-raise the exception if it's not a throttling exception
    raise Exception("Max retries exceeded")


def list_tasks_with_backoff(ecs_client, cluster_name, service_name, max_attempts=5):
    attempt = 0
    while attempt < max_attempts:
        try:
            response = ecs_client.list_tasks(
                cluster=cluster_name,
                serviceName=service_name
            )
            return response['taskArns']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                attempt += 1
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Throttling exception occurred. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise  # Re-raise the exception if it's not a throttling exception
    raise Exception("Max retries exceeded")


def list_ecs_clusters_and_services_with_details(region, session):
    # Create an ECS client
    ecs_client = session.client('ecs', region_name=region)

    # List all ECS clusters
    clusters = ecs_client.list_clusters()
    cluster_arns = clusters['clusterArns']

    # Dictionary to store cluster and services mapping with details
    cluster_services_details = {}

    for cluster_arn in cluster_arns:

        service_arns = []
        next_token = None

        while True:
            if next_token:
                response = ecs_client.list_services(cluster=cluster_arn, nextToken=next_token)
            else:
                response = ecs_client.list_services(cluster=cluster_arn)

            service_arns.extend(response['serviceArns'])

            next_token = response.get('nextToken')
            if not next_token:
                break

        # Get detailed information about each service

        service_details = []
        service_count = 0
        for service_arn in service_arns:

            service_description = ecs_client.describe_services(
                cluster=cluster_arn,
                services=[service_arn]
            )

            for service in service_description['services']:
                service_count = service_count + 1

                temp_service_details = {
                    'serviceName': service['serviceName'],
                    'serviceArn': service['serviceArn'],
                    'runningCount': service['runningCount'],
                    'desiredCount': service['desiredCount']
                }

                tasks_arns = list_tasks_with_backoff(ecs_client, cluster_name, service['serviceName'])

                if tasks_arns:
                    tasks_info = describe_tasks_with_backoff(ecs_client, cluster_name, [tasks_arns[0]])

                    for task in tasks_info:
                        temp_service_details["cpu"] = task['cpu']
                        temp_service_details["memory"] = task['memory']

                        temp_service_details["cpuvCPU"] = int(task['cpu']) / 1024
                        temp_service_details["memoryInGB"] = int(task['memory']) / 1024

                else:
                    temp_service_details["noTaskFound"] = True

                service_details.append(temp_service_details)

        if service_details:
            cluster_services_details[cluster_arn] = service_details

    return cluster_services_details


def list_account_region():
    for account in accounts:

        # Create a session for each account
        session = boto3.Session(
            aws_access_key_id=account["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=account["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=account["AWS_SESSION_TOKEN"]
        )

        print("Running for account: ", account["accountNo"])

        regions = account["regions"]

        for region in regions:
            print("Running for region: ", region)
            temp_result = {}
            temp_result["account"] = account["accountNo"]
            temp_result["region"] = region
            temp_result["clusters"] = list_ecs_clusters_and_services_with_details(region, session)
            result.append(temp_result)

    with open(file_path, 'w') as file:
        json.dump(result, file, cls=DateTimeEncoder, indent=4)


def read_data_and_create_csv():
    final_result = {}
    with open(file_path, 'r') as file:

        raw_data = json.load(file)

        for data in raw_data:
            accountNo = '#' + str(data["account"])
            region = data["region"]

            for cluster_arn, services in data["clusters"].items():
                cluster_name = cluster_arn.split('/')[-1]

                for service in services:
                    serviceName = service["serviceName"]

                    serviceInfo = {

                        "Service Name": serviceName,
                        "Region": region,
                        "AWS Account": accountNo,
                        "Cluster Name": cluster_name,
                        "Desired Count": service["desiredCount"],
                        "Running Count": service["runningCount"],
                        "vCPU": service.get("cpuvCPU", "NA"),
                        "MemoryInGB": service.get("memoryInGB", "NA")
                    }

                    if serviceName not in final_result:
                        final_result[serviceName] = []  # Initialize the list if the key doesn't exist

                    final_result[serviceName].append(serviceInfo)

    final_result = dict(sorted(final_result.items()))

    with open(csv_file_name, mode='w', newline='') as csv_file:
        # Create a CSV writer object
        writer = csv.DictWriter(csv_file, fieldnames=['#', 'Service Name', 'Region', 'AWS Account', 'Cluster Name',
                                                      'Desired Count', 'Running Count', 'vCPU', 'MemoryInGB'])

        # Write the header (field names)
        writer.writeheader()

        service_count = 0

        for serviceName, serviceInfoList in final_result.items():

            if serviceName in service_set:
                service_count = service_count + 1
                service_unique_count = 0
                for serviceInfo in serviceInfoList:
                    service_unique_count = service_unique_count + 1
                    if service_unique_count == 1:
                        serviceInfo["#"] = service_count
                    else:
                        serviceInfo["Cluster Name"] = ''
                        serviceInfo["Service Name"] = ''

                    # Write the data rows
                    writer.writerow(serviceInfo)

    print(f"CSV file '{csv_file_name}' created successfully.")


if __name__ == "__main__":
    # list_account_region()
    read_data_and_create_csv()
