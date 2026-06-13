(function() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session') || 'default';

  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const canvas = document.getElementById('canvas-container');
  const viewport = document.getElementById('board-viewport');
  const equationsLayer = document.getElementById('equations-layer');
  const labelsLayer = document.getElementById('labels-layer');

  let ws = null;
  let reconnectTimer = null;
  let elementCounter = 0;
  let rdkitReady = false;

  function setStatus(state, text) {
    statusDot.className = state;
    statusText.textContent = text;
  }

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/rooms/${sessionId}`;

    setStatus('', 'Подключение...');
    console.log('[board] Connecting to', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setStatus('connected', 'Подключено к ' + sessionId);
      console.log('[board] Connected');
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('[board] Received:', msg.type, msg);
        handleCommand(msg);
      } catch (e) {
        console.error('[board] Parse error:', e, event.data);
      }
    };

    ws.onclose = () => {
      setStatus('error', 'Отключено');
      console.log('[board] Disconnected, reconnecting in 3s...');
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      setStatus('error', 'Ошибка соединения');
      console.error('[board] WebSocket error:', err);
    };
  }

  function handleCommand(msg) {
    switch (msg.type) {
      case 'show_formula':  showFormula(msg); break;
      case 'show_equation': showEquation(msg); break;
      case 'show_svg':      showSVG(msg); break;
      case 'draw_text':     drawText(msg); break;
      case 'draw_handwritten': drawHandwritten(msg); break;
      case 'scroll_to':     scrollTo(msg); break;
      case 'highlight':     highlightElement(msg); break;
      case 'clear':         clearAll(); break;
      case 'clear_step':    clearStep(); break;
      default:
        console.warn('[board] Unknown command:', msg.type);
    }
  }

  function showFormula(msg) {
    if (!rdkitReady || !window.renderFormula) {
      drawHandwritten({text: msg.label || msg.smiles, x: msg.x, y: msg.y, fontSize: 22});
      return;
    }
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
      lbl.className = 'formula-label fade-in handwritten';
      lbl.style.cssText = `left:${msg.x || 100}px; top:${(msg.y || 100) + 260}px;`;
      lbl.textContent = msg.label;
      canvas.appendChild(lbl);
    }
  }

  function showEquation(msg) {
    if (!window.renderEquation) {
      drawHandwritten({text: msg.equation, x: msg.x, y: msg.y, fontSize: 20});
      return;
    }
    const id = 'el_' + (++elementCounter);
    const el = window.renderEquation(msg.equation, canvas, {
      x: msg.x || 100,
      y: msg.y || 100,
      label: msg.label || '',
      fontSize: msg.fontSize || 20,
    });
    if (el) el.id = id;
  }

  function showSVG(msg) {
    if (!window.loadSVG) return;
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

  function drawHandwritten(msg) {
    const id = 'el_' + (++elementCounter);
    const el = document.createElement('div');
    el.className = 'board-element fade-in handwritten';
    el.id = id;
    const size = msg.fontSize || 28;
    const color = msg.color || '#1a1a1a';
    el.style.cssText = `left:${msg.x || 100}px; top:${msg.y || 100}px; font-size: ${size}px; color: ${color};`;
    el.textContent = msg.text;
    canvas.appendChild(el);
    console.log('[board] Drew handwritten:', msg.text, 'at', msg.x, msg.y);
  }

  function scrollTo(msg) {
    viewport.scrollTo({
      left: (msg.x || 100) - viewport.clientWidth / 2,
      top: (msg.y || 100) - viewport.clientHeight / 2,
      behavior: 'smooth'
    });
  }

  function highlightElement(msg) {
    const el = document.getElementById(msg.target);
    if (el) el.classList.add('highlight');
  }

  function clearAll() {
    canvas.querySelectorAll('.board-element, .formula-label, .equation-block, .svg-container').forEach(el => el.remove());
    elementCounter = 0;
  }

  function clearStep() {
    canvas.querySelectorAll('.board-element, .formula-label, .equation-block, .svg-container').forEach(el => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    });
  }

  // Init
  connect();

  if (window.initRDKit) {
    window.initRDKit().then(() => {
      rdkitReady = true;
      console.log('[board] RDKit ready');
    }).catch(err => {
      console.warn('[board] RDKit failed:', err);
    });
  }
})();
