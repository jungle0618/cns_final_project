import hashlib
import json
class HashChain:
    def __init__(self):
        self.chain = []
        genesis_hash = self._hash("GENESIS")
        self.chain.append(("GENESIS", genesis_hash))

    def _hash(self, data):
        # 使用SHA-256計算雜湊值
        return hashlib.sha256(data.encode()).hexdigest()

    def add_operation(self, action:str):
        # 取得前一個雜湊值
        last_hash = self.chain[-1][1] if self.chain else "0"
        # 將操作與前一個雜湊值拼接
        operation_data = f"{action}:{last_hash}"
        new_hash = self._hash(operation_data)
        self.chain.append((action, new_hash))
        return new_hash

    def verify_chain(self):
        # 驗證雜湊鏈是否未被篡改
        for i in range(1, len(self.chain)):
            prev_hash = self.chain[i-1][1]
            current_data = f"{self.chain[i][0]}:{prev_hash}"
            if self._hash(current_data) != self.chain[i][1]:
                return False
        return True
    
    def printLastHash(self):
        print(self.chain[-1][1])
        for i in range(len(self.chain)):
            print(self.chain[i][0])
    
    def getChain(self):
        return self.chain
    
    def compare(self, chain1, chain2):
        str1 = json.dumps(chain1, sort_keys=True, separators=(',', ':'))
        str2 = json.dumps(chain2, sort_keys=True, separators=(',', ':'))
        return str1 == str2

    

        
