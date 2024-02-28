import json
import os
import azure.functions as func
import logging
import requests
import html2text
import base64
from datetime import datetime
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="NotionAI")
def NotionAI(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    req_body = req.get_json()
    page_data = page_data = {
        "DateTimeReceived": {
            "date": {
            "start": req_body["DateTimeReceived"]
            }
        },
        "BodyPreview": {
            "rich_text": [
            {
                "text": {
                "content": req_body["BodyPreview"]
                }
            }
            ]
        },
        "From": {
            "email": req_body["From"]
        },
        "To": {
            "email": "eugene.r.w.12@gmail.com"
        },
        "Subject": {
            "title": [
            {
                "text": {
                "content": req_body["Subject"]
                }
            }
            ]
        }
    }
    if "Attachments" in req_body:
        page_data["Attachments"] = {
            "files": file_handler(req_body["Attachments"])
        }
    ans = post_to_notion(properties=page_data).json()
    ans.get("id")
    logging.info(page_data)
    post_to_notion_blocks(ans.get("id"), req_body["Body"])
    return func.HttpResponse(json.dumps(ans).encode('utf-8'), status_code=200)


def post_to_notion(properties=None):
    """
    Create a new page in a Notion database.

    Parameters:
    - database_id (str): The ID of the database where the new page will be added.
    - integration_token (str): The integration token (API key) for Notion API access.
    - page_data (dict): The data for the new page.

    Returns:
    - response (dict): The response from the Notion API.
    """
    database_id=os.environ["NotionDataBaseId"]
    integration_token=os.environ["NotionIntegrationToken"] 
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f'Bearer {integration_token}',
        "Content-Type": "application/json",
        "Notion-Version": "2021-05-13"  # Use the latest version supported by your integration
    }
    payload = {
        "parent": {"database_id": database_id},
        "properties": properties
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response
    else:
        raise Exception(f"Failed to post to Notion API: {response.text}")


def post_to_notion_blocks(block_id, text):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    integration_token=os.environ["NotionIntegrationToken"] 
    headers = {
        "Authorization": f'Bearer {integration_token}',
        "Content-Type": "application/json",
        "Notion-Version": "2021-05-13"  # Use the latest version supported by your integration
    }

    arr = html_to_notion_blocks(text)
    i = 0
    step = 100
    while i < len(arr):
        payload = {
            "children": arr[i: min(i+step,len(arr))]
        }
        i += step
        logging.info(url)
        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to post to Notion API: {response.text}")
    


def html_to_notion_blocks(html_string):
    x = html2text.html2text(html_string)
    results = list(filter(None, x.split("\n")))[:100]
    blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "text": [
                    {
                        "type": "text",
                        "text": {
                            "content": result
                        }
                    }
                ]
            }
        } for result in results
    ]
    return blocks


# Schema for the "Attachments" property
# "Attachments": [
#       {
#         "@odata.type": "#Microsoft.OutlookServices.FileAttachment",
#         "Id": "AQMkADAwATM0MDAAMS1iOTE2LTljYjEtMDACLTAwCgBGAAADCuE-nplZgEi8o8HCjjF4cwcAOxxRXnCPjUG1PQ7U2EgSPgAAAgEMAAAAOxxRXnCPjUG1PQ7U2EgSPgAHydwlbQAAAAESABAAsZCuznr0rEme-3ADeXDvpg==",
#         "LastModifiedDateTime": "2024-02-27T23:34:17+00:00",
#         "Name": "simple.txt",
#         "ContentType": "text/plain",
#         "Size": 208,
#         "IsInline": false,
#         "ContentId": "f_lt5081bl0",
#         "ContentBytes": "c2ltcGxl"
#       }
def file_handler(attachments):
    li = []
    for attachment in attachments:
        file_name, public_url = upload_file_to_cloud(attachment)
        x = {
                "type": "external",
                "name": f"{file_name}",
                "external": {
                    "url": f"{public_url}"
                }
            }
        li.append(x)
    return li


def format_date_with_underscore():
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y_%m_%d")
    return formatted_date


def upload_file_to_cloud(attachment):
    logging.info(attachment)
    connect_str = os.environ["AzureBlobStorageConnectionString"]
    container_name = os.environ["AzureContainerName"]
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)

    file_name = attachment["Name"]
    file_content = attachment["ContentBytes"]
    decoded_content = base64.b64decode(file_content)
    content_settings = ContentSettings(
        content_type=str(attachment["ContentType"]),
        content_disposition=f'inline; filename="{file_name}"')
    file_tag = f'{format_date_with_underscore()}_{file_name}'
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_tag)
    blob_client.upload_blob(decoded_content, content_settings=content_settings, overwrite=True)
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{file_tag}"
    
    return file_name, blob_url


if __name__ == "__main__":
    file_name = "simple.txt"
    content_bytes = "c2ltcGxl"
    decoded_content = base64.b64decode(content_bytes)
    public_url = upload_file_to_cloud(file_name, decoded_content)
    print(public_url)
