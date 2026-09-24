import asyncio
import json
import httpx
import sys

# Configure UTF-8 for Windows console prints
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"

async def test_health():
    print("--- 1. Testing Health Endpoint ---")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        print(f"Health Response Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def test_chat_rest():
    print("\n--- 2. Testing Chat REST Endpoint ---")
    payload = {
        "message": "Who is the prime minister of India and what is the latest news today?",
        "provider": "auto",
        "enable_search": True
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/api/chat", json=payload)
        print(f"Chat Response Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def test_websocket():
    print("\n--- 3. Testing WebSocket Streaming Endpoint ---")
    try:
        import websockets
        uri = "ws://localhost:8000/ws/chat"
        async with websockets.connect(uri) as ws:
            payload = {"message": "Hello E.V! Introduce yourself and list 3 things you can help me with."}
            await ws.send(json.dumps(payload))
            print("Sent message to WebSocket. Receiving streaming tokens:")
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                msg_type = data.get("type")
                if msg_type == "start":
                    print(f"[{data.get('assistant')}] Streaming started: ", end="", flush=True)
                elif msg_type == "chunk":
                    print(data.get("content", ""), end="", flush=True)
                elif msg_type == "end":
                    print("\n[Streaming Finished]")
                    break
    except ImportError:
        print("Note: 'websockets' library not installed for test_client script. Run `pip install websockets` to test WS.")
    except Exception as e:
        print(f"WebSocket test exception: {e}")

async def test_search_api():
    print("\n--- 4. Testing Direct Search Endpoint ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/api/search", json={"query": "Artificial Intelligence", "max_results": 3})
        print(f"Search Response Status: {resp.status_code}")
        print(f"Results Count: {len(resp.json().get('results', []))}")

async def test_wikipedia_api():
    print("\n--- 5. Testing Direct Wikipedia Endpoint ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/api/wikipedia", json={"query": "Quantum Computing"})
        print(f"Wikipedia Response Status: {resp.status_code}")
        data = resp.json()
        print(f"Found: {data.get('found')}, Title: {data.get('result', {}).get('title') if data.get('result') else 'N/A'}")

async def test_db_persistence():
    print("\n--- 6. Testing Database Chat Persistence & Sessions ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Send chat message with user_id
        chat_resp = await client.post(f"{BASE_URL}/api/chat", json={
            "message": "Remember my favorite programming language is Kotlin.",
            "user_id": "test_user_123"
        })
        print(f"Chat DB Persist Status: {chat_resp.status_code}")
        session_id = chat_resp.json().get("session_id")
        print(f"Assigned Session ID: {session_id}")

        # 2. List sessions for user
        sess_resp = await client.get(f"{BASE_URL}/api/sessions?user_id=test_user_123")
        print(f"List Sessions Count: {len(sess_resp.json().get('sessions', []))}")

        # 3. Retrieve history for session
        if session_id:
            hist_resp = await client.get(f"{BASE_URL}/api/sessions/{session_id}/messages")
            print(f"Retrieved Messages in DB: {len(hist_resp.json().get('messages', []))}")

async def test_user_memories():
    print("\n--- 7. Testing Database User Memory ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Save memory
        save_resp = await client.post(f"{BASE_URL}/api/memories", json={
            "user_id": "test_user_123",
            "key": "user_name",
            "value": "Sanjay",
            "category": "personal_info"
        })
        print(f"Save Memory Status: {save_resp.status_code}")

        # 2. Fetch memories
        get_resp = await client.get(f"{BASE_URL}/api/memories/test_user_123")
        print(f"User Memories Count: {len(get_resp.json().get('memories', []))}")

if __name__ == "__main__":
    asyncio.run(test_health())
    asyncio.run(test_chat_rest())
    asyncio.run(test_websocket())
    asyncio.run(test_search_api())
    asyncio.run(test_wikipedia_api())
    asyncio.run(test_db_persistence())
    asyncio.run(test_user_memories())


