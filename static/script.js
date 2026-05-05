const ws = new WebSocket(`ws://${window.location.host}/ws`);

const elements = {
    status: document.getElementById('status-indicator'),
    btnConnect: document.getElementById('btn-connect'),
    btnDisconnect: document.getElementById('btn-disconnect'),
    interface: document.getElementById('interface'),
    channel: document.getElementById('channel'),
    bitrate: document.getElementById('bitrate'),
    console: document.getElementById('console'),
    filterTelemetry: document.getElementById('filter-telemetry'),
    rpmSlider: document.getElementById('rpm-slider'),
    rpmTargetVal: document.getElementById('rpm-target-val'),
    rpms: {
        593: document.getElementById('rpm-593'),
        594: document.getElementById('rpm-594'),
        595: document.getElementById('rpm-595'),
        596: document.getElementById('rpm-596')
    },
    keys: {
        w: document.getElementById('key-w'),
        a: document.getElementById('key-a'),
        s: document.getElementById('key-s'),
        d: document.getElementById('key-d')
    }
};

let lineCount = 0;

function log(msg) {
    const div = document.createElement('div');
    div.textContent = msg;
    elements.console.appendChild(div);
    lineCount++;
    
    if (lineCount > 500) {
        elements.console.removeChild(elements.console.firstChild);
        lineCount--;
    }
    
    // Autoscroll
    elements.console.scrollTop = elements.console.scrollHeight;
}

function updateStatus(status) {
    if (status === 'Connected') {
        elements.status.textContent = 'Connected';
        elements.status.className = 'status-connected';
        elements.btnConnect.disabled = true;
        elements.btnDisconnect.disabled = false;
        elements.interface.disabled = true;
        elements.channel.disabled = true;
        elements.bitrate.disabled = true;
    } else {
        elements.status.textContent = 'Disconnected';
        elements.status.className = 'status-disconnected';
        elements.btnConnect.disabled = false;
        elements.btnDisconnect.disabled = true;
        elements.interface.disabled = false;
        elements.channel.disabled = false;
        elements.bitrate.disabled = false;
        
        // Reset RPMs
        Object.values(elements.rpms).forEach(el => el.textContent = '0');
    }
}

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
        case 'status':
            updateStatus(data.status);
            break;
        case 'log':
            log(data.message);
            break;
        case 'error':
            alert(`Error: ${data.message}`);
            break;
        case 'rpm':
            if (elements.rpms[data.id]) {
                elements.rpms[data.id].textContent = data.value;
            }
            break;
        case 'rpm_target':
            elements.rpmSlider.value = data.value;
            elements.rpmTargetVal.textContent = data.value;
            break;
        case 'filter_state':
            elements.filterTelemetry.checked = data.value;
            break;
    }
};

// Controls
elements.btnConnect.addEventListener('click', () => {
    ws.send(JSON.stringify({
        type: 'connect',
        interface: elements.interface.value,
        channel: elements.channel.value,
        bitrate: parseInt(elements.bitrate.value)
    }));
});

elements.btnDisconnect.addEventListener('click', () => {
    ws.send(JSON.stringify({ type: 'disconnect' }));
});

elements.rpmSlider.addEventListener('input', (e) => {
    elements.rpmTargetVal.textContent = e.target.value;
    ws.send(JSON.stringify({ type: 'rpm', value: e.target.value }));
});

elements.filterTelemetry.addEventListener('change', (e) => {
    ws.send(JSON.stringify({ type: 'filter', value: e.target.checked }));
});

// WASD
const validKeys = ['w', 'a', 's', 'd'];

window.addEventListener('keydown', (e) => {
    const k = e.key.toLowerCase();
    if (validKeys.includes(k) && document.activeElement.tagName !== 'INPUT') {
        if (!elements.keys[k].classList.contains('active')) {
            elements.keys[k].classList.add('active');
            ws.send(JSON.stringify({ type: 'key', key: k, state: true }));
        }
    }
});

window.addEventListener('keyup', (e) => {
    const k = e.key.toLowerCase();
    if (validKeys.includes(k)) {
        elements.keys[k].classList.remove('active');
        ws.send(JSON.stringify({ type: 'key', key: k, state: false }));
    }
});
