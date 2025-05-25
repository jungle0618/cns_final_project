'''
負責幫助peer之間傳遞資料，不會儲存資料
'''
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import logging
import json
import queue
import json
import os
from datetime import datetime
from network import socketTools
from encrypt.signature import DigitalSignature
from log.loggingTools import logger
# 配置日誌格式
class Client:
    pass
class Room:
    pass
class SocketServer:
    pass



class Client:
    def __init__(self, socket:socket.socket, host:str, port:int):
        self.host = host
        self.port = port
        self.socket = socket
        self.room:Room = None
        self.id = -1
        self.roomId = -1
        self.userId:str = None
    def join(self, room:Room, id:int, roomId:int):
        self.room = room
        self.id = id
        self.roomId = roomId

    def leave(self):
        self.room = None
        self.id = -1
        self.roomId = -1

    def getId(self):
        return self.id
    
    def isInRoom(self):
        return self.roomId != -1
    
class Room:
    def __init__(self, maxSize =4, roomId=48763):
        self.maxSize = maxSize
        self.size = 0
        self.clients:list[Client] = [None]*maxSize
        self.roomId = roomId
        self.lock = threading.Lock()

    def empty(self) -> bool:
        return self.size == 0
    
    def full(self) -> bool:
        return self.size == self.maxSize
    
    def join(self, client:Client):
        assert not self.full()
        with self.lock:
            id = self.find()
            self.clients[id] = client
            client.join(self, id, self.roomId)
            self.size += 1
        return
    
    def leave(self, client:Client):
        assert client.roomId == self.roomId
        with self.lock:
            id = client.getId()
            self.clients[id] = None
            client.leave()
            self.size -=1
        return 

    def find(self) -> int:
        assert not self.full()
        for i in range(self.maxSize):
            if self.clients[i] is None:
                return i
        logger.error('find room error')
    
    def allClients(self) -> list[Client]:
        return [client for client in self.clients if client != None]
    
    def getSize(self) -> int:
        return self.size

class SocketServer:
    def __init__(self, host='0.0.0.0', port=9999, max_threads=10):

        self.host = host
        self.port = port
        self.max_threads = max_threads
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind((self.host, self.port))
        self.serverSocket.listen(max_threads)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_threads)
        logger.info(f"Server started on {self.host}:{self.port}")
        # p2p
        self.rooms:list[Room] = []
        self.lock = threading.Lock()

        self.digitalSignature = DigitalSignature()
        self.isSignature = True
        self.userId = self.digitalSignature.getUserId()

    def recvMsg(self, clientSocket:socket.socket, msgBuf:queue.Queue):
        while msgBuf.empty():
            socketTools.recvMsg(socket=clientSocket, queue=msgBuf)
        msg = msgBuf.get()
        print(msg)
        return msg

    def sendMsg(self, msg:dict, clientSocket:socket.socket):
        socketTools.sendMsg(socket=clientSocket,
                            index=-2,
                            peerIndex=-1,
                            isSignature=self.isSignature,
                            userId=self.userId,
                            msg=msg,
                            digitalSignature=self.digitalSignature)
    def tranMsg(self, msg:dict, clientSocket:socket.socket):
        data = json.dumps(msg, sort_keys=True, separators=(',', ':'))   + '\n'
        clientSocket.sendall(data.encode('utf-8'))

    def handle_client(self, clientSocket:socket.socket, client_address):
        msgBuf = queue.Queue()
        client = Client(socket= clientSocket,
                        host=client_address[0],
                        port=client_address[1])
        try:
            while True:
                msg = self.recvMsg(clientSocket,msgBuf)
                if int(msg["metadata"]["receiver"]) == -2: 
                    match msg["payload"]["type"]:
                        case 'join':
                            self.join(client)
                        case 'leave':
                            self.leave(client)
                        case 'login':
                            userId = msg["metadata"]["userId"]
                            client.userId = userId
                        case 'updateLog':
                            log = msg["payload"]["log"]
                            self.updateLog(client=client, log=log)
                else:
                    assert client.id == int(msg["metadata"]["sender"])
                    peerIndex = int(msg["metadata"]["receiver"])
                    self.transfer(client=client, msg=msg, peerIndex=peerIndex)

        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            clientSocket.close()
            logger.info(f"Connection closed for {client_address}")
    
    def create(self, maxSize:int) -> Room:
        room = Room(maxSize=maxSize)
        self.rooms.append(room)
        return room
    
    def find(self) -> Room:
        for room in self.rooms:
            if not room.full():
                return room
        return None
    
    def join(self, client:Client):
        if client.isInRoom():
            return
        room = self.find()
        if room == None:
            room = self.create(maxSize=4)
        room.join(client)
        if room.full():
            userIds = [c.userId for c in room.allClients()]
            for c in room.allClients():
                self.sendMsg({
                    'type':'server',
                    'msg':'someone join',
                    'number of people in room':room.getSize(),
                    'id': c.id,
                    'is full': room.full(),
                    'userIds':userIds
                }, c.socket)
        return
    
    def leave(self, client:Client):
        if not client.isInRoom():
            return
        room = client.room
        room.leave(client)
        self.sendMsg({
            'type':'server',
            'msg':'leave success',
        }, client.socket)
        for c in room.allClients():
            self.sendMsg({
                'type':'server',
                'msg':'someone leave',
                'number of people in room':room.getSize()
            }, c.socket)
    
    def transfer(self, client:Client, msg:dict, peerIndex:int):
        if not client.isInRoom():
            return
        room = client.room
        if peerIndex == -1:#boradcast
            for c in room.allClients():
                if c.id != client.id:
                    print(c.id, client.id)
                    self.tranMsg(msg, c.socket)
        else:
            peer = room.clients[peerIndex]
            self.tranMsg(msg, peer.socket)

    def updateLog(self, client:Client, log:dict):
        log_dir = "game_logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # 2. 生成唯一的文件名（使用时间戳和客户端ID）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{log_dir}/game_log_{client.userId}_{timestamp}.json"
        
        # 3. 将字典转换为JSON并写入文件
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=4, ensure_ascii=False)
                f.write('\n')  # 添加换行符使文件更易读
            
            print(f"日志已成功保存到: {filename}")
            
            # 4. (可选) 返回文件路径供后续使用
            return filename
            
        except Exception as e:
            print(f"保存日志时出错: {e}")
            raise

    def run(self):
        try:
            while True:
                clientSocket, client_address = self.serverSocket.accept()
                self.thread_pool.submit(self.handle_client, clientSocket, client_address)
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.serverSocket.close()

            self.thread_pool.shutdown(wait=True)



def main():
    server = SocketServer(host='0.0.0.0', port=9999, max_threads=10)
    server.run()
