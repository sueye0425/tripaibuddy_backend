from dotenv import load_dotenv
import os
from openai import OpenAI
import time

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY not found in environment")
    exit(1)

try:
    print("🔄 Connecting to OpenAI...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    print("📊 Testing embeddings API...")
    start_time = time.time()
    embedding = client.embeddings.create(
        model="text-embedding-ada-002",
        input=["Test embedding generation"]
    )
    print(f"✅ Embedding generated in {time.time() - start_time:.2f}s")
    
    print("💬 Testing chat completion API...")
    start_time = time.time()
    completion = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": "Say hello!"}]
    )
    print(f"✅ Chat completion received in {time.time() - start_time:.2f}s")
    print(f"Response: {completion.choices[0].message.content}")
    
    print("✅ OpenAI connection test successful!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    exit(1) 