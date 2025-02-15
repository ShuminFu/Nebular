import asyncio
import logging
import traceback
from typing import Optional, Dict, Any
from aiohttp import (
    ClientSession, ClientTimeout, ClientError, 
    ServerDisconnectedError, ClientConnectorError,
    ContentTypeError,
    WSMsgType,
    TraceConfig,
    TraceRequestStartParams,
    TraceRequestEndParams,
    TraceRequestExceptionParams
)
import aiohttp
import os
from urllib.parse import urlparse, urlencode, parse_qsl

print(os.environ.get('http_proxy'))
# 配置更详细的日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加aiohttp的详细日志
aiohttp_logger = logging.getLogger('aiohttp')
aiohttp_logger.setLevel(logging.DEBUG)

async def on_request_start(session, trace_config_ctx, params: TraceRequestStartParams):
    logger.debug(f"开始请求: method={params.method} url={params.url}")

async def on_request_end(session, trace_config_ctx, params: TraceRequestEndParams):
    logger.debug(f"请求结束: method={params.method} url={params.url} status={params.response.status}")

async def on_request_exception(session, trace_config_ctx, params: TraceRequestExceptionParams):
    logger.error(f"请求异常: method={params.method} url={params.url}")
    logger.error(f"异常详情: {traceback.format_exc()}")

async def test_negotiate(max_retries: int = 3, retry_delay: float = 1.0) -> Optional[Dict[Any, Any]]:
    """
    测试SignalR协商端点，包含重试机制和详细的错误处理
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    
    Returns:
        Optional[Dict]: 成功时返回协商响应，失败时返回None
    """
    negotiate_url = 'http://opera.nti56.com/signalRService/negotiate'
    headers = {
        # 根据实际情况添加必要头信息
        # 'Authorization': 'Bearer YOUR_TOKEN',
        'Content-Type': 'application/json'
    }
    
    timeout = ClientTimeout(total=10, connect=5)  # 总超时10秒，连接超时5秒
    verify_ssl = False
    
    for attempt in range(max_retries):
        try:
            async with ClientSession(trust_env=True, timeout=timeout) as session:
                logger.info(f"尝试第 {attempt + 1} 次连接到 {negotiate_url}")
                
                async with session.post(
                    negotiate_url,
                    headers=headers,
                    ssl=verify_ssl
                ) as response:
                    logger.info(f"响应状态码: {response.status}")
                    logger.debug(f"响应头: {dict(response.headers)}")
                    
                    # 检查状态码
                    if response.status >= 400:
                        logger.error(f"服务器返回错误状态码: {response.status}")
                        return None
                    
                    try:
                        raw_text = await response.text()
                        logger.debug(f"原始响应: {raw_text}")
                        
                        json_data = await response.json()
                        logger.info("成功获取并解析JSON响应")
                        return json_data
                        
                    except ContentTypeError as e:
                        logger.error(f"响应内容类型错误: {str(e)}\n原始响应: {raw_text}")
                        return None
                    except Exception as e:
                        logger.error(f"JSON解析失败: {type(e).__name__} - {str(e)}")
                        return None
                    
        except aiohttp.ServerDisconnectedError as e:
            print("\n[失败原因] 服务器主动断开连接，可能原因：")
            print(f"详细错误: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
        except ClientConnectorError as e:
            logger.error(f"连接错误: {str(e)} (尝试 {attempt + 1}/{max_retries})")
        except ServerDisconnectedError:
            logger.error(f"服务器断开连接 (尝试 {attempt + 1}/{max_retries})")
        except ClientError as e:
            logger.error(f"客户端错误: {type(e).__name__} - {str(e)} (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.error(f"未预期的错误: {type(e).__name__} - {str(e)} (尝试 {attempt + 1}/{max_retries})")
        
        if attempt < max_retries - 1:
            logger.info(f"等待 {retry_delay} 秒后重试...")
            await asyncio.sleep(retry_delay)
        else:
            logger.error("已达到最大重试次数，放弃重试")
    
    return None

async def check_ping():
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection('opera.nti56.com', 80),
            timeout=10
        )
        writer.close()
        await writer.wait_closed()
        print("网络连接正常")
    except Exception as e:
        print(f"网络不可达: {str(e)}")

def get_websocket_url(base_url: str, connection_id: str) -> str:
    """
    将HTTP URL转换为WebSocket URL并添加connection_id
    
    Args:
        base_url: 基础URL（http://或https://开头）
        connection_id: 从negotiate获取的connection ID
    
    Returns:
        str: WebSocket URL
    """
    parsed = urlparse(base_url)
    ws_scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    # 移除末尾的/negotiate
    path = parsed.path.replace('/negotiate', '')
    # 构建查询参数
    query_params = {'id': connection_id}
    if parsed.query:
        # 如果原URL有查询参数，保留它们
        original_params = dict(parse_qsl(parsed.query))
        query_params.update(original_params)
    
    ws_url = f"{ws_scheme}://{parsed.netloc}{path}?{urlencode(query_params)}"
    return ws_url

async def test_websocket_connection(ws_url: str, timeout: int = 30) -> bool:
    """
    测试WebSocket连接
    
    Args:
        ws_url: WebSocket URL
        timeout: 连接超时时间（秒）
    
    Returns:
        bool: 连接是否成功
    """
    # 创建trace config
    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)
    trace_config.on_request_exception.append(on_request_exception)
    
    try:
        logger.info(f"准备连接WebSocket: {ws_url}")
        logger.debug(f"连接参数: timeout={timeout}, heartbeat=30.0, ssl=False")
        
        async with ClientSession(trust_env=True, trace_configs=[trace_config]) as session:
            try:
                logger.debug("开始建立WebSocket连接...")
                async with session.ws_connect(
                    ws_url,
                    timeout=timeout,
                    ssl=False,
                    heartbeat=30.0,
                    protocols=['json', 'text'],  # 添加支持的子协议
                    compress=15  # 启用压缩
                ) as ws:
                    logger.info("WebSocket连接成功建立")
                    # 获取更多可用的连接信息
                    try:
                        local_addr = ws._writer.transport.get_extra_info('socket').getsockname() if ws._writer and ws._writer.transport else None
                        remote_addr = ws._writer.transport.get_extra_info('socket').getpeername() if ws._writer and ws._writer.transport else None
                        logger.debug(f"WebSocket连接信息: 本地地址={local_addr}, 远程地址={remote_addr}")
                    except Exception as e:
                        logger.debug(f"无法获取详细的连接信息: {str(e)}")
                    
                    logger.debug(f"使用的子协议: {ws.protocol}")
                    logger.debug(f"压缩状态: {ws.compress}")
                    
                    # 发送一个简单的ping消息
                    logger.debug("准备发送ping消息...")
                    await ws.ping()
                    logger.info("ping消息发送成功")
                    
                    # 等待任意消息
                    try:
                        logger.debug("等待服务器响应...")
                        msg = await ws.receive(timeout=10.0)
                        logger.debug(f"收到原始消息: type={msg.type}, data={msg.data}")
                        
                        if msg.type == WSMsgType.PONG:
                            logger.info("收到pong响应")
                        elif msg.type == WSMsgType.CLOSE:
                            logger.warning(f"服务器请求关闭连接，代码: {msg.data}, 原因: {msg.extra}")
                        elif msg.type == WSMsgType.TEXT:
                            logger.info(f"收到文本消息: {msg.data}")
                        elif msg.type == WSMsgType.BINARY:
                            logger.info(f"收到二进制消息，长度: {len(msg.data)} 字节")
                        else:
                            logger.info(f"收到其他类型消息: type={msg.type}, data={msg.data}")
                    except asyncio.TimeoutError:
                        logger.warning("等待消息超时，但连接已建立")
                    
                    # 正常关闭连接
                    logger.debug("准备关闭WebSocket连接...")
                    await ws.close()
                    logger.info("WebSocket连接已正常关闭")
                    return True
                    
            except aiohttp.ClientError as e:
                logger.error(f"WebSocket连接错误: {type(e).__name__} - {str(e)}")
                logger.error(f"错误详情:\n{traceback.format_exc()}")
                return False
                
    except asyncio.TimeoutError:
        logger.error(f"WebSocket连接超时 (timeout={timeout}秒)")
    except Exception as e:
        logger.error(f"未预期的错误: {type(e).__name__} - {str(e)}")
        logger.error(f"错误堆栈:\n{traceback.format_exc()}")
    return False

if __name__ == "__main__":
    logger.info("=== 开始SignalR连接测试 ===")
    
    # 测试网络连通性
    logger.info("正在测试基础网络连通性...")
    asyncio.run(check_ping())
    
    # 执行negotiate
    logger.info("开始negotiate请求...")
    negotiate_result = asyncio.run(test_negotiate())
    logger.info(f"Negotiate结果: {negotiate_result}")
    
    if negotiate_result and 'connectionId' in negotiate_result:
        base_url = 'http://opera.nti56.com/signalRService'
        ws_url = get_websocket_url(base_url, negotiate_result['connectionId'])
        logger.info(f"生成的WebSocket URL: {ws_url}")
        
        # 测试WebSocket连接
        logger.info("开始测试WebSocket连接...")
        ws_success = asyncio.run(test_websocket_connection(ws_url))
        logger.info(f"WebSocket连接测试{'成功' if ws_success else '失败'}")
    else:
        logger.error("无法获取connection ID，WebSocket测试取消")
    
    logger.info("=== SignalR连接测试结束 ===")