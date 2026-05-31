// 刷新热点按钮 loading
const fetchForm = document.getElementById('fetchForm');
const fetchBtn = document.getElementById('fetchBtn');
if (fetchForm && fetchBtn) {
    fetchForm.addEventListener('submit', function() {
        fetchBtn.disabled = true;
        fetchBtn.classList.add('btn-loading');
        fetchBtn.querySelector('.btn-text').textContent = '爬取中...';
    });
}

// 选用按钮 loading
document.querySelectorAll('.select-form').forEach(function(form) {
    form.addEventListener('submit', function(e) {
        const btn = form.querySelector('.select-btn');
        btn.disabled = true;
        btn.textContent = '选用中...';
    });
});

// ==================== 自动爬取调度器 ====================

function loadSchedulerStatus() {
    fetch('/api/v1/trends/scheduler/status')
    .then(r => r.json())
    .then(data => {
        if (!data.success) return;
        const st = data.status;
        const toggle = document.getElementById('schedulerToggle');
        const statusText = document.getElementById('schedulerStatus');
        const info = document.getElementById('schedulerInfo');

        toggle.checked = st.enabled;
        if (st.enabled) {
            statusText.textContent = '运行中';
            statusText.style.color = '#16a34a';
            info.style.display = 'block';
        } else {
            statusText.textContent = '已关闭';
            statusText.style.color = '#64748b';
            info.style.display = 'none';
        }

        document.getElementById('nextRunText').textContent = '下次执行: ' + (st.next_run_human || '--');
        document.getElementById('lastRunText').textContent = '上次执行: ' + (st.last_run_human || '--');

        const lr = st.last_result || {};
        let resultText = '--';
        if (lr.status === 'success') {
            resultText = `成功 (${lr.count}条)`;
        } else if (lr.status === 'failed') {
            resultText = '失败';
        } else if (lr.status === 'never') {
            resultText = '从未执行';
        }
        document.getElementById('lastResultText').textContent = '最近结果: ' + resultText;
    });
}

function toggleScheduler() {
    const enabled = document.getElementById('schedulerToggle').checked;
    const interval = parseInt(document.getElementById('schedulerInterval').value);

    fetch('/api/v1/trends/scheduler/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: enabled, interval_minutes: interval})
    })
    .then(r => r.json())
    .then(() => loadSchedulerStatus());
}

function updateInterval() {
    const enabled = document.getElementById('schedulerToggle').checked;
    if (!enabled) return;
    const interval = parseInt(document.getElementById('schedulerInterval').value);

    fetch('/api/v1/trends/scheduler/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: true, interval_minutes: interval})
    })
    .then(r => r.json())
    .then(() => loadSchedulerStatus());
}

function triggerSchedulerNow() {
    const btn = event.target;
    btn.textContent = '执行中...';
    btn.disabled = true;

    fetch('/api/v1/trends/scheduler/trigger', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
        btn.textContent = '立即执行';
        btn.disabled = false;
        if (data.success && data.result.status === 'success') {
            alert(`手动爬取完成，新增 ${data.result.count} 条热点`);
            location.reload();
        } else {
            alert('爬取失败: ' + (data.result.error || '未知错误'));
        }
        loadSchedulerStatus();
    })
    .catch(e => {
        btn.textContent = '立即执行';
        btn.disabled = false;
        alert('请求失败: ' + e.message);
    });
}

// 页面加载时读取状态
loadSchedulerStatus();
// 每30秒刷新一次状态
setInterval(loadSchedulerStatus, 30000);
