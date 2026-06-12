window.renderEquation = function(equation, container, options = {}) {
  const { x = 0, y = 0, label = '', fontSize = 20 } = options;

  const block = document.createElement('div');
  block.className = 'board-element equation-block fade-in';
  block.style.cssText = `left:${x}px; top:${y}px;`;

  const formula = document.createElement('div');
  formula.className = 'equation-formula';

  try {
    katex.render(
      `\\ce{${equation}}`,
      formula,
      { throwOnError: false, displayMode: true }
    );
  } catch (e) {
    formula.textContent = equation;
    formula.style.fontFamily = 'monospace';
    formula.style.fontSize = fontSize + 'px';
  }

  block.appendChild(formula);

  if (label) {
    const lbl = document.createElement('div');
    lbl.className = 'formula-label';
    lbl.textContent = label;
    block.appendChild(lbl);
  }

  container.appendChild(block);
  return block;
};
