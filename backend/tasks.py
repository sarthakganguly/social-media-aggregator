import os
import requests
from dotenv import load_dotenv

# Load environment variables for the worker
project_root = os.path.join(os.path.dirname(__file__), '..')
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path)

def post_to_linkedin(access_token, channel_user_id, content):
    """
    This function contains the logic to post content to LinkedIn.
    It will be executed by the RQ worker in the background.
    """
    print(f"WORKER: Starting job to post '{content}' to LinkedIn.")
    
    post_url = 'https://api.linkedin.com/v2/ugcPosts'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    post_body = {
        "author": f"urn:li:person:{channel_user_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

    try:
        post_response = requests.post(post_url, headers=headers, json=post_body)
        if post_response.status_code == 201:
            print("WORKER: Successfully posted to LinkedIn.")
            return True
        else:
            print(f"WORKER: Failed to post to LinkedIn. Status: {post_response.status_code}, Body: {post_response.text}")
            return False
    except Exception as e:
        print(f"WORKER: An exception occurred while posting: {e}")
        return False
