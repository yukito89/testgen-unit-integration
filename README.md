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