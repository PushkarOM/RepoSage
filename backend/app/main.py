from fastapi import FastAPI
from app.core.database import Base, engine
from app.models import user  
from app.api.routes import router
from app.api.auth import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RepoSage")
app.include_router(auth_router)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "RepoSage API running"}
