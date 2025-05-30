from dotenv import load_dotenv
import os
from openai import OpenAI
import time

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

try:
    import openai
    version = tuple(map(int, openai.__version__.split('.')))
    if version < (1, 12, 0):
        print(f"❌ OpenAI version {openai.__version__} is too old. Please run: pip install --upgrade openai")
        exit(1)
    print("🔄 Connecting to OpenAI...")
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=30.0,
        max_retries=2
    )
    
    print("📊 Testing embeddings API...")
    start_time = time.time()
    embedding = client.embeddings.create(
        model="text-embedding-ada-002",
        input=["Test embedding generation"]
    )
    print(f"✅ Embedding generated in {time.time() - start_time:.2f}s")
    
    print("💬 Testing chat completion API...")
    start_time = time.time()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say hello!"}],
        max_tokens=10
    )
    print(f"✅ Chat completion received in {time.time() - start_time:.2f}s")
    print(f"Response: {response.choices[0].message.content}")
    
    print("✅ OpenAI connection test successful!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("If you see a 'proxies' error, try: pip install --upgrade openai")
    raise 