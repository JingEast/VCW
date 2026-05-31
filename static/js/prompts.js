function savePrompt() {
    const content = document.getElementById('systemPromptEditor').value;
    const status = document.getElementById('saveStatus');
    status.textContent = '保存中...';
    status.className = 'save-status';
    
    fetch('/api/v1/prompts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({system_prompt: content})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            status.textContent = '保存成功！模板已热更新。';
            status.className = 'save-status success';
        } else {
            status.textContent = '保存失败: ' + (data.error || '未知错误');
            status.className = 'save-status error';
        }
    })
    .catch(e => {
        status.textContent = '请求失败: ' + e.message;
        status.className = 'save-status error';
    });
}

function resetPrompt() {
    if (!confirm('确定重置为默认模板？当前修改将丢失。')) return;
    location.reload();
}

function previewPromptRender() {
    const systemPrompt = document.getElementById('systemPromptEditor').value;
    const params = {
        system_prompt: systemPrompt,
        topic: document.getElementById('previewTopic').value,
        audience: document.getElementById('previewAudience').value,
        core_data: document.getElementById('previewData').value,
        policy_points: document.getElementById('previewPolicy').value,
        hidden_path: document.getElementById('previewPath').value,
        call_to_action: document.getElementById('previewCTA').value,
    };
    
    const resultDiv = document.getElementById('previewResult');
    resultDiv.style.display = 'block';
    document.getElementById('previewStats').textContent = '渲染中...';
    
    fetch('/api/v1/prompts/preview', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(params)
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('previewStats').textContent = 
                `System: ${data.system_length} 字符 | User: ${data.user_length} 字符`;
            document.getElementById('previewSystem').textContent = data.system_preview;
            document.getElementById('previewUser').textContent = data.user_preview;
        } else {
            document.getElementById('previewStats').textContent = '渲染失败';
            document.getElementById('previewSystem').textContent = '错误: ' + (data.error || '未知错误');
        }
        resultDiv.scrollIntoView({behavior: 'smooth'});
    })
    .catch(e => {
        document.getElementById('previewStats').textContent = '请求失败';
        document.getElementById('previewSystem').textContent = e.message;
    });
}

function switchPreviewTab(tab) {
    document.querySelectorAll('.preview-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('previewSystem').style.display = tab === 'system' ? 'block' : 'none';
    document.getElementById('previewUser').style.display = tab === 'user' ? 'block' : 'none';
}

// ==================== 任务3: Markdown 实时预览 ====================

function renderMarkdown(text) {
    if (!text) return '';
    let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        // 代码块 ```...```
        .replace(/```([\s\S]*?)```/g, '<pre class="md-code-block"><code>$1</code></pre>')
        // 行内代码 `...`
        .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
        // H2 ## 
        .replace(/^## (.*$)/gim, '<h2 class="md-h2">$1</h2>')
        // H3 ### 
        .replace(/^### (.*$)/gim, '<h3 class="md-h3">$1</h3>')
        // H4+ #### 
        .replace(/^####+ (.*$)/gim, '<h4 class="md-h4">$1</h4>')
        // 粗体 **...**
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // 斜体 *...*
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // 删除线 ~~...~~
        .replace(/~~(.*?)~~/g, '<del>$1</del>')
        // 引用 > 
        .replace(/^&gt; (.*$)/gim, '<blockquote class="md-quote">$1</blockquote>')
        // 列表 - 
        .replace(/^- (.*$)/gim, '<li class="md-li">$1</li>')
        // 复选框 - [ ] / - [x]
        .replace(/^\[ \] (.*$)/gim, '<div class="md-check">&#9744; $1</div>')
        .replace(/^\[x\] (.*$)/gim, '<div class="md-check">&#9745; $1</div>')
        // 水平线 ---
        .replace(/^---$/gim, '<hr class="md-hr">')
        // 换行
        .replace(/\n/g, '<br>');
    return html;
}

function updateLivePreview() {
    const text = document.getElementById('systemPromptEditor').value;
    const preview = document.getElementById('liveMarkdownPreview');
    preview.innerHTML = renderMarkdown(text);
}

function switchEditorTab(tab) {
    document.querySelectorAll('.prompt-editor-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    
    const editor = document.getElementById('systemPromptEditor');
    const preview = document.getElementById('liveMarkdownPreview');
    
    if (tab === 'edit') {
        editor.style.display = 'block';
        preview.style.display = 'none';
    } else {
        editor.style.display = 'none';
        preview.style.display = 'block';
        updateLivePreview();
    }
}

// 页面加载时初始化预览
window.addEventListener('DOMContentLoaded', updateLivePreview);
