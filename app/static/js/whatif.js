let histChart = null;
let previewDone = false;

function syncInput(key) {
  document.getElementById('input-' + key).value = document.getElementById('slider-' + key).value;
}
function syncSlider(key) {
  document.getElementById('slider-' + key).value = document.getElementById('input-' + key).value;
}

function getWeights() {
  return {
    alpha:   parseFloat(document.getElementById('input-alpha').value),
    beta:    parseFloat(document.getElementById('input-beta').value),
    gamma:   parseFloat(document.getElementById('input-gamma').value),
    delta:   parseFloat(document.getElementById('input-delta').value),
    epsilon: parseFloat(document.getElementById('input-epsilon').value),
  };
}

async function previewWhatIf() {
  const btn = document.getElementById('preview-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Đang tính...';

  const resp = await fetch('/manager/whatif/preview', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(getWeights())
  });
  const data = await resp.json();
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-eye"></i> Xem Preview';

  if (data.error) { alert(data.error); return; }

  // Update stat
  document.getElementById('stat-rank-changes').textContent = data.rank_changes;
  document.getElementById('summary-stats').style.removeProperty('display');

  // Render histogram
  const dist = data.score_distribution;
  if (histChart) histChart.destroy();
  document.getElementById('no-preview-msg').style.display = 'none';
  histChart = new Chart(document.getElementById('histChart'), {
    type: 'bar',
    data: {
      labels: dist.labels,
      datasets: [
        { label: 'Hiện tại', data: dist.old_data, backgroundColor: 'rgba(13,110,253,0.5)' },
        { label: 'Mới',      data: dist.new_data, backgroundColor: 'rgba(220,53,69,0.5)' },
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'top' } },
      scales: { x: { ticks: { maxRotation: 30 } }, y: { beginAtZero: true } }
    }
  });

  // Render comparison table
  const tbody = document.getElementById('compare-tbody');
  tbody.innerHTML = data.top20.map(r => {
    const delta = r.rank_delta;
    const arrow = delta > 0 ? `<span class="text-success">↑${delta}</span>`
                : delta < 0 ? `<span class="text-danger">↓${Math.abs(delta)}</span>`
                : '<span class="text-muted">–</span>';
    return `<tr>
      <td>${r.customer_name || '–'}</td>
      <td><code>${r.contract_no}</code></td>
      <td class="text-center">${r.dpd_current}</td>
      <td class="text-end">${Number(r.old_risk_score).toFixed(1)}</td>
      <td class="text-center text-muted">${r.old_priority_rank}</td>
      <td class="text-end fw-bold">${Number(r.risk_score).toFixed(1)}</td>
      <td class="text-center fw-bold text-primary">${r.priority_rank}</td>
      <td class="text-center">${arrow}</td>
    </tr>`;
  }).join('');

  previewDone = true;
  document.getElementById('apply-btn').disabled = false;
}

async function applyConfig() {
  if (!confirm('Áp dụng config mới? Tất cả collector sẽ thấy thứ tự ưu tiên mới khi reload trang.')) return;

  const btn = document.getElementById('apply-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Đang áp dụng...';

  const payload = { ...getWeights(), description: document.getElementById('desc-input').value };
  const resp = await fetch('/manager/whatif/apply', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await resp.json();

  btn.innerHTML = '<i class="bi bi-check-circle"></i> Áp Dụng Cho Hôm Nay';

  if (data.success) {
    document.getElementById('apply-result').innerHTML = `
      <div class="alert alert-success py-2 mt-2 mb-0">
        <i class="bi bi-check-circle"></i>
        Config <strong>#${data.config_id}</strong> đã áp dụng.
        Cập nhật <strong>${data.tasks_updated}</strong> task.
        Collector reload trang sẽ thấy thứ tự mới.
      </div>`;
  } else {
    document.getElementById('apply-result').innerHTML =
      '<div class="alert alert-danger py-2 mt-2 mb-0">Lỗi khi áp dụng config.</div>';
    btn.disabled = false;
  }
}
