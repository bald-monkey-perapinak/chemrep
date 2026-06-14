/**
 * Miro-level Whiteboard Drawing Tools
 * 
 * Features:
 * - Pen/Highlighter freehand drawing
 * - Shapes: Rectangle, Circle, Arrow, Line
 * - Text tool (editable text boxes)
 * - Sticky notes (colored)
 * - Selection tool (select, move, resize)
 * - Eraser
 * - Undo/Redo history
 * - Zoom in/out + fit to screen
 * - Grid snap (optional)
 * - Export to PNG
 * - Touch support
 */
(function() {
  'use strict';

  const svg = document.getElementById('canvas');
  const viewport = document.getElementById('board-viewport');
  const container = document.getElementById('canvas-container');
  
  // ── State ──────────────────────────────────────────────────────────────
  let currentTool = 'pen';
  let currentColor = '#1a1a1a';
  let currentWidth = 3;
  let currentFontSize = 20;
  let isDrawing = false;
  let startX = 0, startY = 0;
  let currentElement = null;
  let selectedElement = null;
  let dragOffsetX = 0, dragOffsetY = 0;
  let pathData = '';
  
  // History for undo/redo
  const undoStack = [];
  const redoStack = [];
  const MAX_HISTORY = 50;
  
  // Zoom state
  let zoomLevel = 1;
  let panX = 0, panY = 0;
  let isPanning = false;
  let panStartX = 0, panStartY = 0;
  
  // Grid
  let gridEnabled = false;
  const GRID_SIZE = 20;
  
  // SVG namespace
  const NS = 'http://www.w3.org/2000/svg';

  // ── Toolbar ────────────────────────────────────────────────────────────
  const toolbar = document.createElement('div');
  toolbar.id = 'miro-toolbar';
  toolbar.innerHTML = `
    <div class="tool-group">
      <button data-tool="select" class="tool-btn" title="Выделение (V)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/>
        </svg>
      </button>
      <button data-tool="pen" class="tool-btn active" title="Карандаш (P)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/>
        </svg>
      </button>
      <button data-tool="highlighter" title="Маркер (H)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15.5 4.5l4 4L8 20H4v-4L15.5 4.5z"/>
        </svg>
      </button>
      <button data-tool="eraser" title="Ластик (E)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 20H7L3 16l9-9 8 8-4 4"/><path d="M6.5 13.5l5-5"/>
        </svg>
      </button>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <button data-tool="rect" title="Прямоугольник (R)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
        </svg>
      </button>
      <button data-tool="circle" title="Круг (C)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
        </svg>
      </button>
      <button data-tool="arrow" title="Стрелка (A)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
        </svg>
      </button>
      <button data-tool="line" title="Линия (L)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="19" x2="19" y2="5"/>
        </svg>
      </button>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <button data-tool="text" title="Текст (T)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4 7 4 4 20 4 20 7"/><line x1="9.5" y1="20" x2="14.5" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/>
        </svg>
      </button>
      <button data-tool="sticky" title="Стикер (S)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15.5 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V8.5L15.5 3z"/>
          <polyline points="14 3 14 9 21 9"/>
        </svg>
      </button>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <input type="color" id="color-picker" value="#1a1a1a" title="Цвет">
      <input type="range" id="width-slider" min="1" max="12" value="3" title="Толщина">
      <select id="font-size-select" title="Размер шрифта">
        <option value="14">14</option>
        <option value="18">18</option>
        <option value="20" selected>20</option>
        <option value="24">24</option>
        <option value="32">32</option>
        <option value="48">48</option>
      </select>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <button id="btn-undo" title="Отменить (Ctrl+Z)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
        </svg>
      </button>
      <button id="btn-redo" title="Повторить (Ctrl+Y)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.13-9.36L23 10"/>
        </svg>
      </button>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <button id="btn-zoom-in" title="Приблизить (+)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
      </button>
      <span id="zoom-level">100%</span>
      <button id="btn-zoom-out" title="Отдалить (-)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/>
        </svg>
      </button>
      <button id="btn-zoom-fit" title="Вписать в экран (0)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
        </svg>
      </button>
    </div>
    <div class="tool-separator"></div>
    <div class="tool-group">
      <button id="btn-grid" title="Сетка (G)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
        </svg>
      </button>
      <button id="btn-export" title="Экспорт PNG">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </button>
      <button id="btn-clear-all" title="Очистить доску">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
        </svg>
      </button>
    </div>
  `;
  document.getElementById('board').insertBefore(toolbar, viewport);

  // ── Tool selection ─────────────────────────────────────────────────────
  const toolButtons = toolbar.querySelectorAll('[data-tool]');
  toolButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      toolButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTool = btn.dataset.tool;
      svg.style.cursor = getCursorForTool(currentTool);
      deselectAll();
    });
  });

  function getCursorForTool(tool) {
    switch(tool) {
      case 'select': return 'default';
      case 'pen': case 'highlighter': return 'crosshair';
      case 'eraser': return 'cell';
      case 'rect': case 'circle': case 'arrow': case 'line': return 'crosshair';
      case 'text': return 'text';
      case 'sticky': return 'crosshair';
      default: return 'default';
    }
  }

  // Color/width/font controls
  const colorPicker = document.getElementById('color-picker');
  const widthSlider = document.getElementById('width-slider');
  const fontSizeSelect = document.getElementById('font-size-select');

  colorPicker.addEventListener('input', e => currentColor = e.target.value);
  widthSlider.addEventListener('input', e => currentWidth = parseInt(e.target.value));
  fontSizeSelect.addEventListener('change', e => currentFontSize = parseInt(e.target.value));

  // ── History (Undo/Redo) ────────────────────────────────────────────────
  function saveState() {
    undoStack.push(svg.innerHTML);
    if (undoStack.length > MAX_HISTORY) undoStack.shift();
    redoStack.length = 0;
  }

  function undo() {
    if (undoStack.length === 0) return;
    redoStack.push(svg.innerHTML);
    svg.innerHTML = undoStack.pop();
    broadcastFullState();
  }

  function redo() {
    if (redoStack.length === 0) return;
    undoStack.push(svg.innerHTML);
    svg.innerHTML = redoStack.pop();
    broadcastFullState();
  }

  document.getElementById('btn-undo').addEventListener('click', undo);
  document.getElementById('btn-redo').addEventListener('click', redo);

  // ── Zoom ───────────────────────────────────────────────────────────────
  function updateTransform() {
    container.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomLevel})`;
    container.style.transformOrigin = '0 0';
    document.getElementById('zoom-level').textContent = Math.round(zoomLevel * 100) + '%';
  }

  document.getElementById('btn-zoom-in').addEventListener('click', () => {
    zoomLevel = Math.min(5, zoomLevel * 1.2);
    updateTransform();
  });

  document.getElementById('btn-zoom-out').addEventListener('click', () => {
    zoomLevel = Math.max(0.1, zoomLevel / 1.2);
    updateTransform();
  });

  document.getElementById('btn-zoom-fit').addEventListener('click', () => {
    zoomLevel = 1; panX = 0; panY = 0;
    updateTransform();
  });

  viewport.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      zoomLevel = Math.min(5, Math.max(0.1, zoomLevel * delta));
      updateTransform();
    }
  }, { passive: false });

  // Middle-click pan
  viewport.addEventListener('mousedown', (e) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
      viewport.style.cursor = 'grabbing';
      e.preventDefault();
    }
  });

  document.addEventListener('mousemove', (e) => {
    if (isPanning) {
      panX = e.clientX - panStartX;
      panY = e.clientY - panStartY;
      updateTransform();
    }
  });

  document.addEventListener('mouseup', () => {
    if (isPanning) {
      isPanning = false;
      viewport.style.cursor = '';
    }
  });

  // ── Grid ───────────────────────────────────────────────────────────────
  const gridBtn = document.getElementById('btn-grid');
  let gridPattern = null;

  function toggleGrid() {
    gridEnabled = !gridEnabled;
    gridBtn.classList.toggle('active', gridEnabled);
    if (gridEnabled) {
      const defs = document.createElementNS(NS, 'defs');
      const pattern = document.createElementNS(NS, 'pattern');
      pattern.setAttribute('id', 'grid');
      pattern.setAttribute('width', GRID_SIZE);
      pattern.setAttribute('height', GRID_SIZE);
      pattern.setAttribute('patternUnits', 'userSpaceOnUse');
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', `M ${GRID_SIZE} 0 L 0 0 0 ${GRID_SIZE}`);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', '#e0e0e0');
      path.setAttribute('stroke-width', '0.5');
      pattern.appendChild(path);
      defs.appendChild(pattern);
      svg.insertBefore(defs, svg.firstChild);
      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('width', '100%');
      rect.setAttribute('height', '100%');
      rect.setAttribute('fill', 'url(#grid)');
      rect.id = 'grid-bg';
      svg.insertBefore(rect, svg.firstChild.nextSibling);
    } else {
      const g = svg.getElementById('grid-bg');
      if (g) g.remove();
      const d = svg.querySelector('defs');
      if (d) d.remove();
    }
  }

  gridBtn.addEventListener('click', toggleGrid);

  function snapToGrid(val) {
    return gridEnabled ? Math.round(val / GRID_SIZE) * GRID_SIZE : val;
  }

  // ── Selection ──────────────────────────────────────────────────────────
  function deselectAll() {
    if (selectedElement) {
      selectedElement.classList.remove('selected');
      selectedElement = null;
    }
    // Remove selection handles
    svg.querySelectorAll('.selection-handle').forEach(h => h.remove());
  }

  function selectElement(el) {
    deselectAll();
    selectedElement = el;
    el.classList.add('selected');
  }

  // ── Drawing handlers ───────────────────────────────────────────────────
  function getSVGCoords(e) {
    const rect = svg.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoomLevel;
    const y = (e.clientY - rect.top) / zoomLevel;
    return { x: snapToGrid(x), y: snapToGrid(y) };
  }

  svg.addEventListener('mousedown', (e) => {
    if (e.target.closest('#miro-toolbar') || e.button === 1 || e.altKey) return;
    
    const coords = getSVGCoords(e);
    startX = coords.x;
    startY = coords.y;

    switch(currentTool) {
      case 'select':
        handleSelect(e, coords);
        break;
      case 'pen':
      case 'highlighter':
        saveState();
        currentElement = document.createElementNS(NS, 'path');
        currentElement.setAttribute('d', `M${coords.x},${coords.y}`);
        currentElement.setAttribute('stroke', currentColor);
        currentElement.setAttribute('stroke-width', currentTool === 'highlighter' ? currentWidth * 3 : currentWidth);
        currentElement.setAttribute('fill', 'none');
        currentElement.setAttribute('stroke-linecap', 'round');
        currentElement.setAttribute('stroke-linejoin', 'round');
        if (currentTool === 'highlighter') {
          currentElement.setAttribute('stroke-opacity', '0.4');
        }
        currentElement.classList.add('board-element');
        svg.appendChild(currentElement);
        isDrawing = true;
        break;
      case 'eraser':
        saveState();
        handleEraser(e, coords);
        isDrawing = true;
        break;
      case 'rect':
        saveState();
        currentElement = document.createElementNS(NS, 'rect');
        currentElement.setAttribute('x', coords.x);
        currentElement.setAttribute('y', coords.y);
        currentElement.setAttribute('width', 0);
        currentElement.setAttribute('height', 0);
        currentElement.setAttribute('stroke', currentColor);
        currentElement.setAttribute('stroke-width', currentWidth);
        currentElement.setAttribute('fill', 'none');
        currentElement.setAttribute('rx', '4');
        currentElement.classList.add('board-element');
        svg.appendChild(currentElement);
        isDrawing = true;
        break;
      case 'circle':
        saveState();
        currentElement = document.createElementNS(NS, 'ellipse');
        currentElement.setAttribute('cx', coords.x);
        currentElement.setAttribute('cy', coords.y);
        currentElement.setAttribute('rx', 0);
        currentElement.setAttribute('ry', 0);
        currentElement.setAttribute('stroke', currentColor);
        currentElement.setAttribute('stroke-width', currentWidth);
        currentElement.setAttribute('fill', 'none');
        currentElement.classList.add('board-element');
        svg.appendChild(currentElement);
        isDrawing = true;
        break;
      case 'line':
        saveState();
        currentElement = document.createElementNS(NS, 'line');
        currentElement.setAttribute('x1', coords.x);
        currentElement.setAttribute('y1', coords.y);
        currentElement.setAttribute('x2', coords.x);
        currentElement.setAttribute('y2', coords.y);
        currentElement.setAttribute('stroke', currentColor);
        currentElement.setAttribute('stroke-width', currentWidth);
        currentElement.setAttribute('stroke-linecap', 'round');
        currentElement.classList.add('board-element');
        svg.appendChild(currentElement);
        isDrawing = true;
        break;
      case 'arrow':
        saveState();
        currentElement = document.createElementNS(NS, 'g');
        const line = document.createElementNS(NS, 'line');
        line.setAttribute('x1', coords.x);
        line.setAttribute('y1', coords.y);
        line.setAttribute('x2', coords.x);
        line.setAttribute('y2', coords.y);
        line.setAttribute('stroke', currentColor);
        line.setAttribute('stroke-width', currentWidth);
        line.setAttribute('stroke-linecap', 'round');
        const head = document.createElementNS(NS, 'polygon');
        head.setAttribute('fill', currentColor);
        head.classList.add('arrow-head');
        currentElement.appendChild(line);
        currentElement.appendChild(head);
        currentElement.classList.add('board-element');
        svg.appendChild(currentElement);
        isDrawing = true;
        break;
      case 'text':
        createTextInput(coords.x, coords.y);
        break;
      case 'sticky':
        saveState();
        createStickyNote(coords.x, coords.y);
        break;
    }
  });

  svg.addEventListener('mousemove', (e) => {
    if (!isDrawing || !currentElement) return;
    const coords = getSVGCoords(e);

    switch(currentTool) {
      case 'pen':
      case 'highlighter':
        const d = currentElement.getAttribute('d');
        currentElement.setAttribute('d', `${d} L${coords.x},${coords.y}`);
        break;
      case 'eraser':
        handleEraser(e, coords);
        break;
      case 'rect':
        const w = coords.x - startX;
        const h = coords.y - startY;
        currentElement.setAttribute('x', w < 0 ? coords.x : startX);
        currentElement.setAttribute('y', h < 0 ? coords.y : startY);
        currentElement.setAttribute('width', Math.abs(w));
        currentElement.setAttribute('height', Math.abs(h));
        break;
      case 'circle':
        const rx = Math.abs(coords.x - startX) / 2;
        const ry = Math.abs(coords.y - startY) / 2;
        currentElement.setAttribute('cx', Math.min(startX, coords.x) + rx);
        currentElement.setAttribute('cy', Math.min(startY, coords.y) + ry);
        currentElement.setAttribute('rx', rx);
        currentElement.setAttribute('ry', ry);
        break;
      case 'line':
        currentElement.setAttribute('x2', coords.x);
        currentElement.setAttribute('y2', coords.y);
        break;
      case 'arrow':
        const arrowLine = currentElement.querySelector('line');
        const arrowHead = currentElement.querySelector('.arrow-head');
        arrowLine.setAttribute('x2', coords.x);
        arrowLine.setAttribute('y2', coords.y);
        updateArrowHead(arrowHead, startX, startY, coords.x, coords.y, currentWidth);
        break;
    }
  });

  svg.addEventListener('mouseup', () => {
    if (isDrawing && currentElement) {
      // Broadcast the drawn element
      broadcastElement(currentElement);
    }
    isDrawing = false;
    currentElement = null;
  });

  svg.addEventListener('mouseleave', () => {
    isDrawing = false;
    currentElement = null;
  });

  // ── Eraser ─────────────────────────────────────────────────────────────
  function handleEraser(e, coords) {
    const elements = svg.querySelectorAll('.board-element, .formula-label, .equation-block, .svg-container, .sticky-note, .text-box');
    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      const elX = (rect.left - svgRect.left) / zoomLevel;
      const elY = (rect.top - svgRect.top) / zoomLevel;
      const elW = rect.width / zoomLevel;
      const elH = rect.height / zoomLevel;
      if (coords.x >= elX && coords.x <= elX + elW && coords.y >= elY && coords.y <= elY + elH) {
        el.remove();
      }
    });
  }

  // ── Selection ──────────────────────────────────────────────────────────
  function handleSelect(e, coords) {
    const target = e.target.closest('.board-element, .sticky-note, .text-box, .formula-label, .equation-block');
    if (target) {
      selectElement(target);
      // Start drag
      const bbox = target.getBBox ? target.getBBox() : { x: coords.x, y: coords.y };
      dragOffsetX = coords.x - bbox.x;
      dragOffsetY = coords.y - bbox.y;
      
      const onMove = (ev) => {
        const c = getSVGCoords(ev);
        const newX = c.x - dragOffsetX;
        const newY = c.y - dragOffsetY;
        if (target.tagName === 'g') {
          target.setAttribute('transform', `translate(${newX - (target.getBBox?.()?.x || 0)}, ${newY - (target.getBBox?.()?.y || 0)})`);
        } else if (target.classList.contains('sticky-note') || target.classList.contains('text-box')) {
          target.style.left = newX + 'px';
          target.style.top = newY + 'px';
        } else {
          const dx = newX - (target.getBBox?.()?.x || 0);
          const dy = newY - (target.getBBox?.()?.y || 0);
          moveSVGElement(target, dx, dy);
        }
      };
      
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        saveState();
        broadcastElement(target);
      };
      
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    } else {
      deselectAll();
    }
  }

  function moveSVGElement(el, dx, dy) {
    const tag = el.tagName;
    if (tag === 'path') {
      const d = el.getAttribute('d');
      el.setAttribute('d', translatePath(d, dx, dy));
    } else if (tag === 'rect') {
      el.setAttribute('x', parseFloat(el.getAttribute('x')) + dx);
      el.setAttribute('y', parseFloat(el.getAttribute('y')) + dy);
    } else if (tag === 'ellipse') {
      el.setAttribute('cx', parseFloat(el.getAttribute('cx')) + dx);
      el.setAttribute('cy', parseFloat(el.getAttribute('cy')) + dy);
    } else if (tag === 'line') {
      el.setAttribute('x1', parseFloat(el.getAttribute('x1')) + dx);
      el.setAttribute('y1', parseFloat(el.getAttribute('y1')) + dy);
      el.setAttribute('x2', parseFloat(el.getAttribute('x2')) + dx);
      el.setAttribute('y2', parseFloat(el.getAttribute('y2')) + dy);
    } else if (tag === 'g') {
      const existing = el.getAttribute('transform') || '';
      el.setAttribute('transform', `${existing} translate(${dx},${dy})`);
    }
  }

  function translatePath(d, dx, dy) {
    return d.replace(/([ML])\s*([\d.]+)\s*,\s*([\d.]+)/gi, (match, cmd, x, y) => {
      return `${cmd}${parseFloat(x) + dx},${parseFloat(y) + dy}`;
    });
  }

  // ── Arrow head ─────────────────────────────────────────────────────────
  function updateArrowHead(polygon, x1, y1, x2, y2, width) {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const headLen = width * 4 + 8;
    const headAngle = Math.PI / 7;
    const p1x = x2 - headLen * Math.cos(angle - headAngle);
    const p1y = y2 - headLen * Math.sin(angle - headAngle);
    const p2x = x2 - headLen * Math.cos(angle + headAngle);
    const p2y = y2 - headLen * Math.sin(angle + headAngle);
    polygon.setAttribute('points', `${x2},${y2} ${p1x},${p1y} ${p2x},${p2y}`);
  }

  // ── Text tool ──────────────────────────────────────────────────────────
  function createTextInput(x, y) {
    const foreignObject = document.createElementNS(NS, 'foreignObject');
    foreignObject.setAttribute('x', x);
    foreignObject.setAttribute('y', y);
    foreignObject.setAttribute('width', '400');
    foreignObject.setAttribute('height', '100');
    
    const div = document.createElement('div');
    div.contentEditable = 'true';
    div.className = 'inline-text-editor';
    div.style.cssText = `font-size:${currentFontSize}px;color:${currentColor};min-width:50px;outline:none;padding:4px;border:2px dashed #4a90d9;border-radius:4px;background:rgba(255,255,255,0.9);`;
    div.textContent = '';
    
    foreignObject.appendChild(div);
    foreignObject.classList.add('board-element', 'text-box');
    svg.appendChild(foreignObject);
    
    div.focus();
    
    const finishEdit = () => {
      const text = div.textContent.trim();
      if (!text) {
        foreignObject.remove();
        return;
      }
      div.contentEditable = 'false';
      div.style.border = 'none';
      div.style.background = 'transparent';
      // Auto-size
      foreignObject.setAttribute('width', Math.max(100, div.scrollWidth + 20));
      foreignObject.setAttribute('height', div.scrollHeight + 10);
      saveState();
      broadcastElement(foreignObject);
    };
    
    div.addEventListener('blur', finishEdit);
    div.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') finishEdit();
      e.stopPropagation();
    });
  }

  // ── Sticky notes ───────────────────────────────────────────────────────
  const STICKY_COLORS = ['#fff9b1', '#ff7eb3', '#7ec8e3', '#b8e6b8', '#f0c987'];

  function createStickyNote(x, y) {
    const div = document.createElement('div');
    div.className = 'sticky-note board-element';
    const color = STICKY_COLORS[Math.floor(Math.random() * STICKY_COLORS.length)];
    div.style.cssText = `
      position:absolute; left:${x}px; top:${y}px;
      width:200px; min-height:150px; padding:12px;
      background:${color}; border-radius:4px;
      box-shadow:2px 2px 8px rgba(0,0,0,0.15);
      font-size:16px; color:#333; cursor:move;
      font-family:'Patrick Hand',cursive,sans-serif;
    `;
    div.contentEditable = 'true';
    div.textContent = '';
    container.appendChild(div);
    
    div.focus();
    div.addEventListener('blur', () => {
      saveState();
      broadcastElement(div);
    });
    div.addEventListener('keydown', e => e.stopPropagation());
  }

  // ── Export PNG ──────────────────────────────────────────────────────────
  document.getElementById('btn-export').addEventListener('click', () => {
    const svgData = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = svg.clientWidth * 2;
      canvas.height = svg.clientHeight * 2;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      const link = document.createElement('a');
      link.download = 'chemrep-board.png';
      link.href = canvas.toDataURL('image/png');
      link.click();
    };
    img.src = url;
  });

  // ── Clear all ──────────────────────────────────────────────────────────
  document.getElementById('btn-clear-all').addEventListener('click', () => {
    if (!confirm('Очистить всю доску?')) return;
    saveState();
    svg.querySelectorAll('.board-element, .formula-label, .equation-block, .svg-container').forEach(el => el.remove());
    container.querySelectorAll('.sticky-note').forEach(el => el.remove());
    broadcastFullState();
  });

  // ── Keyboard shortcuts ─────────────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.target.contentEditable === 'true' || e.target.tagName === 'INPUT') return;
    
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key === 'y') { e.preventDefault(); redo(); return; }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (selectedElement) {
        saveState();
        selectedElement.remove();
        selectedElement = null;
      }
      return;
    }
    
    const shortcuts = { v:'select', p:'pen', h:'highlighter', e:'eraser', r:'rect', c:'circle', a:'arrow', l:'line', t:'text', s:'sticky', g:'grid' };
    if (shortcuts[e.key]) {
      const btn = toolbar.querySelector(`[data-tool="${shortcuts[e.key]}"]`);
      if (btn) btn.click();
    }
    if (e.key === '+' || e.key === '=') document.getElementById('btn-zoom-in').click();
    if (e.key === '-') document.getElementById('btn-zoom-out').click();
    if (e.key === '0') document.getElementById('btn-zoom-fit').click();
  });

  // ── WebSocket broadcast ────────────────────────────────────────────────
  function broadcastElement(el) {
    if (!window._boardWs || window._boardWs.readyState !== WebSocket.OPEN) return;
    const tag = el.tagName;
    let msg = { type: 'draw_element' };
    
    if (tag === 'path') {
      msg = { type: 'draw', tool: 'pen', d: el.getAttribute('d'), stroke: el.getAttribute('stroke'), strokeWidth: el.getAttribute('stroke-width'), strokeOpacity: el.getAttribute('stroke-opacity') };
    } else if (tag === 'rect') {
      msg = { type: 'shape', tool: 'rect', x: el.getAttribute('x'), y: el.getAttribute('y'), width: el.getAttribute('width'), height: el.getAttribute('height'), stroke: el.getAttribute('stroke'), strokeWidth: el.getAttribute('stroke-width') };
    } else if (tag === 'ellipse') {
      msg = { type: 'shape', tool: 'circle', cx: el.getAttribute('cx'), cy: el.getAttribute('cy'), rx: el.getAttribute('rx'), ry: el.getAttribute('ry'), stroke: el.getAttribute('stroke'), strokeWidth: el.getAttribute('stroke-width') };
    } else if (tag === 'line') {
      msg = { type: 'shape', tool: 'line', x1: el.getAttribute('x1'), y1: el.getAttribute('y1'), x2: el.getAttribute('x2'), y2: el.getAttribute('y2'), stroke: el.getAttribute('stroke'), strokeWidth: el.getAttribute('stroke-width') };
    }
    
    try { window._boardWs.send(JSON.stringify(msg)); } catch {}
  }

  function broadcastFullState() {
    if (!window._boardWs || window._boardWs.readyState !== WebSocket.OPEN) return;
    try {
      window._boardWs.send(JSON.stringify({ type: 'full_state', svg: svg.innerHTML }));
    } catch {}
  }

  // Touch support
  svg.addEventListener('touchstart', (e) => {
    if (e.target.closest('#miro-toolbar')) return;
    e.preventDefault();
    const touch = e.touches[0];
    svg.dispatchEvent(new MouseEvent('mousedown', { clientX: touch.clientX, clientY: touch.clientY }));
  }, { passive: false });

  svg.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    svg.dispatchEvent(new MouseEvent('mousemove', { clientX: touch.clientX, clientY: touch.clientY }));
  }, { passive: false });

  svg.addEventListener('touchend', () => {
    svg.dispatchEvent(new MouseEvent('mouseup', {}));
  });

  // ── Init ───────────────────────────────────────────────────────────────
  svg.style.cursor = getCursorForTool(currentTool);
  console.log('[draw] Miro-level drawing tools initialized');
})();
