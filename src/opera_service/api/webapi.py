from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.opera_service.api.routers import (
    opera, resource,
    stage
)
from src.opera_service.api.routers import bot, temp_file, dialogue, opera_property, invitation, staff

app = FastAPI(
    title="src API",
    version="1.0.0",
    description="src API服务",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
routers = [
    bot.router,
    opera.router,
    staff.router,
    resource.router,
    dialogue.router,
    invitation.router,
    stage.router,
    temp_file.router,
    opera_property.router
]

for router in routers:
    app.include_router(router)
