### **環境構築手順**

1.  **Pythonのインストール**
    お使いの環境にPython 3.9以降がインストールされていることを確認してください。

2.  **プロジェクトのクローン**
    バージョン管理システム（Gitなど）からプロジェクトをクローンします。
    ```bash
    git clone <リポジトリのURL>
    cd <プロジェクトディレクトリ>
    ```

3.  **仮想環境の作成と有効化**
    プロジェクトルートで以下のコマンドを実行し、仮想環境を作成して有効化します。
    ```bash
    # 仮想環境を作成
    python -m venv .venv

    # 仮想環境を有効化 (Windowsの場合)
    .venv\Scripts\activate

    # 仮想環境を有効化 (macOS/Linuxの場合)
    # source .venv/bin/activate
    ```

4.  **必要なライブラリのインストール**
    `requirements.txt`ファイルを使用して、必要なPythonライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

5.  **接続情報の設定**
    本アプリケーションはAzure OpenAI Serviceを利用するため、接続情報の設定が必要です。
    
    1. プロジェクトルートにある `.env.example` ファイルをコピーし、`.env` という名前のファイルを作成します。
    2. 作成した `.env` ファイルを開き、サンプルを参考に4つの必須項目（APIキー、エンドポイント、APIバージョン、デプロイ名）をすべて設定してください。
    
    ```.env
    # Azure OpenAI Serviceの接続情報をここに設定してください

    # APIキー (必須)
    AZURE_OPENAI_API_KEY=...

    # エンドポイント (必須)
    # 例: https://your-service-name.openai.azure.com
    AZURE_OPENAI_ENDPOINT=...

    # APIバージョン (必須)
    # 例: 2024-02-01
    AZURE_OPENAI_API_VERSION=...

    # デプロイ名 (必須)
    # 例: gpt-4
    AZURE_OPENAI_DEPLOYMENT=...
    ```
    
    **注意**: `.env` ファイルは `.gitignore` により、Gitリポジトリには追加されない設定になっています。すべての値が設定されていない場合、アプリケーションは起動時にエラーとなります。

6.  **Azure Functions Core Toolsのインストール** (任意)
    このプロジェクトはAzure Functionsを利用しているため、ローカルでの実行やデバッグには[Azure Functions Core Tools](https://learn.microsoft.com/ja-jp/azure/azure-functions/functions-run-local)が必要です。インストールされていない場合は、リンク先の手順に従ってインストールしてください。

7.  **ローカルでの実行**
    Azure Functions Core Toolsを使用して、ローカルで関数を起動します。
    ```bash
    func start
    ```

### **Azureへのデプロイ手順**

デプロイにはいくつかの方法がありますが、ここでは代表的な2つの方法を説明します。

#### **方法1: Visual Studio Codeから直接デプロイする（推奨）**

VS CodeのAzure拡張機能を使うと、GUI操作で簡単にデプロイと設定が完了します。

1.  **Azure Tools拡張機能のインストール**
    VS Codeの拡張機能マーケットプレイスで `Azure Tools` を検索し、インストールします。これにはAzure Functionsの操作に必要な機能がすべて含まれています。

2.  **Azureへのサインイン**
    VS Codeの左側にあるAzureアイコンをクリックし、`Sign in to Azure...` を選択してブラウザ経由でAzureアカウントにサインインします。

3.  **関数アプリの作成とデプロイ**
    1.  Azure拡張機能パネルの `RESOURCES` セクションで、`Function App` の横にある `+` アイコン（Create Resource...）をクリックします。
    2.  プロンプトに従い、「Create Function App in Azure...」を選択します。
    3.  以下の項目を対話形式で入力していきます。
        -   **関数アプリ名**: グローバルで一意の名前
        -   **ランタイムスタック**: `Python 3.9` (またはプロジェクトに合わせたバージョン)
        -   **リージョン**: 最適なリージョン
    4.  リソースの作成が完了すると、デプロイするかどうかを尋ねる通知が表示されるので、「Deploy」をクリックします。
    
    *注意: もし既存の関数アプリにデプロイする場合は、`RESOURCES` の一覧から対象の関数アプリを右クリックし、`Deploy to Function App...` を選択してください。*

4.  **環境変数の設定**
    デプロイが完了したら、ローカルの `.env` ファイルの内容をAzureに反映させます。
    1.  Azure拡張機能パネルで作成した関数アプリを探します。
    2.  関数アプリの配下にある `Application Settings` を右クリックし、`Upload Local Settings...` を選択します。
    3.  プロジェクトルートにある `.env` ファイルを選択します。
    4.  アップロードする環境変数の確認画面が表示されるので、すべて選択して「OK」をクリックします。

5.  **デプロイの確認**
    デプロイが完了したら、Azure拡張機能パネルで関数アプリを右クリックし `Browse Site` を選択するか、Azureポータルで動作確認をします。


#### **方法2: AzureポータルとGitHub ActionsでCI/CDを構築する**

GitHubリポジトリへのプッシュをトリガーに、自動でデプロイが実行される環境（CI/CD）を構築する方法です。

1.  **関数アプリの作成**
    Azureポータルで、基本的な設定（リソースグループ、アプリ名、ランタイムスタック `Python 3.9` など）を行い、関数アプリのリソースを作成します。

2.  **環境変数の設定**
    作成した関数アプリの「設定」>「構成」メニューから、「アプリケーション設定」に `.env` ファイルに記載されている4つのキーと値を手動で追加し、保存します。

3.  **デプロイセンターの設定**
    1.  関数アプリの「デプロイ」>「デプロイセンター」に移動します。
    2.  ソースとして `GitHub` を選択し、ご自身のアカウントと連携させ、対象のリポジトリとブランチを指定します。
    3.  設定を保存すると、GitHubリポジトリに `workflow` ファイルが自動で作成され、CI/CDパイプラインが構築されます。以降は、指定したブランチにプッシュするたびに自動でデプロイが実行されます。

### **関連テクノロジーとツール**

本プロジェクトで利用している主要なライブラリ、開発ツール、およびAzureのサービスは以下の通りです。

#### **1. Pythonライブラリ (`requirements.txt`)**

-   `azure-functions`: Azure Functionsのトリガーやバインディングなど、Pythonでの関数開発を可能にするためのコアライブラリ。
-   `openai`: Azure OpenAI ServiceおよびOpenAI APIを呼び出すためのクライアントライブラリ。
-   `python-dotenv`: `.env`ファイルから環境変数を読み込むために使用。ローカル開発で接続情報を管理します。
-   `pandas`, `openpyxl`, `tabulate`: 主にExcelファイルの読み書きやデータ整形のために使用されるライブラリ群。

#### **2. 開発・デプロイツール**

-   **Azure Functions Core Tools**:
    ローカル環境でAzure Functionsを開発、実行、デバッグするためのコマンドラインツール (`func`コマンド)。`func start`でのローカルテストに必須です。

-   **Visual Studio Code 拡張機能**:
    -   **Azure Tools**: Azure Functions, App Service, Storageなど、AzureリソースをVS CodeのGUI上から直接操作・管理・デプロイできる統合拡張機能パック。
    -   **Python**: VS CodeでPythonのコード補完、デバッグ、IntelliSenseなどを有効にするための必須拡張機能。

#### **3. 利用しているAzureサービス**

-   **Azure Functions**:
    サーバーレスでコードを実行するためのコンピューティングサービス。本プロジェクトのバックエンド処理はこの上で動作します。

-   **Azure OpenAI Service**:
    Microsoft Azure上で提供される、GPT-4などの大規模言語モデルを利用するためのマネージドサービス。本プロジェクトの中核機能です。