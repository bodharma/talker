# talker/main.py
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from talker.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Talker", lifespan=lifespan)

templates = Jinja2Templates(directory="talker/templates")
