from websockets.sync.client import connect
from datetime import datetime
import json
import hmac
import hashlib
import os
import logging
import socket
import ssl
from typing import Dict, List
from websockets.exceptions import WebSocketException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bitfinex_service')

class BitfinexService:
    URI = "wss://api-pub.bitfinex.com/ws/2"
    API_HOST = "api-pub.bitfinex.com"
    API_PORT = 443

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        
        # Validate credentials
        if not api_key or not api_secret:
            logger.error("API credentials not provided")
            raise ValueError("API_KEY and API_SECRET must be provided")
        
        # Test DNS resolution
        try:
            logger.info(f"Testing DNS resolution for {self.API_HOST}")
            socket.getaddrinfo(self.API_HOST, self.API_PORT)
            logger.info("DNS resolution successful")
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed: {str(e)}")
            # Try alternative DNS
            try:
                logger.info("Trying alternative DNS resolution...")
                # Try to resolve using Google's DNS
                import dns.resolver
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ['8.8.8.8', '8.8.4.4']
                answers = resolver.resolve(self.API_HOST, 'A')
                self.ip = answers[0].address
                logger.info(f"Resolved IP: {self.ip}")
            except Exception as dns_error:
                logger.error(f"Alternative DNS resolution failed: {str(dns_error)}")
                raise

        logger.info("BitfinexService initialized")

    def _build_auth_message(self) -> str:
        try:
            message = {
                "event": "auth",
                "apiKey": self.api_key,
                "authNonce": round(datetime.now().timestamp() * 1_000),
                "filter": [
                    "funding",  # offers, credits, loans, funding trades
                    "wallet",   # wallet information
                ]
            }
            
            message["authPayload"] = f"AUTH{message['authNonce']}"
            message["authSig"] = hmac.new(
                key=self.api_secret.encode("utf8"),
                msg=message["authPayload"].encode("utf8"),
                digestmod=hashlib.sha384
            ).hexdigest()

            logger.debug("Auth message built successfully")
            return json.dumps(message)
        except Exception as e:
            logger.error(f"Error building auth message: {str(e)}")
            raise

    def connect_and_authenticate(self) -> bool:
        """Connect to Bitfinex and authenticate"""
        try:
            logger.info("Attempting to connect to Bitfinex WebSocket...")
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            # Try connection with SSL context
            try:
                if hasattr(self, 'ip'):
                    # Use resolved IP if DNS failed earlier
                    uri = f"wss://{self.ip}/ws/2"
                    logger.info(f"Connecting using IP: {uri}")
                    self.ws = connect(uri, ssl=ssl_context)
                else:
                    self.ws = connect(self.URI, ssl=ssl_context)
                logger.info("WebSocket connection established")
            except Exception as conn_error:
                logger.error(f"Connection error: {str(conn_error)}")
                raise

            auth_message = self._build_auth_message()
            logger.debug(f"Sending auth message: {auth_message}")
            self.ws.send(auth_message)

            # Wait for auth response
            for message in self.ws:
                logger.debug(f"Received message: {message}")
                data = json.loads(message)
                if isinstance(data, dict) and data["event"] == "auth":
                    if data["status"] != "OK":
                        logger.error(f"Authentication failed: {data}")
                        raise Exception(f"Authentication failed: {data.get('msg', 'Unknown error')}")
                    logger.info("Successfully authenticated with Bitfinex")
                    return True
                    
        except WebSocketException as e:
            logger.error(f"WebSocket error: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}")
            raise

    def get_active_loans(self) -> List[Dict]:
        """Get active loans"""
        try:
            if not self.ws:
                logger.info("No active connection, attempting to connect...")
                if not self.connect_and_authenticate():
                    logger.error("Failed to establish connection")
                    return []

            # Subscribe to funding info
            subscribe_message = {
                "event": "subscribe",
                "channel": "funding",
                "symbol": "fUSD"  # for USD funding
            }
            logger.info("Subscribing to funding channel...")
            self.ws.send(json.dumps(subscribe_message))

            loans = []
            # Listen for loan information
            for message in self.ws:
                logger.debug(f"Received loan data: {message}")
                data = json.loads(message)
                if isinstance(data, list) and len(data) > 1:
                    loans.append(data)
                    break  # Get first batch of loans

            logger.info(f"Retrieved {len(loans)} loans")
            return loans

        except Exception as e:
            logger.error(f"Error getting loans: {str(e)}")
            return []

    def close(self):
        """Close WebSocket connection"""
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}") 