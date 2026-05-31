function previewFile(path) {
    fetch('/api/v1/files/preview/' + encodeURIComponent(path))
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('previewContent').textContent = data.content;
            document.getElementById('previewModal').style.display = 'block';
        } else {
            alert('预览失败: ' + data.error);
        }
    });
}

function closePreview() {
    document.getElementById('previewModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('previewModal');
    if (event.target === modal) modal.style.display = 'none';
}
