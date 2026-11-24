/**
 * map.js — Lógica do mapa Leaflet
 * Carregamento de GeoJSON por BBOX, popups e linha do tempo do processo.
 */

// Paleta de cores por fase
const FASE_CORES = {
  'Requerimento de Pesquisa':    '#58a6ff',
  'Autorização de Pesquisa':     '#3fb950',
  'Requerimento de Lavra':       '#f9a825',
  'Concessão de Lavra':          '#ff7b72',
  'Licenciamento':               '#bc8cff',
  'Manifesto de Mina':           '#ffa657',
  'Registro de Extração':        '#79c0ff',
  'default':                     '#8b949e',
};

function getCorFase(fase) {
  return FASE_CORES[fase] || FASE_CORES['default'];
}

// ============================================================
// Mapa Principal (index.html — div#map)
// ============================================================
(function initMapaPrincipal() {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  // Centro do Pará
  const map = L.map('map', {
    center: [-3.5, -52.0],
    zoom: 6,
    zoomControl: true,
  });

  // Basemap dark
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 19,
  }).addTo(map);

  let geojsonLayer = null;
  let loadTimeout = null;

  function showLoading(show) {
    const el = document.getElementById('mapLoading');
    if (!el) return;
    el.classList.toggle('d-none', !show);
  }

  function carregarProcessos() {
    const bounds = map.getBounds();
    const bbox = [
      bounds.getWest().toFixed(6),
      bounds.getSouth().toFixed(6),
      bounds.getEast().toFixed(6),
      bounds.getNorth().toFixed(6),
    ].join(',');

    const fase = document.getElementById('filtroFase')?.value || '';
    const substancia = document.getElementById('filtroSubstancia')?.value || '';

    let url = `/api/processos?bbox=${bbox}`;
    if (fase) url += `&fase=${encodeURIComponent(fase)}`;
    if (substancia) url += `&substancia=${encodeURIComponent(substancia)}`;

    showLoading(true);

    fetch(url)
      .then(r => r.json())
      .then(data => {
        if (geojsonLayer) map.removeLayer(geojsonLayer);

        geojsonLayer = L.geoJSON(data, {
          style: feat => ({
            color: getCorFase(feat.properties.fase),
            weight: 1,
            fillOpacity: 0.35,
            fillColor: getCorFase(feat.properties.fase),
          }),
          onEachFeature: (feat, layer) => {
            const p = feat.properties;
            const popupHtml = `
              <div class="popup-titulo">${p.numero_processo || '—'}</div>
              <div class="popup-linha"><span class="popup-label">Nome</span><span class="popup-valor">${p.nome || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Fase</span><span class="popup-valor">${p.fase || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Substância</span><span class="popup-valor">${p.substancia || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Área (ha)</span><span class="popup-valor">${p.area_ha ? Number(p.area_ha).toLocaleString('pt-BR') : '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Município</span><span class="popup-valor">${p.municipio || '—'}</span></div>
              <div class="mt-2">
                <button class="btn btn-sm btn-outline-info w-100"
                  onclick="carregarHistorico('${p.numero_processo}')">
                  <i class="bi bi-clock-history me-1"></i>Ver Histórico
                </button>
              </div>
            `;
            layer.bindPopup(popupHtml, { maxWidth: 300 });
          },
        }).addTo(map);

        const count = data.features ? data.features.length : 0;
        const el = document.getElementById('carregados');
        if (el) el.textContent = count.toLocaleString('pt-BR');

        atualizarLegenda();
        showLoading(false);
      })
      .catch(err => {
        console.error('Erro ao carregar processos:', err);
        showLoading(false);
      });
  }

  function atualizarLegenda() {
    const el = document.getElementById('legenda');
    if (!el) return;
    el.innerHTML = Object.entries(FASE_CORES)
      .filter(([k]) => k !== 'default')
      .map(([fase, cor]) => `
        <div class="legenda-item">
          <div class="cor-box" style="background:${cor}"></div>
          <span class="text-muted">${fase}</span>
        </div>`)
      .join('');
  }

  // Carrega com debounce ao mover mapa
  map.on('moveend zoomend', () => {
    clearTimeout(loadTimeout);
    loadTimeout = setTimeout(carregarProcessos, 600);
  });

  // Botão filtrar
  document.getElementById('btnFiltrar')?.addEventListener('click', carregarProcessos);

  // Carga inicial
  carregarProcessos();

  // Expõe ao escopo global para o popup
  window.carregarHistorico = function(numeroProcesso) {
    fetch(`/api/historico/${encodeURIComponent(numeroProcesso)}`)
      .then(r => r.json())
      .then(data => {
        const painel = document.getElementById('painelDetalhe');
        const conteudo = document.getElementById('detalheConteudo');
        const timeline = document.getElementById('timeline');
        if (!painel) return;

        const feats = data.features || [];
        if (feats.length === 0) {
          conteudo.innerHTML = '<p class="text-muted small">Sem histórico disponível.</p>';
          timeline.innerHTML = '';
          painel.style.display = 'block';
          return;
        }

        const p = feats[feats.length - 1].properties;
        conteudo.innerHTML = `
          <div class="popup-linha"><span class="popup-label">Processo</span><span class="popup-valor fw-bold text-info">${p.numero_processo}</span></div>
          <div class="popup-linha"><span class="popup-label">Fase atual</span><span class="popup-valor">${p.fase || '—'}</span></div>
          <div class="popup-linha"><span class="popup-label">Substância</span><span class="popup-valor">${p.substancia || '—'}</span></div>
        `;

        timeline.innerHTML = feats.map(f => {
          const fp = f.properties;
          const tipo = fp.tipo_mudanca || '';
          const data = fp.valido_de ? fp.valido_de.substring(0, 10) : '—';
          return `
            <div class="timeline-item ${tipo}">
              <div class="d-flex justify-content-between align-items-start">
                <span class="timeline-badge badge-${tipo}">${tipo}</span>
                <small class="text-muted">${data}</small>
              </div>
              <div class="text-muted" style="font-size:0.75rem">${fp.fase || ''}</div>
            </div>
          `;
        }).join('');

        painel.style.display = 'block';
      })
      .catch(err => console.error('Erro ao carregar histórico:', err));
  };
})();


// ============================================================
// Mapa de Dinâmica (dinamica.html — div#mapDinamica)
// ============================================================
(function initMapaDinamica() {
  const mapEl = document.getElementById('mapDinamica');
  if (!mapEl) return;

  const map = L.map('mapDinamica', {
    center: [-3.5, -52.0],
    zoom: 6,
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 19,
  }).addTo(map);

  const COR_TIPO = {
    NOVO:      '#2ea043',
    FASE:      '#f9a825',
    TITULAR:   '#58a6ff',
    GEOMETRIA: '#8b949e',
    REMOVIDO:  '#f85149',
  };

  let dinamicaLayer = null;

  window.carregarDinamica = function(tipo) {
    fetch(`/api/dinamica?tipo=${tipo}`)
      .then(r => r.json())
      .then(data => {
        if (dinamicaLayer) map.removeLayer(dinamicaLayer);
        const cor = COR_TIPO[tipo] || '#8b949e';
        dinamicaLayer = L.geoJSON(data, {
          style: {
            color: cor,
            weight: 1.5,
            fillOpacity: 0.5,
            fillColor: cor,
          },
          onEachFeature: (feat, layer) => {
            const p = feat.properties;
            layer.bindPopup(`
              <strong class="text-info">${p.numero_processo}</strong><br>
              <span class="text-muted">Fase:</span> ${p.fase || '—'}<br>
              <span class="text-muted">Data:</span> ${p.valido_de ? p.valido_de.substring(0,10) : '—'}
            `);
          },
        }).addTo(map);
      })
      .catch(err => console.error('Erro ao carregar dinâmica:', err));
  };

  // Event listeners nos radio buttons
  document.querySelectorAll('input[name="tipoDinamica"]').forEach(radio => {
    radio.addEventListener('change', e => {
      window.carregarDinamica(e.target.value);
    });
  });

  // Carga inicial
  window.carregarDinamica('NOVO');
})();
