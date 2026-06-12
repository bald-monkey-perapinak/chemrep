let RDKit = null;

window.initRDKit = async function() {
  try {
    RDKit = await window.initRDKitModule();
    console.log('[board] RDKit loaded');
    return true;
  } catch (e) {
    console.error('[board] RDKit load failed:', e);
    return false;
  }
};

window.renderFormula = function(smiles, container, options = {}) {
  const { width = 350, height = 250, fontSize = 16 } = options;

  if (!RDKit) {
    const placeholder = document.createElement('div');
    placeholder.className = 'board-element fade-in';
    placeholder.style.cssText = `left:${options.x || 0}px; top:${options.y || 0}px; font-size: ${fontSize}px; color: #333; font-family: monospace;`;
    placeholder.textContent = smiles;
    container.appendChild(placeholder);
    return placeholder;
  }

  try {
    const mol = RDKit.get_mol(smiles);
    if (!mol.is_valid()) {
      console.warn('[board] Invalid SMILES:', smiles);
      mol.delete();
      return null;
    }

    const svgStr = mol.get_svg_with_highlights(JSON.stringify({
      width, height,
      bondLineWidth: 2,
      addAtomIndices: false,
      addStereoAnnotation: true,
    }));

    const wrapper = document.createElement('div');
    wrapper.className = 'board-element fade-in';
    wrapper.style.cssText = `left:${options.x || 0}px; top:${options.y || 0}px;`;
    wrapper.innerHTML = svgStr;
    container.appendChild(wrapper);

    mol.delete();
    return wrapper;
  } catch (e) {
    console.error('[board] RDKit render error:', e);
    return null;
  }
};
