(function() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session') || window.location.pathname.split('/').pop();

  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const canvas = document.getElementById('canvas-container');
  const equationsLayer = document.getElementById('equations-layer');
  const labelsLayer = document.getElementById('labels-layer');

  let ws = null;
  let reconnectTimer = null;
  let elementCounter = 0;

  function setStatus(state, text) {
    statusDot.className = state;
    statusText.textContent = text;
  }

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/rooms/${sessionId}`;

    setStatus('', 'Подключение...');
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setStatus('connected', 'Подключено');
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleCommand(msg);
      } catch (e) {
        console.error('[board] Parse error:', e);
      }
    };

    ws.onclose = () => {
      setStatus('error', 'Отключено');
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setStatus('error', 'Ошибка соединения');
    };
  }

  function handleCommand(msg) {
    switch (msg.type) {
      case 'show_formula':
        showFormula(msg);
        break;
      case 'show_equation':
        showEquation(msg);
        break;
      case 'show_svg':
        showSVG(msg);
        break;
      case 'draw_text':
        drawText(msg);
        break;
      case 'highlight':
        highlightElement(msg);
        break;
      case 'clear':
        clearAll();
        break;
      case 'clear_step':
        clearStep();
        break;
      default:
        console.warn('[board] Unknown command:', msg.type);
    }
  }

  function showFormula(msg) {
    const id = 'el_' + (++elementCounter);
    const el = window.renderFormula(msg.smiles, canvas, {
      x: msg.x || 100,
      y: msg.y || 100,
      width: msg.width || 350,
      height: msg.height || 250,
    });
    if (el) el.id = id;

    if (msg.label) {
      const lbl = document.createElement('div');
      lbl.className = 'formula-label fade-in';
      lbl.style.cssText = `left:${msg.x || 100}px; top:${(msg.y || 100) + 260}px;`;
      lbl.textContent = msg.label;
      labelsLayer.appendChild(lbl);
    }
  }

  function showEquation(msg) {
    const id = 'el_' + (++elementCounter);
    const el = window.renderEquation(msg.equation, equationsLayer, {
      x: msg.x || 100,
      y: msg.y || 100,
      label: msg.label || '',
      fontSize: msg.fontSize || 20,
    });
    if (el) el.id = id;
  }

  function showSVG(msg) {
    const id = 'el_' + (++elementCounter);
    window.loadSVG(msg.asset_url, canvas, {
      x: msg.x || 100,
      y: msg.y || 100,
      animate: msg.animate || false,
      width: msg.width || 600,
    }).then(el => {
      if (el) el.id = id;
    });
  }

  function drawText(msg) {
    const id = 'el_' + (++elementCounter);
    const el = document.createElement('div');
    el.className = 'board-element fade-in';
    el.id = id;
    el.style.cssText = `left:${msg.x || 100}px; top:${msg.y || 100}px; font-size: ${msg.style?.fontSize || 24}px; color: ${msg.style?.color || '#333'}; font-weight: ${msg.style?.bold ? '700' : '400'};`;
    el.textContent = msg.text;
    canvas.appendChild(el);
  }

  function highlightElement(msg) {
    const el = document.getElementById(msg.target);
    if (el) el.classList.add('highlight');
  }

  function clearAll() {
    canvas.querySelectorAll('.board-element').forEach(el => el.remove());
    equationsLayer.querySelectorAll('.board-element').forEach(el => el.remove());
    labelsLayer.querySelectorAll('.formula-label').forEach(el => el.remove());
    elementCounter = 0;
  }

  function clearStep() {
    canvas.querySelectorAll('.board-element').forEach(el => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
    equationsLayer.querySelectorAll('.board-element').forEach(el => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
    labelsLayer.querySelectorAll('.formula-label').forEach(el => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
  }

  window.initRDKit().then(() => connect());
})();
