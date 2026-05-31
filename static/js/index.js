function previewPrompt() {
    const form = document.getElementById('generateForm');
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    
    fetch('/api/v1/prompts/check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('promptStats').innerHTML = 
            `System: ${data.system_prompt_length} 字符 | User: ${data.user_prompt_length} 字符`;
        document.getElementById('systemPrompt').textContent = data.system_prompt;
        document.getElementById('userPrompt').textContent = data.user_prompt;
        document.getElementById('promptModal').style.display = 'block';
    });
}

function closeModal() {
    document.getElementById('promptModal').style.display = 'none';
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('systemPrompt').style.display = tab === 'system' ? 'block' : 'none';
    document.getElementById('userPrompt').style.display = tab === 'user' ? 'block' : 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('promptModal');
    if (event.target === modal) modal.style.display = 'none';
}

// ==================== Phase 1: 流式生成 (SSE) ====================

let eventSource = null;
let streamFullText = "";
let streamMetaInfo = "";

function getFormData() {
    const form = document.getElementById('generateForm');
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    return data;
}

function startStreamGenerate() {
    const data = getFormData();
    if (!data.topic || !data.topic.trim()) {
        alert('主题不能为空');
        return;
    }

    // 显示流式区域
    document.getElementById('streamArea').style.display = 'block';
    document.getElementById('streamContent').innerHTML = '';
    document.getElementById('streamMeta').textContent = '';
    document.getElementById('streamActions').style.display = 'none';
    streamFullText = "";
    streamMetaInfo = "";

    // 滚动到流式区域
    document.getElementById('streamArea').scrollIntoView({ behavior: 'smooth' });

    // 建立 SSE 连接
    eventSource = new EventSource('/api/v1/generate/stream?' + new URLSearchParams(data));

    eventSource.onmessage = function(event) {
        // 标准消息（这里我们使用自定义事件名，所以 onmessage 通常不会触发）
    };

    eventSource.addEventListener('content', function(e) {
        const text = e.data.replace(/\\n/g, '\n');
        streamFullText += text;
        const contentDiv = document.getElementById('streamContent');
        contentDiv.textContent += text;
        contentDiv.scrollTop = contentDiv.scrollHeight;
    });

    eventSource.addEventListener('meta', function(e) {
        streamMetaInfo = e.data;
        document.getElementById('streamMeta').textContent = e.data;
    });

    eventSource.addEventListener('done', function(e) {
        stopStream();
        document.getElementById('streamActions').style.display = 'flex';
    });

    eventSource.addEventListener('error', function(e) {
        const text = e.data ? e.data.replace(/\\n/g, '\n') : '连接错误';
        document.getElementById('streamContent').innerHTML +=
            '<span style="color:#dc3545">\n' + text + '</span>';
        stopStream();
    });

    eventSource.onerror = function() {
        document.getElementById('streamContent').innerHTML +=
            '<span style="color:#dc3545">\n[连接中断]</span>';
        stopStream();
    };
}

function stopStream() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    const badge = document.querySelector('.stream-badge');
    if (badge) badge.textContent = '生成结束';
}

function saveStreamResult() {
    if (!streamFullText) return;
    
    const topic = document.getElementById('topic').value || '未命名文案';
    const btn = document.querySelector('#streamActions .btn-primary');
    if (btn) btn.textContent = '保存中...';
    
    fetch('/api/v1/generate/save-stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            content: streamFullText,
            topic: topic,
            meta: streamMetaInfo
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            window.location.href = '/editor?draft=' + data.draft_id;
        } else {
            alert('保存失败: ' + (data.error || '未知错误'));
            if (btn) btn.textContent = '保存到精修库';
        }
    })
    .catch(e => {
        alert('请求失败: ' + e.message);
        if (btn) btn.textContent = '保存到精修库';
    });
}

function copyStreamResult() {
    if (!streamFullText) return;
    navigator.clipboard.writeText(streamFullText).then(() => {
        alert('文案已复制到剪贴板');
    });
}

// ==================== Phase 1: 异步任务 ====================

let asyncTaskId = null;
let asyncPollTimer = null;

function startAsyncGenerate() {
    const data = getFormData();
    if (!data.topic || !data.topic.trim()) {
        alert('主题不能为空');
        return;
    }

    // 显示异步面板
    document.getElementById('asyncPanel').style.display = 'block';
    document.getElementById('asyncResult').style.display = 'none';
    updateAsyncProgress(0, '提交任务...');

    fetch('/api/v1/generate/async', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            asyncTaskId = res.task_id;
            updateAsyncProgress(5, '任务已创建，等待执行...');
            pollAsyncStatus();
        } else {
            updateAsyncProgress(0, '创建失败: ' + res.error);
        }
    })
    .catch(e => {
        updateAsyncProgress(0, '请求失败: ' + e.message);
    });
}

function pollAsyncStatus() {
    if (!asyncTaskId) return;

    fetch('/api/v1/generate/status/' + asyncTaskId)
    .then(r => r.json())
    .then(res => {
        if (!res.success) {
            updateAsyncProgress(0, '查询失败: ' + res.error);
            return;
        }

        const task = res.task;
        updateAsyncProgress(task.progress, task.message);

        if (task.status === 'completed') {
            document.getElementById('asyncResult').style.display = 'block';
            const result = task.result || {};
            const draftId = result.draft_id || '';
            const link = document.getElementById('asyncResultLink');
            if (draftId) {
                link.href = '/editor?draft=' + draftId;
                link.textContent = '前往精修编辑器';
            } else {
                link.href = '/history';
                link.textContent = '查看历史文案';
            }
            // 刷新页面记忆库计数
            location.reload();
        } else if (task.status === 'failed') {
            updateAsyncProgress(0, '生成失败: ' + task.error);
        } else if (task.status === 'cancelled') {
            updateAsyncProgress(0, '已取消');
        } else {
            // 继续轮询
            asyncPollTimer = setTimeout(pollAsyncStatus, 1500);
        }
    })
    .catch(e => {
        asyncPollTimer = setTimeout(pollAsyncStatus, 3000);
    });
}

function cancelAsyncTask() {
    if (!asyncTaskId) return;
    fetch('/api/v1/generate/cancel/' + asyncTaskId, {method: 'POST'})
    .then(() => {
        if (asyncPollTimer) clearTimeout(asyncPollTimer);
        updateAsyncProgress(0, '已取消');
    });
}

function updateAsyncProgress(percent, message) {
    document.getElementById('asyncProgressBar').style.width = percent + '%';
    document.getElementById('asyncProgressText').textContent = percent + '%';
    document.getElementById('asyncMessage').textContent = message;
}

// ==================== 任务1: 表单自动保存草稿（localStorage 防抖）====================

const DRAFT_KEY = 'vcw_form_draft';
const DRAFT_FIELDS = ['topic', 'audience', 'core_data', 'policy_points', 'hidden_path', 'call_to_action', 'sample_ref', 'extra_requirements'];
let draftTimer = null;

function saveDraft() {
    const data = {};
    DRAFT_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) data[id] = el.value;
    });
    data._savedAt = new Date().toISOString();
    localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    showDraftStatus('草稿已自动保存', 'saved');
}

function loadDraft() {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return false;
    try {
        const data = JSON.parse(raw);
        // 检查是否有有效内容（不只是默认值）
        let hasContent = false;
        DRAFT_FIELDS.forEach(id => {
            if (data[id] && data[id].trim()) {
                const el = document.getElementById(id);
                if (el) {
                    // 如果页面有 prefill（从热点跳转过来），不覆盖
                    const prefillVal = el.getAttribute('value') || el.textContent;
                    if (!prefillVal || prefillVal.trim() === '' || prefillVal.includes('例如')) {
                        el.value = data[id];
                        hasContent = true;
                    }
                }
            }
        });
        if (hasContent) {
            const time = data._savedAt ? new Date(data._savedAt).toLocaleString() : '之前';
            showDraftStatus(`已恢复 ${time} 的草稿 <a href="#" onclick="clearDraft();return false;" style="color:#dc3545;margin-left:8px;">清除</a>`, 'restored');
        }
        return hasContent;
    } catch (e) {
        return false;
    }
}

function clearDraft() {
    localStorage.removeItem(DRAFT_KEY);
    showDraftStatus('草稿已清除', 'cleared');
    setTimeout(() => { document.getElementById('draftStatus').innerHTML = ''; }, 2000);
}

function showDraftStatus(text, type) {
    const el = document.getElementById('draftStatus');
    el.innerHTML = text;
    el.className = 'draft-status draft-' + type;
}

// 防抖自动保存（输入停止2秒后保存）
DRAFT_FIELDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
        el.addEventListener('input', function() {
            showDraftStatus('正在输入...', 'typing');
            clearTimeout(draftTimer);
            draftTimer = setTimeout(saveDraft, 2000);
        });
    }
});

// 表单提交成功后清除草稿
document.getElementById('generateForm').addEventListener('submit', function() {
    localStorage.removeItem(DRAFT_KEY);
});

// 页面加载时尝试恢复草稿
window.addEventListener('DOMContentLoaded', loadDraft);
