# AI 模型處理服務專案 - 開發者指南

## 1. 專案目標與架構概覽

這個專案提供一個穩定的 Web 服務框架，讓 AI 工程師能專注在模型開發，不用處理複雜的後端排程與前端互動。

使用者從網頁上傳資料後，系統會把這件事當作一個「任務」，丟進佇列中排隊。處理完後，結果會即時回傳給使用者。這種**非同步**設計的好處是，就算 AI 模型跑很久，使用者的網頁也不會卡住，系統也能同時服務很多人。

### [修改] 核心工作流程 (新版)

1.  **接收任務**：前端介面 (UI) 將使用者上傳的 PDF 或文字，透過 API 傳送給後端。
2.  **任務排隊**：後端伺服器 (FastAPI) 收到請求後，將任務打包好，放入一個任務佇列 (Redis)。
3.  **執行模型**：一個獨立的運算程序 (Celery Worker) 會持續監控佇列。一旦發現新任務，它就會取出並執行指定的 AI 處理腳本 (`tasks.py`)。
4.  **[新] 發布進度**：在模型運算過程中，Celery Worker 會將進度訊息**發布**到 Redis 的一個特定頻道 (Pub/Sub)。
5.  **[新] 訂閱與轉發**：FastAPI 伺服器會持續**訂閱** Redis 的那個頻道。一旦收到來自 Celery 的訊息，它就會透過 WebSocket 將訊息轉發給正確的前端使用者。

## 2. 關鍵技術角色解析

可以把整個系統想像成一個分工合作的團隊：

* **前端 (`index.html` + React)**
    * **角色**：使用者介面 (UI)。
* **後端 API (`main.py` + FastAPI)**
    * **角色**：總機/接待員 兼 **訊息轉發員**。它接收請求、指派任務，並負責監聽來自 Redis 的內部訊息，再轉發給使用者。
* **任務佇列 Broker (`Redis`)**
    * **角色**：**任務待辦清單 (To-Do List)** 兼 **中央郵局 (Post Office)**。它既存放待辦任務，也負責傳遞 Celery 和 FastAPI 之間的進度訊息。
* **運算核心 (`tasks.py` + Celery)**
    * **角色**：AI 工程師/科學家。這是整個系統的「大腦」。它從 Redis 領取任務，執行運算，並將進度回報給 Redis 郵局。
* **即時通訊 (`WebSocket`)**
    * **角色**：內部直線電話。FastAPI 透過它將從 Redis 收到的訊息，即時通知使用者。
... (後續內容省略，與 Canvas 版本相同)

## **3. 專案結構**

.  
├── uploads/              # (自動建立) 存放使用者上傳的暫存檔案  
├── results/              # (自動建立) 存放由 Server B 回傳的結果檔案  
├── index.html            # 前端應用程式 (UI)  
├── main.py               # 後端總機 (FastAPI)  
├── tasks.py              # AI 運算核心 (Celery 任務) - **主要工作區**  
├── celery_app.py         # Celery 設定檔  
├── requirements.txt      # Python 依賴套件  
└── README.md             # 本說明檔案

## **4. 環境設定與啟動指南**

### **步驟 1: 建立任務佇列 (安裝 Redis)**

AI 任務需要一個地方排隊，這裡用的是 Redis。

**(若伺服器無法連外網，請跳過步驟1與2並參閱【6.離線環境安裝指南】)**

* **macOS (使用 Homebrew):**  
  brew install redis  
  brew services start redis

* **Linux (Ubuntu/Debian):**  
  sudo apt-get update  
  sudo apt-get install redis-server  
  sudo systemctl enable redis-server.service

* **Windows:** 建議使用 WSL2 (Windows Subsystem for Linux) 或 Docker 來運行 Redis。

### **步驟 2: 設定 Python 獨立環境**

為了避免與系統中其他的 Python 專案互相干擾，建議建立一個獨立的虛擬環境。

```bash
# 1. 建立一個新的 Conda 環境 (例如取名為 drc-gui)
# 建議指定一個明確的 Python 版本，例如 3.10
conda create --name drc-gui python=3.10

# 2. 啟用這個新建立的 Conda 環境
conda activate drc-gui

# 3. 在這個獨立的環境中，安裝所有 Web 服務需要的套件
pip install -r requirements.txt
```

### **步驟 3: 啟動所有服務 (重要！)**

需要開啟 **3 個**獨立的終端機視窗，並確保每個視窗都已啟用虛擬環境 (source venv/bin/activate)。這代表要同時啟動「總機」、「AI 運算核心」和「監控儀表板」。

**1. 終端機 1: 啟動 AI 運算核心 (Celery Worker)**

此程序會待命，隨時準備從 Redis 佇列中接收並執行 AI 任務。
```bash
celery -A celery_app worker --loglevel=info
```
**2. 終端機 2: 啟動後端總機 (FastAPI Web Server)**

此程序會開始監聽來自前端的 HTTP 請求。
```bash
uvicorn main:app --reload
```
**3. 終端機 3: (可選) 啟動監控儀表板 (Flower)**

Flower 提供一個網頁介面，能即時查看目前有哪些任務在排隊、哪些已完成。
```bash
# 若尚未安裝  
pip install flower  

# 啟動  
celery -A celery_app flower --port=5555
```
接著在瀏覽器中開啟 http://localhost:5555 查看。

### **步驟 4: 開啟前端介面**

用網頁瀏覽器**開啟 以下網址**即可開始測試。
http://127.0.0.1:8000

## **5. 如何整合 AI 模型**

**這是最需要關注的部分。**

所有核心的 AI 邏輯都放在 tasks.py 檔案裡。

1. **找到 run_ai_processing_task 函式**: 這是整個任務的進入點。  
2. **修改 mock_ai_model 函式**: 把這個函式裡的 time.sleep(5) 換成真實的 AI 模型載入與推論 (inference) 程式碼。  
3. **修改 FTP 相關函式**: 在 mock_ftp_to_server_b 和 mock_wait_for_server_b_response 裡，要實現與 Server B 進行檔案交換的邏輯，可以使用 Python 內建的 ftplib 函式庫。  
4. **(可選) 更新進度**: 在模型運算過程中，可以多次呼叫 update_progress 函式來回傳即時進度。

## **6. 離線環境安裝指南**

若 AI 伺服器無法連外網，請照著這個流程操作。

### **階段 A: 在可上網的電腦上準備安裝包**

1. **建立工作目錄**：  
   `mkdir offline-packages && cd offline-packages`

2. **複製 requirements.txt**：  
   `cp ../requirements.txt .`
3. **下載所有套件**：此指令會下載所有套件及其依賴項的安裝檔。  
   `pip download -r requirements.txt`

4. **打包**：將整個 offline-packages 資料夾壓縮成一個 .tar.gz 檔。  
   `cd ..`
   `tar -czvf offline-packages.tar.gz offline-packages/`


### **階段 B: 在離線的 AI 伺服器上進行安裝**

1. **傳輸與解壓縮**：將 offline-packages.tar.gz 檔複製到伺服器上並解壓縮。  
  ```sh
  tar -xzvf offline-packages.tar.gz
  ```
2. **設定 Python 虛擬環境** (同步驟 2)。  
    
     a. 建立一個新的 Conda 環境 (例如取名為 drc-gui)
     建議指定一個明確的 Python 版本，例如 3.10    
    ```sh
    conda create --name drc-gui python=3.10
    ```    
    b. 啟用這個新建立的 Conda 環境    
    ```sh
    conda activate drc-gui
    ```
    
3. **從本地資料夾安裝**：此指令會強制 pip 從提供的本地資料夾安裝，而不是從網路。  
   ```sh
   pip install --no-index --find-links=./offline-packages -r ./offline-packages/requirements.txt
   ```

### **階段 C: 在可上網的電腦上準備安裝包 針對 Redis (適用於 Ubuntu/Debian)**

*注意：這台電腦的系統版本最好與離線伺服器一致 (例如，同為 Ubuntu 24.04.3 LTS)。*
```bash
# 1. 建立下載目錄: 
mkdir redis-offline-install && cd redis-offline-install
# apt-cache depends --recurse --no-recommends --no-suggests redis-server | grep "^\w" | xargs sudo apt-get download

# 2. 僅下載不安裝: 此指令會找出 redis-server 所有需要的 .deb 檔案並下載到系統快取。  
sudo apt-get install --download-only redis-server

# 3. 複製安裝檔: 將所有下載好的 .deb 檔案從快取複製到目前目錄。  
sudo cp /var/cache/apt/archives/*.deb .

# 4. 打包: 將整個資料夾壓縮，方便傳輸。  
cd ..  
tar -czvf redis-offline-install.tar.gz redis-offline-install/
```

### **階段 D: 在離線的 AI 伺服器上安裝 Redis**
1. **傳輸與解壓縮**: 將 `redis-offline-install.tar.gz` 檔複製到伺服器上並解壓縮。  
  ```bash
  tar -xzvf redis-offline-install.tar.gz
  ```
2. **本地安裝**: 使用 dpkg 指令安裝資料夾內所有的 `.deb` 檔案。  
  ```bash
  cd redis-offline-install  
  sudo dpkg -i *.deb
  ```

3. **啟動與驗證**: 安裝完成後，即可啟動服務。  
  ```bash
  sudo systemctl start redis-server  
  sudo systemctl enable redis-server.service  
  redis-cli ping # 看到 PONG 即為成功  
  ```

  **回到4.步驟 3開啟服務**

## **7. 如何讓團隊成員訪問 (進階)**

預設情況下，這個服務只會在本機 (localhost 或 127.0.0.1) 運行。若要讓區域網路內的其他電腦也能訪問這個網頁介面，需要進行以下設定：

### **步驟 1: 找出 AI 伺服器的區域網路 IP**

首先，需要知道運行這個服務的 AI 伺服器在區域網路 (LAN) 中的 IP 位址。

在 AI 伺服器的終端機中，執行以下指令之一：
```sh
# 建議使用 ip addr  
ip addr show

# 或是傳統的 ifconfig  
ifconfig
```
找到類似 inet 192.168.1.101/24。  
其中192.168.1.101 就是區域網路 IP。

### **步驟 2: 修改後端伺服器啟動指令**

為了讓 FastAPI 伺服器接收來自外部的連線，需要修改**終端機 2** 的啟動指令。

將原本的指令：  
uvicorn main:app --reload  
修改為：  
uvicorn main:app --reload --host 0.0.0.0

* --host 0.0.0.0 的意思是告訴伺服器「監聽所有網路介面」，而不僅僅是本機。

### **步驟 3: 設定伺服器防火牆**

出於安全考量，伺服器的防火牆通常會阻擋來自外部的連線。需要明確地允許 8000 連接埠 (port) 的通訊。

* **在 Ubuntu/Debian 上 (使用 ufw 防火牆):**  
  ```bash
  # 允許 8000 連接埠的 TCP 流量  
  sudo ufw allow 8000/tcp

  # 檢查防火牆狀態，確認規則已加入  
  sudo ufw status
  ```

### **步驟 4: 從其他電腦訪問**

完成以上設定後，任何人只要和 AI 伺服器在同一個區域網路內，就可以在瀏覽器中輸入以下網址來訪問：

http://<AI_伺服器的_IP_位址>:8000

例如：http://192.168.1.101:8000