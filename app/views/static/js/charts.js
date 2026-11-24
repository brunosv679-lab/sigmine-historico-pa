/**
 * charts.js — Gráficos Chart.js
 * Novos requerimentos por mês/substância e mudanças detectadas.
 * Usado na página dinamica.html
 */

// Prefixo dinâmico para suportar subrota /sigmine/ e raiz /
const API_BASE = window.location.pathname.startsWith('/sigmine') ? '/sigmine/' : '/';

let chartNovosMes = null;
let chartSubstancia = null;

// Paleta de cores para gráficos
const PALETA = [
  '#58a6ff', '#2ea043', '#f9a825', '#ff7b72', '#bc8cff',
  '#ffa657', '#79c0ff', '#3fb950', '#d2a8ff', '#56d364',
  '#e3b341', '#f85149', '#8b949e', '#1f6feb', '#388bfd',
];

function formatarMes(anoMes) {
  if (!anoMes) return '';
  const [ano, mes] = anoMes.split('-');
  const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  return `${meses[parseInt(mes) - 1]}/${ano.slice(2)}`;
}

// --- Gráfico: Novos por Mês ---
function carregarNovosPorMes(meses = 24) {
  fetch(`${API_BASE}api/stats/novos-por-mes?meses=${meses}`)
    .then(r => r.json())
    .then(resp => {
      const dados = resp.data || [];
      const labels = dados.map(d => formatarMes(d.mes));
      const valores = dados.map(d => Number(d.total));

      const ctx = document.getElementById('chartNovosMes');
      if (!ctx) return;

      if (chartNovosMes) chartNovosMes.destroy();

      chartNovosMes = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Novos requerimentos',
            data: valores,
            backgroundColor: 'rgba(88, 166, 255, 0.5)',
            borderColor: '#58a6ff',
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.parsed.y} novos`,
              },
            },
          },
          scales: {
            x: {
              ticks: { color: '#8b949e', maxRotation: 45 },
              grid: { color: '#21262d' },
            },
            y: {
              ticks: { color: '#8b949e', precision: 0 },
              grid: { color: '#21262d' },
              beginAtZero: true,
            },
          },
        },
      });
    })
    .catch(err => console.error('Erro ao carregar novos por mês:', err));
}

// --- Gráfico: Por Substância ---
function carregarPorSubstancia() {
  fetch(`${API_BASE}api/stats/por-substancia?meses=12`)
    .then(r => r.json())
    .then(resp => {
      const dados = resp.data || [];
      const labels = dados.map(d => d.substancia);
      const valores = dados.map(d => Number(d.total));
      const cores = dados.map((_, i) => PALETA[i % PALETA.length]);

      const ctx = document.getElementById('chartSubstancia');
      if (!ctx) return;

      if (chartSubstancia) chartSubstancia.destroy();

      chartSubstancia = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{
            data: valores,
            backgroundColor: cores.map(c => c + 'bb'),
            borderColor: cores,
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: '#8b949e',
                font: { size: 10 },
                boxWidth: 12,
                padding: 8,
              },
            },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.parsed}`,
              },
            },
          },
        },
      });
    })
    .catch(err => console.error('Erro ao carregar por substância:', err));
}

// --- Cards de resumo de mudanças ---
function carregarResumoMudancas() {
  fetch(`${API_BASE}api/stats/mudancas?meses=6`)
    .then(r => r.json())
    .then(resp => {
      const dados = resp.data || [];
      const mapa = {};
      dados.forEach(d => { mapa[d.tipo_mudanca] = d.total; });

      const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = Number(val || 0).toLocaleString('pt-BR');
      };
      set('totalNovos', mapa['NOVO']);
      set('totalFase', mapa['FASE']);
      set('totalGeometria', mapa['GEOMETRIA']);
      set('totalRemovidos', mapa['REMOVIDO']);
    })
    .catch(err => console.error('Erro ao carregar resumo de mudanças:', err));
}

// --- Inicialização ---
(function init() {
  // Só inicializa na página de dinâmica
  if (!document.getElementById('chartNovosMes')) return;

  carregarNovosPorMes(24);
  carregarPorSubstancia();
  carregarResumoMudancas();

  // Listener do seletor de meses
  document.getElementById('selectMeses')?.addEventListener('change', e => {
    carregarNovosPorMes(Number(e.target.value));
  });
})();
