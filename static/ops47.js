/* v4.7 — Админ: ажлын цуцлалт · өдрийн байршил оноолт · бонус & зөрчил.
   index.html-ийн S, api(), render(), modal(), closeModal(), esc(), todayISO(), curMonth(), toast() ашиглана. */
const OPS_KIND_LABEL = {alcohol:'Архи / согтуу', equipment:'Хэрэгсэл эвдсэн', material:'Материал үрсэн'};

function opsTab(){
  const O = S.ops || {};
  const d = O.date || todayISO();
  const m = O.month || curMonth();
  const sites = S.sites || [];
  const emps = S.employees || O.emps || [];
  const cancels = O.cancels || [];
  const roster = O.roster || {groups:{}};
  const bonus = O.bonus || {rows:[], total:0, eligible_count:0};
  const siteOpts = sites.filter(s=>s.active!==0).map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');
  const groups = Object.entries(roster.groups||{});
  const cancelOnDay = (roster.cancellations||[]);

  return `
  <div class="card" style="margin-bottom:14px;border-left:4px solid #dc2626">
    <h2 style="margin:0 0 4px">Ажил цуцлах (цас, салхи, бороо)</h2>
    <div class="sub" style="margin:0 0 10px">Цуцлагдсан өдөр <b>цалин бодогдохгүй</b>, тасалт гэж тооцогдохгүй. Ажилтанд мэдэгдэл очно.</div>
    <div class="row" style="gap:8px;flex-wrap:wrap;align-items:flex-end">
      <label class="small">Огноо<br><input type="date" id="opsCDate" value="${esc(d)}" onchange="opsSetDate(this.value)"></label>
      <label class="small">Хамрах хүрээ<br>
        <select id="opsCScope" onchange="document.getElementById('opsCSite').disabled=this.value!=='site'">
          <option value="all">Бүх байршил</option><option value="site">Зөвхөн нэг байршил</option></select></label>
      <label class="small">Байршил<br><select id="opsCSite" disabled>${siteOpts}</select></label>
      <label class="small" style="flex:1;min-width:180px">Шалтгаан<br><input id="opsCReason" placeholder="Жнь: цас орсон, салхи"></label>
      <button class="btn primary" onclick="opsCancel()">Цуцлах</button>
    </div>
    <div class="small" style="margin-top:8px">${cancelOnDay.length?`<b>${esc(d)}</b> өдөр цуцлагдсан: `+cancelOnDay.map(c=>`<span class="pill red">${esc(c.site_name)}</span>`).join(' '):`<b>${esc(d)}</b> өдөр цуцлагдаагүй.`}</div>
    ${cancels.length?`<div class="tbl-scroll" style="margin-top:10px"><table>
      <thead><tr><th>Огноо</th><th>Хүрээ</th><th>Шалтгаан</th><th class="cn">Нөлөөлсөн</th><th class="no-print">Үйлдэл</th></tr></thead>
      <tbody>${cancels.map(c=>`<tr><td>${esc(c.work_date)}</td><td>${esc(c.scope_label)}</td><td>${esc(c.reason||'—')}</td>
        <td class="cn">${c.active?c.affected+' ажилтан':'<span class="pill gray">Сэргээсэн</span>'}</td>
        <td class="no-print">${c.active?`<button class="btn small" onclick="opsUndo(${c.id})">Сэргээх</button>`:''}</td></tr>`).join('')}</tbody></table></div>`:''}
  </div>

  <div class="card" style="margin-bottom:14px;border-left:4px solid #2563eb">
    <h2 style="margin:0 0 4px">Өдрийн байршил оноох (өөр талбайд ажиллуулах)</h2>
    <div class="sub" style="margin:0 0 10px">Ажилтны үндсэн байршлаас гадна тухайн өдөрт өөр талбайд оноож болно. Ажилтан тэр талбарт гео хаалтаар бүртгүүлнэ.</div>
    <div class="row" style="gap:8px;flex-wrap:wrap;align-items:flex-end">
      <label class="small">Байршил<br><select id="opsASite">${siteOpts}</select></label>
      <button class="btn primary" onclick="opsAssign()">Сонгосон ажилтнуудыг оноох</button>
      <button class="btn" onclick="opsAllCheck(true)">Бүгдийг сонгох</button>
      <button class="btn" onclick="opsAllCheck(false)">Арилгах</button>
    </div>
    <div class="tbl-scroll" style="margin-top:10px;max-height:260px;overflow:auto"><table>
      <thead><tr><th style="width:36px"></th><th>Ажилтан</th><th>Үндсэн байршил</th><th>Энэ өдөр</th></tr></thead>
      <tbody>${(roster.rows||[]).map(r=>`<tr>
        <td><input type="checkbox" class="ops-emp" value="${r.employee_id}"></td>
        <td><b>${esc(r.full_name)}</b> <span class="small mono">${esc(r.code)}</span></td>
        <td>${esc(r.home_site_name||'—')}</td>
        <td>${r.cancelled?'<span class="pill red">Цуцлагдсан</span>':(r.assigned_today?`<span class="pill blue">${esc(r.site_name)} (оноосон)</span>`:`<span class="pill green">${esc(r.site_name)}</span>`)}
          ${r.assigned_today?`<button class="btn small" onclick="opsUnassign(${r.employee_id})">Буцаах</button>`:''}</td></tr>`).join('')
      }</tbody></table></div>
    <div class="small" style="margin-top:8px">${groups.map(([g,rows])=>`<b>${esc(g)}</b>: ${rows.length} хүн`).join(' · ')}</div>
  </div>

  <div class="card" style="margin-bottom:14px;border-left:4px solid #16a34a">
    <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:10px">
      <div><h2 style="margin:0">Бонус (${bonus.per_day?bonus.per_day.toLocaleString():'10,000'}₮ / ажилласан өдөр)</h2>
        <div class="sub" style="margin:2px 0 0">Сард бүх нөхцөл биелсэн ажилтан л бонус авна: 2+ чөлөөгүй · хоцролт+тасалт &lt;120 мин · архи/хэрэгсэл/материалын зөрчилгүй.</div></div>
      <div class="row no-print" style="gap:8px">
        <input type="month" id="opsBMonth" value="${esc(m)}" onchange="opsSetMonth(this.value)">
        <button class="btn" onclick="opsIncidentModal()">+ Зөрчил бүртгэх</button>
      </div>
    </div>
    <div class="tbl-scroll" style="margin-top:10px"><table>
      <thead><tr><th>Ажилтан</th><th class="cn">Ажилласан өдөр</th><th>Нөхцөл</th><th class="cn">Бонус</th></tr></thead>
      <tbody>${(bonus.rows||[]).map(b=>`<tr>
        <td><b>${esc(b.full_name||'')}</b><div class="small mono">${esc(b.code||'')}</div></td>
        <td class="cn">${b.worked_days}</td>
        <td>${b.checks.map(c=>`<span class="pill ${c.ok?'green':'red'}" title="${esc(c.value)}">${esc(c.label)}</span>`).join(' ')}
          ${b.incidents.length?`<div class="small">${b.incidents.map(i=>`${esc(i.kind_label)} <a href="#" onclick="opsIncDel(${i.id});return false">[x]</a>`).join(', ')}</div>`:''}</td>
        <td class="cn"><b class="${b.eligible?'':'mono'}" style="color:${b.eligible?'#15803d':'#b91c1c'}">${b.eligible?Number(b.bonus).toLocaleString()+'₮':'0₮ (алдсан)'}</b></td></tr>`).join('')}
      </tbody></table></div>
    <div class="small" style="margin-top:8px">Нийт бонус: <b>${Number(bonus.total||0).toLocaleString()}₮</b> · Бонус авах ажилтан: ${bonus.eligible_count||0}</div>
  </div>`;
}

async function loadOps(){
  S.ops = S.ops || {};
  const O = S.ops;
  O.date = O.date || todayISO();
  O.month = O.month || curMonth();
  const [emps, sites, canc, roster, bonus] = await Promise.all([
    api('/api/admin/employees'), api('/api/admin/sites'),
    api('/api/admin/cancellations?month='+O.month), api('/api/admin/roster?date='+O.date),
    api('/api/admin/bonus?month='+O.month)]);
  S.employees = emps.employees; S.sites = sites.sites;
  O.cancels = canc.cancellations; O.roster = roster; O.bonus = bonus; O.emps = emps.employees;
  // Үндсэн байршлын нэрийг оноолтын хүснэгтэд
  const sn = Object.fromEntries((sites.sites||[]).map(s=>[s.id, s.name]));
  roster.rows.forEach(r=>{ r.home_site_name = sn[(emps.employees.find(e=>e.id===r.employee_id)||{}).site_id] || '—'; });
}

function opsSetDate(v){ S.ops = S.ops||{}; S.ops.date = v; loadOps().then(render); }
function opsSetMonth(v){ S.ops = S.ops||{}; S.ops.month = v; loadOps().then(render); }

async function opsCancel(){
  const date = document.getElementById('opsCDate').value;
  const scope = document.getElementById('opsCScope').value;
  const site_id = scope==='site' ? Number(document.getElementById('opsCSite').value) : null;
  const reason = document.getElementById('opsCReason').value.trim();
  if(!date) return toast('Огноо сонгоно уу.','warn');
  if(scope==='site' && !site_id) return toast('Байршил сонгоно уу.','warn');
  const what = scope==='all' ? 'БҮХ байршлын' : 'сонгосон байршлын';
  if(!(await confirmModal('Ажил цуцлах уу?', `${date} өдрийн ${what} ажлыг цуцлах уу?\nЦуцлагдсан өдөр цалин бодогдохгүй. Ажилтнуудад мэдэгдэл очно.`, 'Цуцлах', 'Болих'))) return;
  try{
    const r = await api('/api/admin/cancellations', {method:'POST', body:{date, scope, site_id, reason}});
    toast(`Цуцлагдлаа — ${r.affected} ажилтанд мэдэгдэл илгээв.`, 'ok');
    S.ops.date = date; await loadOps(); render();
  }catch(e){ toast(e.message,'err'); }
}

async function opsUndo(id){
  if(!(await confirmModal('Ажлыг сэргээх үү?', 'Энэ цуцлалтыг буцаах уу? Ажилтнуудад "ажил сэргээгдлээ" гэж мэдэгдэнэ.', 'Сэргээх', 'Болих'))) return;
  try{ await api('/api/admin/cancellations/'+id+'/undo', {method:'POST', body:{}}); toast('Сэргээгдлээ.','ok'); await loadOps(); render(); }
  catch(e){ toast(e.message,'err'); }
}

async function opsAssign(){
  const ids = [...document.querySelectorAll('.ops-emp:checked')].map(x=>Number(x.value));
  const site_id = Number(document.getElementById('opsASite').value);
  if(!ids.length) return toast('Ажилтан сонгоно уу.','warn');
  try{
    const r = await api('/api/admin/assignments', {method:'POST', body:{date:S.ops.date, employee_ids:ids, site_id}});
    toast(`${r.assigned} ажилтан оноогдлоо.`,'ok'); await loadOps(); render();
  }catch(e){ toast(e.message,'err'); }
}

async function opsUnassign(eid){
  try{ await api('/api/admin/assignments/clear', {method:'POST', body:{date:S.ops.date, employee_id:eid}}); await loadOps(); render(); }
  catch(e){ toast(e.message,'err'); }
}

function opsAllCheck(on){ document.querySelectorAll('.ops-emp').forEach(x=>x.checked=on); }

function opsIncidentModal(){
  const emps = S.employees||[];
  const o = modal(`<h3>Зөрчил бүртгэх</h3>
    <div class="sub" style="margin-bottom:8px">Зөвхөн админд харагдана. Ажилтанд бонус алдагдсан шалтгааныг тайлбарлахад ашиглана.</div>
    <label class="small">Ажилтан<br><select id="ocEmp" style="width:100%">${emps.map(e=>`<option value="${e.id}">${esc(e.code)} — ${esc(e.full_name)}</option>`).join('')}</select></label>
    <label class="small">Зөрчлийн төрөл<br><select id="ocKind" style="width:100%">${Object.entries(OPS_KIND_LABEL).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('')}</select></label>
    <label class="small">Сар<br><input type="month" id="ocMonth" value="${esc(S.ops.month)}"></label>
    <label class="small">Тайлбар<br><input id="ocNote" style="width:100%" placeholder="Жнь: 3-р талбарт тоног төхөөрөмж эвдсэн"></label>
    <div class="actions"><button class="btn" id="ocNo">Болих</button><button class="btn primary" id="ocYes">Хадгалах</button></div>`);
  o.querySelector('#ocNo').onclick = closeModal;
  o.querySelector('#ocYes').onclick = async ()=>{
    try{
      await api('/api/admin/incidents', {method:'POST', body:{employee_id:Number(o.querySelector('#ocEmp').value),
        kind:o.querySelector('#ocKind').value, month:o.querySelector('#ocMonth').value, note:o.querySelector('#ocNote').value}});
      closeModal(); toast('Зөрчил бүртгэгдлээ. Бонус шинэчлэгдлээ.','ok'); await loadOps(); render();
    }catch(e){ toast(e.message,'err'); }
  };
}

async function opsIncDel(id){
  if(!(await confirmModal('Зөрчил устгах уу?', 'Энэ бүртгэлийг устгавал бонус дахин тооцоологдоно.', 'Устгах', 'Болих'))) return;
  try{ await api('/api/admin/incidents/'+id+'/delete', {method:'POST', body:{}}); await loadOps(); render(); }
  catch(e){ toast(e.message,'err'); }
}
