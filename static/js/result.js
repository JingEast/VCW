function copyContent() {
    const text = document.getElementById('copyContent').textContent;
    navigator.clipboard.writeText(text).then(() => {
        alert('已复制到剪贴板');
    });
}

// 任务10: 按段落渲染 + 一键复制各段落
function renderParagraphs() {
    const content = document.getElementById('copyContent').textContent;
    const container = document.getElementById('paragraphsContainer');
    
    // 按双换行或换行分割段落
    const paragraphs = content.split(/\n\n+/).filter(p => p.trim());
    
    if (paragraphs.length <= 1) {
        // 只有一段，直接显示全文
        container.innerHTML = '<pre class="paragraph-text">' + escapeHtml(content) + '</pre>';
        return;
    }
    
    let html = '';
    paragraphs.forEach((para, idx) => {
        const text = para.trim();
        if (!text) return;
        html += `
            <div class="paragraph-block">
                <div class="paragraph-actions">
                    <span class="paragraph-num">#${idx + 1}</span>
                    <button class="btn-para-copy" onclick="copyParagraph(${idx})" title="复制此段">复制</button>
                </div>
                <pre class="paragraph-text" data-idx="${idx}">${escapeHtml(text)}</pre>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyParagraph(idx) {
    const el = document.querySelector(`pre[data-idx="${idx}"]`);
    if (!el) return;
    const text = el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.querySelectorAll('.btn-para-copy')[idx];
        const old = btn.textContent;
        btn.textContent = '已复制';
        btn.style.background = '#16a34a';
        btn.style.color = '#fff';
        setTimeout(() => {
            btn.textContent = old;
            btn.style.background = '';
            btn.style.color = '';
        }, 1500);
    });
}

// 页面加载时渲染段落
window.addEventListener('DOMContentLoaded', renderParagraphs);
