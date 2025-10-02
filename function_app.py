import azure.functions as func
import logging
import io
import pandas as pd
from openpyxl import load_workbook
import re
import zipfile
from openai import AzureOpenAI
from urllib.parse import quote
from pathlib import Path
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# FunctionAppの初期化
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- Azure OpenAI Service 接続情報 ---
# .envファイルまたは環境変数から設定を読み込む
api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# 必須の環境変数が設定されているか確認
if not all([api_key, endpoint, api_version, deployment]):
    missing_vars = [
        var for var, value in {
            "AZURE_OPENAI_API_KEY": api_key,
            "AZURE_OPENAI_ENDPOINT": endpoint,
            "AZURE_OPENAI_API_VERSION": api_version,
            "AZURE_OPENAI_DEPLOYMENT": deployment
        }.items() if not value
    ]
    raise ValueError(f"必須の環境変数が設定されていません: {', '.join(missing_vars)}")

# AzureOpenAIクライアントの初期化
client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=api_key,
)

def call_openai_structuring(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            messages = [
                {
                    "role": "system",
                    "content": '''
                        あなたは業務システムの設計書を解析し、処理Noごとに意味的に整理されたMarkdownテーブルを作成する構造化エンジニアです。

                        出力要件：
                        - 処理Noごとにセクション分け（例：### 処理No.1）
                        - 各処理に対し、以下の項目を表形式で抽出：
                        - No（1〜999、処理Noとは連動不要）
                        - タイトル
                        - トリガ（画面操作・遷移条件）
                        - 処理内容（要点を簡潔に）
                        - 使用DB・テーブル
                        - 画面遷移先（URLや備考）

                        記述ルール：
                        - 処理内に複数ステップがある場合は、No.を分割して1行ずつ記載
                        - 同一処理内で区分・トリガ・処理内容が重複する場合は、該当欄を省略してもよい（視認性重視）
                        - 処理内容の改行はMarkdownの箇条書き（-）で表現し、`<br>`タグは使用しない
                        - 仕様ルールは注記として記載
                        - 意味のない行・空欄は除外
                        - 出力形式はMarkdown
                    '''
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_completion_tokens=30000,
            model=deployment
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error("構造化処理中にエラーが発生しました。詳細：" + str(e))
        raise RuntimeError("AIによる構造化処理に失敗しました。ログを確認してください。")
    
def call_openai_extract_test_perspectives(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            messages = [
                {
                    "role": "system",
                    "content": '''
                        あなたは業務システムの設計書を解析し、以下の情報を統合してテスト観点抽出を行う構造化エンジニアです。

                        対象情報（すべて構造化済み）：
                        - 画面項目定義（No／項目名／種別／I/O／桁数／必須／初期値／備考）
                        - 処理詳細（処理Noごとの画面遷移・DBアクセス・処理内容）
                        - 画面処理概要（処理Noと画面の関係、使用オブジェクト）
                        - 入力チェック説明（項目ごとのチェック区分・条件・エラーコード）
                        
                        出力形式：
                        - 各シートごとに `##` セクションで分けてください
                        - 各シート内は項目または処理単位で `###` セクションに分けてください
                        - 各項目・処理に対して、以下の3つに分けて構造化（処理No./処理名を明記）
                        - 表示仕様：画面上の表示や初期値、取得元、遷移条件など
                        - 業務ルール：業務上の制約、依存関係、モード別の分岐、DB条件など
                        - テスト観点：入力チェック、表示確認、処理分岐、エラー制御、境界値、異常系など
                        
                        記述ルール：
                        - モード（登録／更新／削除）による分岐は明示
                        - 複数シートにまたがる情報は統合して構造化
                        - テスト観点は網羅的かつ粒度を揃えて抽出
                        - 出力形式はMarkdown
                    '''
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_completion_tokens=30000,
            model=deployment
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error("テスト観点抽出中にエラーが発生しました。詳細：" + str(e))
        raise RuntimeError("AIによるテスト観点抽出に失敗しました。ログを確認してください。")

def call_openai_create_test_spec(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            messages = [
                {
                    "role": "system",
                    "content": '''
                        あなたはソフトウェア品質保証の専門家です。
                        ユーザーが提示する業務アプリケーションの仕様情報をもとに、Excel形式で管理しやすいテスト仕様書を作成してください。

                        出力要件：
                        - 出力形式は以下の4列構成の表形式（Markdown）で統一すること：
                            - No（テストケースごとの連番）
                            - 区分（画面状態や操作単位）
                            - テストケース（操作観点を簡潔に記述）
                            - 期待結果（画面表示 / DB更新 / エラー等）

                        記述ルール：
                        - テスト観点は正常系・異常系・境界値・業務ルール適用などを網羅すること
                        - 区分は「初期表示」「確認ボタン押下」「絞り込み入力時」など、画面状態や操作単位で分類すること
                        - 期待結果が複数ある場合は、Noを分割して1行ずつ記載すること（1期待結果＝1行）
                        - 同じ区分やテストケースが連続する場合は、区分やテストケース欄を省略してもよい（Excelでの視認性を考慮）
                        - 期待結果は、画面表示内容・DB更新内容・エラーメッセージなどを具体的かつ簡潔に記述すること
                        - 業務ルールや仕様注記も反映すること
                        - 出力はMarkdown表形式とし、Excel変換可能な構造で記述すること
                    '''
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_completion_tokens=30000,
            model=deployment
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error("テスト仕様書生成中にエラーが発生しました。詳細：" + str(e))
        raise RuntimeError("AIによるテスト仕様書生成に失敗しました。ログを確認してください。")

def _clean_sheet(df: pd.DataFrame) -> pd.DataFrame:
    original_df = df.copy()
    try:
        # 1. 基本的なクレンジング
        df.dropna(how='all', axis=1, inplace=True) # 全部NaNの列を削除
        df.dropna(how='all', axis=0, inplace=True) # 全部NaNの行を削除
        df.reset_index(drop=True, inplace=True)    # 行番号を振りなおす
        
        rows_before_header_change = len(df)

        # 2. ヘッダー特定と設定
        if not df.empty and len(df) > 1:
            # 上から5行を候補にして「最も空欄が少ない行」をヘッダー列名の行）として採用
            header_candidates = df.head(5)
            best_header_row_index = header_candidates.notna().sum(axis=1).idxmax()
            
            new_header = df.iloc[best_header_row_index] # ヘッダーにする行
            df = df[best_header_row_index + 1:]         # その下からデータ
            df.columns = new_header                     # ヘッダーに設定
        
        # 3. ヘッダー後のクレンジング
        if not df.empty:
            df = df.loc[:, pd.notna(df.columns)] # ヘッダー名がNaNの列を削除
            df.dropna(how='all', inplace=True)   # 空行を削除

        # 4. 【保険】行数が激減していたら、ヘッダー変更を破棄
        if df.empty or (rows_before_header_change > 5 and len(df) < rows_before_header_change * 0.2):
            df = original_df.copy()
            df.dropna(how='all', axis=1, inplace=True)
            df.dropna(how='all', axis=0, inplace=True)

    except Exception:
        # 何かエラーが起きたら、安全策として元のデータに戻す
        df = original_df.copy()
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(how='all', axis=0, inplace=True)

    # 5. 最終的な仕上げ
    df.fillna('', inplace=True)       # NaNを空文字に
    df = df.infer_objects(copy=False) # 型を推測（数字は数値型に）
    return df

@app.route(route="upload", methods=["POST"])
def upload(req: func.HttpRequest) -> func.HttpResponse:
    try:
        file = req.files.get("documentFile")
        file_bytes = file.read()
        filename = file.filename
    except Exception as e:
        logging.error(f"ファイル取得エラー: {e}")
        return func.HttpResponse("ファイルの取得に失敗しました", status_code=400)

    logging.info(f"{filename} を受信しました。処理を開始します。")

    try:
        # アップロードされたExcelファイル（バイナリ）をメモリ上で読み込み、全シートを辞書形式で取得
        # すべてのシートが {シート名: DataFrame} の形式で格納される
        excel_data = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)

        # Markdown構造化のためのリスト初期化
        toc_list = [] # 目次(Table of Contents)用のリスト
        md_sheets = [] # 各シートのmd文字列を格納するリスト

        # --- 各シートの処理 ---
        for sheet_name, df in excel_data.items():
            # 目次用のアンカーを生成 (GitHub-flavored)
            anchor = re.sub(r'[^a-z0-9-]', '', sheet_name.strip().lower().replace(' ', '-'))
            toc_list.append(f'- [{sheet_name}](#{anchor})')
            
            sheet_content = f"## {sheet_name}\n\n"

            # 「処理詳細」シートはAIで、それ以外はPythonで処理を分岐
            if sheet_name == '処理詳細':
                # --- AIによる構造化 ---
                logging.info(f"「{sheet_name}」シートをAIで構造化します。")
                try:
                    # DataFrameをAIが解釈しやすい単純なテキストに変換
                    raw_text = '\n'.join(df.apply(lambda row: ' '.join(row.astype(str).fillna('')), axis=1))
                    
                    # AI呼び出し (1回目)
                    structuring_prompt = f'''
                        以下の非構造化テキストを解析し、指定の形式で整理してください。

                        --- テキスト開始 ---
                        {raw_text}
                        --- テキスト終了 ---
                        '''
                    structured_table = call_openai_structuring(structuring_prompt)
                    sheet_content += structured_table
                    
                except Exception as e:
                    logging.error(f"AIによるシート構造化中にエラー: {e}")
                    sheet_content += "（AIによる構造化に失敗しました）"
            else:
                # --- Pythonによるデータ前処理 ---
                logging.info(f"「{sheet_name}」シートをPythonで処理します。")
                cleaned_df = _clean_sheet(df)
                if not cleaned_df.empty:
                    sheet_content += cleaned_df.to_markdown(index=False)
                else:
                    sheet_content += "（このシートは空です）"
            
            md_sheets.append(sheet_content)

        # --- 1. 全体を結合して最終的なMarkdown設計書を生成 ---
        logging.info("全シートの処理が完了。最終的な設計書を組み立てます。")
        md_output_first = f"# {filename}\n\n"
        md_output_first += "## 目次\n\n"
        md_output_first += "\n".join(toc_list)
        md_output_first += "\n\n---\n\n"
        md_output_first += "\n\n---\n\n".join(md_sheets)
        logging.info("Markdown設計書をメモリ上に生成しました。")
        
        # --- 2. AIによるテスト観点抽出 ---
        logging.info("設計書全体をAIに渡し、テスト観点を抽出します。")
        extract_test_perspectives_prompt = f'''
            以下の構造化テキストを解析し、指定の形式で整理してください。

            --- テキスト開始 ---
            {md_output_first}
            --- テキスト終了 ---
        '''
        md_output_second = call_openai_extract_test_perspectives(extract_test_perspectives_prompt)
        logging.info("テスト観点抽出が完了し、メモリ上に保持しました。")

        # --- 3. AIによるテスト仕様書生成 ---
        logging.info("設計書全体をAIに渡し、テスト仕様書を生成します。")
        test_gen_prompt = f'''
            以下は対象システムの基準仕様書です。  
            この仕様に基づいて、実務レベルのテスト仕様書を作成してください。  

            --- 対象仕様書開始 ---
            {md_output_second}
            --- 対象仕様書終了 ---
        '''
        md_output_third = call_openai_create_test_spec(test_gen_prompt)
        logging.info("テスト仕様書の生成が完了し、メモリ上に保持しました。")

        # --- 4. テスト仕様書(Markdown)をExcelに変換 ---
        logging.info("テスト仕様書をMarkdownからExcel形式に変換します。")
        
        # Markdownから表部分だけを抽出
        md_lines = [line.strip() for line in md_output_third.splitlines() if line.strip().startswith("|")]
        tsv_text = "\n".join([line.strip("|").replace("|", "\t") for line in md_lines])

        # DataFrame化
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t")
        df.columns = [col.strip() for col in df.columns]
        
        # 既存テンプレートを読み込み
        template_path = "単体テスト仕様書.xlsx"
        wb = load_workbook(template_path)
        ws = wb.active   # もしくはシート名指定 → wb["Sheet1"]

        # マッピング定義（DataFrame列名 → Excel列番号）
        column_map = {
            "No": 1,         # A列
            "区分": 2,        # B列
            "テストケース": 6, # F列
            "期待結果": 19     # S列
        }

        # DataFrameをA11,B11,F11,S11に書き込み
        start_row = 11
        for i, row in enumerate(df.itertuples(index=False), start=start_row):
            for col_name, excel_col in column_map.items():
                if col_name in df.columns:
                    ws.cell(row=i, column=excel_col, value=getattr(row, col_name))

        # バッファに保存（メモリ上）
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        excel_bytes = excel_buffer.read()
        
        logging.info("テンプレートExcelへの書き込みが完了しました。")

        # --- 5. 全成果物をZIPファイルにまとめる ---
        logging.info("全成果物をZIPファイルにまとめています。")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("1_構造化設計書.md", md_output_first.encode('utf-8'))
            zip_file.writestr("2_テスト観点.md", md_output_second.encode('utf-8'))
            zip_file.writestr("3_テスト仕様書.md", md_output_third.encode('utf-8'))
            zip_file.writestr("テスト仕様書.xlsx", excel_bytes)
        
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()
        logging.info("ZIPファイルの作成が完了しました。")

        # --- 6. ユーザーへの返却（ZIPファイル） ---
        output_filename = f"テスト仕様書_{Path(filename).stem}.zip"
        encoded_filename = quote(output_filename)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": "application/zip",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        return func.HttpResponse(zip_bytes, status_code=200, headers=headers)

    except ValueError as ve:
        # ハンドル済みのエラー（AI接続情報未設定など）
        logging.error(f"設定エラー: {ve}")
        return func.HttpResponse(str(ve), status_code=500)
    except Exception as e:
        logging.error(f"処理全体で予期せぬエラーが発生: {e}")
        return func.HttpResponse("処理中にサーバーエラーが発生しました", status_code=500)