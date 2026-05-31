function switchTab(tabId) {
    // 切换按钮状态
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    
    // 切换面板
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('panel-' + tabId).classList.add('active');
}

function switchWorkflow(wfId) {
    document.querySelectorAll('.wf-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('wf-tab-' + wfId).classList.add('active');
    
    document.querySelectorAll('.wf-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('wf-panel-' + wfId).classList.add('active');
}
