import socket
from log.loggingTools import logger
import json
import queue
import json
import time
import secrets
from encrypt.signature import DigitalSignature

def sendMsg(socket:socket.socket, 
            index,
            peerIndex,
            isSignature,
            userId,
            msg:dict={},
            digitalSignature: DigitalSignature=None): #peerIndex=-1為sendall, -2為send to server
    msg1 = wrapWithSignature(message=msg,
                             index=index,
                             peerIndex=peerIndex,
                             userId=userId,
                             isSignature=isSignature,
                             digitalSignature=digitalSignature)
    transMsg(socket=socket, msg=msg1)
def transMsg(socket:socket.socket, msg:dict):
    msg_str = json.dumps(msg, sort_keys=True, separators=(',', ':')).encode('utf-8')
    msg_length = len(msg_str).to_bytes(4, byteorder='big')  # 4 bytes length header
    socket.sendall(msg_length + msg_str)

def wrapWithSignature(message: dict,
                      index: int,
                      peerIndex: int,
                      userId: str,
                      isSignature:bool,
                      digitalSignature: DigitalSignature) -> dict:
    # 生成安全相关的元数据
    timestamp = int(time.time())  # 当前UNIX时间戳
    nonce = secrets.token_hex(8)  # 16字节随机数

    # 生成数字签名
    if isSignature:
        # 构建待签名的安全消息（包含所有关键字段）
        secure_message = {
            'original_message': message,
            'timestamp': timestamp,
            'nonce': nonce,
            'sender_index': index,
            'peer_index': peerIndex,  # 包含目标节点信息防止转发攻击
            'userId':userId,
        }
        
        # 确保JSON序列化的一致性（按key排序，紧凑格式）
        message_str = json.dumps(secure_message, sort_keys=True, separators=(',', ':'))
        signature = digitalSignature.signature(message_str)
        # 返回最终消息结构
        return {
            'metadata': {
                'timestamp': timestamp,
                'nonce': nonce,
                'sender': index,
                'receiver': peerIndex,
                'userId': userId,
                'publicKey': digitalSignature.getPubKey(),
            },
            'payload': message,
            'signature': signature,
            'isSigned': True
        }
    else:
        return {
            'metadata': {
                'timestamp': timestamp,
                'nonce': nonce,
                'sender': index,
                'receiver': peerIndex,
                'userId': userId,
            },
            'payload': message,
            'isSigned': False
        }

def recvMsg(socket:socket.socket, queue:queue.Queue):
    # 先收4個byte的長度
    raw_len = socket.recv(4)
    if not raw_len:
        return None
    msg_len = int.from_bytes(raw_len, byteorder='big')
    
    # 再收指定長度的JSON資料
    data = b''
    while len(data) < msg_len:
        more = socket.recv(msg_len - len(data))
        if not more:
            raise ConnectionError("Connection closed before full message received")
        data += more
    json_data = json.loads(data.decode('utf-8'))
    queue.put(json_data)
    return json_data

def getMsg(queue: queue.Queue, 
           type: str = '', 
           digitalSignature: DigitalSignature = None,
           max_timestamp_diff: int = 30,
           used_nonces: set=None) -> dict:
    """
    从队列中获取并验证消息
    
    参数:
        queue: 消息队列
        type: 过滤指定类型的消息（空字符串表示接收所有类型）
        digitalSignature: 数字签名验证对象
        max_timestamp_diff: 允许的最大时间戳差异（秒）
        
    返回:
        - 验证通过的消息内容（dict）
        - None 表示无有效消息或验证失败
    """
    temp_queue = []  # 临时存储不匹配的消息
    
    try:
        while True:
            raw_data = queue.get()
            
            # 1. 基本检查
            if not isinstance(raw_data, dict):
                temp_queue.append(raw_data)
                continue
                
            # 2. 类型过滤
            if type and raw_data.get("payload", {}).get("type") != type:
                temp_queue.append(raw_data)
                continue
                
            # 3. 签名验证（如果要求）
            if digitalSignature and raw_data.get("isSigned", False):
                # 检查必要字段
                required_fields = {"signature", "metadata", "payload"}
                if not all(field in raw_data for field in required_fields):
                    logger.warning("Missing required fields in signed message")
                    temp_queue.append(raw_data)
                    continue
                    
                metadata = raw_data["metadata"]
                payload = raw_data["payload"]
                
                # 3.1 验证时间戳
                current_time = time.time()
                if abs(current_time - metadata.get("timestamp", 0)) > max_timestamp_diff:
                    logger.warning(f"Expired message (timestamp: {metadata['timestamp']})")
                    #temp_queue.append(raw_data)
                    continue
                    
                # 3.2 验证Nonce防重放

                nonce = metadata.get("nonce")

                if nonce in used_nonces:
                    logger.warning(f"Duplicate nonce detected: {nonce}")
                    temp_queue.append(raw_data)
                    continue
                used_nonces.add(nonce)
                # 3.3 重建签名内容
                sign_content = {
                    "original_message": payload,
                    "timestamp": metadata["timestamp"],
                    "nonce": nonce,
                    "sender_index": metadata["sender"],
                    "peer_index": metadata["receiver"],
                    "userId": metadata["userId"]
                }
                message_str = json.dumps(sign_content, sort_keys=True, separators=(',', ':'))
                
                # 3.4 验证签名
                if not digitalSignature.verify(
                    sig_b64=raw_data["signature"],
                    pKey_b64=metadata["publicKey"],
                    msg=message_str
                ):
                    logger.warning("Invalid digital signature")
                    temp_queue.append(raw_data)
                    continue
            
            # 4. 返回有效消息
            # 将非目标消息放回队列
            for item in temp_queue:
                queue.put(item)
            
            return raw_data["payload"]
        
            
    except json.JSONDecodeError:
        logger.error("Failed to decode message")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
    
    return None





