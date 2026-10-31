/* v4.7.2 — Ахмад настанд зориулсан энгийн горим (ажилтны хуудас).
   Анхдагчаар асна. «Дэлгэрэнгүй» товчоор хуучин бүрэн хуудас руу буцна.
   «Том үсэг» товч бүх хуудасны үсгийг томруулна (localStorage-д хадгална). */
(function(){
  if (localStorage.getItem('att_big') === '1') document.body.classList.add('bigtext');
  const css = `
    body.bigtext{zoom:1.15}
    .elder-wrap{max-width:560px;margin:0 auto;padding:12px 14px 40px;font-size:19px;line-height:1.5}
    .elder-wrap .simple-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap}
    .elder-wrap .big-name{font-size:24px}
    .elder-wrap .simple-date{color:#475569;font-size:16px}
    .elder-wrap .simple-status{margin:14px 0 6px;padding:16px;border-radius:16px;font-size:23px;font-weight:800;text-align:center;background:#e2e8f0;color:#0f172a}
    .elder-wrap .simple-status.working{background:#dcfce7;color:#14532d}
    .elder-wrap .simple-status.done{background:#dbeafe;color:#1e3a8a}
    .elder-wrap .simple-note{margin:8px 0;padding:12px;border-radius:12px;font-size:19px;font-weight:700}
    .elder-wrap .simple-note.warn{background:#fef3c7;color:#78350f}
    .elder-wrap .simple-times{text-align:center;color:#334155;margin:6px 0 14px}
    .elder-wrap .simple-clock{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .elder-wrap .simple-big{min-height:150px;border:none;border-radius:20px;font-size:24px;font-weight:900;color:#fff;cursor:pointer;line-height:1.3}
    .elder-wrap .simple-big .emo{font-size:44px;display:block}
    .elder-wrap .simple-big.in{background:#15803d}
    .elder-wrap .simple-big.out{background:#b91c1c}
    .elder-wrap .simple-big:disabled{background:#cbd5e1;color:#475569;cursor:not-allowed}
    .elder-wrap .simple-help{margin:12px 0 16px;font-size:17px;color:#334155;text-align:center}
    .elder-wrap .simple-tiles{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .elder-wrap .simple-tile{min-height:120px;border:2px solid #cbd5e1;background:#fff;border-radius:18px;font-size:20px;font-weight:800;color:#0f172a;cursor:pointer}
    .elder-wrap .simple-tile .emo{font-size:38px;display:block}
    .elder-wrap .simple-foot{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:18px}
    .elder-wrap .simple-foot .btn{min-height:52px;font-size:17px}
    .elder-wrap .btn,.elder-wrap button{min-height:52px}
    .simple-check{display:flex;justify-content:space-between;gap:10px;padding:12px 0;border-bottom:1px solid #e2e8f0;font-size:19px}
    .simple-check b{white-space:nowrap}
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
})();

function simpleEmployeeView(){
  const d = S.emp;
  const emp = (S.me && S.me.employee) || {full_name:'', code:''};
  if(!d) return `<div class="elder-wrap"><div class="card">Уншиж байна…</div></div>`;
  const st = d.status_code;
  const canIn = st === 'not_checked_in', canOut = st === 'working';
  const late = d.record ? (d.record.late_minutes || 0) : 0;
  const text = {not_checked_in:'Та ажилд ороогүй байна', working:'Та ажил дээрээ байна', done:'Өнөөдрийн ажил дууссан'}[st] || d.status_label || '';
  return `<div class="elder-wrap">
    <div class="simple-top">
      <div><div class="big-name"><b>${esc(emp.full_name)}</b></div><div class="small">Ажилтны код: ${esc(emp.code)}</div></div>
      <div class="simple-date">${esc(d.weekday_mn||'')}, ${esc(d.date||'')}</div>
    </div>
    <div class="simple-status ${st==='working'?'working':(st==='done'?'done':'')}">${esc(text)}</div>
    ${late ? `<div class="simple-note warn">⚠ Өнөөдөр ${late} минут хоцорсон. Маргааш цагтаа ирээрэй.</div>` : ''}
    <div class="simple-times">Ажлын цаг: <b>${esc(d.schedule.start)}</b> – <b>${esc(d.schedule.end)}</b></div>
    <div class="simple-clock">
      <button class="simple-big in" id="btnIn" ${canIn?'':'disabled'}><span class="emo">🟢</span>АЖИЛД<br>ОРОХ</button>
      <button class="simple-big out" id="btnOut" ${canOut?'':'disabled'}><span class="emo">🔴</span>АЖЛААС<br>ГАРАХ</button>
    </div>
    <div class="simple-help">Бүртгэл бүрт <b>зураг авна</b>. Утасныхаа камер ба байршлын зөвшөөрлийг нээлттэй байлгаарай.</div>
    ${simpleSiteCard(d)}
    <div class="simple-tiles">
      <button class="simple-tile" onclick="simpleMoney()"><span class="emo">💰</span>Миний цалин</button>
      <button class="simple-tile" onclick="simpleBonus()"><span class="emo">🎁</span>Миний бонус</button>
      <button class="simple-tile" data-act="req-leave"><span class="emo">🏖</span>Чөлөө хүсэх</button>
      <button class="simple-tile" data-act="notif"><span class="emo">🔔</span>Мэдэгдэл</button>
    </div>
    <div class="simple-foot">
      <button class="btn" onclick="simpleBigText()">🔠 Том үсэг</button>
      <button class="btn" onclick="simpleClassic(true)">📋 Дэлгэрэнгүй</button>
      <button class="btn" data-act="logout">Гарах</button>
    </div>
  </div>`;
}

function simpleBigText(){
  const on = !document.body.classList.contains('bigtext');
  document.body.classList.toggle('bigtext', on);
  localStorage.setItem('att_big', on ? '1' : '0');
  toast(on ? 'Үсэг томорлоо.' : 'Үсэг энгийн болоо.', 'info');
}

function simpleClassic(on){
  S.classic = !!on;
  localStorage.setItem('att_classic', on ? '1' : '0');
  render();
}

function simpleMoney(){
  const o = modal(`<h3>💰 Миний цалин</h3>
    <div class="elder-wrap" style="padding:0;max-width:none">${typeof myPayHTML==='function'?myPayHTML():''}</div>
    <div id="minuteBox" style="margin-top:12px"><div class="small">Минутын тооцоо ачаалж байна…</div></div>
    <div class="actions"><button class="btn primary" onclick="closeModal()">Хаах</button></div>`);
  loadMinuteImpact();
  return o;
}
/* v4.7.4: минут бүрийн цалингийн нөлөө (хоцрол, эрт явалт, ирээгүй) */
async function loadMinuteImpact(){
  const box = document.getElementById('minuteBox'); if(!box) return;
  try{
    const m = await api('/api/employee/minute-impact?month='+todayISO().slice(0,7));
    box.innerHTML = minuteImpactHTML(m);
  }catch(e){ box.innerHTML = `<div class="small">${esc(e.message)}</div>`; }
}
function minuteImpactHTML(m){
  const f = v => Number(v||0).toLocaleString();
  const t = m.totals || {};
  const rows = (m.days||[]).map(d => `<tr>
      <td>${esc(d.date.slice(5))}</td><td>${esc(d.kind)}${d.shift==='night'?' (шөнө)':''}</td>
      <td style="text-align:right">${d.late_minutes||''}</td><td style="text-align:right">${d.early_minutes||''}</td>
      <td style="text-align:right">${d.other_minutes||''}</td>
      <td style="text-align:right"><b>${d.cut_minutes}</b></td><td style="text-align:right;color:#b91c1c"><b>−${f(d.cut_amount)}₮</b></td></tr>`).join('');
  return `<div class="simple-site" style="border-color:#2563eb">
    <div style="font-size:17px;font-weight:800;margin-bottom:6px">⏱ Минут бүр цалинд хэрхэн нөлөөлөх вэ</div>
    <div class="simple-note" style="background:#eff6ff;border-color:#2563eb">
      Өдрийн ээлж: <b>1 минут = ${f(m.per_minute_day)}₮</b> · Шөнийн ээлж: <b>1 минут = ${f(m.per_minute_night)}₮</b><br>
      Хоцрох <b>10 минут</b> → <b style="color:#b91c1c">−${f(Math.round(10*m.late_minute_cost))}₮</b><br>
      Эрт гарах <b>30 минут</b> → <b style="color:#b91c1c">−${f(Math.round(30*m.late_minute_cost))}₮</b><br>
      Бүтэн өдөр ирээгүй → <b style="color:#b91c1c">−${f(m.absent_day_cost)}₮</b>
    </div>
    <div class="small" style="margin:8px 0 4px">Энэ сарын хасалт (өдөр бүрээр):</div>
    ${rows ? `<div style="overflow-x:auto"><table style="width:100%;font-size:14px;border-collapse:collapse">
      <thead><tr style="background:#f1f5f9"><th style="text-align:left">Өдөр</th><th style="text-align:left">Төрөл</th>
      <th>Хоцор</th><th>Эрт</th><th>Бусад</th><th>Мин</th><th style="text-align:right">₮</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr style="border-top:2px solid #334155"><td colspan="5"><b>Нийт</b></td><td style="text-align:right"><b>${t.cut_minutes||0}</b></td>
      <td style="text-align:right;color:#b91c1c"><b>−${f(t.cut_amount)}₮</b></td></tr></tfoot></table></div>`
      : `<div class="small">Энэ сард хоцролт, эрт явалт, ирээгүй өдөр алга. 👍</div>`}
    <div class="small" style="margin-top:8px">${esc(m.note||'')}</div>
    <div class="small">Хоцор = хоцорсон минут · Эрт = эрт гарсан минут · Бусад = бүртгэлгүй эсвэл ирээгүй минут.</div>
  </div>`;
}

async function simpleBonus(){
  const month = todayISO().slice(0,7);
  let b;
  try{ b = await api('/api/employee/bonus?month='+month); }
  catch(e){ return toast(e.message,'err'); }
  const amt = Number(b.bonus||0).toLocaleString();
  const head = b.eligible
    ? `<div class="simple-status working">Бонус авна: ${amt}₮</div>`
    : `<div class="simple-status">Энэ сар бонус авахгүй байна</div>`;
  modal(`<h3>🎁 Миний бонус — ${esc(monthLabel(month))}</h3>
    ${head}
    <div class="simple-times">Ажилласан өдөр: <b>${b.worked_days}</b> · Бонус өдөрт: <b>${Number(b.bonus_per_day).toLocaleString()}₮</b></div>
    <div style="margin:10px 0">${b.checks.map(c=>`<div class="simple-check"><span>${esc(c.label)}</span><b style="color:${c.ok?'#15803d':'#b91c1c'}">${c.ok?'✔ Зөв':'✖ Алдсан'}</b></div>`).join('')}</div>
    <div class="small">Сард бүх зүйл зөв байвал ажилласан өдөр бүрд бонус авна.</div>
    <div class="actions"><button class="btn primary" onclick="closeModal()">Хаах</button></div>`);
}

/* ---------- v4.7.3: Админ — энгийн горим (ахмад хүнд зориулсан нүүр хуудас) ---------- */
(function(){
  const css = `
    .simple-admin{max-width:720px;margin:0 auto;padding:12px 14px 40px;font-size:18px;line-height:1.5}
    .simple-admin h2{font-size:24px}
    .simple-admin .tiles{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}
    .simple-admin .tile{min-height:120px;border:2px solid #cbd5e1;background:#fff;border-radius:18px;font-size:19px;font-weight:800;color:#0f172a;cursor:pointer;padding:10px}
    .simple-admin .tile .emo{font-size:36px;display:block}
    .simple-admin .tile.red{border-color:#fca5a5;background:#fef2f2}
    .simple-admin .tile.green{border-color:#86efac;background:#f0fdf4}
    .simple-admin .tile.blue{border-color:#93c5fd;background:#eff6ff}
    .simple-admin .foot{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:16px}
    .simple-admin .btn{min-height:52px;font-size:17px}
    .simple-admin .hint{color:#475569;font-size:16px;margin-top:6px}
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  if (localStorage.getItem('att_admin_classic') === '1') S.adminClassic = true;
})();

function simpleAdminView(){
  const sec = S.security && !S.security.ok ? securityBanner() : '';
  if (S.simpleTab) {
    return `<div class="simple-admin">
      <div class="no-print" style="margin-bottom:8px"><button class="btn" onclick="simpleAdminHome()">⬅ Эхлэл рүү буцах</button></div>
      <div id="tabBody">${adminTabBody()}</div>
    </div>`;
  }
  const tile = (tab, emo, label, cls='', hint='') =>
    `<button class="tile ${cls}" onclick="simpleAdminOpen('${tab}')"><span class="emo">${emo}</span>${label}${hint?`<div class="hint">${hint}</div>`:''}</button>`;
  return `<div class="simple-admin">
    ${sec}
    <h2 style="margin:6px 0 0">Сайн байна уу, Админ</h2>
    <div class="hint">Юу хийх вэ? Доорх товчийг дарна уу.</div>
    <div class="tiles">
      ${tile('board','📋','Өнөөдөр<br>хэн ажиллаж байгаа',"blue",'Ирсэн, ирээгүй')}
      ${tile('ops','🌧','Ажил цуцлах',"red",'Цас, салхи, бороо')}
      ${tile('ops','📍','Өөр байршилд<br>оноох',"",'Өдрөөр')}
      ${tile('leave','🏖','Чөлөөний<br>хүсэлт',"green",'Батлах / татгалзах')}
      ${tile('pay','💰','Цалин',"",'Сараар')}
      ${tile('ops','🎁','Бонус ба<br>зөрчил',"",'Сар бүр')}
      ${tile('emp','👷','Ажилтнууд',"",'Нэмэх, PIN солих')}
      ${tile('cfg','⚙️','Тохиргоо',"",'Нууц үг, нөөц хуулбар')}
    </div>
    <div class="foot">
      <button class="btn" data-act="notif">🔔 Мэдэгдэл</button>
      <button class="btn" onclick="simpleAdminClassic(true)">📋 Бүх хуудас (дэлгэрэнгүй)</button>
      <button class="btn" data-act="logout">Гарах</button>
    </div>
  </div>`;
}

function simpleAdminOpen(tab){
  S.tab = tab; S.simpleTab = tab; render(); loadTabData();
  window.scrollTo(0, 0);
}
function simpleAdminHome(){ S.simpleTab = null; render(); window.scrollTo(0, 0); }
function simpleAdminClassic(on){
  S.adminClassic = !!on; S.simpleTab = null;
  localStorage.setItem('att_admin_classic', on ? '1' : '0');
  render();
}

/* ===== v4.7.4: ажлын байрны хүрээ + миний байрлал (зургаар) ===== */
function geoDistM(a, b){                       // хоёр цэгийн зай (м) — сервертэй ижил томьёо (haversine)
  const R = 6371000, t = x => x * Math.PI / 180;
  const dLat = t(b.lat - a.lat), dLng = t(b.lng - a.lng);
  const h = Math.sin(dLat/2)**2 + Math.cos(t(a.lat)) * Math.cos(t(b.lat)) * Math.sin(dLng/2)**2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
function siteHasCoords(g){ return !!g && g.lat!=null && g.lng!=null && g.mode!=='off' && g.source!=='off'; }
/* Схем зураг: ногоон тойрог = ажлын байрны хүрээ, цэг = таны байрлал (хойд = дээш) */
function siteMapSVG(g, me){
  const W = 300, c = 150, r = Number(g.radius_m) || 300;
  let dist = null, px = null, py = null;
  if (me) {
    dist = geoDistM({lat:g.lat, lng:g.lng}, me);
    const dy = (me.lat - g.lat) * 110574, dx = (me.lng - g.lng) * 111320 * Math.cos(g.lat * Math.PI/180);
    const ext = Math.max(r * 1.5, dist * 1.25, 40), k = (c - 30) / ext;
    px = c + dx * k; py = c - dy * k;
    var kk = k;
  } else { var kk = (c - 30) / Math.max(r * 1.5, 40); }
  const inside = dist !== null && dist <= r;
  const col = dist === null ? '#2563eb' : (inside ? '#16a34a' : '#dc2626');
  return `<svg viewBox="0 0 ${W} ${W}" width="100%" style="max-width:300px;display:block;margin:6px auto;background:#f8fafc;border:1px solid #cbd5e1;border-radius:14px">
    <circle cx="${c}" cy="${c}" r="${r*kk}" fill="rgba(22,163,74,.13)" stroke="#16a34a" stroke-width="2" stroke-dasharray="6 4"/>
    <text x="${c}" y="${c + r*kk + 16}" text-anchor="middle" font-size="13" fill="#166534" font-weight="700">хүрээ ${Math.round(r)} м (ногоон тойрог)</text>
    ${me ? `<line x1="${c}" y1="${c}" x2="${px}" y2="${py}" stroke="${col}" stroke-width="2" stroke-dasharray="4 3"/>` : ''}
    <circle cx="${c}" cy="${c}" r="9" fill="#1d4ed8" stroke="#fff" stroke-width="2"/>
    <text x="${c}" y="${c+26}" text-anchor="middle" font-size="12" fill="#1e3a8a" font-weight="700">Ажлын байр</text>
    ${me ? `<circle cx="${px}" cy="${py}" r="10" fill="${col}" stroke="#fff" stroke-width="2"/>
            <text x="${px+14}" y="${py+5}" font-size="14" font-weight="800" fill="${col}">Та</text>` : ''}
    <text x="${W/2}" y="${W-8}" text-anchor="middle" font-size="11" fill="#64748b">⬆ Хойд</text></svg>`;
}
function siteStatusHTML(g, dist){
  const r = Math.round(Number(g.radius_m) || 300);
  if (dist === null) return '';
  const d = Math.round(dist);
  if (d <= r) return `<div class="simple-note" style="background:#ecfdf5;border-color:#16a34a">✅ Та ажлын байрны хүрээнд байна.<br><b>Зай ${d} м</b> · хүрээ ${r} м. Зураг авч бүртгэл хийж болно.</div>`;
  return `<div class="simple-note" style="background:#fef2f2;border-color:#dc2626">❌ Та ажлын байрны хүрээнээс гадна байна.<br><b>Зай ${d} м</b> · хүрээ ${r} м → таны байрлал <b>${d - r} м</b> гадна.<br>Бүртгэл хийгдэхгүй. Хүрээн дотор ойртоод дахин оролдоно уу.</div>`;
}
/* ---- Газрын зураг (Leaflet + OpenStreetMap), амьд байршил ---- */
const LEAFLET_CFG = {
  css: 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', cssSri: 'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H',
  js: 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', jsSri: 'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH'
};
let _leafletP = null;
function loadLeaflet(){
  if (window.L) return Promise.resolve(window.L);
  if (_leafletP) return _leafletP;
  _leafletP = new Promise((res, rej) => {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = LEAFLET_CFG.css;
    l.integrity = LEAFLET_CFG.cssSri; l.crossOrigin = '';
    document.head.appendChild(l);
    const s = document.createElement('script'); s.src = LEAFLET_CFG.js;
    s.integrity = LEAFLET_CFG.jsSri; s.crossOrigin = '';
    s.onload = () => res(window.L);
    s.onerror = () => { _leafletP = null; rej(new Error('Газрын зураг ачаалагдсангүй. Интернэт холболтоо шалгана уу.')); };
    document.head.appendChild(s);
  });
  return _leafletP;
}
function gmapsLink(g){
  return `https://www.google.com/maps/dir/?api=1&destination=${g.lat},${g.lng}&travelmode=driving`;
}
/* Газрын зураг үүсгэж, ажлын байр + (сонголтоор) амьд байршлыг харуулна.
   Буцаах: { update, stop } — watch-ийг зогсооно. */
async function mountLiveMap(box, g, onStatus, live){
  const L = await loadLeaflet();
  if (!document.body.contains(box)) return null;
  box.innerHTML = '<div class="livemap" style="height:300px;border-radius:14px;overflow:hidden;border:1px solid #cbd5e1"></div>';
  const map = L.map(box.firstChild, { zoomControl: true, attributionControl: true });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(map);
  const r = Number(g.radius_m) || 300;
  const site = [g.lat, g.lng];
  const circle = L.circle(site, { radius: r, color: '#16a34a', fillColor: '#16a34a', fillOpacity: .15, weight: 2 }).addTo(map);
  L.circleMarker(site, { radius: 9, color: '#fff', weight: 3, fillColor: '#1d4ed8', fillOpacity: 1 })
    .bindPopup('<b>Ажлын байр</b><br>' + (g.name || '')).addTo(map);
  // Харах хэсэг: ажлын байрны хүрээг бүтэн харуулна (радиусаас тооцно)
  const span = r * 1.6, dLat = span / 110574, dLng = span / (111320 * Math.cos(g.lat * Math.PI / 180));
  map.fitBounds([[g.lat - dLat, g.lng - dLng], [g.lat + dLat, g.lng + dLng]], { padding: [16, 16] });
  let meMarker = null, meAcc = null, watchId = null;
  const stop = () => { if (watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(watchId); watchId = null; };
  const update = pos => {
    if (!document.body.contains(box)) { stop(); return; }
    const ll = [pos.coords.latitude, pos.coords.longitude];
    const acc = pos.coords.accuracy || 10;
    const dist = geoDistM({lat: g.lat, lng: g.lng}, {lat: ll[0], lng: ll[1]});
    const colour = dist <= r ? '#16a34a' : '#dc2626';
    if (!meMarker) {
      meMarker = L.circleMarker(ll, { radius: 10, color: '#fff', weight: 3, fillColor: colour, fillOpacity: 1 })
        .bindPopup('<b>Таны байрлал</b>').addTo(map);
      meAcc = L.circle(ll, { radius: acc, color: colour, weight: 1, fillOpacity: .08 }).addTo(map);
    } else {
      meMarker.setLatLng(ll); meMarker.setStyle({ fillColor: colour, color: '#fff' });
      meAcc.setLatLng(ll); meAcc.setRadius(acc); meAcc.setStyle({ color: colour });
    }
    if (onStatus) onStatus(dist, acc);
  };
  if (live && navigator.geolocation) {
    watchId = navigator.geolocation.watchPosition(update,
      e => { if (onStatus) onStatus(null, null, e.code === 1
        ? 'Байршлын зөвшөөрөл өгөгдөөгүй байна. Утасны тохиргооноос байршлыг зөвшөөрнө үү.'
        : 'Байршил тодорхойлогдохгүй байна. GPS-ээ асаана уу.'); },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
  }
  setTimeout(() => map.invalidateSize(), 150);
  return { map, update, stop };
}
function siteStatusFromDist(g, dist, acc){
  if (dist === null || dist === undefined) return '';
  return siteStatusHTML(g, dist) + `<div class="small" style="text-align:center">GPS нарийвчлал ±${Math.round(acc||0)} м · амьд шинэчлэгдэж байна</div>
    <a class="btn small" style="display:block;text-align:center;margin-top:8px" href="${gmapsLink(g)}" target="_blank" rel="noopener">🗺 Google Maps-д нээх (чиглэл)</a>`;
}
let _siteLive = null;   // одоогийн харагдаж буй амьд зургийн watch
function stopSiteLive(){ if (_siteLive) { try { _siteLive.stop(); } catch(e){} _siteLive = null; } }

function simpleSiteCard(d){
  const g = d.geo || {};
  const name = (d.site && d.site.name) || g.name || '—';
  if (!siteHasCoords(g)) {
    return `<div class="simple-site"><div class="small"><b>📍 Өнөөдрийн ажлын байр</b></div>
      <div>${esc(name)}</div><div class="small">Хаалтгүй (байршлын хяналтгүй)</div></div>`;
  }
  g.name = name;
  setTimeout(startSiteLive, 0);          // DOM бэлэн болсны дараа эхлүүлнэ
  return `<div class="simple-site">
    <div class="small"><b>📍 Өнөөдрийн ажлын байр</b></div>
    <div style="font-size:18px;font-weight:700">${esc(name)}</div>
    <div class="small">Зөвшөөрөгдөх хүрээ: <b>${Math.round(g.radius_m)} м</b> · Газрын зураг дээр та болон ажлын байр харагдана</div>
    <div id="siteMapBox" style="margin-top:6px"><div class="small" style="text-align:center;padding:30px 0">Газрын зураг ачаалж байна…</div></div>
    <div id="siteStatus"><div class="small" style="text-align:center">Таны байрлал тодорхойлж байна…</div></div>
  </div>`;
}
async function startSiteLive(){
  const box = document.getElementById('siteMapBox'), st = document.getElementById('siteStatus');
  const g = (S.emp && S.emp.geo) || {};
  if (!box || !siteHasCoords(g)) return;
  stopSiteLive();
  try{
    _siteLive = await mountLiveMap(box, g, (dist, acc, err) => {
      if (!st) return;
      if (err) { st.innerHTML = `<div class="simple-note warn">${esc(err)}</div>`; return; }
      st.innerHTML = siteStatusFromDist(g, dist, acc);
    }, true);
  }catch(e){
    // Газрын зураг ачаалагдахгүй бол зурсан схем
    if (box) box.innerHTML = siteMapSVG(g, null);
    if (st) st.innerHTML = `<div class="simple-note warn">${esc(e.message)}</div>`;
  }
}
/* Зураг авахын өмнө: газрын зураг + зай → үргэлжлүүлэх эсэхийг сонгоно. Хүрээнээс гадна бол зураг авахгүй. */
function geoPrePhoto(pos){
  const g = (S.emp && S.emp.geo) || {};
  if (!siteHasCoords(g) || !pos || pos.demo || pos.latitude==null) return Promise.resolve(true);
  const me = {lat: pos.latitude, lng: pos.longitude};
  const dist = geoDistM({lat:g.lat, lng:g.lng}, me);
  const inside = dist <= Number(g.radius_m || 300);
  return new Promise(resolve => {
    const o = modal(`<h3>📍 Байрлал шалгах</h3>
      <div id="preMapBox"><div class="small" style="text-align:center;padding:30px 0">Газрын зураг ачаалж байна…</div></div>
      <div id="preStatus">${siteStatusHTML(g, dist)}</div>
      <div class="actions">
        <button class="btn" id="gpNo">Болих</button>
        <button class="btn primary" id="gpYes" ${inside?'':'disabled'}>📷 Зураг авах</button>
      </div>`);
    let done = false, live = null;
    const finish = v => { if (done) return; done = true; clearInterval(timer); if (live) live.stop(); resolve(v); };
    const timer = setInterval(() => { if (!document.body.contains(o)) finish(false); }, 300);
    o.querySelector('#gpNo').onclick = () => { closeModal(); finish(false); };
    if (inside) o.querySelector('#gpYes').onclick = () => { closeModal(); finish(true); };
    const box = o.querySelector('#preMapBox');
    const onStatus = (dd) => {
      if (dd === null || dd === undefined) return;
      const st = o.querySelector('#preStatus');
      if (st) st.innerHTML = siteStatusHTML(g, dd);
      const yes = o.querySelector('#gpYes');
      if (yes) yes.disabled = dd > Number(g.radius_m || 300);
    };
    loadLeaflet().then(async () => {
      live = await mountLiveMap(box, g, onStatus, true);
      if (live) live.update({coords:{latitude: me.lat, longitude: me.lng, accuracy: pos.accuracy || 10}});
    }).catch(() => { if (box) box.innerHTML = siteMapSVG(g, me); });
  });
}
