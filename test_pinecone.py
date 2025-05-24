from dotenv import load_dotenv
import os
from pinecone import Pinecone

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    print("❌ PINECONE_API_KEY not found in environment")
    exit(1)

try:
    print("🔄 Connecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    print("📋 Listing indexes...")
    indexes = pc.list_indexes()
    print(f"Found indexes: {indexes}")
    
    if "plan-your-trip" not in [idx.name for idx in indexes]:
        print("❌ 'plan-your-trip' index not found!")
        exit(1)
        
    print("🔍 Checking 'plan-your-trip' index...")
    index = pc.Index("plan-your-trip")
    
    print("📊 Checking index stats...")
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")
    
    print("✅ Pinecone connection test successful!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    exit(1) 