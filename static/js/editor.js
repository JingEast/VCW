const originalText = window.__EDITOR_DATA__.original;
const editArea = document.getElementById('editContent');
const charCount = document.getElementById('charCount');

function updateCount() {
    const text = editArea.value;
    charCount.textContent = text.length + ' 字';
}

editArea.addEventListener('input', updateCount);
updateCount();

function resetToOriginal() {
    if (confirm('确定恢复为原始文案？当前修改将丢失。')) {
        editArea.value = originalText;
        updateCount();
    }
}

function finalizeDraft() {
    const form = document.getElementById('editorForm');
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'finalize';
    input.value = 'true';
    form.appendChild(input);
    form.submit();
}

function deAI() {
    const btn = document.getElementById('deAIBtn');
    const status = document.getElementById('deAIStatus');
    const content = editArea.value;
    
    if (!content || content.length < 50) {
        alert('文案内容太短，无法优化');
        return;
    }
    
    btn.disabled = true;
    status.textContent = '正在优化中...';
    
    fetch('/api/v1/editor/de-ai', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content: content})
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        if (data.success) {
            editArea.value = data.optimized;
            updateCount();
            status.textContent = '优化完成！请人工复核。';
        } else {
            status.textContent = '优化失败: ' + data.error;
        }
    })
    .catch(e => {
        btn.disabled = false;
        status.textContent = '请求失败: ' + e;
    });
}
