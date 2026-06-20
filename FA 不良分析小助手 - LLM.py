import streamlit as st
import pandas as pd
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import glob
import sys
import requests
import json

# --- 設定與路徑 ---
DATA_FOLDER_NAME = "FA_History"
INDEX_FILE_NAME = "fa.index"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "deepseek-r1:1.5b"

COL_SYMPTOM = 'Fail Symptom'
COL_ACTION = 'FA Summary'
COL_STATION = 'Station'

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

@st.cache_resource
def load_resources():
    model_path = get_resource_path("bge-small-zh-v1.5")
    data_folder = get_resource_path(DATA_FOLDER_NAME)
    index_file = get_resource_path(INDEX_FILE_NAME)
    
    if not os.path.exists(model_path):
        st.error(f"❌ 找不到模型資料夾：{model_path}")
        return None, None, None

    model = SentenceTransformer(model_path)
    
    # 掃描 Excel
    all_files = glob.glob(os.path.join(data_folder, "*.xlsx"))
    if not all_files:
        st.error(f"❌ 在 {data_folder} 中找不到任何 .xlsx 檔案！")
        return None, None, None

    df_list = []
    all_files = glob.glob(os.path.join(data_folder, "*.xlsx"))
    
    for file in all_files:
        try:
            # 1. 讀取 Excel (保持 header=)
            temp_df = pd.read_excel(file, engine='openpyxl', header=[2, 3])
            
            # 2. 處理合併標題：將多層標題壓平為單一字串
            new_columns = []
            for col in temp_df.columns:
                clean_parts = [str(c).strip() for c in col if "Unnamed" not in str(c)]
                clean_col = " ".join(clean_parts).strip()
                new_columns.append(clean_col)
            temp_df.columns = new_columns
            
            # 3. 識別欄位 (使用更寬鬆的匹配)
            symptom_col = next((c for c in temp_df.columns if "Fail Symptom" in c), None)
            action_col = next((c for c in temp_df.columns if any(k in c for k in ["FA Summary", "FA Status"])), None)
            station_col = next((c for c in temp_df.columns if "Station" in c), None)

            # 4. 安全檢查與執行更名
            if symptom_col and action_col:
                rename_map = {symptom_col: COL_SYMPTOM, action_col: COL_ACTION}
                if station_col:
                    rename_map[station_col] = COL_STATION
                
                temp_df = temp_df.rename(columns=rename_map)
                if COL_SYMPTOM in temp_df.columns and COL_ACTION in temp_df.columns:
                    if COL_STATION not in temp_df.columns:
                        temp_df[COL_STATION] = "N/A"
                        
                    temp_df['來源檔案'] = os.path.basename(file)
                    
                    df_list.append(temp_df[[COL_SYMPTOM, COL_ACTION, COL_STATION, '來源檔案']])
                else:
                    st.warning(f"⚠️ {os.path.basename(file)} 更名失敗！預期欄位未出現。")
            else:
                st.warning(f"⚠️ {os.path.basename(file)} 找不到標題關鍵字。偵測標題：{list(temp_df.columns[:5])}")

        except Exception as e:
            st.error(f"❌ 讀取 {os.path.basename(file)} 失敗: {e}")


    if not df_list: return None, None, None
    df = pd.concat(df_list, ignore_index=True)

    if COL_STATION in df.columns:
        df[COL_STATION] = df[COL_STATION].ffill()

    # 檢查英文標題

    if COL_SYMPTOM not in df.columns or COL_ACTION not in df.columns:
        st.error(f"❌ Excel 格式不符！目前欄位：{list(df.columns)}")
        return None, None, None

    df[COL_SYMPTOM] = df[COL_SYMPTOM].fillna('')
    df[COL_ACTION] = df[COL_ACTION].fillna('No suggestion')

    # --- 索引邏輯 ---
    need_rebuild = True
    if os.path.exists(index_file):
        index = faiss.read_index(index_file)
        if index.ntotal == len(df):
            need_rebuild = False
    
    if need_rebuild:
        with st.spinner("重新建立索引..."):
            # 確保內容是字串且不為空
            texts = df[COL_SYMPTOM].astype(str).tolist()
            embeddings = model.encode(texts, convert_to_numpy=True).astype('float32')
            
            # 💡 必須執行這行，否則匹配度會破千
            faiss.normalize_L2(embeddings) 
            
            index = faiss.IndexFlatIP(embeddings.shape[1])
            index.add(embeddings)
            faiss.write_index(index, index_file)
            
    return model, df, index


# --- 新增：Ollama 串流產生器 ---
def get_ollama_stream(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                content = chunk.get("response", "")
                yield content
                if chunk.get("done"):
                    break
    except Exception as e:
        yield f"❌ 連接 Ollama 失敗: {str(e)}"

# --- UI 介面 ---
st.set_page_config(page_title="FA AI 診斷助手", layout="wide")
st.title("📂 FA 自動分析助手")

model, df, index = load_resources()

if df is not None:
    st.sidebar.header("📊 系統狀態")
    st.sidebar.info(f"已載入記錄: {len(df)} 筆")
    
    query = st.text_input("🔍 輸入故障現象 (例如: 'Power on fail' 或 'Display abnormal'):")
    
    if query:
        query_vec = model.encode([query]).astype('float32')
        faiss.normalize_L2(query_vec) 
        
        D, I = index.search(query_vec, k=10)
        
        search_results = []
        for dist, idx in zip(D[0], I[0]): 
            if idx == -1: continue
            row = df.iloc[idx].copy()
            row['score'] = round(float(dist) * 100, 1) 
            search_results.append(row)
        
        if search_results:
            res_df = pd.DataFrame(search_results)
            # 聚合相似對策
            merged_df = res_df.groupby(COL_ACTION).agg({
                '來源檔案': lambda x: " | ".join(set(x)),
                COL_SYMPTOM: lambda x: " / ".join(list(dict.fromkeys(x.astype(str)))[:2]),
                COL_STATION: lambda x: " / ".join(list(dict.fromkeys(x.astype(str)))),
                'score': 'max'
            }).sort_values(by='score', ascending=False).reset_index()

            # --- 2. AI 串流分析區塊 ---
            st.subheader("深度分析報告")
            
            # 建立 Prompt Context
            context_text = "\n".join([
                f"- 現象: {r[COL_SYMPTOM]} | 對策: {r[COL_ACTION]} | 站別: {r[COL_STATION]}" 
                for _, r in merged_df.head(5).iterrows()
            ])
            
            prompt = f"""
            你是一名資深電子產品維修專家。
            用戶目前的故障問題是：『{query}』
            
            以下是從歷史資料庫中檢索出的相似案例：
            {context_text}
            
            請根據以上資料進行診斷分析：
            1. 總結最可能的根本原因 (Root Cause)。
            2. 提供具體的檢查與維修步驟建議。
            3. 若有特定站別風險請註明。
            回答要求：專業、精確，使用繁體中文。
            """

            # 串流輸出效果
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = st.write_stream(get_ollama_stream(prompt))
            
            st.divider()

            # --- 3. 原始資料比對區塊 ---
            st.subheader("💡 檢索參考案例 (Raw Data)")
            for i, row in merged_df.iterrows():
                with st.expander(f"案例 {i+1} - 匹配度: {row['score']}%"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**參考現象:**\n{row[COL_SYMPTOM]}")
                    with col2:
                        st.success(f"**建議對策 (FA Summary):**\n\n{row[COL_ACTION]}")
                        if row[COL_STATION] != "N/A":
                            st.warning(f"**對應站別 (Station):** {row[COL_STATION]}")
                    st.caption(f"來自檔案: {row['來源檔案']} | 站別: {row[COL_STATION]}")
        else:
            st.warning("查無相似案例，請嘗試更換關鍵字。")
