/* ── DPD Bucket Bar Chart ─────────────────────────────── */
new Chart(document.getElementById('bucketChart'), {
  type: 'bar',
  data: {
    labels: Object.keys(bucketRaw),
    datasets: [{
      label: 'Số task',
      data: Object.values(bucketRaw),
      backgroundColor: ['#198754', '#ffc107', '#fd7e14', '#dc3545'],
      borderRadius: 6,
      borderSkipped: false,
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => {
            const labels = { A: 'DPD 1–9 (EMAIL)', B: 'DPD 10–19 (SMS)', C: 'DPD 20–29 (CALL)', D: 'DPD ≥30 (FIELD)' };
            return labels[items[0].label] || items[0].label;
          },
        },
      },
    },
    scales: {
      y: { beginAtZero: true, ticks: { font: { size: 11 } } },
      x: { ticks: { font: { size: 12, weight: 'bold' } } },
    },
  },
});

/* ── Channel Doughnut ─────────────────────────────────── */
const channelColors = {
  EMAIL: '#cfe2ff',
  SMS:   '#e0cffc',
  CALL:  '#ffe5d0',
  FIELD: '#212529',
  NONE:  '#dee2e6',
};
const channelBorders = {
  EMAIL: '#084298',
  SMS:   '#3d0a91',
  CALL:  '#a93226',
  FIELD: '#000',
  NONE:  '#adb5bd',
};
new Chart(document.getElementById('channelChart'), {
  type: 'doughnut',
  data: {
    labels: Object.keys(channelRaw),
    datasets: [{
      data: Object.values(channelRaw),
      backgroundColor: Object.keys(channelRaw).map(k => channelColors[k] || '#dee2e6'),
      borderColor: Object.keys(channelRaw).map(k => channelBorders[k] || '#adb5bd'),
      borderWidth: 2,
      hoverOffset: 8,
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'right', labels: { font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (item) => ` ${item.label}: ${item.raw} task`,
        },
      },
    },
    cutout: '55%',
  },
});

/* ── Risk Score Histogram ─────────────────────────────── */
const riskLabels = Object.keys(riskRaw);
const riskCounts = Object.values(riskRaw);
// Color gradient: green → yellow → orange → red by bucket order
const riskColors = ['#198754', '#20c997', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1'];
new Chart(document.getElementById('riskChart'), {
  type: 'bar',
  data: {
    labels: riskLabels,
    datasets: [{
      label: 'Số case',
      data: riskCounts,
      backgroundColor: riskLabels.map((_, i) => riskColors[i % riskColors.length]),
      borderRadius: 5,
      borderSkipped: false,
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item) => ` ${item.raw} case có risk score ${item.label}`,
        },
      },
    },
    scales: {
      y: { beginAtZero: true, ticks: { font: { size: 11 } } },
      x: { ticks: { font: { size: 11 } } },
    },
  },
});

/* ── Task Status Doughnut ─────────────────────────────── */
const statusColors = {
  DONE:        '#198754',
  IN_PROGRESS: '#ffc107',
  PENDING:     '#0d6efd',
  SKIPPED:     '#6c757d',
};
const statusLabels = { DONE: 'Hoàn thành', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ', SKIPPED: 'Bỏ qua' };
new Chart(document.getElementById('statusChart'), {
  type: 'doughnut',
  data: {
    labels: Object.keys(statusRaw).map(k => statusLabels[k] || k),
    datasets: [{
      data: Object.values(statusRaw),
      backgroundColor: Object.keys(statusRaw).map(k => statusColors[k] || '#dee2e6'),
      borderWidth: 2,
      hoverOffset: 8,
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'right', labels: { font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (item) => ` ${item.label}: ${item.raw} task`,
        },
      },
    },
    cutout: '55%',
  },
});
