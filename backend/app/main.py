from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path

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
for key in ['BFX_API_KEY', 'BFX_API_SECRET']:
    if key in os.environ:
        value = os.environ[key]
        logger.debug(f"{key}: {value[:4]}..." if value else f"{key}: None")

app = FastAPI()

# Update CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://0.0.0.0:3000",
        "http://127.0.0.1:3000",
        # Add any other origins you need
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Bitfinex service
bitfinex = None

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
async def get_loans():
    """Get active loans from Bitfinex"""
    global bitfinex  # Ensure we can modify the global instance if needed
    
    async def attempt_fetch():
        try:
            loans = bitfinex.get_active_loans(maintain_connection=False)
            logger.info(f"Retrieved {len(loans)} loans")
            if loans:  # Only return if we actually got loans
                return loans
            return None
        except Exception as e:
            logger.warning(f"Fetch attempt failed: {str(e)}")
            return None

    try:
        logger.debug("Loan request received")
        logger.debug(f"Bitfinex service initialized: {bitfinex is not None}")
        
        if not bitfinex:
            logger.error("Bitfinex service not initialized")
            raise HTTPException(
                status_code=503,
                detail="Bitfinex service not available"
            )

        # First attempt
        logger.info("Attempting first fetch...")
        loans = await attempt_fetch()
        
        # If first attempt fails, try reconnecting
        if not loans:
            logger.info("First attempt failed, reconnecting...")
            try:
                await bitfinex.reconnect()
                await asyncio.sleep(1)  # Give the connection time to establish
                logger.info("Attempting fetch after reconnection...")
                loans = await attempt_fetch()
            except Exception as reconnect_error:
                logger.error(f"Reconnection failed: {str(reconnect_error)}")
                raise HTTPException(
                    status_code=503,
                    detail="Failed to reconnect to Bitfinex"
                )

        # If we still don't have loans after reconnection
        if not loans:
            logger.error("Failed to retrieve loans after reconnection")
            raise HTTPException(
                status_code=503,
                detail="Failed to retrieve loans after reconnection"
            )

        return loans

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching loans: {str(e)}")
        logger.exception("Full exception details:")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching loans: {str(e)}"
        )