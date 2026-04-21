import asyncio
import uvicorn
import argparse
import logging
import sys
import os
from api import app
from engine import collection_loop
from generate_certs import generate_certificates, SERVER_KEY, SERVER_CRT

# Default log level - can be set here or via --log-level command line argument
log_level = "OFF"
LOG_FILE = "/var/log/pi-solar.log"

def setup_logging(level_name):
    if not level_name or level_name.upper() == "OFF":
        return

    level = logging.INFO
    if level_name.upper() == "DEBUG":
        level = logging.DEBUG
    elif level_name.upper() == "STANDARD":
        level = logging.INFO
    elif level_name.upper() == "ERROR":
        level = logging.ERROR
    else:
        # If an invalid level is provided, we'll default to INFO if it wasn't OFF
        level = logging.INFO

    # Check if we can write to the log file
    try:
        if os.path.exists(LOG_FILE):
            if not os.access(LOG_FILE, os.W_OK):
                raise PermissionError(f"Cannot write to log file: {LOG_FILE}")
        else:
            parent_dir = os.path.dirname(LOG_FILE)
            if not os.access(parent_dir, os.W_OK):
                raise PermissionError(f"Cannot create log file in: {parent_dir}")
    except Exception as e:
        print(f"Logging Error: {e}")
        sys.exit(1)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging initialized at level {level_name}")

async def main(log_level_arg):
    global log_level
    # Command line argument takes precedence
    effective_log_level = log_level_arg if log_level_arg is not None else log_level

    setup_logging(effective_log_level)

    # Ensure certificates are generated
    generate_certificates()

    # Start the collection loop as a background task
    collection_task = asyncio.create_task(collection_loop())

    # Start the FastAPI server
    uvicorn_log_level = "info"
    if effective_log_level.upper() == "DEBUG":
        uvicorn_log_level = "debug"
    elif effective_log_level.upper() == "OFF" or effective_log_level.upper() == "ERROR":
        uvicorn_log_level = "error"

    # HTTP Config
    http_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level=uvicorn_log_level)
    http_server = uvicorn.Server(http_config)

    # HTTPS Config
    https_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8443,
        log_level=uvicorn_log_level,
        ssl_keyfile=SERVER_KEY,
        ssl_certfile=SERVER_CRT
    )
    https_server = uvicorn.Server(https_config)

    # Run both servers
    await asyncio.gather(
        http_server.serve(),
        https_server.serve()
    )

    # Cancel the collection task when the server stops
    collection_task.cancel()
    try:
        await collection_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pi Solar Monitor")
    parser.add_argument("--log-level", type=str, help="Set log level (OFF, STANDARD, ERROR, DEBUG)", default=None)
    args = parser.parse_args()

    try:
        asyncio.run(main(args.log_level))
    except KeyboardInterrupt:
        print("System shutting down...")
