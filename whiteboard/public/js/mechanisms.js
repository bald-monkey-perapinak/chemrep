window.loadSVG = function(url, container, options = {}) {
  const { x = 0, y = 0, animate = false, width = 600 } = options;

  return fetch(url)
    .then(r => r.text())
    .then(svgText => {
      const wrapper = document.createElement('div');
      wrapper.className = 'board-element svg-container fade-in' + (animate ? ' animate' : '');
      wrapper.style.cssText = `left:${x}px; top:${y}px; max-width:${width}px;`;
      wrapper.innerHTML = svgText;
      container.appendChild(wrapper);
      return wrapper;
    })
    .catch(e => {
      console.error('[board] SVG load error:', e);
      return null;
    });
};
