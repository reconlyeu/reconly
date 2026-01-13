# Reconly API

FastAPI-based REST API for single-user Reconly deployments.

## Features

- RESTful API endpoints for sources, feeds, digests, and templates
- Built-in scheduler for automated feed runs (APScheduler)
- Background task processing via FastAPI BackgroundTasks
- Health monitoring
- OpenAPI documentation

## Installation

```bash
pip install reconly-api
```

## Usage

```bash
uvicorn reconly_api.main:app --host 0.0.0.0 --port 8000
```

The scheduler starts automatically with the API and runs feed schedules based on cron expressions.

## License

AGPL-3.0
