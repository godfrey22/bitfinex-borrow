# backend/app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import os
from dotenv import load_dotenv
import logging
from socket import gaierror

from app.services.bitfinex import BitfinexService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bitfinex_api')

# Load environment variables
load_dotenv()

# Debug environment variables (don't log full values in production)
logger.info(f"Environment check:")
logger.info(f"BFX_API_KEY exists: {bool(os.getenv('BFX_API_KEY'))}")
logger.info(f"BFX_API_SECRET exists: {bool(os.getenv('BFX_API_SECRET'))}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f".env file exists: {os.path.exists('.env')}")
logger.info(f"Full path to .env: {os.path.abspath('.env')}")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Bitfinex service
try:
    api_key = os.getenv("BFX_API_KEY")
    api_secret = os.getenv("BFX_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("Bitfinex API credentials not found in environment variables")
        raise ValueError("BFX_API_KEY and BFX_API_SECRET must be set in .env file")
        
    # Log partial key to verify it's loaded (first 4 chars only)
    logger.info(f"API Key starts with: {api_key[:4]}***")
    
    bitfinex = BitfinexService(api_key=api_key, api_secret=api_secret)
    logger.info("Bitfinex service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Bitfinex service: {str(e)}")
    bitfinex = None

@app.get("/")
async def hello_world():
    return {"message": "Hello World"}

@app.get("/api/loans")
async def get_loans():
    """Get active loans from Bitfinex"""
    try:
        if not bitfinex:
            logger.error("Bitfinex service not initialized")
            raise HTTPException(
                status_code=503,
                detail="Bitfinex service not available"
            )

        logger.info("Fetching loans from Bitfinex...")
        loans = bitfinex.get_active_loans()
        logger.info(f"Retrieved {len(loans)} loans")
        return loans

    except gaierror as e:
        logger.error(f"Network error connecting to Bitfinex: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Network error connecting to Bitfinex"
        )
    except Exception as e:
        logger.error(f"Error fetching loans: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching loans: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("API starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    if bitfinex:
        logger.info("Closing Bitfinex connection...")
        bitfinex.close()
    logger.info("API shutting down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)