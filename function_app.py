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
import boto3
from botocore.config import Config
import json

# .envファイルから環境変数を読み込む
load_dotenv()

# FunctionAppの初期化
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- LLM Service Configuration ---
llm_service = os.getenv("LLM_SERVICE", "AZURE")

# --- Azure OpenAI Service Connection Information ---
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# --- AWS Bedrock Connection Information ---
aws_region = os.getenv("AWS_REGION")
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_bedrock_model_id = os.getenv("AWS_BEDROCK_MODEL_ID")

# LLMクライアントの初期化用変数
azure_client = None
bedrock_client = None

# 必須環境変数のチェック関数
def validate_env():
    if llm_service == "AZURE":
        # Azure OpenAIに必要な環境変数がすべて設定されているか確認
        required = [azure_api_key, azure_endpoint, azure_api_version, azure_deployment]
        if not all(required):
            raise ValueError("Azure OpenAI の必須環境変数が設定されていません。")
    elif llm_service == "AWS":
        # AWS Bedrockに必要な環境変数がすべて設定されているか確認
        required = [aws_region, aws_access_key_id, aws_secret_access_key, aws_bedrock_model_id]
        if not all(required):
            raise ValueError("AWS Bedrock の必須環境変数が設定されていません。")
    else:
        # サポートされていないLLMサービスが指定された場合のエラー
        raise ValueError(f"無効なLLMサービスが指定されました: {llm_service}")

# LLMクライアントの初期化関数
def initialize_client():
    global azure_client, bedrock_client
    validate_env()  # 環境変数の妥当性をチェック

    if llm_service == "AZURE":
        # Azure OpenAIクライアントの初期化
        azure_client = AzureOpenAI(
            api_version=azure_api_version,
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
        )
    elif llm_service == "AWS":
        # AWS Bedrockクライアントの初期化（タイムアウト設定付き）
        config = Config(read_timeout=600, connect_timeout=60)
        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=config,
        )

# LLMサービスを呼び出す共通関数
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    指定されたLLMサービス（AzureまたはAWS）を使ってプロンプトを送信し、応答を取得する。
    system_prompt: システムプロンプト（モデルの振る舞いを定義）
    user_prompt: ユーザーからの入力
    戻り値: モデルからの応答テキスト
    """
    global azure_client, bedrock_client
    
    # クライアントが未初期化の場合は初期化する
    if llm_service == "AZURE" and azure_client is None:
        initialize_client()
    elif llm_service == "AWS" and bedrock_client is None:
        initialize_client()
    
    try:
        if llm_service == "AZURE":
            # Azure OpenAIにチャット形式でリクエストを送信
            response = azure_client.chat.completions.create(
                model=azure_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=16384,
            )
            return response.choices[0].message.content

        elif llm_service == "AWS":
            # AWS BedrockにConverse APIでリクエストを送信
            response = bedrock_client.converse(
                modelId=aws_bedrock_model_id,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 16384},
            )
            # レスポンスの構造を確認してから取得
            if 'output' in response and 'message' in response['output']:
                return response['output']['message']['content'][0]['text']
            else:
                logging.error(f"予期しないレスポンス構造: {json.dumps(response, ensure_ascii=False)}")
                raise RuntimeError("AWS Bedrockからの応答形式が不正です。")

    except Exception as e:
        logging.error(f"{llm_service} API呼び出し中にエラーが発生しました: {str(e)}")
        raise RuntimeError(f"{llm_service} API呼び出しに失敗しました: {str(e)}")


def structuring(prompt: str) -> str:
    system_prompt = '''
        あなたは業務システムの設計書を解析し、構造化されたMarkdownドキュメントを作成する専門家です。

        タスク：
        提供されたテキストから処理フローや機能仕様を抽出し、読みやすく整理してください。

        出力要件：
        - 処理や機能ごとにセクション分け（### 見出し）
        - 各処理・機能について以下を抽出（存在する場合）：
          - 処理ID/番号
          - 処理名/機能名
          - トリガー/実行条件
          - 処理内容/動作
          - 使用するデータ/テーブル/API
          - 遷移先/出力
        - 表形式で記述可能な場合は表形式を使用

        記述ルール：
        - 複数ステップがある場合は分割して記載
        - 箇条書きは `-` を使用（`<br>`タグは使用しない）
        - 重複情報は省略可
        - 意味のない行・空欄は除外
        - 出力形式はMarkdown
    '''
    return call_llm(system_prompt, prompt)

def extract_test_perspectives(prompt: str) -> str:
    system_prompt = '''
        あなたはソフトウェアテストの専門家です。提供された設計書からテスト観点を抽出してください。

        タスク：
        設計書の内容を分析し、機能・処理単位でテスト観点を整理してください。

        出力形式：
        - 機能・処理単位で `##` セクションに分けてください
        - 各機能・処理について以下を記述：
          - **仕様概要**：機能の目的、入出力、制約条件
          - **業務ルール**：業務上の制約、分岐条件、依存関係
          - **テスト観点**：確認すべきポイント（正常系、異常系、境界値、エラー処理）
        
        記述ルール：
        - 個別の画面項目ごとではなく、機能・処理単位でまとめて記述
        - 入力チェックや制約条件は要約して記載
        - モードや状態による分岐は明示
        - 簡潔かつ網羅的に記述
        - 出力形式はMarkdown
    '''
    return call_llm(system_prompt, prompt)

def create_test_spec(prompt: str) -> str:
    system_prompt = '''
        あなたはソフトウェア品質保証の専門家です。
        提供された仕様情報をもとに、実務レベルのテスト仕様書を作成してください。

        出力要件：
        - 以下の4列構成の表形式（Markdown）で出力：
            - No（連番）
            - 区分（機能・処理単位）
            - テストケース（テスト内容）
            - 期待結果（確認事項）

        記述ルール：
        - 正常系・異常系・境界値・エラー処理を網羅
        - 区分は機能・処理単位で分類（例：「初期表示」「登録処理」「入力チェック」）
        - 期待結果が複数ある場合は行を分割（1期待結果＝1行）
        - 同じ区分・テストケースが連続する場合は該当欄を省略可
        - 期待結果は具体的かつ簡潔に記述
        - 重複するテストケースは統合
        - セクション区切りは行わない（表のみ出力）
        
        出力例：
        | No | 区分 | テストケース | 期待結果 |
        |---|---|---|---|
        | 1 | 初期表示 | 画面を開く | 入力欄が空白で表示されること |
        | 2 |  |  | 一覧が全件表示されること |
        | 3 | 入力チェック | 必須項目を未入力で登録 | エラーメッセージが表示されること |
    '''
    return call_llm(system_prompt, prompt)

def _clean_sheet(df: pd.DataFrame) -> pd.DataFrame:
    original_df = df.copy()
    try:
        # 1. 基本的なクレンジング
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(how='all', axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        rows_before_header_change = len(df)

        # 2. ヘッダー特定と設定
        fixed_header_row_index = 0  # 1行目ヘッダーとして固定
        if len(df) > fixed_header_row_index:
            new_header = df.iloc[fixed_header_row_index].values  # 明示的に配列化
            df = df.iloc[fixed_header_row_index + 1:].copy()     # 2行目以降をデータとして残す
            df.columns = new_header                              # ヘッダーを設定
        
        # 3. ヘッダー後のクレンジング
        if not df.empty:
            df = df.loc[:, pd.notna(df.columns)]
            df.dropna(how='all', inplace=True)

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
    df.fillna('', inplace=True)
    df = df.infer_objects(copy=False)
    return df

@app.route(route="upload", methods=["POST"])
def upload(req: func.HttpRequest) -> func.HttpResponse:
    try:
        file = req.files.get("documentFile")
        if not file:
            return func.HttpResponse("ファイルがアップロードされていません", status_code=400)
        
        file_bytes = file.read()
        filename = file.filename
        
        if not filename.endswith('.xlsx'):
            return func.HttpResponse("Excelファイル(.xlsx)のみ対応しています", status_code=400)
            
    except Exception as e:
        logging.error(f"ファイル取得エラー: {e}")
        return func.HttpResponse("ファイルの取得に失敗しました", status_code=400)

    logging.info(f"{filename} を受信しました。処理を開始します。")

    try:
        # アップロードされたExcelファイル（バイナリ）をメモリ上で読み込み、全シートを辞書形式で取得
        # すべてのシートが {シート名: DataFrame} の形式で格納される
        # header=Noneで全行をデータとして読み込み、_clean_sheet()でヘッダーを設定
        excel_data = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)

        # Markdown構造化のためのリスト初期化
        toc_list = [] # 目次(Table of Contents)用のリスト
        md_sheets = [] # 各シートのmd文字列を格納するリスト

        # --- 各シートの処理 ---
        for sheet_name, df in excel_data.items():
            # 目次用のアンカーを生成 (GitHub-flavored)
            anchor = re.sub(r'[^a-z0-9-]', '', sheet_name.strip().lower().replace(' ', '-'))
            toc_list.append(f'- [{sheet_name}](#{anchor})')
            
            sheet_content = f"## {sheet_name}\n\n"

            # AI処理が必要なシート名をリストで指定（完全一致）
            ai_processing_sheets = ['処理詳細仕様(初期処理)', '処理詳細仕様(当月仕掛発生PJ出力)']
            
            if sheet_name in ai_processing_sheets:
                # --- AIによる構造化 ---
                logging.info(f"「{sheet_name}」シートをAIで構造化します。")
                try:
                    raw_text = '\n'.join(df.apply(lambda row: ' '.join(row.astype(str).fillna('')), axis=1))
                    
                    structuring_prompt = f'''
                        以下の非構造化テキストを解析し、指定の形式で整理してください。

                        --- テキスト開始 ---
                        {raw_text}
                        --- テキスト終了 ---
                        '''
                    structured_table = structuring(structuring_prompt)
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
        md_output_second = extract_test_perspectives(extract_test_perspectives_prompt)
        logging.info("テスト観点抽出が完了し、メモリ上に保持しました。")

        # --- 3. AIによるテスト仕様書生成 ---
        logging.info("設計書全体をAIに渡し、テスト仕様書を生成します。")
        test_gen_prompt = f'''
            以下は対象システムの設計書とテスト観点です。
            この情報に基づいて、実務レベルのテスト仕様書を作成してください。
            
            重要：設計書の詳細情報を参照しつつ、テスト観点で抽出された重要ポイントを中心にテストケースを作成してください。
            
            --- 抽出されたテスト観点（優先参照） ---
            {md_output_second}
            
            --- 元の設計書（詳細情報参照用） ---
            {md_output_first}
            --- 終了 ---
        '''

        md_output_third = create_test_spec(test_gen_prompt)
        logging.info("テスト仕様書の生成が完了し、メモリ上に保持しました。")

        # --- 4. テスト仕様書(Markdown)をExcelに変換 ---
        logging.info("テスト仕様書をMarkdownからExcel形式に変換します。")
        
        # Markdownから表部分だけを抽出
        md_lines = [line.strip() for line in md_output_third.splitlines() if line.strip().startswith("|")]
        
        if not md_lines:
            logging.error("テスト仕様書にMarkdown表が見つかりませんでした")
            return func.HttpResponse("テスト仕様書の生成に失敗しました（表形式が見つかりません）", status_code=500)
        
        tsv_text = "\n".join([line.strip("|").replace("|", "\t") for line in md_lines])

        # DataFrame化
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t")
        df.columns = [col.strip() for col in df.columns]
        
        # 必須列の存在確認
        required_columns = ["No", "区分", "テストケース", "期待結果"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logging.error(f"必須列が不足しています: {missing_columns}")
            return func.HttpResponse(f"テスト仕様書の形式が不正です（不足列: {', '.join(missing_columns)}）", status_code=500)
        
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