"""Main entry point for the FastAPI application."""

from .warnings_filter import filter_warnings

filter_warnings()

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Config
from .db import engine
from .docs import generate_db_schema, save_openapi_json
from .files import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from .models import Base
from .routers import stt, stt_services, task

# Load environment variables from .env
load_dotenv()

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.

    This function is used to perform startup and shutdown tasks for the FastAPI application.
    It saves the OpenAPI JSON and generates the database schema.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    save_openapi_json(app)
    generate_db_schema(Base.metadata.tables.values())
    yield


tags_metadata = [
    {
        "name": "Speech-2-Text",
        "description": "Operations related to transcript",
    },
    {
        "name": "Speech-2-Text services",
        "description": "Individual services for transcript",
    },
    {
        "name": "Tasks Management",
        "description": "Manage tasks.",
    },
]


app = FastAPI(
    title="whisperX REST service",
    description=f"""
    # whisperX REST Service

    Welcome to the whisperX RESTful API! This API provides a suite of audio processing services to enhance and analyze your audio content.

    ## Documentation:

    For detailed information on request and response formats, consult the [WhisperX Documentation](https://github.com/m-bain/whisperX).

    ## Services:

    Speech-2-Text provides a suite of audio processing services to enhance and analyze your audio content. The following services are available:

    1. Transcribe: Transcribe an audio/video  file into text.
    2. Align: Align the transcript to the audio/video file.
    3. Diarize: Diarize an audio/video file into speakers.
    4. Combine Transcript and Diarization: Combine the transcript and diarization results.

    ## Supported file extensions:
    AUDIO_EXTENSIONS = {Config.AUDIO_EXTENSIONS}

    VIDEO_EXTENSIONS = {Config.VIDEO_EXTENSIONS}

    """,
    version="0.0.1",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# Include routers
app.include_router(stt.stt_router)
app.include_router(task.task_router)
app.include_router(stt_services.service_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def index():
    """Redirect to the documentation."""
    return "/docs"
