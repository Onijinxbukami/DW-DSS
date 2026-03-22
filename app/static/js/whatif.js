let histChart = null;
let previewData = null;
let previewDone = false;
let applyModal = null;

/* ── Slider/Input sync ────────────────────────────────── */
function syncInput(key) {
  document.getElementById('input-' + key).value = document.getElementById('slider-' + key).value;
}
function syncSlider(key) {
  document.getElementById('slider-' + key).value = document.getElementById('input-' + key).value;
}

function resetPreview() {
  // When weights change, disable Apply until preview is re-run
  previewDone = false;
  document.getElementById('apply-btn').disabled = true;
  document.getElementById('impact-summary').style.setProperty('display', 'none', 'important');
  document.getElementById('preview-hint').textContent = '(Nhấn "Xem Preview" để cập nhật)';
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

/* ── Toast helper ─────────────────────────────────────── */
function showToast(msg, type = 'success') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const id = 't' + Date.now();
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill' };
  c.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center text-white bg-${type} border-0 show">
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${icons[type] || icons.success}"></i> ${msg}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  setTimeout(() => document.getElementById(id)?.remove(), 4000);
}

/* ── Preview ──────────────────────────────────────────── */
async function previewWhatIf() {
  const btn = document.getElementById('preview-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Đang tính...';

  try {
    const resp = await fetch('/manager/whatif/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getWeights()),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    previewData = data;
    renderPreview(data);
    previewDone = true;
    document.getElementById('apply-btn').disabled = false;
  } catch (e) {
    showToast('Lỗi khi tính preview: ' + e.message, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-eye"></i> Xem Preview';
  }
}

function renderPreview(data) {
  /* ── Impact summary cards ── */
  document.getElementById('stat-rank-changes').textContent = data.rank_changes ?? '–';
  document.getElementById('stat-channel-changes').textContent = data.channel_changes ?? '–';

  const avgDelta = data.top20 && data.top20.length
    ? (data.top20.reduce((s, r) => s + Math.abs(r.rank_delta || 0), 0) / data.top20.length).toFixed(1)
    : '–';
  document.getElementById('stat-avg-delta').textContent = avgDelta;
  document.getElementById('impact-summary').style.removeProperty('display');
  document.getElementById('preview-hint').textContent = '';

  /* ── Top 20 table (rank-change first) ── */
  const dpdClass = (d) => d >= 30 ? 'dpd-d' : d >= 20 ? 'dpd-c' : d >= 10 ? 'dpd-b' : d > 0 ? 'dpd-a' : 'dpd-ok';
  const tbody = document.getElementById('compare-tbody');
  if (!data.top20 || !data.top20.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">Không có dữ liệu</td></tr>';
  } else {
    tbody.innerHTML = data.top20.map(r => {
      const delta = r.rank_delta || 0;
      const arrowHtml = delta > 0
        ? `<span class="rank-change-up">↑${delta}</span>`
        : delta < 0
          ? `<span class="rank-change-down">↓${Math.abs(delta)}</span>`
          : `<span class="rank-change-none">–</span>`;
      const rankChange = `
        <span class="text-muted">#${r.old_priority_rank}</span>
        <i class="bi bi-arrow-right text-muted mx-1"></i>
        <strong class="text-primary">#${r.priority_rank}</strong>`;
      const outstanding = r.total_outstanding
        ? (Number(r.total_outstanding) / 1e6).toFixed(0) + 'M'
        : '–';
      return `<tr>
        <td class="fw-semibold">${r.customer_name || '–'}</td>
        <td><code>${r.contract_no}</code></td>
        <td class="text-center"><span class="dpd-badge ${dpdClass(r.dpd_current)}">${r.dpd_current}d</span></td>
        <td class="text-center text-muted small">${outstanding}</td>
        <td class="text-center">${rankChange}</td>
        <td class="text-center">${arrowHtml}</td>
        <td class="text-end fw-bold">${Number(r.risk_score).toFixed(1)}</td>
      </tr>`;
    }).join('');
  }

  /* ── Score distribution histogram ── */
  const dist = data.score_distribution;
  document.getElementById('no-preview-msg').style.display = 'none';
  if (histChart) histChart.destroy();
  histChart = new Chart(document.getElementById('histChart'), {
    type: 'bar',
    data: {
      labels: dist.labels,
      datasets: [
        {
          label: 'Hiện tại',
          data: dist.old_data,
          backgroundColor: 'rgba(13,110,253,0.45)',
          borderColor: 'rgba(13,110,253,0.8)',
          borderWidth: 1,
        },
        {
          label: 'Sau điều chỉnh',
          data: dist.new_data,
          backgroundColor: 'rgba(220,53,69,0.45)',
          borderColor: 'rgba(220,53,69,0.8)',
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 11 } } },
        tooltip: { mode: 'index' },
      },
      scales: {
        x: { ticks: { maxRotation: 30, font: { size: 10 } } },
        y: { beginAtZero: true, ticks: { font: { size: 10 } } },
      },
    },
  });
}

/* ── Apply modal ──────────────────────────────────────── */
function openApplyModal() {
  if (!previewDone || !previewData) return;

  const desc = document.getElementById('desc-input').value || '(Không có ghi chú)';
  document.getElementById('apply-desc-display').textContent = desc;

  const rankChanges = previewData.rank_changes ?? '?';
  const channelChanges = previewData.channel_changes ?? '?';
  document.getElementById('apply-summary-text').innerHTML =
    `Preview cho thấy: <strong>${rankChanges}</strong> task đổi thứ hạng, ` +
    `<strong>${channelChanges}</strong> task đổi kênh liên hệ.`;

  applyModal = new bootstrap.Modal(document.getElementById('applyModal'));
  applyModal.show();
}

async function applyConfig() {
  const btn = document.getElementById('confirm-apply-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Đang áp dụng...';

  const payload = {
    ...getWeights(),
    description: document.getElementById('desc-input').value,
  };

  try {
    const resp = await fetch('/manager/whatif/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();

    if (applyModal) applyModal.hide();

    if (data.success) {
      document.getElementById('apply-result').innerHTML = `
        <div class="alert alert-success py-2 mt-2 mb-0 d-flex align-items-center gap-2">
          <i class="bi bi-check-circle-fill"></i>
          <div>Config <strong>#${data.config_id}</strong> đã áp dụng.
          Đã cập nhật <strong>${data.tasks_updated}</strong> task.
          Collector reload trang sẽ thấy thứ tự mới.</div>
        </div>`;
      document.getElementById('apply-btn').disabled = true;
      showToast(`Config #${data.config_id} áp dụng thành công – ${data.tasks_updated} task cập nhật.`, 'success');
    } else {
      throw new Error('server error');
    }
  } catch (e) {
    showToast('Lỗi khi áp dụng config. Vui lòng thử lại.', 'danger');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-circle-fill"></i> Xác Nhận Áp Dụng';
  }
}
