import servo_control
import requests
import time
import hmac
import hashlib

DEVICE_ID = "sunshade-01"
PSK = b"secretkey"
SERVER_URL = "http://localhost:5138/api/deviceauth"
LISTENER_URL = "http://localhost:5138/api/channel/listener/connect"
LONG_POLL_URL = "http://localhost/long-poll-endpoint"

def authenticate():
    try:
        challenge_resp = requests.post(f"{SERVER_URL}/challenge", json={"deviceId": DEVICE_ID})
        challenge_resp.raise_for_status()
        challenge = challenge_resp.json().get("challenge")
        
        response_signature = hmac.new(PSK, challenge.encode(), hashlib.sha256).hexdigest()
        auth_resp = requests.post(f"{SERVER_URL}/respond", json={
            "deviceId": DEVICE_ID,
            "challengeResponse": response_signature
        })
        auth_resp.raise_for_status()
        
        return auth_resp.json().get("token")
    except requests.exceptions.RequestException as e:
        print("Authentication failed:", e)
        return None

def get_channel_id(token):
    headers = {"Authorization": token}
    try:
        resp = requests.post(LISTENER_URL, headers=headers)
        resp.raise_for_status()
        return resp.json().get("channelId")
    except requests.exceptions.RequestException as e:
        print("Failed to get channel ID:", e)
        return None

def handle_action(action):
    if action == "close":
        # servo_control.set_angle(0)
        print("Status: closed")
    elif action == "open":
        # servo_control.set_angle(180)
        print("Status: opened")
    else:
        print(f"Error: unknown action received: {action}")

def long_polling_client(token, channel_id):
    headers = {"Authorization": token}
    payload = {"channelId": channel_id}
    
    while True:
        try:
            response = requests.post(LONG_POLL_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                action = data.get("action")
                handle_action(action)
            else:
                print("Error:", response.status_code, response.text)
        except requests.exceptions.RequestException as e:
            print("Request failed:", e)
        
        time.sleep(1)

if __name__ == "__main__":
    token = authenticate()
    if token:
        channel_id = get_channel_id(token)
        if channel_id:
            long_polling_client(token, channel_id)
        else:
            print("Failed to obtain channel ID.")
    else:
        print("Authentication failed. Exiting.")

