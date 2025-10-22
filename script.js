const status = document.querySelector("#status");
const uploadBtn = document.querySelector("#uploadBtn");
const testTypeRadios = document.querySelectorAll('input[name="testType"]');
const unitTestInputs = document.querySelector("#unitTestInputs");
const integrationTestInputs = document.querySelector("#integrationTestInputs");

// ラジオボタンの切り替え処理
testTypeRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
        if (e.target.value === 'unit') {
            unitTestInputs.style.display = 'block';
            integrationTestInputs.style.display = 'none';
        } else {
            unitTestInputs.style.display = 'none';
            integrationTestInputs.style.display = 'block';
        }
    });
});

uploadBtn.addEventListener("click", async () => {
    const testType = document.querySelector('input[name="testType"]:checked').value;
    const formData = new FormData();
    formData.append("testType", testType);

    if (testType === 'unit') {
        const file = document.querySelector("#unitFileInput").files[0];
        if (!file) {
            status.textContent = "詳細設計書を選択してください";
            return;
        }
        formData.append("documentFile", file);
    } else {
        const screenList = document.querySelector("#screenListInput").files[0];
        const transition = document.querySelector("#transitionInput").files[0];
        const detailDocs = document.querySelector("#detailDocsInput").files;

        if (!screenList || !transition || detailDocs.length === 0) {
            status.textContent = "必須ファイルをすべて選択してください";
            return;
        }

        formData.append("screenListFile", screenList);
        formData.append("transitionFile", transition);
        for (let i = 0; i < detailDocs.length; i++) {
            formData.append("detailDocs", detailDocs[i]);
        }
    }

    uploadBtn.disabled = true;
    status.textContent = "生成中...";

    const endpoint = "http://localhost:7071/api/upload";

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
