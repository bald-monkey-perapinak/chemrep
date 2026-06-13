window.renderEquation = function(equation, container, options = {}) {
  const { x = 0, y = 0, label = '', fontSize = 20 } = options;

  const block = document.createElement('div');
  block.className = 'board-element equation-block fade-in';
  block.style.cssText = `left:${x}px; top:${y}px; font-size: ${fontSize}px;`;

  const formula = document.createElement('div');
  formula.className = 'equation-formula';

  try {
    // Пробуем через mhchem
    katex.render(
      `\\ce{${equation}}`,
      formula,
      { throwOnError: false, displayMode: true }
    );
  } catch (e1) {
    try {
      // Fallback: простой KaTeX без mhchem
      // Заменяем стрелки на Unicode
      let tex = equation
        .replace(/\\\\rightarrow/g, '\\rightarrow')
        .replace(/->/g, '\\rightarrow')
        .replace(/←/g, '\\leftarrow');
      katex.render(tex, formula, { throwOnError: false, displayMode: true });
    } catch (e2) {
      // Если KaTeX не работает — показываем текст
      let text = equation
        .replace(/\\\\rightarrow/g, ' → ')
        .replace(/->/g, ' → ')
        .replace(/\\rightarrow/g, ' →')
        .replace(/\\leftarrow/g, '← ')
        .replace(/\\_/g, '_')
        .replace(/\\^/g, '^')
        .replace(/[{}]/g, '');
      formula.textContent = text;
      formula.style.fontFamily = 'serif';
      formula.style.fontSize = fontSize + 'px';
    }
  }

  block.appendChild(formula);

  if (label) {
    const lbl = document.createElement('div');
    lbl.className = 'formula-label handwritten';
    lbl.textContent = label;
    block.appendChild(lbl);
  }

  container.appendChild(block);
  return block;
};
