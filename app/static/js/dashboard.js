// DPD Bucket Bar Chart
new Chart(document.getElementById('bucketChart'), {
  type: 'bar',
  data: {
    labels: Object.keys(bucketRaw),
    datasets: [{
      label: 'Số task',
      data: Object.values(bucketRaw),
      backgroundColor: ['#198754','#ffc107','#fd7e14','#dc3545'],
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
  }
});

// Channel Doughnut
const channelColors = { EMAIL: '#0d6efd', SMS: '#6f42c1', CALL: '#fd7e14', FIELD: '#dc3545', NONE: '#adb5bd' };
new Chart(document.getElementById('channelChart'), {
  type: 'doughnut',
  data: {
    labels: Object.keys(channelRaw),
    datasets: [{
      data: Object.values(channelRaw),
      backgroundColor: Object.keys(channelRaw).map(k => channelColors[k] || '#adb5bd'),
    }]
  },
  options: { responsive: true }
});
