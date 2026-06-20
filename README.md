FA 自動分析助手 (FA AI Diagnosis Assistant)本項目是一款基於 Streamlit、FAISS 向量檢索與 Local LLM (Ollama - DeepSeek-R1) 構建的電子產品不良分析（Failure Analysis, FA）決策支持工具。

它能夠自動讀取、清洗歷史維修 Excel 數據，利用語義向量實現精準的故障現象（Fail Symptom）匹配，並結合本地大語言模型生成結構化的深度診斷分析報告。

核心特性智能語義檢索：採用 bge-small-zh-v1.5 嵌入模型，擺脫傳統關鍵字匹配的局限，即使輸入的故障現象描述不同（如拼寫略有差異或同義詞），也能通過餘弦相似度精準檢索。

強健的 Excel 數據兼容性：支持多層合併標題（Multi-index Header）壓平處理。具備寬鬆的欄位模糊匹配機制，自動識別 Fail Symptom、FA Summary/FA Status 及 Station。

支持多個 Excel 文件的自動掃描與數據合併，並具備前向填充（ffill）修復缺失站別數據的能力。

高效向量索引與內存優化：基於 FAISS (IndexFlatIP) 實現高速向量比對。內置 L2 正規化 (Normalize L2)，確保檢索得分精確落在 0 - 100% 區間內。支持索引緩存校驗，僅在數據量發生變化時重新構建索引，提升啟動速度。

生成式 AI 深度診斷：集成本地 Ollama 服務，調用 DeepSeek-R1:1.5b 模型進行增強檢索生成（RAG），以流式傳輸（Streaming）實時輸出結構化的根本原因分析與維修步驟建議。

響應式 Web 界面：使用 Streamlit 構建，具備清晰的系統狀態看板、摺疊式原始數據對比（Raw Data Expander）以及 AI 聊天交互界面。

架構流程項目核心採用了經典的 RAG (Retrieval-Augmented Generation) 架構：

數據層：掃描 FA_History/ 文件夾下所有 Excel 文件 $\rightarrow$ 提取並壓平標題 $\rightarrow$ 生成/加載 FAISS 索引。

檢索層：用戶輸入故障現象 $\rightarrow$ 向量化並正規化 $\rightarrow$ FAISS 檢索 Top 10 相似案例 $\rightarrow$ 數據聚合與過濾。

生成層：提取最相關的 Top 5 案例拼接為 Context $\rightarrow$ 注入資深維修專家 Prompt $\rightarrow$ Ollama 串流輸出繁體中文分析報告。

環境依賴在運行本項目之前，請確保環境中已安裝 Python 3.8+ 以及以下依賴庫：
前端與核心框架：
streamlit數據處理：pandas、openpyxl、numpy

向量檢索與模型：faiss-cpu（或 faiss-gpu）、sentence-transformers

網絡請求：requests

安裝與配置

1. 克隆與依賴安裝Bash# 安裝所需 Python 依賴包
pip install streamlit pandas openpyxl faiss-cpu numpy sentence-transformers requests

2. 放置本地模型與數據請在腳本同級目錄下建立並配置文件夾：bge-small-zh-v1.5/：下載 BGE 嵌入模型並放置於此目錄。
3. FA_History/：將歷史 FA 記錄的 .xlsx 文件放入此文件夾。注：Excel 文件的第 3、4 行（代碼中為 header=[2, 3]）應包含類似 Fail Symptom、FA Summary 或 Station 的關鍵欄位。
4. 配置本地 Ollama 服務確保本地已安裝 Ollama 並成功拉取目標模型：Bash# 啟動 Ollama 並下載模型ollama run deepseek-r1:1.5b
提示：如果使用其他模型或遠程服務，可修改代碼頂部的 OLLAMA_URL 和 MODEL_NAME 常量。

快速上手在終端中切換至代碼所在目錄，運行以下命令啟動 Streamlit 服務：Bashstreamlit run "FA 不良分析小助手 - LLM.py"
服務啟動後，瀏覽器會自動打開 http://localhost:8501。
此時可以在輸入框中輸入故障現象（例如：Power on fail），系統將自動為你輸出： 深度分析報告：由大模型結合歷史案例生成的維修建議。 檢索參考案例 (Raw Data)：按匹配度（%）從高到低排列的歷史真實維修記錄卡片。

項目文件結構

Plaintext

├── FA 不良分析小助手 - LLM.py  # 主程序代碼

├── bge-small-zh-v1.5/          # HuggingFace 下載的嵌入模型文件夾

├── FA_History/                 # 存放歷史維修 Excel 數據的文件夾

│   ├── FA_Record_2025.xlsx

│   └── Report_Final.xlsx

└── fa.index                    # 系統自動生成的 FAISS 向量索引文件（免手動創建）

注意事項打包兼容性：代碼中集成了 sys._MEIPASS 路徑處理函數 get_resource_path()，這使得項目完美支持使用 PyInstaller 等工具打包成獨立的 .exe 執行文件。

首次加載：第一次運行或修改 FA_History/ 中的數據後，系統會自動觸發 重新建立索引... 提示，這屬於正常現象，構建完成後後續啟動將實現秒級加載。
