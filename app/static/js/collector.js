/* ── Toast helper ─────────────────────────────────────── */
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const id = 'toast-' + Date.now();
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill' };
  const html = `
    <div id="${id}" class="toast align-items-center text-white bg-${type} border-0 show" role="alert" aria-live="assertive">
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${icons[type] || icons.success}"></i> ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);
  setTimeout(() => document.getElementById(id)?.remove(), 3000);
}

/* ── Status update with optimistic UI ────────────────── */
async function updateStatus(taskId, newStatus, selectEl) {
  // Optimistic: apply style immediately
  const card = document.getElementById('card-' + taskId);
  selectEl.classList.add('status-saving');

  const statusStyles = {
    'DONE':        'bg-success text-white',
    'IN_PROGRESS': 'bg-warning text-dark',
    'SKIPPED':     'bg-secondary text-white',
    'PENDING':     '',
  };

  // Update card opacity to signal state
  if (card) {
    card.style.opacity = newStatus === 'DONE' ? '0.65' : '1';
    card.style.transition = 'opacity 0.3s ease';
  }

  try {
    const resp = await fetch('/collector/update_status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, new_status: newStatus }),
    });
    const data = await resp.json();

    if (data.success) {
      selectEl.classList.remove('status-saving');
      // Update progress bar in header
      updateProgressBar();
      const labels = { PENDING: 'Chờ', IN_PROGRESS: 'Đang xử lý', DONE: 'Hoàn thành', SKIPPED: 'Bỏ qua' };
      showToast(`Cập nhật: <strong>${labels[newStatus] || newStatus}</strong>`, 'success');
    } else {
      throw new Error('server error');
    }
  } catch (e) {
    // Rollback optimistic update
    selectEl.classList.remove('status-saving');
    if (card) card.style.opacity = '1';
    showToast('Lỗi cập nhật trạng thái. Vui lòng thử lại.', 'danger');
    // Revert select to previous value by reloading options state
    location.reload();
  }
}

/* ── Live progress bar update ─────────────────────────── */
function updateProgressBar() {
  const selects = document.querySelectorAll('.status-select');
  const total = selects.length;
  const done = Array.from(selects).filter(s => s.value === 'DONE').length;
  const pct = total ? Math.round(done / total * 100) : 0;
  const bar = document.querySelector('.progress .progress-bar');
  const countEl = document.querySelector('.text-success.fw-bold') ||
                  document.querySelector('[class*="text-success"]');
  if (bar) bar.style.width = pct + '%';
  // Update done count display
  const doneSpan = document.querySelector('.text-success.fw-bold');
  if (doneSpan && !isNaN(parseInt(doneSpan.textContent))) doneSpan.textContent = done;
}

/* ── Detail modal ─────────────────────────────────────── */
async function showDetail(taskId) {
  document.getElementById('detail-body').innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-primary"></div>
      <p class="text-muted mt-2 small">Đang tải chi tiết...</p>
    </div>`;
  const modal = new bootstrap.Modal(document.getElementById('detailModal'));
  modal.show();

  try {
    const resp = await fetch(`/collector/task_detail/${taskId}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    renderDetail(data.task, data.history);
  } catch (e) {
    document.getElementById('detail-body').innerHTML =
      '<div class="alert alert-danger m-3">Không thể tải chi tiết. Vui lòng thử lại.</div>';
  }
}

function renderDetail(t, h) {
  /* DPD class helper */
  const dpdClass = (dpd) => {
    if (dpd === 0)  return 'dpd-ok';
    if (dpd < 10)   return 'dpd-a';
    if (dpd < 20)   return 'dpd-b';
    if (dpd < 30)   return 'dpd-c';
    return 'dpd-d';
  };
  const dotColors = { 'dpd-ok': '#198754', 'dpd-a': '#ffc107', 'dpd-b': '#fd7e14', 'dpd-c': '#dc3545', 'dpd-d': '#212529' };
  const statusColors = { PAID: 'bg-success', OVERDUE: 'bg-danger', PARTIAL: 'bg-warning text-dark', PENDING: 'bg-secondary' };

  /* 6-month history timeline */
  const histItems = h.length ? h.map(r => {
    const cls = dpdClass(r.dpd);
    const dot = dotColors[cls] || '#adb5bd';
    return `
      <li>
        <span class="timeline-dot" style="background:${dot}"></span>
        <span class="text-muted" style="min-width:85px">${r.due_date}</span>
        <span class="badge ${statusColors[r.status] || 'bg-secondary'}">${r.status}</span>
        <span class="dpd-badge ${cls} ms-1">${r.dpd}d</span>
        <span class="ms-auto text-end text-muted" style="font-size:0.78rem">
          ${Number(r.amount_paid).toLocaleString('vi-VN')} / ${Number(r.amount_due).toLocaleString('vi-VN')}
        </span>
      </li>`;
  }).join('') : '<li class="text-muted">Không có dữ liệu lịch sử</li>';

  const channelIcons = { EMAIL: 'bi-envelope-fill', SMS: 'bi-chat-text-fill', CALL: 'bi-telephone-fill', FIELD: 'bi-geo-alt-fill' };
  const dpd = Number(t.dpd_current);
  const dpdCls = dpdClass(dpd);

  document.getElementById('detail-body').innerHTML = `
    <div class="row g-3 mb-3">
      <!-- Customer info -->
      <div class="col-md-6">
        <h6 class="fw-bold text-muted text-uppercase" style="font-size:0.72rem;letter-spacing:.05em">Khách Hàng</h6>
        <div class="fw-bold fs-5">${t.customer_name}</div>
        <div class="text-muted small mt-1">
          <i class="bi bi-card-text"></i> CCCD: <strong>${t.national_id || '–'}</strong>
        </div>
        <div class="mt-2 d-flex flex-column gap-1">
          <a href="tel:${t.phone}" class="btn btn-sm btn-outline-success w-100">
            <i class="bi bi-telephone-fill"></i> ${t.phone}
          </a>
          ${t.email ? `<a href="mailto:${t.email}" class="btn btn-sm btn-outline-secondary w-100">
            <i class="bi bi-envelope"></i> ${t.email}</a>` : ''}
          ${t.address ? `<a href="https://maps.google.com/?q=${encodeURIComponent(t.address)}" target="_blank"
            class="btn btn-sm btn-outline-secondary w-100">
            <i class="bi bi-geo-alt"></i> ${t.address}</a>` : ''}
        </div>
      </div>
      <!-- Contract info -->
      <div class="col-md-6">
        <h6 class="fw-bold text-muted text-uppercase" style="font-size:0.72rem;letter-spacing:.05em">Hợp Đồng</h6>
        <div><code class="fs-6">${t.contract_no}</code></div>
        <div class="text-muted small mt-1">
          ${t.product_source} · ${t.product_code} · ${t.branch_name || ''}
        </div>
        <div class="fw-bold mt-2" style="font-size:1.1rem">
          ${Number(t.total_outstanding).toLocaleString('vi-VN')} <span class="text-muted fs-6">VNĐ dư nợ</span>
        </div>
        <div class="mt-2">
          <span class="channel-badge channel-${t.assigned_channel}">
            <i class="bi ${channelIcons[t.assigned_channel] || 'bi-question'}"></i> ${t.assigned_channel}
          </span>
        </div>
      </div>
    </div>

    <!-- Risk mini-cards -->
    <div class="row g-2 mb-3">
      <div class="col-3">
        <div class="text-center p-2 rounded border">
          <div class="dpd-badge ${dpdCls} d-inline-block mb-1">${dpd}d</div>
          <div class="text-muted" style="font-size:0.7rem">DPD</div>
        </div>
      </div>
      <div class="col-3">
        <div class="text-center p-2 rounded border">
          <div class="fw-bold text-warning fs-5">${t.num_overdue_6m}</div>
          <div class="text-muted" style="font-size:0.7rem">Kỳ trễ 6T</div>
        </div>
      </div>
      <div class="col-3">
        <div class="text-center p-2 rounded border">
          <div class="fw-bold text-info fs-5">${t.max_dpd_6m}</div>
          <div class="text-muted" style="font-size:0.7rem">Max DPD 6T</div>
        </div>
      </div>
      <div class="col-3">
        <div class="text-center p-2 rounded border">
          <div class="fw-bold text-danger fs-5">${Number(t.risk_score).toFixed(1)}</div>
          <div class="text-muted" style="font-size:0.7rem">Risk Score</div>
        </div>
      </div>
    </div>

    <!-- 6-month timeline -->
    <h6 class="fw-bold mb-2">
      <i class="bi bi-clock-history text-primary"></i> Lịch Sử 6 Tháng Gần Nhất
    </h6>
    <ul class="history-timeline">${histItems}</ul>`;
}
