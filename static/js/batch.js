function copyText(text) {
    navigator.clipboard.writeText(text.replace(/\\n/g, '\n')).then(() => {
        alert('已复制到剪贴板');
    });
}
