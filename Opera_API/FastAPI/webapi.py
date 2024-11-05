from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    bot, opera, staff, resource, 
    dialogue, invitation, stage, 
    temp_file, property
)

app = FastAPI(
    title="Opera API",
    version="1.0.0",
    description="Opera API服务",
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
    property.router
]

for router in routers:
    app.include_router(router)
