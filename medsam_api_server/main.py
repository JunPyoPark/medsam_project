import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medsam_api_server.api.v1.jobs import router as jobs_router

app = FastAPI(title="MedSAM2 API Server", version="0.1.0")

origins = [
    os.getenv("CORS_ORIGIN", "*")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)


@app.get("/")
async def root():
    return {"ok": True}