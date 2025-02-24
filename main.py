import requests
import time
import hmac
import hashlib
import sys
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    DEVICE_ID = "sunshade-01"
    PSK = b"secretkey"
    SERVER_URL = "http://localhost:5138"
    POLL_TIMEOUT = 5
    RETRY_DELAY = 1

class DeviceAction(Enum):
    OPEN = "open"
    CLOSE = "close"

@dataclass
class AuthToken:
    token: str
    channel_id: Optional[str] = None

class DeviceAPIError(Exception):
    """Custom exception for device API related errors"""
    pass

class DeviceController:
    def set_angle(self, angle: int) -> None:
        """
        Control the device servo motor angle
        Currently stubbed out for demonstration
        """
        logger.info(f"Setting servo angle to {angle}")
        # Actual servo control implementation would go here
        pass

class DeviceAPI:
    def __init__(self, server_url: str, device_id: str, psk: bytes):
        self.server_url = server_url
        self.device_id = device_id
        self.psk = psk
        self.session = requests.Session()

    def _make_request(self, endpoint: str, method: str = "POST", allow_timeout: bool = False, **kwargs) -> Dict[str, Any]:
        """Helper method to make HTTP requests with error handling"""
        try:
            url = f"{self.server_url}/api/{endpoint}"
            response = self.session.request(method, url, **kwargs)
            
            # Check for non-200 status codes
            if response.status_code != 200:
                raise DeviceAPIError(f"HTTP {response.status_code}: {response.text}")
                
            return response.json()
            
        except requests.exceptions.Timeout:
            if allow_timeout:
                raise  # Re-raise the Timeout exception if it's allowed
            raise DeviceAPIError("Request timed out")
            
        except requests.exceptions.RequestException as e:
            raise DeviceAPIError(f"API request failed: {e}")

    def get_challenge(self) -> str:
        """Request authentication challenge from server"""
        response = self._make_request(
            "deviceauth/challenge",
            json={"Serial": self.device_id}
        )
        return response["challenge"]

    def submit_challenge_response(self, challenge: str) -> str:
        """Submit challenge response and get auth token"""
        signature = hmac.new(self.psk, challenge.encode(), hashlib.sha256).hexdigest()
        response = self._make_request(
            "deviceauth/respond",
            json={
                "Serial": self.device_id,
                "challengeResponse": signature
            }
        )
        return response["token"]

    def get_channel_id(self, token: str) -> str:
        """Get channel ID for long polling"""
        response = self._make_request(
            "channel/listener/connect",
            headers={"Authorization": token}
        )
        return response["channelId"]

    def poll_channel(self, token: str, channel_id: str) -> Optional[str]:
        """Poll for new messages"""
        try:
            response = self._make_request(
                "channel/listener/poll",
                headers={"Authorization": token},
                json={"channelId": channel_id},
                timeout=Config.POLL_TIMEOUT,
                allow_timeout=True  # Allow timeout exceptions to propagate
            )
            return response.get("message")
        except requests.exceptions.Timeout:
            logger.debug("Poll timeout (expected)")
            return None
        except DeviceAPIError as e:
            # Re-raise other API errors
            raise

class DeviceManager:
    def __init__(self):
        self.api = DeviceAPI(Config.SERVER_URL, Config.DEVICE_ID, Config.PSK)
        self.controller = DeviceController()
        self.auth_token: Optional[AuthToken] = None

    def authenticate(self) -> bool:
        """Perform device authentication"""
        try:
            challenge = self.api.get_challenge()
            token = self.api.submit_challenge_response(challenge)
            channel_id = self.api.get_channel_id(token)
            self.auth_token = AuthToken(token=token, channel_id=channel_id)
            logger.info("Authentication successful")
            return True
        except DeviceAPIError as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def handle_action(self, action: str) -> None:
        """Handle received device actions"""
        try:
            device_action = DeviceAction(action)
            if device_action == DeviceAction.CLOSE:
                self.controller.set_angle(0)
                logger.info("Status: closed")
            elif device_action == DeviceAction.OPEN:
                self.controller.set_angle(180)
                logger.info("Status: opened")
        except ValueError:
            logger.error(f"Unknown action received: {action}")

    def run(self) -> None:
        """Main run loop"""
        if not self.authenticate():
            logger.error("Initial authentication failed")
            sys.exit(1)
        #Debug
        print(f"Auth: {self.auth_token.token}")
        print(f"ChannelId: {self.auth_token.channel_id}")
        
        while True:
            try:
                if not self.auth_token or not self.auth_token.channel_id:
                    raise DeviceAPIError("Missing authentication token or channel ID")

                message = self.api.poll_channel(
                    self.auth_token.token,
                    self.auth_token.channel_id
                )
                
                if message:
                    self.handle_action(message)
                    
                time.sleep(Config.RETRY_DELAY)

            except DeviceAPIError as e:
                logger.error(f"Fatal error: {e}")
                sys.exit(1)

def main():
    try:
        device_manager = DeviceManager()
        device_manager.run()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully")
        sys.exit(0)

if __name__ == "__main__":
    main()