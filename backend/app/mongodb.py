import logging
from motor.motor_asyncio import AsyncIOMotorClient
from .settings import settings

# Configure logging to see connection issues
logger = logging.getLogger(__name__)

try:
    # Strip any potential quotes from the URI if they were imported literally
    uri = settings.MONGODB_URI.strip('"').strip("'")
    
    # Check if the URI is using the SRV format
    is_srv = uri.startswith("mongodb+srv://")
    
    # Configure client with parameters that often help with SRV resolution issues
    client_kwargs = {
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 10000,
        "tls": True,
        "tlsAllowInvalidCertificates": True
    }
    
    # Some environments have trouble with SRV records. If it's SRV, we can try to force
    # a specific resolver or just let it try with the standard settings.
    client = AsyncIOMotorClient(uri, **client_kwargs)
    
    import urllib.parse
    parsed_uri = urllib.parse.urlparse(uri)
    # For mongodb+srv, the path is the DB name. For standard mongodb://, it's after the host.
    db_name = parsed_uri.path.strip('/') or 'interior_design'
    db = client[db_name]
    
    users_collection = db.users
    otp_collection = db.otp
    
    # Attempt a ping to verify connection immediately
    async def check_connection():
        try:
            await client.admin.command('ping')
            print(f"✅ Successfully connected to MongoDB: {db_name}")
        except Exception as ping_err:
            print(f"❌ MongoDB Ping failed: {ping_err}")
            if "NXDOMAIN" in str(ping_err) and is_srv:
                print("💡 TIP: Your local DNS cannot resolve the Atlas SRV record.")
                print("💡 ACTION: Try using the 'Older Driver' (standard mongodb://) connection string from Atlas dashboard.")

    import asyncio
    # Note: This might not run if we aren't in an active loop yet, 
    # but we'll try to trigger it later or just log it.
    
    print(f"DEBUG: Initializing MongoDB client for {db_name}...")
except Exception as e:
    logger.error(f"Failed to initialize MongoDB client: {e}")
    print(f"CRITICAL ERROR: MongoDB setup failed: {e}")

async def get_user_by_email(email: str):
    return await users_collection.find_one({"email": email})

async def create_user(user_data: dict):
    # Default 100 credits
    user_data["credits"] = 100
    user_data["is_active"] = True  # Verified by OTP
    result = await users_collection.insert_one(user_data)
    return result.inserted_id

async def update_user_credits(email: str, amount: int = -1):
    await users_collection.update_one(
        {"email": email},
        {"$inc": {"credits": amount}}
    )

async def store_otp(email: str, otp: str):
    # Upsert OTP with 5 min TTL (should set TTL index in DB manually or on startup)
    await otp_collection.update_one(
        {"email": email},
        {"$set": {"otp": otp, "created_at": "datetime_now_placeholder"}}, # simplified for logic
        upsert=True
    )

async def verify_otp_in_db(email: str, otp: str):
    record = await otp_collection.find_one({"email": email, "otp": otp})
    if record:
        await otp_collection.delete_one({"email": email})
        return True
    return False
