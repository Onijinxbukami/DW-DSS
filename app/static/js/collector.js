async function updateStatus(taskId, newStatus) {
  const resp = await fetch('/collector/update_status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({task_id: taskId, new_status: newStatus})
  });
  const data = await resp.json();
  if (!data.success) alert('Lỗi cập nhật trạng thái');
}

async function showDetail(taskId) {
  document.getElementById('detail-body').innerHTML =
    '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';
  const modal = new bootstrap.Modal(document.getElementById('detailModal'));
  modal.show();

  const resp = await fetch(`/collector/task_detail/${taskId}`);
  const data = await resp.json();
  const t = data.task;
  const h = data.history;

  let histRows = h.map(r => `
    <tr>
      <td>${r.due_date}</td>
      <td class="text-end">${Number(r.amount_due).toLocaleString('vi-VN')}</td>
      <td class="text-end">${Number(r.amount_paid).toLocaleString('vi-VN')}</td>
      <td><span class="badge ${r.dpd > 0 ? 'bg-danger' : 'bg-success'}">${r.dpd} ngày</span></td>
      <td><span class="badge ${r.status === 'PAID' ? 'bg-success' : r.status === 'OVERDUE' ? 'bg-danger' : 'bg-warning text-dark'}">${r.status}</span></td>
    </tr>`).join('');

  document.getElementById('detail-body').innerHTML = `
    <div class="row g-3 mb-3">
      <div class="col-md-6">
        <strong>Họ tên:</strong> ${t.customer_name}<br>
        <strong>CMND/CCCD:</strong> ${t.national_id}<br>
        <strong>SĐT:</strong> <a href="tel:${t.phone}">${t.phone}</a><br>
        <strong>Email:</strong> ${t.email || '–'}
      </div>
      <div class="col-md-6">
        <strong>Hợp đồng:</strong> <code>${t.contract_no}</code><br>
        <strong>Sản phẩm:</strong> ${t.product_source} – ${t.product_code}<br>
        <strong>Chi nhánh:</strong> ${t.branch_name}<br>
        <strong>Dư nợ:</strong> ${Number(t.total_outstanding).toLocaleString('vi-VN')} VNĐ
      </div>
    </div>
    <div class="row g-3 mb-3">
      <div class="col-md-3">
        <div class="card text-center border-danger">
          <div class="card-body py-2">
            <div class="fs-4 fw-bold text-danger">${t.dpd_current}</div>
            <small class="text-muted">DPD hiện tại</small>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-center border-warning">
          <div class="card-body py-2">
            <div class="fs-4 fw-bold text-warning">${t.num_overdue_6m}</div>
            <small class="text-muted">Kỳ trễ 6T</small>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-center border-info">
          <div class="card-body py-2">
            <div class="fs-4 fw-bold text-info">${t.max_dpd_6m}</div>
            <small class="text-muted">Max DPD 6T</small>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-center border-primary">
          <div class="card-body py-2">
            <div class="fs-4 fw-bold text-primary">${Number(t.risk_score).toFixed(1)}</div>
            <small class="text-muted">Risk Score</small>
          </div>
        </div>
      </div>
    </div>
    <h6 class="fw-bold">Lịch sử thanh toán 6 tháng gần nhất</h6>
    <table class="table table-sm table-bordered">
      <thead class="table-light">
        <tr><th>Ngày đến hạn</th><th class="text-end">Phải trả</th><th class="text-end">Đã trả</th><th>DPD</th><th>Trạng thái</th></tr>
      </thead>
      <tbody>${histRows || '<tr><td colspan="5" class="text-center text-muted">Không có dữ liệu</td></tr>'}</tbody>
    </table>`;
}
