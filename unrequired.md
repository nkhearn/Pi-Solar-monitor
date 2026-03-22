# Unrequired Requirements Audit

This document tracks the removal and retention of packages from `requirements.txt` for the `pi solar monitor` project. The goal is to minimize external dependencies without impacting performance or functionality, especially considering the target hardware (Pi Zero 2 W).

| Requirement | Status | Reason |
| :--- | :--- | :--- |
| `aiohappyeyeballs` | Removed | Dependency of `aiohttp`, which is not used. |
| `aiohttp` | Removed | Not used in the codebase. `requests` (or `urllib`) is used for synchronous HTTP calls. |
| `aiosignal` | Removed | Dependency of `aiohttp`. |
| `annotated-doc` | Removed | Transitive dependency of `fastapi`. No need to list explicitly. |
| `annotated-types` | Removed | Transitive dependency of `pydantic`. No need to list explicitly. |
| `anyio` | Removed | Transitive dependency of `fastapi`. No need to list explicitly. |
| `attrs` | Removed | Dependency of `aiohttp`. |
| `certifi` | Removed | Transitive dependency of `requests`. |
| `charset-normalizer` | Removed | Transitive dependency of `requests`. |
| `click` | Removed | Transitive dependency of `uvicorn`. |
| `fastapi` | **Kept** | Core framework for the API. |
| `frozenlist` | Removed | Dependency of `aiohttp`. |
| `greenlet` | Removed | Transitive dependency of `playwright`. |
| `h11` | Removed | Transitive dependency of `uvicorn`. |
| `idna` | Removed | Transitive dependency of `requests`. |
| `multidict` | Removed | Dependency of `aiohttp`. |
| `playwright` | **Kept** | Required for UI verification tests. |
| `propcache` | Removed | Dependency of `aiohttp`. |
| `pydantic` | Removed | Transitive dependency of `fastapi`. No need to list explicitly. |
| `pydantic_core` | Removed | Transitive dependency of `pydantic`. |
| `pyee` | Removed | Transitive dependency of `playwright`. |
| `requests` | Removed | Replaced with standard library `urllib.request` in `engine.py` and collectors. |
| `starlette` | Removed | Transitive dependency of `fastapi`. |
| `typing-inspection` | Removed | Transitive dependency of `fastapi`. |
| `typing_extensions` | Removed | Transitive dependency of `fastapi`. |
| `urllib3` | Removed | Transitive dependency of `requests`. |
| `uvicorn` | **Kept** | Core ASGI server for running the FastAPI application. |
| `websockets` | **Kept** | Used for real-time data updates. |
| `yarl` | Removed | Dependency of `aiohttp`. |
| `mysql-connector-python` | **Kept** | Required for importing data from EmonCMS (MySQL). |

## Summary of Changes

- Removed `aiohttp` and all its sub-dependencies as it was unused.
- Replaced `requests` with the built-in `urllib.request` in `engine.py`, `collectors/solar_predict.py`, and `tests/test_new_endpoints.py` to reduce external dependencies.
- Trimmed `requirements.txt` to only include direct, top-level requirements (`fastapi`, `uvicorn`, `websockets`, `playwright`, `mysql-connector-python`), allowing the package manager to handle transitive dependencies.
