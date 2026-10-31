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
    <div class="actions"><button class="btn primary" onclick="closeModal()">Хаах</button></div>`);
  return o;
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
