# 設計書からのテスト仕様書自動生成アプリケーション（現在は単体テスト仕様書のみ対応可能、結合テスト仕様書にも対応予定）

このアプリケーションは、Excel形式の設計書をアップロードすると、LLM（大規模言語モデル）を利用して構造化された設計書、テスト観点、そして単体テスト仕様書を自動生成するAzure Functionsアプリケーションです。

バックエンドのLLMは、設定によって **AWS Bedrock** と **Azure OpenAI Service** を切り替えて使用することができます。

## 主な機能

- Excel形式の設計書（`.xlsx`）をHTTP POSTで受け付けます。
- アップロードされたExcelを解析し、内容をMarkdown形式で構造化します。
- 構造化された情報をもとに、LLMがテスト観点を抽出します。
- 抽出されたテスト観点から、LLMが単体テスト仕様書（Markdown形式）を生成します。
- 生成されたMarkdownを`単体テスト仕様書.xlsx`テンプレートに書き込みます。
- 最終的な成果物（構造化設計書.md, テスト観点.md, テスト仕様書.md, テスト仕様書.xlsx）をZIPファイルにまとめて返却します。

---

## 目次

- [前提条件](#前提条件)
- [環境構築](#環境構築)
- [設定](#設定)
  - [.envファイル](#envファイル)
  - [LLMサービスの選択](#llmサービスの選択)
  - [AWS Bedrockの設定](#aws-bedrockの設定)
  - [Azure OpenAIの設定](#azure-openaiの設定)
- [ローカルでの実行](#ローカルでの実行)
- [Azureへのデプロイ](#azureへのデプロイ)
- [主要ファイル構成](#主要ファイル構成)
- [使用技術一覧](#使用技術一覧)

---

## 前提条件

- [Python 3.11](https://www.python.org/)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Node.js 18.x 以降](https://nodejs.org/) （Azure Functions Core Toolsのインストールに必要）
- [AWS アカウント](https://aws.amazon.com/jp/) （Bedrock利用時）
- [Azure アカウント](https://azure.microsoft.com/ja-jp/) （Azure OpenAI利用時、またはAzureへのデプロイ時）

---

## 環境構築

### 1. Azure Functions Core Toolsのインストール

Azure Functions Core Toolsは、ローカル環境でAzure Functionsを開発・実行・デバッグするために必要なコマンドラインツールです。

**方法1: npm経由でインストール（推奨）**

1. ターミナルでNode.jsがインストールされていることを確認します。
   ```
   node --version
   ```
   
2. 管理者権限でターミナルを開き、以下を実行します。
   ```
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```

3. インストール完了後、バージョンを確認します。
   ```
   func --version
   ```

**方法2: MSIインストーラーを使用**

1. [Azure Functions Core Tools リリースページ](https://github.com/Azure/azure-functions-core-tools/releases)にアクセスします。
2. 最新バージョンの `Azure.Functions.Cli.win-x64.<version>.msi` をダウンロードします。
3. ダウンロードしたMSIファイルを実行し、インストールウィザードに従います。
4. インストール完了後、新しいターミナルを開いて確認します。
   ```
   func --version
   ```

### 2. Visual Studio Code 拡張機能のインストール

開発を効率化するために、以下の拡張機能をインストールします。

**1. Azure Tools（拡張機能パック）**

1. VS Codeを開きます。
2. 左側のアクティビティバーから「拡張機能」アイコン（四角が4つ並んだアイコン）をクリックするか、`Ctrl+Shift+X`を押します。
3. 検索ボックスに「**Azure Tools**」と入力します。
4. 「Azure Tools」（発行元: Microsoft）を見つけて「インストール」ボタンをクリックします。
5. この拡張機能パックには以下が含まれます：
   - Azure Account
   - Azure Functions
   - Azure Resources
   - Azure Storage
   - Azure App Service
   - その他Azure関連ツール

**2. Python**

1. 拡張機能の検索ボックスに「**Python**」と入力します。
2. 「Python」（発行元: Microsoft）を見つけて「インストール」ボタンをクリックします。
3. この拡張機能により、以下の機能が有効になります：
   - コード補完（IntelliSense）
   - デバッグ機能
   - リンティング
   - コードフォーマット

**3. Pylance（Pythonの言語サーバー）**

1. 拡張機能の検索ボックスに「**Pylance**」と入力します。
2. 「Pylance」（発行元: Microsoft）を見つけて「インストール」ボタンをクリックします。
3. Python拡張機能と連携して、高速な型チェックとコード補完を提供します。

**4. Live Server**

1. 拡張機能の検索ボックスに「**Live Server**」と入力します。
2. 「Live Server」（発行元: Ritwick Dey）を見つけて「インストール」ボタンをクリックします。
3. HTMLファイルを右クリックして「Open with Live Server」を選択すると、ローカルWebサーバーが起動します。

### 3. プロジェクトのセットアップ

1.  **リポジトリのクローン**
    
    VS Codeのターミナルで以下を実行します。
    ```
    git clone <リポジトリのURL>
    cd <プロジェクトディレクトリ>
    ```

2.  **VS Codeでプロジェクトを開く**
    
    ファイルメニューから「フォルダーを開く」でプロジェクトディレクトリを開きます。

3.  **仮想環境の作成と有効化**
    
    VS Codeのターミナル（`Ctrl+@`で開く）で以下を実行します。
    ```
    py -3.11 -m venv .venv
    .venv\Scripts\activate
    ```
    
    **注意:** Python 3.11がインストールされていない場合は、[Python公式サイト](https://www.python.org/downloads/)からダウンロードしてインストールしてください。

4.  **必要なライブラリのインストール**
    ```
    pip install -r requirements.txt
    ```

5.  **CORS設定（ローカル開発用）**
    
    フロントエンドからAPIを呼び出すために、`local.settings.json`にCORS設定が必要です。
    
    プロジェクトルートに`local.settings.json`ファイルを作成し、以下の内容を記述します：
    
    ```json
    {
        "IsEncrypted": false,
        "Values": {
            "AzureWebJobsStorage": "",
            "FUNCTIONS_WORKER_RUNTIME": "python"
        },
        "Host": {
            "CORS": "*"
        }
    }
    ```
    
    **注意:** `"CORS": "*"` はすべてのオリジンからのアクセスを許可します。本番環境では、特定のドメインのみを許可するように設定することを推奨します。

---

## 設定

### .envファイル

プロジェクトのルートにある`.env.example`をコピーして`.env`ファイルを作成します。このファイルに各種サービスの接続情報を記述します。

VS Codeのターミナルで以下を実行します。
```
copy .env.example .env
```

**注意:** `.env`ファイルには認証情報などの機密情報が含まれるため、絶対にGitでコミットしないでください。`.gitignore`に`.env`が記載されていることを確認してください。

### LLMサービスの選択

`.env`ファイル内の`LLM_SERVICE`で使用するサービスを指定します。

- **AWS Bedrockを利用する場合:**
  ```
  LLM_SERVICE="AWS"
  ```
- **Azure OpenAI Serviceを利用する場合:**
  ```
  LLM_SERVICE="AZURE"
  ```

### AWS Bedrockの設定

`LLM_SERVICE="AWS"`を選択した場合、以下の設定を行います。

#### 1. モデルアクセスの有効化

AWS Bedrockでモデルを利用する前に、使用したいリージョンで対象モデルへのアクセスを有効化する必要があります。

1.  AWSマネジメントコンソールで **Bedrock** サービスに移動します。
2.  左下のメニューから **「モデルアクセス」** をクリックします。
3.  右上の **「モデルアクセスを管理」** ボタンをクリックします。
4.  **Anthropic** の **「Claude Sonnet 4.5」** にチェックを入れ、右下の「変更を保存」をクリックします。
    - アクセスステータスが「アクセス権が付与されました」に変わるまで数分待ちます。

#### 2. IAMユーザーの作成

このアプリケーション専用のIAMユーザーを作成し、プログラムによるアクセスキー（アクセスキーIDとシークレットアクセスキー）を発行します。

1.  AWSマネジメントコンソールでIAMサービスに移動します。
2.  「ユーザー」→「ユーザーを作成」をクリックします。
3.  ユーザー名を指定し、「次へ」をクリックします。
4.  「ポリシーを直接アタッチする」を選択します。（ポリシーは次のステップで作成します）
5.  ユーザーを作成後、「セキュリティ認証情報」タブに移動し、「アクセスキーを作成」をクリックします。
6.  「コマンドラインインターフェイス (CLI)」を選択し、アクセスキーを作成します。
7.  表示された「アクセスキーID」と「シークレットアクセスキー」をコピーし、`.env`ファイルに設定します。**この画面を閉じるとシークレットアクセスキーは二度と表示できないので注意してください。**

#### 3. IAMポリシーの作成とアタッチ

Bedrockのモデルを呼び出すための権限をまとめたIAMポリシーを作成し、上記で作成したIAMユーザーにアタッチします。

1.  IAMサービスの「ポリシー」→「ポリシーを作成」をクリックします。
2.  「JSON」タブを選択し、以下のポリシーを貼り付けます。

    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": "*"
            }
        ]
    }
    ```
    *本番環境では、`Resource`をより厳密に特定のモデルARNやプロファイルARN (`arn:aws:bedrock:ap-northeast-1:799642483126:inference-profile/jp.anthropic.claude-sonnet-4-5-20250929-v1:0` など) に限定することが推奨されます。*

3.  ポリシーに名前（例: `BedrockAppInvokePolicy`）を付けて保存します。
4.  作成したIAMユーザーの「許可を追加」から、今作成したポリシーをアタッチします。

推論プロファイルは共有のものを利用するため、自身で作成する必要はありません。

#### 4. .envファイルの設定

日本リージョン用の共有推論プロファイルが用意されているため、それを利用します。

```.env
# -------------------- LLMサービスの選択 --------------------
# 使用するLLMサービスを選択します ("AZURE" or "AWS")
LLM_SERVICE=AWS


# -------------------- AWS Bedrock 接続情報 --------------------
# AWSリージョン (例: "ap-northeast-1")
AWS_REGION=ap-northeast-1

# AWSアクセスキーID
AWS_ACCESS_KEY_ID=<ここにアクセスキーIDを記述>

# AWSシークレットアクセスキー
AWS_SECRET_ACCESS_KEY=<ここにシークレットアクセスキーを記述>

# AWS BedrockモデルID (例: "jp.anthropic.claude-sonnet-4-5-20250929-v1:0")
AWS_BEDROCK_MODEL_ID=jp.anthropic.claude-sonnet-4-5-20250929-v1:0
```
**注意:** 上記の推論プロファイルは `ap-northeast-1` (東京リージョン) 専用です。他のリージョンで実行する場合は、別途推論プロファイルを作成し、そのARNを指定する必要があります。

---

### Azure OpenAIの設定

`LLM_SERVICE="AZURE"`を選択した場合、以下の環境変数を設定します。

```.env
# -------------------- Azure OpenAI Service 接続情報 --------------------
# APIキー (必須)
AZURE_OPENAI_API_KEY=<ここにAPIキーを記述>

# エンドポイント (必須)
# 例: https://your-service-name.openai.azure.com
AZURE_OPENAI_ENDPOINT=<ここにエンドポイントを記述>

# APIバージョン (必須)
# 例: 2024-02-01
AZURE_OPENAI_API_VERSION=<ここにAPIバージョンを記述>

# デプロイ名 (必須)
# 例: gpt-4o
AZURE_OPENAI_DEPLOYMENT=<ここにデプロイ名を記述>
```

これらの値は、AzureポータルでAzure OpenAI Serviceのリソースを作成し、「キーとエンドポイント」から取得できます。`AZURE_OPENAI_DEPLOYMENT`には、作成したモデルのデプロイ名を指定します。

---

## ローカルでの実行

1.  **Azure Functionsホストの起動**
    
    VS Codeのターミナルで以下を実行します。
    ```
    func start
    ```

2.  起動後、`http://localhost:7071/api/upload` というエンドポイントが利用可能になります。

3.  フロントエンドからの動作確認
    - VS Codeで「Live Server」拡張機能をインストール
    - `frontend/index.html`を右クリック→「Open with Live Server」で起動
    - ブラウザでExcelファイルをアップロードして動作確認

---

## Azureへのデプロイ

### バックエンド（Azure Functions）のデプロイ

1.  **Azure Tools拡張機能のインストール**
    VS Codeの拡張機能から「Azure Tools」をインストールします。

2.  **Azureにサインイン**
    VS Codeのサイドバーから「Azure」アイコンをクリックし、「Sign in to Azure」でサインインします。

3.  **Function Appの作成とデプロイ**
    - サイドバーの「Azure」→「Functions」を右クリック
    - 「Create Function App in Azure...」を選択
    - アプリ名、Pythonバージョン（**3.11を推奨**）、リージョンを指定
    - 作成完了後、作成したFunction Appを右クリック→「Deploy to Function App...」を選択
    - **注意:** `単体テスト仕様書.xlsx`がプロジェクトルートに配置されていることを確認してください。デプロイ時に自動的に含まれます。`.funcignore`に`*.xlsx`が記載されている場合は削除してください。

4.  **環境変数の設定**
    - Azureポータルで作成したFunction Appを開く
    - 「設定」→「環境変数」→「+追加」→「アプリケーション設定の追加/編集」
    - `.env`ファイルの内容を1つずつ追加（`LLM_SERVICE`, `AWS_ACCESS_KEY_ID`など）

### フロントエンド（Azure Static Web Apps）のデプロイ

1.  **script.jsのAPIエンドポイント変更**
    
    `frontend/script.js`を編集し、Function AppのURLを設定します。
    ```javascript
    const endpoint = 'https://<your-function-app>.azurewebsites.net/api/upload';
    ```

2.  **GitHubリポジトリにプッシュ**
    
    VS Codeのターミナルで以下を実行し、変更をGitHubにプッシュします。
    ```bash
    git add .
    git commit -m "Update endpoint for deployment"
    git push origin main
    ```
    
    **注意:** GitHubリポジトリがまだない場合は、事前にGitHub上でリポジトリを作成し、ローカルリポジトリと連携してください。

3.  **Azure Static Web Appsの作成とデプロイ**
    - Azureポータル (https://portal.azure.com) にアクセス
    - 「リソースの作成」→「Static Web App」を検索して選択
    - 「作成」をクリック
    - 基本設定:
      - サブスクリプション、リソースグループを選択
      - 名前を入力
      - リージョンを選択（例: East Asia）
    - デプロイの詳細:
      - ソース: 「GitHub」を選択
      - GitHubアカウントでサインイン
      - 組織、リポジトリ、ブランチを選択
    - ビルドの詳細:
      - ビルドプリセット: 「Custom」を選択
      - アプリの場所: `/frontend`
      - APIの場所: 空欄（APIはFunction Appで別途デプロイ済み）
      - 出力場所: 空欄
    - 「確認および作成」→「作成」をクリック
    - 作成完了後、GitHub Actionsが自動でデプロイを実行します

4.  **CORS設定（Function App側）**
    - Function Appの「API」→「CORS」
    - Static Web AppsのURL（`https://<your-static-app>.azurestaticapps.net`）を追加
    - URLはVS CodeのAzureパネルから確認できます

5.  **動作確認**
    - Static Web AppsのURLにアクセス
    - Excelファイルをアップロードして動作確認

---

## 主要ファイル構成

- **`function_app.py`**: メインの処理が記述されたAzure FunctionsのHTTPトリガー関数。
- **`requirements.txt`**: Pythonの依存パッケージリスト。
- **`.env.example`**: 環境変数のテンプレートファイル。
- **`host.json`**: Azure Functionsホストのグローバル設定ファイル。ログ設定、拡張機能バンドルのバージョンなど、アプリケーション全体の動作を制御します。
- **`local.settings.json`**: ローカル開発環境専用の設定ファイル。ランタイム設定、CORS設定、ローカル環境変数などを管理します（`.gitignore`で除外済み）。
- **`単体テスト仕様書.xlsx`**: テスト仕様書を生成する際の書き込み先テンプレートExcelファイル。プロジェクトルートに配置し、Azure Functionsと一緒にデプロイされます。
- **`frontend/index.html`, `frontend/script.js`, `frontend/style.css`**: 簡単な動作確認用のフロントエンドファイル。

---

## 使用技術一覧

本プロジェクトで利用している主要なライブラリ、開発ツール、およびクラウドサービスは以下の通りです。

### 1. Pythonライブラリ (`requirements.txt`)

-   `azure-functions`: Azure Functionsのトリガーやバインディングなど、Pythonでの関数開発を可能にするためのコアライブラリ。
-   `boto3`: AWS SDK for Python。AWS Bedrockなど、AWSサービスを呼び出すためのクライアントライブラリ。
-   `openai`: Azure OpenAI ServiceおよびOpenAI APIを呼び出すためのクライアントライブラリ。
-   `python-dotenv`: `.env`ファイルから環境変数を読み込むために使用。ローカル開発で接続情報を管理します。
-   `pandas`: データ操作とExcelファイルの読み込みに使用。
-   `openpyxl`: Excelファイルの書き込みと操作に使用。

### 2. 開発・デプロイツール

-   **Azure Functions Core Tools**:
    ローカル環境でAzure Functionsを開発、実行、デバッグするためのコマンドラインツール (`func`コマンド)。`func start`でのローカルテストに必須です。

-   **Visual Studio Code 拡張機能**:
    -   **Azure Tools**: Azure Functions, App Service, Storageなど、AzureリソースをVS CodeのGUI上から直接操作・管理・デプロイできる統合拡張機能パック。
    -   **Python**: VS CodeでPythonのコード補完、デバッグ、IntelliSenseなどを有効にするための必須拡張機能。
    -   **Pylance**: Python拡張機能と連携し、高速な型チェックとコード補完を提供するPython言語サーバー。
    -   **Live Server**: ローカル開発時にHTMLファイルを簡易Webサーバーで起動するための拡張機能。

### 3. 利用しているクラウドサービス

-   **Azure Functions**:
    サーバーレスでコードを実行するためのコンピューティングサービス。本プロジェクトのバックエンド処理はこの上で動作します。

-   **Azure Static Web Apps**:
    静的コンテンツ（HTML、CSS、JavaScript）をホスティングするためのサービス。本プロジェクトのフロントエンドをデプロイします。

-   **AWS Bedrock**:
    Amazon Web Services上で提供される、Claude Sonnetなどの大規模言語モデルを利用するためのマネージドサービス。

-   **Azure OpenAI Service**:
    Microsoft Azure上で提供される、GPTなどの大規模言語モデルを利用するためのサービス。
