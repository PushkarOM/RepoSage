from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.models import user  
from app.api.routes import router
from app.api.auth import router as auth_router

app = FastAPI(title="RepoSage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "RepoSage API running"}
