# Verification Mocks and Script

This directory contains the logic used to verify the application in a simulated environment.

## Contents
- `verify_all.py`: A Playwright script that starts the system (assuming database is initialized), navigates the dashboard, and captures screenshots and API responses.

## How it was tested
The following steps were taken to verify the code:
1. Created mock files for 1-wire sensors in `mocks/w1/`.
2. Created a mock `mpp-solar` executable in `mocks/mpp-solar-mock.py`.
3. Temporarily patched `collectors/inverter.py` and `collectors/temps.py` to use these mocks.
4. Temporarily reduced the collection interval in `engine.py` to 5 seconds.
5. Initialized the database with `python3 init_db.py`.
6. Ran the application with `python3 main.py`.
7. Executed `verify_all.py` to capture the interface.
8. Reverted all patches to the source code.
