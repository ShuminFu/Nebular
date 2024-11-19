from fastapi import FastAPI, HTTPException
from your_application import WorkflowManager

app = FastAPI()
manager = WorkflowManager()

@app.post("/query")
async def handle_query(user_query: str):
    try:
        response = manager.run(user_query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))