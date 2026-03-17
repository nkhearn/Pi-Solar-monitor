import asyncio
import uvicorn
from api import app
from engine import collection_loop

async def main():
    # Start the collection loop as a background task
    collection_task = asyncio.create_task(collection_loop())

    # Start the FastAPI server
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    await server.serve()

    # Cancel the collection task when the server stops
    collection_task.cancel()
    try:
        await collection_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System shutting down...")
