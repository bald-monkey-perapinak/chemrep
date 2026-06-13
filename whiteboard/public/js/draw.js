(function() {
  const canvas = document.getElementById('canvas');
  let isDrawing = false;
  let currentPath = null;
  let currentColor = '#333';
  let currentWidth = 3;
  let paths = [];

  // Создаём панель инструментов
  const toolbar = document.createElement('div');
  toolbar.id = 'draw-toolbar';
  toolbar.innerHTML = `
    <button id="btn-draw" class="active" title="Карандаш">Карандаш</button>
    <button id="btn-eraser" title="Ластик">Ластик</button>
    <button id="btn-clear" title="Очистить">Очистить</button>
    <input type="color" id="color-picker" value="#333333" title="Цвет">
    <input type="range" id="width-slider" min="1" max="10" value="3" title="Толщина">
  `;
  document.getElementById('board').appendChild(toolbar);

  const btnDraw = document.getElementById('btn-draw');
  const btnEraser = document.getElementById('btn-eraser');
  const btnClear = document.getElementById('btn-clear');
  const colorPicker = document.getElementById('color-picker');
  const widthSlider = document.getElementById('width-slider');

  // Обработчики кнопок
  btnDraw.addEventListener('click', () => {
    currentColor = colorPicker.value;
    currentWidth = parseInt(widthSlider.value);
    btnDraw.classList.add('active');
    btnEraser.classList.remove('active');
  });

  btnEraser.addEventListener('click', () => {
    currentColor = '#f8f8f7';
    currentWidth = 20;
    btnEraser.classList.add('active');
    btnDraw.classList.remove('active');
  });

  btnClear.addEventListener('click', () => {
    paths.forEach(p => p.remove());
    paths = [];
  });

  colorPicker.addEventListener('input', (e) => {
    currentColor = e.target.value;
    if (btnDraw.classList.contains('active')) {
      btnDraw.click();
    }
  });

  widthSlider.addEventListener('input', (e) => {
    currentWidth = parseInt(e.target.value);
  });

  // Рисование на SVG
  function getCoords(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  canvas.addEventListener('mousedown', (e) => {
    if (e.target.closest('#draw-toolbar')) return;
    isDrawing = true;
    const coords = getCoords(e);
    currentPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    currentPath.setAttribute('d', `M${coords.x},${coords.y}`);
    currentPath.setAttribute('stroke', currentColor);
    currentPath.setAttribute('stroke-width', currentWidth);
    currentPath.setAttribute('fill', 'none');
    currentPath.setAttribute('stroke-linecap', 'round');
    currentPath.setAttribute('stroke-linejoin', 'round');
    canvas.appendChild(currentPath);
    paths.push(currentPath);
  });

  canvas.addEventListener('mousemove', (e) => {
    if (!isDrawing || !currentPath) return;
    const coords = getCoords(e);
    const d = currentPath.getAttribute('d');
    currentPath.setAttribute('d', `${d} L${coords.x},${coords.y}`);
  });

  canvas.addEventListener('mouseup', () => {
    isDrawing = false;
    currentPath = null;
  });

  canvas.addEventListener('mouseleave', () => {
    isDrawing = false;
    currentPath = null;
  });

  // Touch support
  canvas.addEventListener('touchstart', (e) => {
    if (e.target.closest('#draw-toolbar')) return;
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousedown', {
      clientX: touch.clientX,
      clientY: touch.clientY
    });
    canvas.dispatchEvent(mouseEvent);
  });

  canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
      clientX: touch.clientX,
      clientY: touch.clientY
    });
    canvas.dispatchEvent(mouseEvent);
  });

  canvas.addEventListener('touchend', () => {
    const mouseEvent = new MouseEvent('mouseup', {});
    canvas.dispatchEvent(mouseEvent);
  });

  console.log('[draw] Drawing tools initialized');
})();
