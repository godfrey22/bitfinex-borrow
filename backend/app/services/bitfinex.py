from websockets.sync.client import connect
from datetime import datetime
import json
import hmac
import hashlib
import os
import logging
from typing import Dict, List

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
            "rate": self.rate * 365 * 100,  # Convert to annual percentage
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
            "rate": self.rate * 365 * 100,  # Convert to annual percentage
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

class BitfinexService:
    URI = "wss://api-pub.bitfinex.com/ws/2"

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
        
        logger.info("BitfinexService initialized successfully")

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
            self.ws = connect(self.URI)
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

    def get_active_loans(self, maintain_connection: bool = False) -> List[Dict]:
        """
        Get active funding loans and credits
        Args:
            maintain_connection (bool): If True, keeps the connection open for updates
        Returns:
            List[Dict]: List of active loans
        """
        try:
            if not self.ws:
                logger.info("No active connection, attempting to connect...")
                if not self.connect_and_authenticate():
                    logger.error("Failed to establish connection")
                    return []

            loans = []
            message_count = 0
            max_messages = 10  # Maximum number of messages to wait for

            while message_count < max_messages:
                message = self.ws.recv()
                message_count += 1
                data = json.loads(message)
                logger.debug(f"Received message: {data}")

                # Check if it's a funding message
                if isinstance(data, list) and len(data) > 1:
                    msg_type = data[1]
                    
                    # Handle different funding message types
                    if msg_type in ["fcs", "fcn", "fcu"]:  # Credits
                        if msg_type == "fcs" and len(data) > 2:  # Snapshot
                            credits_data = data[2]
                            for credit in credits_data:
                                try:
                                    funding_credit = FundingCredit(credit)
                                    loans.append(funding_credit.to_dict())
                                    logger.info(f"Processed credit: {funding_credit.to_dict()}")
                                except Exception as e:
                                    logger.error(f"Error processing credit: {str(e)}")
                    
                    elif msg_type in ["fls", "fln", "flu"]:  # Loans
                        if msg_type == "fls" and len(data) > 2:  # Snapshot
                            loans_data = data[2]
                            for loan in loans_data:
                                try:
                                    funding_loan = FundingLoan(loan)
                                    loans.append(funding_loan.to_dict())
                                    logger.info(f"Processed loan: {funding_loan.to_dict()}")
                                except Exception as e:
                                    logger.error(f"Error processing loan: {str(e)}")
                    
                    elif msg_type == "hb":  # Heartbeat
                        logger.debug("Received heartbeat")
                        continue

                # Break if we have processed both snapshots
                if message_count >= 3:  # We usually get fos, fcs, and fls messages
                    break

            logger.info(f"Retrieved {len(loans)} funding positions")
            
            if not maintain_connection:
                self.close()
                
            return loans

        except Exception as e:
            logger.error(f"Error getting funding positions: {str(e)}")
            if not maintain_connection:
                self.close()
            return []

    def close(self):
        """Close WebSocket connection"""
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}") 