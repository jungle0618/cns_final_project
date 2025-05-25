
import socket
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from encrypt.signature import DigitalSignature
import time
import secrets
from network import socketTools
logger = logging.getLogger(__name__)


maxThreads = 5

class Worker():
    def __init__(self, serverHost, serverPort, queue:queue.Queue, userId):
        self.serverHost = serverHost
        self.serverPort = serverPort
        self.queue = queue
        self.userId = userId
        self.isConnect = False
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.serverHost, self.serverPort))
        except Exception as e:
            logger.error(f'error {e}')
        self.isConnect = True

    def getSocket(self):
        assert self.isConnect
        return self.socket


    def runLoop(self):
        while True:
            try:
                socketTools.recvMsg(socket=self.socket, queue=self.queue)
            except Exception as e:
                logger.error(f'Receive error: {e}')
                break
        self.cleanup()

    def cleanup(self):
        try:
            self.socket.close()
        except:
            pass
        self.isConnect = False

class p2pInterface():
    def __init__(self, peerNum=4, isSignature = False, serverHost='0.0.0.0', serverPort=9999):
        
        self.serverHost = serverHost
        self.serverPort = serverPort
        self.peerNum = peerNum
        self.alreadyExchangePubKey = False
        self.isSignature = isSignature
        self.userIds:list[str] = [None]*peerNum
        self.index = -1
        if self.isSignature:
            self.digitalSignature = DigitalSignature()
            self.userId = self.digitalSignature.getUserId()
        else:
            self.digitalSignature = None
            self.userId = -1
        
        #初始化tpool
        self.maxThreads = maxThreads
        self.threadPool = ThreadPoolExecutor(max_workers=self.maxThreads)
        self.queue = queue.Queue()
        self.usedNonces = set()
        #建立連線
        self.p2pStart()

        #數位簽章
        if self.isSignature:
            self.signatureInit()
        return
    
    def p2pStart(self):
        self.worker:Worker = Worker(serverHost=self.serverHost, serverPort=self.serverPort, queue=self.queue, userId = self.userId) 
        self.threadPool.submit(self.worker.runLoop)

        self.sendMsg(message={
            'type':'login'
        },peerIndex= -2)
        self.sendMsg(message={
            'type':'join'
        },peerIndex= -2)

        while True:
            msg = self.recvMsg(type='server')
            if int(msg["is full"]):
                self.index = int(msg["id"])
                self.userIds = msg["userIds"]
                break
        logger.info(f'p2p finish')

    def sendMsg(self, message, peerIndex = -1):
        # Input data is already in JSON format (dict)
        if 'type' not in message:
            logger.error('Error: message must contain type')
            return
        isSignature = self.isSignature and self.alreadyExchangePubKey
        socket = self.worker.getSocket()
        socketTools.sendMsg(socket=socket,
                            index=self.index,
                            peerIndex=peerIndex,
                            isSignature=isSignature,
                            userId=self.userId,
                            msg=message,
                            digitalSignature=self.digitalSignature)
        
    def recvMsg(self, type='') -> dict:
        return socketTools.getMsg(queue=self.queue,type=type,digitalSignature=None, used_nonces=self.usedNonces)
    
    def getIndex(self):
        return self.index
    
    def signatureInit(self):
        self.alreadyExchangePubKey = 0
        
        self.PubKeyList = [""]*self.peerNum
        self.PubKey = self.digitalSignature.getPubKey()
        self.PubKeyList[self.index] = self.PubKey
        msg = {
            'type': 'signature public key',
            'index': self.index,
            'userId': self.userId, 
            'public key': self.PubKey,
            'signature': self.digitalSignature.signature(f'userId: {self.userId}, index: {self.index}, public key: {self.PubKey}')
        }
        self.sendMsg(msg, peerIndex=-1)
        for _ in range(self.peerNum-1):
            msg = self.recvMsg(type='signature public key')
            index = int(msg["index"])
            
            userId = msg["userId"]
            sig = msg["signature"]
            otherpublicKey = msg["public key"]
            ok = self.digitalSignature.verify(sig, otherpublicKey, f'userId: {userId}, index: {index}, public key: {otherpublicKey}')
            if not ok:
                logger.error('error signature')
                continue
            self.PubKeyList[index] = otherpublicKey
        self.alreadyExchangePubKey = 1 #這步驟以後發送和驗證都會使用簽章
        #檢查所有人收到的publiclist是否一樣
        self.sendMsg({
            'type': 'check signature public key',
            'public list': self.PubKeyList,
            'from': self.index
        }, peerIndex=-1)
        temp = [False]*self.peerNum
        temp[self.index] = True
        while not all(temp):
            msg = self.recvMsg(type='check signature public key')
            otherPubKeyList = msg["public list"]
            index = int(msg["from"])
            if self.PubKeyList != otherPubKeyList:
                logger.error(f'error signature aaa')
                self.sendMsg({
                    'type': 'signature result',
                    'result': 'error'
                }, peerIndex=-1)
                return -1
            temp[index] = True
        #發送確認結果
        self.sendMsg({
            'type': 'signature result',
            'result': 'good',
            'from': self.index
        }, peerIndex=-1)
        temp = [False]*self.peerNum
        temp[self.index] = True
        while not all(temp):
            msg = self.recvMsg(type='signature result')
            result = msg["result"]
            index = int(msg['from'])
            if result != "good" or not(0<= index and index<self.peerNum):
                return -1
            temp[index] = True

