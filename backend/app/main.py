from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path
from typing import List
from pydantic import BaseModel

from app.services.bitfinex import BitfinexService

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bitfinex_api')

# Load environment variables from the correct path
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Debug environment loading
logger.debug("Environment variables check:")
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Looking for .env at: {env_path}")
logger.debug(f".env file exists: {env_path.exists()}")
logger.debug(f"BFX_API_KEY exists: {'BFX_API_KEY' in os.environ}")
logger.debug(f"BFX_API_SECRET exists: {'BFX_API_SECRET' in os.environ}")

# Print environment variables (be careful with this in production)
logger.debug("Environment variables content:")
for key in ['BFX_API_KEY', 'BFX_API_SECRET', 'APP_API_KEY', 'APP_USERNAME', 'APP_PASSWORD']:
    if key in os.environ:
        value = os.environ[key]
        logger.debug(f"{key}: {value[:4]}..." if value else f"{key}: None")

app = FastAPI()

# Add API key security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != os.getenv("APP_API_KEY"):
        raise HTTPException(
            status_code=403,
            detail="Could not validate API key"
        )
    return api_key_header

# Update CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),  # Get from environment variable
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Specify only needed methods
    allow_headers=["*"],
)

# Initialize Bitfinex service
bitfinex = None

# Add request model
class CloseLoansRequest(BaseModel):
    loan_ids: List[int]

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    api_key: str

@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login endpoint to get API key"""
    expected_username = os.getenv("APP_USERNAME")
    expected_password = os.getenv("APP_PASSWORD")
    
    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=500,
            detail="Login credentials not configured"
        )
    
    if request.username != expected_username or request.password != expected_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    return LoginResponse(api_key=os.getenv("APP_API_KEY"))

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global bitfinex
    try:
        logger.debug("Starting Bitfinex service initialization...")
        
        api_key = os.getenv("BFX_API_KEY")
        api_secret = os.getenv("BFX_API_SECRET")
        
        # Debug credential loading
        logger.debug(f"API Key loaded: {bool(api_key)} (starts with: {api_key[:4] if api_key else 'None'})")
        logger.debug(f"API Secret loaded: {bool(api_secret)}")
        
        if not api_key or not api_secret:
            logger.error("Bitfinex API credentials not found in environment variables")
            raise ValueError("BFX_API_KEY and BFX_API_SECRET must be set in .env file")
            
        logger.debug("Creating BitfinexService instance...")
        bitfinex = BitfinexService(api_key=api_key, api_secret=api_secret)
        logger.info("Bitfinex service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Bitfinex service: {str(e)}")
        logger.exception("Full initialization error details:")
        bitfinex = None

@app.get("/api/loans")
async def get_loans(api_key: str = Depends(get_api_key)):
    """Get active loans from Bitfinex"""
    global bitfinex
    
    try:
        logger.debug("Loan request received")
        logger.debug(f"Bitfinex service initialized: {bitfinex is not None}")
        
        if not bitfinex:
            logger.error("Bitfinex service not initialized")
            raise HTTPException(
                status_code=503,
                detail="Bitfinex service not available"
            )

        # Get loans and maintain the connection
        loans = bitfinex.get_active_loans(maintain_connection=True)
        logger.info(f"Retrieved {len(loans)} loans")
        return loans

    except Exception as e:
        logger.error(f"Error fetching loans: {str(e)}")
        logger.exception("Full exception details:")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching loans: {str(e)}"
        )

@app.post("/api/loans/close")
async def close_loans(request: CloseLoansRequest, api_key: str = Depends(get_api_key)):
    """Close selected funding positions"""
    try:
        if not bitfinex:
            raise HTTPException(
                status_code=503,
                detail="Bitfinex service not available"
            )

        logger.info(f"Attempting to close loans: {request.loan_ids}")
        results = await bitfinex.close_loans(request.loan_ids)
        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"Error closing loans: {str(e)}")
        logger.exception("Full exception details:")
        raise HTTPException(
            status_code=500,
            detail=f"Error closing loans: {str(e)}"
        )

@app.get("/api/funding-book/{symbol}")
async def get_funding_book(symbol: str, api_key: str = Depends(get_api_key)):
    """Get funding book for a specific symbol"""
    try:
        if not bitfinex:
            raise HTTPException(
                status_code=503,
                detail="Bitfinex service not available"
            )

        logger.info(f"Fetching funding book for {symbol}")
        book = await bitfinex.get_funding_book(symbol)
        return book

    except Exception as e:
        logger.error(f"Error fetching funding book: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching funding book: {str(e)}"
        )