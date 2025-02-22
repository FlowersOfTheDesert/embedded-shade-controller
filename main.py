import requests
import time
import servo_control

URL = "localhost/long-poll-endpoint"

def handle_action(action):
    if action == "close":
        servo_control.set_angle(0)
        print("Status: closed")
    elif action == "open":
        servo_control.set_angle(180)
        print("Status: opened")
    else:
        print(f"Error: unknown action received: {action}")

def long_polling_client():
    while True:
        try:
            response = requests.get(URL, timeout=30)
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
    long_polling_client()
