function addEndpointRow() {
    const tbody = document.querySelector('#endpointTable tbody');
    const row = document.createElement('tr');
    row.className = 'endpoint-row';
    row.innerHTML = `
        <td><input type="text" name="ep_name[]" placeholder="kimi"></td>
        <td><input type="password" name="ep_key[]" placeholder="sk-..."></td>
        <td><input type="text" name="ep_url[]" placeholder="https://api.moonshot.cn/v1"></td>
        <td><input type="text" name="ep_model[]" placeholder="moonshot-v1-8k"></td>
        <td><input type="number" name="ep_priority[]" value="0" min="0" max="10" style="width:60px"></td>
        <td><button type="button" class="btn btn-small btn-danger" onclick="removeEndpointRow(this)">删除</button></td>
    `;
    tbody.appendChild(row);
}

function removeEndpointRow(btn) {
    const row = btn.closest('.endpoint-row');
    if (row) row.remove();
}
