from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import gradio as gr
import uvicorn
from threading import Thread

app = FastAPI()

# 定义一个简单的FastAPI路由
@app.get("/api/hello")
async def read_root():
    return {"message": "Hello World"}

# 定义Gradio界面函数
def greet(name: str) -> str:
    return f"Hello {name}!"

# 创建Gradio界面
iface = gr.Interface(fn=greet, inputs="text", outputs="text")

# 启动Gradio界面的线程
def run_gradio():
    iface.launch(server_name="0.0.0.0", server_port=7860, share=False, inline=False)

gradio_thread = Thread(target=run_gradio)
gradio_thread.start()

# 将Gradio界面嵌入到FastAPI应用中
@app.get("/gradio")
async def gradio_app():
    # 生成嵌入Gradio界面的HTML内容
    html_content = """
    <html>
        <head>
            <title>Gradio Interface</title>
        </head>
        <body>
            <iframe src="http://127.0.0.1:7860/" width="100%" height="800px" frameborder="0"></iframe>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    # 启动FastAPI应用
    uvicorn.run(app, host="0.0.0.0", port=8000)