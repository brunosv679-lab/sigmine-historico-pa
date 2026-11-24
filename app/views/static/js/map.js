/**
 * map.js — Lógica do mapa Leaflet
 * Carregamento de GeoJSON por BBOX, popups e linha do tempo do processo.
 */

// Prefixo dinâmico para suportar subrota /sigmine/ e raiz /
const API_BASE = window.location.pathname.startsWith('/sigmine') ? '/sigmine/' : '/';

// Paleta de cores por fase
const FASE_CORES = {
  'Requerimento de Pesquisa':        '#58a6ff',
  'Autorização de Pesquisa':         '#3fb950',
  'Requerimento de Lavra':           '#f9a825',
  'Concessão de Lavra':              '#ff7b72',
  'Licenciamento':                   '#bc8cff',
  'Manifesto de Mina':               '#ffa657',
  'Registro de Extração':            '#79c0ff',
  'Requerimento de Lavra Garimpeira':'#e3b341',
  'Lavra Garimpeira':                '#d29922',
  'Disponibilidade':                 '#8b949e',
  'default':                         '#8b949e',
};

function getCorFase(fase) {
  if (!fase) return FASE_CORES['default'];
  for (const [key, cor] of Object.entries(FASE_CORES)) {
    if (fase.toLowerCase().includes(key.toLowerCase())) return cor;
  }
  return FASE_CORES['default'];
}

// Bounding Box padrão do Estado do Pará (fallback)
const BBOX_PADRAO_PA = '-58.90,-9.85,-46.05,2.45';

// ============================================================
// Mapa Principal (index.html — div#map)
// ============================================================
(function initMapaPrincipal() {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  // Centro do Estado do Pará: [-5.5, -52.5], zoom 6
  const map = L.map('map', {
    center: [-5.5, -52.5],
    zoom: 6,
    zoomControl: true,
    minZoom: 4,
    maxZoom: 18,
  });

  // Camadas base gratuitas e sem API Key
  // 1. Escuro (Padrão): Esri Dark Gray Canvas
  const darkTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16,
  }).addTo(map);

  // 2. Ruas / Claro: OpenStreetMap padrão
  const osmTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  });

  // 3. Satélite: Esri World Imagery
  const satTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP',
    maxZoom: 19,
  });

  L.control.layers({
    '🌙 Mapa Escuro (Esri)': darkTiles,
    '☀️ Ruas (OpenStreetMap)': osmTiles,
    '🛰️ Satélite (Esri)': satTiles,
  }, null, { position: 'topright' }).addTo(map);

  let geojsonLayer = null;
  let loadTimeout = null;

  function showLoading(show) {
    const el = document.getElementById('mapLoading');
    if (!el) return;
    el.classList.toggle('d-none', !show);
  }

  function carregarProcessos() {
    let bbox = BBOX_PADRAO_PA;
    try {
      const bounds = map.getBounds();
      if (bounds && bounds.isValid() && !isNaN(bounds.getWest())) {
        bbox = [
          bounds.getWest().toFixed(4),
          bounds.getSouth().toFixed(4),
          bounds.getEast().toFixed(4),
          bounds.getNorth().toFixed(4),
        ].join(',');
      }
    } catch (e) {
      console.warn('Usando BBOX padrão do Pará:', e);
    }

    const fase = document.getElementById('filtroFase')?.value || '';
    const substancia = document.getElementById('filtroSubstancia')?.value || '';

    let url = `${API_BASE}api/processos?bbox=${bbox}&limit=2000`;
    if (fase) url += `&fase=${encodeURIComponent(fase)}`;
    if (substancia) url += `&substancia=${encodeURIComponent(substancia)}`;

    showLoading(true);

    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then(data => {
        if (geojsonLayer) {
          map.removeLayer(geojsonLayer);
        }

        geojsonLayer = L.geoJSON(data, {
          style: feat => ({
            color: getCorFase(feat.properties.fase),
            weight: 1.2,
            opacity: 0.9,
            fillOpacity: 0.4,
            fillColor: getCorFase(feat.properties.fase),
          }),
          onEachFeature: (feat, layer) => {
            const p = feat.properties;
            const popupHtml = `
              <div class="popup-titulo">${p.numero_processo || '—'}</div>
              <div class="popup-linha"><span class="popup-label">Titular</span><span class="popup-valor">${p.nome || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Fase</span><span class="popup-valor">${p.fase || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Substância</span><span class="popup-valor">${p.substancia || '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Área</span><span class="popup-valor">${p.area_ha ? Number(p.area_ha).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' ha' : '—'}</span></div>
              <div class="popup-linha"><span class="popup-label">Município</span><span class="popup-valor">${p.municipio || 'Pará'}</span></div>
              <div class="popup-linha"><span class="popup-label">Último Evento</span><span class="popup-valor">${p.ult_eve_data || '—'}</span></div>
              <div class="mt-2 pt-2 border-top border-secondary">
                <button class="btn btn-sm btn-outline-info w-100"
                  onclick="carregarHistorico('${p.numero_processo}')">
                  <i class="bi bi-clock-history me-1"></i>Ver Linha do Tempo
                </button>
              </div>
            `;
            layer.bindPopup(popupHtml, { maxWidth: 320 });
            layer.on('mouseover', function() { this.setStyle({ fillOpacity: 0.7, weight: 2 }); });
            layer.on('mouseout', function() { geojsonLayer.resetStyle(this); });
          },
        }).addTo(map);

        const count = data.features ? data.features.length : 0;
        const el = document.getElementById('carregados');
        if (el) el.textContent = count.toLocaleString('pt-BR');

        atualizarLegenda();
        showLoading(false);
      })
      .catch(err => {
        console.error('Erro ao carregar processos no mapa:', err);
        showLoading(false);
      });
  }

  function atualizarLegenda() {
    const el = document.getElementById('legenda');
    if (!el) return;
    el.innerHTML = Object.entries(FASE_CORES)
      .filter(([k]) => k !== 'default')
      .slice(0, 8)
      .map(([fase, cor]) => `
        <div class="legenda-item">
          <div class="cor-box" style="background:${cor}"></div>
          <span class="text-muted" style="font-size:0.75rem">${fase}</span>
        </div>`)
      .join('');
  }

  // Redimensionamento responsivo e recálculo do viewport
  window.addEventListener('resize', () => map.invalidateSize());

  // Debounce ao mover ou aplicar zoom no mapa
  map.on('moveend zoomend', () => {
    clearTimeout(loadTimeout);
    loadTimeout = setTimeout(carregarProcessos, 400);
  });

  // Botão filtrar
  document.getElementById('btnFiltrar')?.addEventListener('click', carregarProcessos);

  // Inicialização com invalidateSize garantido em múltiplos tempos
  setTimeout(() => {
    map.invalidateSize();
    carregarProcessos();
  }, 100);

  setTimeout(() => {
    map.invalidateSize();
  }, 400);

  setTimeout(() => {
    map.invalidateSize();
  }, 1000);

  // Expõe função de histórico global para os popups
  window.carregarHistorico = function(numeroProcesso) {
    const painel = document.getElementById('painelDetalhe');
    const conteudo = document.getElementById('detalheConteudo');
    const timeline = document.getElementById('timeline');
    if (!painel) return;

    fetch(`${API_BASE}api/historico/${encodeURIComponent(numeroProcesso)}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        const feats = data.features || [];
        if (feats.length === 0) {
          conteudo.innerHTML = '<p class="text-muted small">Sem histórico registrado.</p>';
          timeline.innerHTML = '';
          painel.style.display = 'block';
          return;
        }

        const p = feats[feats.length - 1].properties;
        conteudo.innerHTML = `
          <div class="popup-linha"><span class="popup-label">Processo</span><span class="popup-valor fw-bold text-info">${p.numero_processo}</span></div>
          <div class="popup-linha"><span class="popup-label">Fase</span><span class="popup-valor">${p.fase || '—'}</span></div>
          <div class="popup-linha"><span class="popup-label">Substância</span><span class="popup-valor">${p.substancia || '—'}</span></div>
          <div class="popup-linha"><span class="popup-label">Área</span><span class="popup-valor">${p.area_ha ? Number(p.area_ha).toLocaleString('pt-BR') + ' ha' : '—'}</span></div>
        `;

        timeline.innerHTML = feats.map(f => {
          const fp = f.properties;
          const tipo = fp.tipo_mudanca || 'NOVO';
          const data = fp.valido_de ? fp.valido_de.substring(0, 10) : '—';
          return `
            <div class="timeline-item ${tipo}">
              <div class="d-flex justify-content-between align-items-start">
                <span class="timeline-badge badge-${tipo}">${tipo}</span>
                <small class="text-muted">${data}</small>
              </div>
              <div class="text-light small mt-1">${fp.fase || ''}</div>
              ${fp.ult_evento ? `<div class="text-muted" style="font-size:0.7rem">${fp.ult_evento}</div>` : ''}
            </div>
          `;
        }).join('');

        painel.style.display = 'block';
        painel.scrollIntoView({ behavior: 'smooth' });
      })
      .catch(err => {
        console.error('Erro ao carregar histórico:', err);
      });
  };
})();


// ============================================================
// Mapa de Dinâmica (dinamica.html — div#mapDinamica)
// ============================================================
(function initMapaDinamica() {
  const mapEl = document.getElementById('mapDinamica');
  if (!mapEl) return;

  const map = L.map('mapDinamica', {
    center: [-5.5, -52.5],
    zoom: 6,
  });

  const darkTilesDinamica = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    maxZoom: 16,
  }).addTo(map);

  const osmTilesDinamica = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  });

  const satTilesDinamica = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  });

  L.control.layers({
    '🌙 Mapa Escuro': darkTilesDinamica,
    '☀️ Ruas': osmTilesDinamica,
    '🛰️ Satélite': satTilesDinamica,
  }, null, { position: 'topright' }).addTo(map);

  const COR_TIPO = {
    NOVO:      '#2ea043',
    FASE:      '#f9a825',
    TITULAR:   '#58a6ff',
    GEOMETRIA: '#8b949e',
    REMOVIDO:  '#f85149',
  };

  let dinamicaLayer = null;

  window.carregarDinamica = function(tipo) {
    fetch(`${API_BASE}api/dinamica?tipo=${tipo}`)
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
              <span class="text-muted">Substância:</span> ${p.substancia || '—'}<br>
              <span class="text-muted">Data:</span> ${p.valido_de ? p.valido_de.substring(0,10) : '—'}
            `);
          },
        }).addTo(map);
      })
      .catch(err => console.error('Erro ao carregar dinâmica:', err));
  };

  document.querySelectorAll('input[name="tipoDinamica"]').forEach(radio => {
    radio.addEventListener('change', e => {
      window.carregarDinamica(e.target.value);
    });
  });

  setTimeout(() => {
    map.invalidateSize();
    window.carregarDinamica('NOVO');
  }, 300);
})();
