const fileInput = document.querySelector("#fileInput");
const status = document.querySelector("#status");
const uploadBtn = document.querySelector("#uploadBtn");

uploadBtn.addEventListener("click", async () => {
    const file = fileInput.files[0];

    if (!file) {
        status.textContent = "ファイルを選択してください";
        return;
    }

    uploadBtn.disabled = true;
    status.textContent = "生成中...";

    const formData = new FormData();
    formData.append("documentFile", file);

    // ===== ローカル開発用 =====
    const endpoint = "http://localhost:7071/api/upload";
    // const endpoint = "http://localhost:3000/bedrock";

    try {
        const res = await fetch(endpoint, {
            method: "POST",
            body: formData,
        });

        console.log(res)

        if (!res.ok) {
            status.textContent = `エラー: ${res.status}`;
            uploadBtn.disabled = false;
            return;
        }

        // ファイルダウンロード処理
        const blob = await res.blob();
        const contentDisposition = res.headers.get('content-disposition');
        let filename = 'generated_files.zip'; // fallback filename
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
            if (filenameMatch && filenameMatch.length > 1) {
                filename = decodeURIComponent(filenameMatch[1]);
            } else {
                const filenameMatchRegular = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatchRegular && filenameMatchRegular.length > 1) {
                    filename = filenameMatchRegular[1];
                }
            }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();

        status.textContent = "完了しました";
    } catch (err) {
        status.textContent = `通信エラー: ${err.message}`;
    } finally {
        uploadBtn.disabled = false;
    }
});
