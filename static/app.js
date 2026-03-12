let usageChart = null;
let requestChart = null;
let currentData = null;

document.addEventListener('DOMContentLoaded', function() {
    loadData();
    setInterval(loadData, 300000);
});

function setStatus(status, message) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    
    dot.className = 'status-dot';
    if (status === 'syncing') dot.classList.add('syncing');
    if (status === 'error') dot.classList.add('error');
    
    text.textContent = message;
}

function showLoading() {
    document.getElementById('loading').classList.add('active');
    document.getElementById('statsGrid').style.opacity = '0.5';
}

function hideLoading() {
    document.getElementById('loading').classList.remove('active');
    document.getElementById('statsGrid').style.opacity = '1';
}

async function loadData() {
    showLoading();
    setStatus('syncing', 'Loading...');
    
    const days = document.getElementById('daysSelect').value;
    
    try {
        const response = await fetch(`/usage?days=${days}`);
        const data = await response.json();
        
        if (data.success) {
            currentData = data;
            updateDashboard(data);
            setStatus('ready', 'Ready');
            
            document.getElementById('lastUpdated').textContent = 
                `Last updated: ${new Date().toLocaleString()}`;
            document.getElementById('dataRange').textContent = 
                `Data range: ${data.start_date} to ${data.end_date}`;
        } else {
            throw new Error(data.error || 'Failed to load data');
        }
    } catch (error) {
        console.error('Error loading data:', error);
        setStatus('error', 'Error loading data');
    } finally {
        hideLoading();
    }
}

async function refreshData() {
    showLoading();
    setStatus('syncing', 'Fetching from API...');
    
    try {
        const response = await fetch('/usage?days=30');
        const data = await response.json();
        
        if (data.success) {
            currentData = data;
            updateDashboard(data);
            const msg = data.fetched_from_api ? 'Data refreshed from API!' : 'Data loaded from cache';
            setStatus('ready', msg);
            
            document.getElementById('lastUpdated').textContent = 
                `Last updated: ${new Date().toLocaleString()}`;
            document.getElementById('dataRange').textContent = 
                `Data range: ${data.start_date} to ${data.end_date}`;
        } else {
            throw new Error(data.error || 'Failed to fetch data');
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        setStatus('error', 'Error fetching data');
        alert('Failed to fetch data from API. Check console for details.');
    } finally {
        hideLoading();
    }
}

function exportData() {
    fetch('/export')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const blob = new Blob([JSON.stringify(data.data, null, 2)], 
                                  {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `ark-usage-export-${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
            } else {
                alert('Failed to export data: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error exporting data:', error);
            alert('Failed to export data.');
        });
}

function updateDashboard(data) {
    updateDashboardStats(data.summary);
    updateCharts(data.summary.daily_breakdown);
}

function updateDashboardStats(summary) {
    animateNumber('totalTokens', summary.total_tokens);
    animateNumber('totalRequests', summary.total_requests);
    animateNumber('inputTokens', summary.total_input_tokens);
    animateNumber('outputTokens', summary.total_output_tokens);
}

function animateNumber(elementId, value) {
    const element = document.getElementById(elementId);
    const start = 0;
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (value - start) * easeProgress);
        
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

function updateCharts(dailyData) {
    const dates = dailyData.map(d => d.date);
    const tokens = dailyData.map(d => d.tokens);
    const requests = dailyData.map(d => d.requests);
    
    const tokenCtx = document.getElementById('usageChart').getContext('2d');
    
    if (usageChart) {
        usageChart.destroy();
    }
    
    usageChart = new Chart(tokenCtx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Total Tokens',
                data: tokens,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: dates.length > 30 ? 0 : 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 15, maxRotation: 0 }
                },
                y: {
                    beginAtZero: true,
                    ticks: { callback: function(value) { return value.toLocaleString(); } }
                }
            }
        }
    });
    
    const requestCtx = document.getElementById('requestChart').getContext('2d');
    
    if (requestChart) {
        requestChart.destroy();
    }
    
    requestChart = new Chart(requestCtx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [{
                label: 'Request Count',
                data: requests,
                backgroundColor: 'rgba(118, 75, 162, 0.6)',
                borderColor: 'rgba(118, 75, 162, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' }
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 15, maxRotation: 0 }
                },
                y: {
                    beginAtZero: true,
                    ticks: { callback: function(value) { return value.toLocaleString(); } }
                }
            }
        }
    });
}
