/* Tableau de bord Suivi Carburant — EHCVM III Phase II */
const FMT = new Intl.NumberFormat('fr-FR');
const money = n => FMT.format(Math.round(n || 0)) + ' F';
const num1  = n => FMT.format(Math.round((n || 0) * 10) / 10);
// palette sobre : bleu pétrole principal + neutres, ambre/vert réservés au carburant
const C = { primary:'#2f6f8f', primaryLite:'#7aa7bd', slate:'#64748b',
            gas:'#c77b30', ess:'#3f9d6d', neutral:'#b6c0cc' };

let RAW = [];           // toutes les recharges
let charts = {};        // instances Chart.js

const $ = s => document.querySelector(s);

function montant(r){ return (r.MontRecharge != null ? r.MontRecharge : (r.MontRechargeCalc || 0)); }
function jour(r){
  const d = r.date || r.lastEntryDate || '';
  return (d || '').slice(0, 10);
}

async function load(){
  const res = await fetch('data/carburant.json?_=' + Date.now());
  const data = await res.json();
  RAW = data.recharges || [];
  $('#exportDate').textContent = 'Export : ' + (data.metadata?.date_export || '—') +
        ' · ' + RAW.length + ' recharges';
  buildFilters();
  render();
}

function uniq(key){
  return [...new Set(RAW.map(r => r[key]).filter(v => v != null && v !== ''))].sort();
}

function buildFilters(){
  fill('#fRegion', uniq('Region'));
  fill('#fType',   uniq('TypeCarburant'));
  fill('#fResp',   uniq('responsable'));
  fill('#fStatut', uniq('status'));
}
function fill(sel, vals){
  const el = $(sel);
  const cur = el.value;
  el.innerHTML = '<option value="">' + el.options[0].text + '</option>' +
    vals.map(v => `<option value="${v}">${v}</option>`).join('');
  el.value = cur;
}

function applyFilters(){
  const reg = $('#fRegion').value, typ = $('#fType').value,
        rsp = $('#fResp').value, st = $('#fStatut').value,
        q = $('#fSearch').value.trim().toLowerCase();
  return RAW.filter(r => {
    if (reg && r.Region !== reg) return false;
    if (typ && r.TypeCarburant !== typ) return false;
    if (rsp && r.responsable !== rsp) return false;
    if (st  && r.status !== st) return false;
    if (q){
      const hay = [r.matricule, r.NomChauff, r.LieuExact, r.agent, r.Departement]
        .map(x => (x || '').toLowerCase()).join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function groupSum(rows, key, valFn){
  const m = {};
  rows.forEach(r => {
    const k = r[key]; if (k == null || k === '') return;
    m[k] = (m[k] || 0) + (valFn(r) || 0);
  });
  return m;
}

function render(){
  const rows = applyFilters();
  renderKpis(rows);
  renderRegion(rows);
  renderType(rows);
  renderTime(rows);
  renderVeh(rows);
  renderResp(rows);
  renderTable(rows);
}

function renderKpis(rows){
  const litres = rows.reduce((s, r) => s + (r.QttRecharge || 0), 0);
  const mont   = rows.reduce((s, r) => s + montant(r), 0);
  const veh    = new Set(rows.map(r => r.matricule).filter(Boolean)).size;
  const ag     = new Set(rows.map(r => r.responsable).filter(Boolean)).size;
  const reg    = new Set(rows.map(r => r.Region).filter(Boolean)).size;
  const pmoy   = litres ? mont / litres : 0;
  const cards = [
    ['accent', rows.length, 'Recharges'],
    ['blue',   num1(litres) + ' L', 'Litres totaux'],
    ['gas',    money(mont), 'Montant total'],
    ['',       veh, 'Véhicules'],
    ['',       ag, 'Équipes / agents'],
    ['',       reg, 'Régions'],
    ['',       money(pmoy) + '/L', 'Prix moyen / litre'],
  ];
  $('#kpis').innerHTML = cards.map(([c, v, l]) =>
    `<div class="kpi ${c}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');
}

function makeChart(id, cfg){
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($('#' + id), cfg);
}
const gridColor = 'rgba(31,42,58,.08)';
const tickColor = '#6b7787';
const axes = (horizontal=false) => ({
  x:{grid:{color:gridColor},ticks:{color:tickColor}},
  y:{grid:{color:gridColor},ticks:{color:tickColor}}
});

function renderRegion(rows){
  const m = groupSum(rows, 'Region', montant);
  const keys = Object.keys(m).sort((a,b)=>m[b]-m[a]);
  makeChart('chRegion', {
    type:'bar',
    data:{labels:keys,datasets:[{data:keys.map(k=>m[k]),backgroundColor:C.primary,borderRadius:6}]},
    options:{plugins:{legend:{display:false}},scales:axes()}
  });
}

function renderType(rows){
  const m = groupSum(rows, 'TypeCarburant', r => r.QttRecharge);
  const keys = Object.keys(m);
  const colors = keys.map(k => k === 'Gasoil' ? C.gas : k === 'Essence' ? C.ess : C.neutral);
  makeChart('chType', {
    type:'doughnut',
    data:{labels:keys.map(k=>`${k} (${num1(m[k])} L)`),datasets:[{data:keys.map(k=>m[k]),backgroundColor:colors,borderColor:'#ffffff',borderWidth:2}]},
    options:{plugins:{legend:{position:'bottom',labels:{color:tickColor}}}}
  });
}

function renderTime(rows){
  const byDay = {};
  rows.forEach(r => { const d = jour(r); if(!d) return;
    byDay[d] = byDay[d] || {l:0,m:0}; byDay[d].l += r.QttRecharge||0; byDay[d].m += montant(r); });
  const days = Object.keys(byDay).sort();
  makeChart('chTime', {
    type:'line',
    data:{labels:days,datasets:[
      {label:'Litres',data:days.map(d=>byDay[d].l),borderColor:C.primary,backgroundColor:'rgba(47,111,143,.12)',fill:true,tension:.3,yAxisID:'y'},
      {label:'Montant (F)',data:days.map(d=>byDay[d].m),borderColor:C.gas,backgroundColor:'rgba(199,123,48,.08)',fill:false,tension:.3,yAxisID:'y1'}
    ]},
    options:{plugins:{legend:{labels:{color:tickColor}}},
      scales:{x:{grid:{color:gridColor},ticks:{color:tickColor}},
        y:{position:'left',grid:{color:gridColor},ticks:{color:tickColor},title:{display:true,text:'Litres',color:tickColor}},
        y1:{position:'right',grid:{drawOnChartArea:false},ticks:{color:tickColor},title:{display:true,text:'FCFA',color:tickColor}}}}
  });
}

function renderVeh(rows){
  const m = groupSum(rows, 'matricule', montant);
  const keys = Object.keys(m).sort((a,b)=>m[b]-m[a]).slice(0,10);
  makeChart('chVeh', {
    type:'bar',
    data:{labels:keys,datasets:[{data:keys.map(k=>m[k]),backgroundColor:C.slate,borderRadius:6}]},
    options:{indexAxis:'y',plugins:{legend:{display:false}},scales:axes()}
  });
}

function renderResp(rows){
  const m = {};
  rows.forEach(r => { const k = r.responsable; if(!k) return; m[k]=(m[k]||0)+1; });
  const keys = Object.keys(m).sort((a,b)=>m[b]-m[a]);
  makeChart('chResp', {
    type:'bar',
    data:{labels:keys,datasets:[{data:keys.map(k=>m[k]),backgroundColor:C.primaryLite,borderRadius:6}]},
    options:{plugins:{legend:{display:false}},scales:axes()}
  });
}

function renderTable(rows){
  $('#rowCount').textContent = rows.length;
  const sorted = [...rows].sort((a,b)=>(b.date||b.lastEntryDate||'').localeCompare(a.date||a.lastEntryDate||''));
  const cell = v => (v == null || v === '') ? '<span class="empty">—</span>' : v;
  const carb = t => t === 'Gasoil' ? '<span class="tag-gas">Gasoil</span>'
                  : t === 'Essence' ? '<span class="tag-ess">Essence</span>' : cell(t);
  const badge = s => {
    const u = (s || '').toUpperCase();
    if (u.startsWith('APPROVED'))  return '<span class="badge ok">Validé</span>';
    if (u.startsWith('REJECTED'))  return '<span class="badge rej">Rejeté</span>';
    if (u === 'COMPLETED')         return '<span class="badge done">Terminé</span>';
    return '<span class="badge prog">En cours</span>';
  };
  $('#dataTable tbody').innerHTML = sorted.map(r => `<tr>
    <td>${cell((r.date||'').slice(0,16))}</td>
    <td>${cell(r.Region)}</td><td>${cell(r.Departement)}</td><td>${cell(r.LieuExact)}</td>
    <td>${cell(r.matricule)}</td><td>${cell(r.NomChauff)}</td>
    <td>${carb(r.TypeCarburant)}</td>
    <td class="num">${r.QttRecharge!=null?num1(r.QttRecharge):'<span class="empty">—</span>'}</td>
    <td class="num">${montant(r)?money(montant(r)):'<span class="empty">—</span>'}</td>
    <td class="num">${r.Kilometrage!=null?FMT.format(r.Kilometrage):'<span class="empty">—</span>'}</td>
    <td>${cell(r.agent)}</td><td>${cell(r.responsable)}</td><td>${badge(r.status)}</td>
  </tr>`).join('') || `<tr><td colspan="13" class="empty" style="text-align:center;padding:24px">Aucune recharge ne correspond aux filtres.</td></tr>`;
}

function exportCsv(){
  const rows = applyFilters();
  const cols = ['date','Region','Departement','LieuExact','matricule','NomChauff',
    'TypeCarburant','QttRecharge','MontRecharge','Kilometrage','Soldecarte','agent','responsable','status'];
  const head = cols.join(';');
  const body = rows.map(r => cols.map(c => {
    let v = c === 'MontRecharge' ? montant(r) : r[c];
    if (v == null) v = '';
    return ('' + v).replace(/;/g, ',');
  }).join(';')).join('\n');
  const blob = new Blob(['﻿' + head + '\n' + body], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'recharges_carburant.csv';
  a.click();
}

// Events
['#fRegion','#fType','#fResp','#fStatut'].forEach(s => $(s).addEventListener('change', render));
$('#fSearch').addEventListener('input', render);
$('#resetBtn').addEventListener('click', () => {
  ['#fRegion','#fType','#fResp','#fStatut'].forEach(s => $(s).value='');
  $('#fSearch').value=''; render();
});
$('#reloadBtn').addEventListener('click', load);
$('#csvBtn').addEventListener('click', exportCsv);

async function loadFactures(){
  const card = $('#facturecard');
  try{
    const res = await fetch('factures/factures_index.json?_=' + Date.now());
    if(!res.ok) throw new Error('no index');
    const idx = await res.json();
    const g = $('#facGlobal');
    g.href = 'factures/' + idx.global.fichier;
    g.textContent = `⬇ Tout (${idx.total_factures} factures · ${idx.global.taille_mo} Mo)`;
    $('#facGrid').innerHTML = idx.equipes.map(e =>
      `<a class="facbtn" href="factures/${e.fichier}" download>
         <span class="facname">${e.label}</span>
         <span class="faccount">${e.nb} facture${e.nb>1?'s':''} · ${e.taille_mo} Mo</span>
       </a>`).join('');
    $('#facMeta').textContent = 'Photos regroupées par équipe · générées le ' + idx.date_generation;
  }catch(e){
    card.style.display = 'none';   // pas encore de factures publiées
  }
}
loadFactures();

load().catch(e => {
  document.querySelector('main').innerHTML =
    '<div class="card"><h3>Erreur de chargement</h3><p class="empty">Impossible de lire data/carburant.json : ' + e + '</p></div>';
});
