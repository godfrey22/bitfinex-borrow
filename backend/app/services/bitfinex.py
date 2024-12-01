from websockets.sync.client import connect
from datetime import datetime
import json
import hmac
import hashlib
import logging
from typing import Dict, List
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bitfinex_service')


class FundingCredit:
    """Class to represent a funding credit"""
    def __init__(self, data: List):
        self.credit_id = data[0]
        self.symbol = data[1]
        self.side = self._parse_side(data[2])
        self.created_at = self._parse_timestamp(data[3])
        self.updated_at = self._parse_timestamp(data[4])
        self.amount = float(data[5])
        self.status = data[7]
        self.rate = float(data[11])
        self.period = int(data[12])
        self.opening_timestamp = self._parse_timestamp(data[13])
        self.last_payout = self._parse_timestamp(data[14])
        self.is_notify = bool(data[15])
        self.is_hidden = bool(data[16])
        self.auto_renew = bool(data[18])
        self.rate_real = float(data[19]) if data[19] is not None else self.rate
        self.no_close = bool(data[20])
        self.position_pair = data[21]

    def _parse_side(self, side: int) -> str:
        return {
            1: "lender",
            0: "both",
            -1: "borrower"
        }.get(side, "unknown")

    def _parse_timestamp(self, ts: int) -> str:
        return datetime.fromtimestamp(ts/1000).isoformat() if ts else None

    def to_dict(self) -> Dict:
        return {
            "credit_id": self.credit_id,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "status": self.status,
            "rate": self.rate * 100,  # Convert to percentage
            "period_days": self.period,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "opening_date": self.opening_timestamp,
            "last_payout": self.last_payout,
            "auto_renew": self.auto_renew,
            "position_pair": self.position_pair,
            "daily_earnings": self.amount * self.rate,  # Daily earnings
            "annual_earnings": self.amount * self.rate * 365  # Annual earnings
        }

class FundingLoan:
    """Class to represent a funding loan"""
    def __init__(self, data: List):
        self.loan_id = data[0]
        self.symbol = data[1]
        self.side = self._parse_side(data[2])
        self.created_at = self._parse_timestamp(data[3])
        self.updated_at = self._parse_timestamp(data[4])
        self.amount = float(data[5])
        self.status = data[7]
        self.rate = float(data[11]) if data[11] is not None else 0
        self.period = int(data[12]) if data[12] is not None else 0
        self.opening_timestamp = self._parse_timestamp(data[13])
        self.last_payout = self._parse_timestamp(data[14])
        self.notify = bool(data[15]) if data[15] is not None else False
        self.hidden = bool(data[16]) if data[16] is not None else False
        self.renew = bool(data[18]) if data[18] is not None else False
        self.rate_real = float(data[19]) if data[19] is not None else self.rate
        self.no_close = bool(data[20]) if data[20] is not None else False
        self.position_pair = data[21] if len(data) > 21 else None

    def _parse_side(self, side: int) -> str:
        return {
            1: "lender",
            0: "both",
            -1: "borrower"
        }.get(side, "unknown")

    def _parse_timestamp(self, ts: int) -> str:
        return datetime.fromtimestamp(ts/1000).isoformat() if ts else None

    def to_dict(self) -> Dict:
        return {
            "loan_id": self.loan_id,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "status": self.status,
            "rate": self.rate * 100,  # Convert to percentage
            "period_days": self.period,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "opening_date": self.opening_timestamp,
            "last_payout": self.last_payout,
            "auto_renew": self.renew,
            "position_pair": self.position_pair,
            "daily_earnings": self.amount * self.rate if self.amount and self.rate else 0,
            "annual_earnings": self.amount * self.rate * 365 if self.amount and self.rate else 0
        }

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.pop('timeout', 30)
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        kwargs['timeout'] = self.timeout
        return super().send(request, **kwargs)

class BitfinexService:
    WS_URI = "wss://api-pub.bitfinex.com/ws/2"
    REST_URI = "https://api.bitfinex.com/v2"
    API_HOST = "api.bitfinex.com"
    API_PORT = 443

    def __init__(self, api_key: str, api_secret: str):
        logger.debug("BitfinexService initialization started")
        
        # Validate credentials
        if not api_key or not api_secret:
            logger.error("Missing API credentials")
            logger.debug(f"API Key provided: {bool(api_key)}")
            logger.debug(f"API Secret provided: {bool(api_secret)}")
            raise ValueError("API_KEY and API_SECRET must be provided")
            
        # Store credentials
        self.api_key = api_key
        self.api_secret = api_secret
        logger.debug(f"API Key validation: starts with {api_key[:4]}...")
        
        # Initialize connection variables
        self.ws = None
        self.is_connected = False
        self.loans = []
        self.session = None
        self.connector = None
        logger.info("BitfinexService initialized successfully")

    async def _init_session(self):
        """Initialize aiohttp session with proper DNS resolution"""
        import aiohttp
        import socket
        try:
            # Resolve IP address
            logger.debug(f"Resolving {self.API_HOST}")
            ip_address = socket.gethostbyname(self.API_HOST)
            logger.debug(f"Resolved {self.API_HOST} to {ip_address}")

            # Create TCP connector with resolved DNS
            self.connector = aiohttp.TCPConnector(
                ssl=True,
                force_close=True,
                enable_cleanup_closed=True
            )
            
            # Create session
            self.session = aiohttp.ClientSession(connector=self.connector)
            logger.debug("HTTP session initialized")
            
        except Exception as e:
            logger.error(f"Error initializing session: {str(e)}")
            raise

    def _build_auth_message(self) -> str:
        """Build authentication message for Bitfinex"""
        try:
            logger.debug("Building authentication message")
            nonce = round(datetime.now().timestamp() * 1_000)
            
            message = {
                "event": "auth",
                "apiKey": self.api_key,
                "authNonce": nonce,
                "filter": ["funding"]
            }
            
            # Create authentication signature
            auth_payload = f"AUTH{nonce}"
            message["authPayload"] = auth_payload
            
            # Generate signature
            signature = hmac.new(
                key=self.api_secret.encode("utf8"),
                msg=auth_payload.encode("utf8"),
                digestmod=hashlib.sha384
            ).hexdigest()
            
            message["authSig"] = signature
            
            logger.debug("Authentication message built successfully")
            logger.debug(f"Using API Key: {self.api_key[:4]}...")
            return json.dumps(message)
            
        except Exception as e:
            logger.error(f"Error building auth message: {str(e)}")
            logger.exception("Full auth message error details:")
            raise
    def connect_and_authenticate(self) -> bool:
        try:
            logger.info("Attempting to connect to Bitfinex WebSocket...")
            self.ws = connect(self.WS_URI)
            logger.info("WebSocket connection established")

            auth_message = self._build_auth_message()
            self.ws.send(auth_message)

            # Wait for auth response
            for message in self.ws:
                data = json.loads(message)
                if isinstance(data, dict) and data["event"] == "auth":
                    if data["status"] != "OK":
                        logger.error(f"Authentication failed: {data}")
                        raise Exception(f"Authentication failed: {data.get('msg', 'Unknown error')}")
                    logger.info("Successfully authenticated with Bitfinex")
                    return True
                    
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}")
            raise

    async def reconnect(self) -> bool:
        """Reconnect to Bitfinex WebSocket"""
        logger.info("Attempting to reconnect...")
        try:
            # Close existing connection if any
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass
                self.ws = None
                self.is_connected = False

            # Create new connection
            self.ws = connect(self.WS_URI)
            logger.info("New WebSocket connection established")

            # Re-authenticate
            auth_message = self._build_auth_message()
            self.ws.send(auth_message)

            # Wait for auth response
            for message in self.ws:
                data = json.loads(message)
                if isinstance(data, dict) and data["event"] == "auth":
                    if data["status"] != "OK":
                        logger.error(f"Re-authentication failed: {data}")
                        raise Exception(f"Re-authentication failed: {data.get('msg', 'Unknown error')}")
                    logger.info("Successfully re-authenticated with Bitfinex")
                    self.is_connected = True
                    return True

        except Exception as e:
            logger.error(f"Reconnection failed: {str(e)}")
            self.ws = None
            self.is_connected = False
            raise

    def get_active_loans(self, maintain_connection: bool = False) -> List[Dict]:
        """Get active funding loans and credits (borrower side only)"""
        try:
            if not self.ws or not self.is_connected:
                logger.info("No active connection, attempting to connect...")
                if not self.connect_and_authenticate():
                    logger.error("Failed to establish connection")
                    return []

            loans = []
            message_count = 0
            max_messages = 10

            while message_count < max_messages:
                try:
                    message = self.ws.recv()
                    message_count += 1
                    data = json.loads(message)
                    logger.debug(f"Received message: {data}")

                    # Check if it's a funding message
                    if isinstance(data, list) and len(data) > 1:
                        msg_type = data[1]
                        
                        if msg_type == "hb":  # Heartbeat
                            logger.debug("Received heartbeat")
                            continue

                        # Handle different funding message types
                        if msg_type in ["fcs", "fcn", "fcu"]:  # Credits
                            if msg_type == "fcs" and len(data) > 2:  # Snapshot
                                credits_data = data[2]
                                for credit in credits_data:
                                    try:
                                        funding_credit = FundingCredit(credit)
                                        # Only include borrower side
                                        if funding_credit.side == "borrower":
                                            loan_dict = funding_credit.to_dict()
                                            loans.append(loan_dict)
                                            logger.info(f"Processed borrower credit: {loan_dict}")
                                    except Exception as e:
                                        logger.error(f"Error processing credit: {str(e)}")
                        
                        elif msg_type in ["fls", "fln", "flu"]:  # Loans
                            if msg_type == "fls" and len(data) > 2:  # Snapshot
                                loans_data = data[2]
                                for loan in loans_data:
                                    try:
                                        funding_loan = FundingLoan(loan)
                                        # Only include borrower side
                                        if funding_loan.side == "borrower":
                                            loan_dict = funding_loan.to_dict()
                                            loans.append(loan_dict)
                                            logger.info(f"Processed borrower loan: {loan_dict}")
                                    except Exception as e:
                                        logger.error(f"Error processing loan: {str(e)}")

                    # Break if we have loans
                    if loans:
                        break

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    if "connection is closed" in str(e):
                        raise  # Re-raise to trigger reconnection

            logger.info(f"Retrieved {len(loans)} borrower-side funding positions")
            
            # Only close if not maintaining connection
            if not maintain_connection:
                logger.info("Closing connection as maintain_connection=False")
                self.close()
            else:
                logger.info("Keeping connection open as maintain_connection=True")
                
            return loans

        except Exception as e:
            logger.error(f"Error getting funding positions: {str(e)}")
            if not maintain_connection:
                self.close()
            raise  # Re-raise to allow retry in main.py

    def close(self):
        """Close WebSocket connection"""
        if self.ws:
            try:
                self.ws.close()
                self.is_connected = False
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}") 

    def _generate_auth_headers(self, endpoint: str, body: dict = None) -> dict:
        """Generate authentication headers for REST API"""
        nonce = str(int(time.time() * 1000))
        signature_data = f'/api/v2/{endpoint}{nonce}'
        if body:
            signature_data += json.dumps(body)
            
        signature = hmac.new(
            self.api_secret.encode(),
            signature_data.encode(),
            hashlib.sha384
        ).hexdigest()

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.api_key,
            "bfx-signature": signature,
            "content-type": "application/json"
        }

    async def close_loans(self, loan_ids: List[int]) -> List[Dict]:
        """Close multiple funding positions with improved connection handling"""
        results = []
        
        # Configure session with retries and timeouts
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504],
        )
        adapter = TimeoutHTTPAdapter(timeout=10, max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        for loan_id in loan_ids:
            try:
                logger.info(f"Attempting to close loan {loan_id}")
                
                endpoint = "auth/w/funding/close"
                payload = {"id": loan_id}
                
                # Generate authentication headers
                nonce = str(int(time.time() * 1000))
                signature_payload = f'/api/v2/{endpoint}{nonce}{json.dumps(payload)}'
                
                logger.debug(f"Signature payload: {signature_payload}")
                
                signature = hmac.new(
                    self.api_secret.encode(),
                    signature_payload.encode(),
                    hashlib.sha384
                ).hexdigest()
                
                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "bfx-nonce": nonce,
                    "bfx-apikey": self.api_key,
                    "bfx-signature": signature
                }
                
                url = f"{self.REST_URI}/{endpoint}"
                logger.debug(f"Sending request to {url}")
                logger.debug(f"Payload: {json.dumps(payload)}")
                logger.debug(f"Headers: {headers}")
                
                # Test connection first
                try:
                    test_response = session.get("https://api.bitfinex.com/v2/platform/status")
                    logger.debug(f"Platform status response: {test_response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Cannot connect to Bitfinex API: {str(e)}")
                    raise ConnectionError(f"Cannot connect to Bitfinex API: {str(e)}")
                
                # Send the actual request
                response = session.post(
                    url,
                    json=payload,
                    headers=headers,
                    verify=True  # Verify SSL certificates
                )
                
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response text: {response.text}")
                
                try:
                    response_data = response.json()
                    message = json.dumps(response_data)
                except json.JSONDecodeError:
                    message = response.text if response.text else "No response text"
                
                success = response.status_code == 200
                
                results.append({
                    "loan_id": loan_id,
                    "success": success,
                    "message": message,
                    "status_code": response.status_code
                })
                
                logger.info(f"Close result for loan {loan_id}: {success} ({message})")
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "loan_id": loan_id,
                    "success": False,
                    "message": error_msg,
                    "status_code": None
                })
            except requests.exceptions.RequestException as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "loan_id": loan_id,
                    "success": False,
                    "message": error_msg,
                    "status_code": None
                })
            except Exception as e:
                error_msg = f"Error closing loan {loan_id}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "loan_id": loan_id,
                    "success": False,
                    "message": error_msg,
                    "status_code": None
                })
        
        session.close()
        return results

    async def cleanup(self):
        """Cleanup resources"""
        if self.ws:
            self.ws.close()
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()

    async def get_funding_book(self, symbol: str) -> List[Dict]:
        """Get funding book for a specific symbol (ask side only)"""
        try:
            logger.info(f"Fetching funding book for {symbol}")
            url = f"https://api-pub.bitfinex.com/v2/book/{symbol}/P0?len=25"
            
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            
            if not response.ok:
                logger.error(f"Failed to fetch funding book: {response.text}")
                return []
            
            book_data = response.json()
            formatted_book = []
            
            for entry in book_data:
                # Only include ask side (amount > 0)
                if float(entry[3]) > 0:
                    formatted_entry = {
                        "rate": float(entry[0]),
                        "period": int(entry[1]),
                        "count": int(entry[2]),
                        "amount": float(entry[3])
                    }
                    formatted_book.append(formatted_entry)
            
            # Sort by rate ascending
            formatted_book.sort(key=lambda x: x['rate'])
            
            logger.info(f"Retrieved {len(formatted_book)} ask-side funding book entries")
            return formatted_book
            
        except Exception as e:
            logger.error(f"Error fetching funding book: {str(e)}")
            return []