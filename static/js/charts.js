let tiltChartInstance = null;
let memoryDistChartInstance = null;
let kdTrendChartInstance = null;

function renderKdTrendChart(canvasId, trendData) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (kdTrendChartInstance) {
    kdTrendChartInstance.destroy();
  }

  const labels = trendData.map(d => `Session ${d.session_id}`);
  const values = trendData.map(d => Number(d.kd_ratio || 0));

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
  gradient.addColorStop(1, 'rgba(168, 85, 247, 0.02)');

  kdTrendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'K/D Ratio',
        data: values,
        borderColor: '#00f2fe',
        borderWidth: 2.5,
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#070a13',
        pointBorderColor: '#00f2fe',
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointHoverBackgroundColor: '#a855f7',
        pointHoverBorderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(7, 10, 19, 0.95)',
          titleColor: '#00f2fe',
          bodyColor: '#e2e8f0',
          borderColor: 'rgba(6, 182, 212, 0.3)',
          borderWidth: 1,
          padding: 10,
          displayColors: false,
          callbacks: {
            title: function(items) {
              const idx = items[0].dataIndex;
              const item = trendData[idx];
              return `Session #${item.session_id} (${item.game || 'Valorant'})`;
            },
            label: function(context) {
              const item = trendData[context.dataIndex];
              return [
                `K/D Ratio: ${item.kd_ratio}`,
                `Map: ${item.map || 'Ascent'}`,
                `Result: ${item.result || 'Win'}`
              ];
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          suggestedMax: 2.2,
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: {
            color: '#64748b',
            font: { family: 'JetBrains Mono', size: 10 },
            callback: function(v) { return v.toFixed(1); }
          }
        },
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.03)' },
          ticks: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 10 }
          }
        }
      }
    }
  });
}

function renderTiltTrendChart(canvasId, trendData) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (tiltChartInstance) {
    tiltChartInstance.destroy();
  }

  const labels = trendData.map((d, i) => `S#${d.session_id}`);
  const tilts = trendData.map(d => d.tilt);
  const colors = trendData.map(d => 
    d.outcome.includes("Victory") || d.outcome.includes("Defeated") 
      ? 'rgba(16, 185, 129, 0.7)' 
      : 'rgba(239, 68, 68, 0.7)'
  );
  const borderColors = trendData.map(d => 
    d.outcome.includes("Victory") || d.outcome.includes("Defeated") 
      ? '#10b981' 
      : '#ef4444'
  );

  const ctx = canvas.getContext('2d');
  tiltChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Peak Tilt / Stress Index (0-10)',
        data: tilts,
        backgroundColor: colors,
        borderColor: borderColors,
        borderWidth: 1.5,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#e2e8f0',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            afterLabel: function(context) {
              const item = trendData[context.dataIndex];
              return `Outcome: ${item.outcome}\nTitle: ${item.title}`;
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 10,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b', font: { family: 'JetBrains Mono' } }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', font: { family: 'JetBrains Mono' } }
        }
      }
    }
  });
}

function renderMemoryDistChart(canvasId, episodicCount, semanticCount, proceduralCount) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (memoryDistChartInstance) {
    memoryDistChartInstance.destroy();
  }

  const ctx = canvas.getContext('2d');
  memoryDistChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Episodic (Sessions)', 'Semantic (Facts)', 'Procedural (Habits)'],
      datasets: [{
        data: [episodicCount, semanticCount, proceduralCount],
        backgroundColor: [
          'rgba(6, 182, 212, 0.8)',
          'rgba(168, 85, 247, 0.8)',
          'rgba(245, 158, 11, 0.8)'
        ],
        borderColor: '#0f172a',
        borderWidth: 3,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 }, padding: 12 }
        }
      },
      cutout: '70%'
    }
  });
}
