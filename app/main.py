
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import private_messages
import sentry_sdk
from app.settings.config import settings


sentry_sdk.init(
    dsn=settings.sentry_url,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
)



app = FastAPI(
    docs_url="/docs",
    title="Private Messages API",
    description="API for private messages",
    version="0.1.0",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(private_messages.router)
