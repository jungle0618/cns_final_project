# cns_final_project
現在先瞎雞巴亂寫
## 環境設置
首先先安裝python <br/>
接者在終端機輸入
<br/>
``
pip install requirement.txt
``
## 運行方式
因為還沒有架server，所以server和client目前都是在同台主機上進行
### 啟動server
``
python serverRun.py
``
### 啟動client
另外開啟四個terminal，分別輸入
<br/>
``
python clientRun.py
``
## feature
目前有:<br/>
relay p2p server(解決不了nat穿透)<br/>
mental poker機制<br/>
數位簽章<br/>
hash chain<br/>
nonces(防重播攻擊)
