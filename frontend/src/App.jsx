import { useCallback, useEffect, useRef, useState } from 'react';

const labels = {awaiting_approval:'Menunggu persetujuan', scheduled:'Dipantau', paused:'Dijeda', running:'Sedang berjalan', completed:'Selesai', failed:'Gagal', cancelled:'Dibatalkan'};
const capabilities = {'business.list_orders':'Membaca pesanan simulasi','business.check_orders':'Memeriksa pesanan dan selisih','business.remind':'Membuat pengingat simulasi','device.read_temperature':'Membaca suhu simulasi','device.turn_on_light':'Menyalakan lampu simulasi','external.latest_event':'Membaca data terbaru dari sumber eksternal','external.escalate':'Membuat pemberitahuan untuk pemilik'};
const prompts = ['Periksa suhu sensor simulasi.', 'Periksa pesanan dan lihat apakah ada selisih jumlah.', 'Periksa pesanan yang belum dikemas.'];
const fields = {temperature_c:'suhu', unpacked_count:'jumlah pesanan yang belum dikemas', mismatch_count:'jumlah pesanan yang berbeda'};
const operators = {eq:'sama dengan', ne:'tidak sama dengan', gt:'lebih dari', gte:'setidaknya', lt:'kurang dari', lte:'paling banyak'};

const iconPaths = {
  plus: <path d="M12 5v14M5 12h14"/>,
  chat: <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22l5.9-2Z"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></>,
  plug: <path d="M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  dots: <path strokeWidth="2.6" d="M12 6h.01M12 12h.01M12 18h.01"/>,
  up: <path d="M12 19V5M5 12l7-7 7 7"/>,
  thermometer: <path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 1 1 4 0Z"/>,
  list: <path d="M8.5 6H20M8.5 12H20M8.5 18H20M4 6h.01M4 12h.01M4 18h.01"/>,
  sun: <><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M5 5l1.8 1.8M17.2 17.2 19 19M19 5l-1.8 1.8M6.8 17.2 5 19"/></>,
  moon: <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"/>
};
function Icon({name, size=20}) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name]}</svg>;
}

function Brand({className='brand'}) {
  return <div className={className}><div className="brand-icon">k.</div><span className="brand-name">kanca</span></div>;
}

function ChatTopics({chats, current, onSelect, onNew}) {
  return <select className="topic-select" aria-label="Pilih topik chat" value={current || ''} onChange={e => {
    if (e.target.value === 'new') onNew(); else onSelect(e.target.value);
  }}>
    {!current && <option value="">Pilih topik chat</option>}
    <option value="new">＋ Chat baru</option>
    {['active','draft'].map(status => {
      const group = chats.filter(chat => chat.status === status);
      return group.length > 0 && <optgroup key={status} label={status === 'draft' ? 'Draft' : 'Percakapan'}>
        {group.map(chat => <option key={chat.id} value={chat.id}>{chat.title}</option>)}
      </optgroup>;
    })}
  </select>;
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem('kanca-theme', next);
    const meta = document.getElementById('theme-color');
    if (meta) meta.content = next === 'dark' ? '#0c1410' : '#f1f4ef';
  }
  return [theme, toggleTheme];
}

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', ...options.headers}});
  let data;
  try { data = await response.json(); } catch { throw new Error('Respons server tidak dapat dibaca.'); }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.clarification || JSON.stringify(detail || 'Permintaan gagal'));
  }
  return data;
}

function TaskCard({ task, onAction, onRerun }) {
  return <div className="plan">
    <div className="plan-top"><strong>Rencana tugas</strong><span className={`status ${task.status}`}>{labels[task.status] || task.status}</span></div>
    <p>{task.plan.summary || 'Rencana untuk instruksi ini.'}</p>
    <ol>{(task.plan.steps || []).map((step, index) => <li key={index}>
      {capabilities[step.capability] || step.capability}
      {step.arguments?.message && <div className="details">Pesan: {step.arguments.message}</div>}
      {step.arguments?.source_id && <div className="details">Sumber: {step.arguments.source_id}</div>}
      {step.condition && <div className="details">Jika {fields[step.condition.field] || step.condition.field} {operators[step.condition.operator] || step.condition.operator} {String(step.condition.value)} berdasarkan langkah {step.condition.step + 1}.</div>}
    </li>)}</ol>
    {task.plan.schedule && <div className="meta">{task.plan.schedule.max_runs === 1 ? 'Dijalankan sekali' : `Setiap ${task.plan.schedule.interval_seconds} detik · maksimal ${task.plan.schedule.max_runs} pemeriksaan`}</div>}
    {task.result && <div className="result"><strong>{task.status === 'failed' ? 'Ada kendala' : 'Hasil pemeriksaan'}</strong>
      {task.result.error && <p>{task.result.error}</p>}
      {(task.result.steps || []).map((step, index) => <div key={index}><p>{capabilities[step.capability] || step.capability}: {step.status || 'selesai'}</p>
        {step.result && <details className="details"><summary>Lihat hasil</summary><pre>{JSON.stringify(step.result, null, 2)}</pre></details>}</div>)}
      {(task.result.limitations || []).map((limit, index) => <p className="meta" key={index}>{limit}</p>)}
    </div>}
    <div className="actions">{task.status === 'awaiting_approval' && <button className="primary" onClick={() => onAction(task, 'approve', {version: task.version})}>Setujui &amp; mulai</button>}
      {task.status === 'scheduled' && <button className="secondary" onClick={() => onAction(task, 'pause')}>Jeda</button>}
      {task.status === 'paused' && <button className="primary" onClick={() => onAction(task, 'resume')}>Lanjutkan</button>}
      {!task.archived && ['completed','failed','cancelled'].includes(task.status) && <button className="secondary" onClick={() => onRerun(task)}>Jalankan ulang</button>}
      {['awaiting_approval','scheduled','paused'].includes(task.status) && <button className="secondary" onClick={() => onAction(task, 'cancel')}>Batalkan</button>}</div>
  </div>;
}

function Workers({ tasks, onAction, onEdit, onArchive, onCreate, onRerun }) {
  const [editing, setEditing] = useState(null);
  const [interval, setInterval] = useState(60);
  const [runs, setRuns] = useState(1);
  return <div className="workers"><div className="workers-header"><div><div className="eyebrow">PEMANTAUAN</div><h1>Tugas latar belakang</h1><p>Pantau pekerjaan yang dibuat dari percakapanmu.</p></div><button className="primary" onClick={onCreate}>＋ Tugas baru</button></div>
    <div className="worker-summary"><strong>{tasks.filter(t => t.status === 'scheduled' || t.status === 'running').length}</strong><span>tugas aktif</span><span className="summary-divider"/><strong>{tasks.filter(t => t.status === 'awaiting_approval').length}</strong><span>menunggu persetujuan</span></div>
    {!tasks.length && <div className="worker-empty"><strong>Belum ada tugas</strong><p>Ceritakan apa yang ingin dipantau di percakapan. Rencana akan muncul di sini.</p><button className="secondary" onClick={onCreate}>Mulai percakapan</button></div>}
    <div className="worker-list">{tasks.map(task => <article className="worker-card" key={task.id}>
      <div className="plan-top"><div><strong>{task.instruction}</strong><p>{task.plan.summary}</p></div><span className={`status ${task.status}`}>{labels[task.status] || task.status}</span></div>
      <div className="worker-meta"><span>{task.plan.schedule?.max_runs === 1 ? 'Sekali' : `Setiap ${task.plan.schedule?.interval_seconds} detik`}</span><span>{task.result?.runs_completed || 0} / {task.plan.schedule?.max_runs || 1} pemeriksaan</span><span>Dibuat {new Date(task.created_at).toLocaleString('id-ID')}</span></div>
      {editing === task.id && <form className="schedule-form" onSubmit={async e => {e.preventDefault(); if(await onEdit(task, Number(interval), Number(runs))) setEditing(null);}}><label>Jeda pemeriksaan (detik)<input type="number" min="1" max="86400" required value={interval} onChange={e=>setInterval(e.target.value)}/></label><label>Maksimal pemeriksaan<input type="number" min="1" max="1000" required value={runs} onChange={e=>setRuns(e.target.value)}/></label><p>Perubahan membutuhkan persetujuan kembali sebelum tugas dilanjutkan.</p><div className="actions"><button className="primary">Simpan perubahan</button><button type="button" className="secondary" onClick={()=>setEditing(null)}>Batal</button></div></form>}
      {task.status==='failed' && task.result?.error && <p className="worker-failure">{task.result.error}</p>}<div className="actions">{task.status === 'awaiting_approval' && <button className="primary" onClick={()=>onAction(task,'approve',{version:task.version})}>Setujui &amp; mulai</button>}{task.status === 'scheduled' && <button className="secondary" onClick={()=>onAction(task,'pause')}>Jeda</button>}{task.status === 'paused' && <button className="primary" onClick={()=>onAction(task,'resume')}>Lanjutkan</button>}{['awaiting_approval','scheduled','paused'].includes(task.status) && <><button className="secondary" onClick={()=>{setEditing(task.id);setInterval(task.plan.schedule?.interval_seconds || 1);setRuns(task.plan.schedule?.max_runs || 1);}}>Ubah jadwal</button><button className="secondary" onClick={()=>onAction(task,'cancel')}>Hentikan</button></>}{['completed','failed','cancelled'].includes(task.status) && <button className="secondary" onClick={()=>onRerun(task)}>Jalankan ulang</button>}<button className="text-button" onClick={()=>onArchive(task)}>Hapus dari daftar</button></div>
    </article>)}</div>
  </div>;
}

const notificationLabels = {'task.approval_requested.v1':'Tugas menunggu persetujuan','task.completed.v1':'Tugas selesai','task.failed.v1':'Tugas gagal','task.escalated.v1':'Ada hal yang perlu perhatianmu','task.cancelled.v1':'Tugas dihentikan','task.paused.v1':'Tugas dijeda','task.resumed.v1':'Tugas dilanjutkan'};
function Notifications({ items, onRead, onReadAll, unreadCount, onRerun }) {
  return <div className="workers"><div className="workers-header"><div><div className="eyebrow">AKTIVITAS</div><h1>Notifikasi</h1><p>Pembaruan terbaru dari tugas latar belakangmu.</p></div>{unreadCount>0 && <button className="secondary" onClick={onReadAll}>Tandai semua dibaca</button>}</div>
    {!items.length && <div className="worker-empty"><strong>Belum ada notifikasi</strong><p>Pembaruan tugas akan muncul di sini.</p></div>}
    <div className="worker-list">{items.map(item=><article className={`worker-card notification ${item.is_read?'':'unread'}`} key={item.id}><div className="plan-top"><div><strong>{notificationLabels[item.type] || 'Pembaruan tugas'}</strong><p>{item.instruction || 'Tugas'}</p></div>{!item.is_read && <span className="unread-dot" aria-label="Belum dibaca"/>}</div><div className="worker-meta">{new Date(item.occurred_at).toLocaleString('id-ID')}</div>{item.type==='task.failed.v1' && item.task_result?.error && <p className="worker-failure">{item.task_result.error}</p>}{item.type==='task.escalated.v1' && item.data?.message && <p>{item.data.message}</p>}<div className="actions">{!item.is_read && <button className="secondary" onClick={()=>onRead(item)}>Tandai dibaca</button>}{!item.archived && ['completed','failed','cancelled'].includes(item.task_status) && <button className="secondary" onClick={()=>onRerun({id:item.task_id})}>Jalankan ulang</button>}</div></article>)}</div>
  </div>;
}

function ConfirmDialog({ config, onClose }) {
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); return () => { if (dialog.current?.open) dialog.current.close(); }; }, []);
  return <dialog className="confirm-dialog" ref={dialog} onCancel={e=>{e.preventDefault();onClose();}} aria-labelledby="confirm-title" aria-describedby="confirm-description"><div className="confirm-content"><div className="confirm-icon" aria-hidden="true">!</div><h2 id="confirm-title">{config.title}</h2><p id="confirm-description">{config.description}</p><div className="confirm-actions"><button className="secondary" autoFocus onClick={onClose}>Batal</button><button className="danger-button" onClick={()=>{onClose();config.onConfirm();}}>{config.confirmLabel || 'Hapus'}</button></div></div></dialog>;
}

function Sources({ sources, onChanged, requestConfirm }) {
  const [name, setName] = useState('');
  const [kind, setKind] = useState('iot');
  const [editing, setEditing] = useState(null);
  const [credential, setCredential] = useState(null);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [mediaSettings, setMediaSettings] = useState(null);
  const [error, setError] = useState('');
  async function submit(e) { e.preventDefault(); setError(''); try {
    if (editing) await api(`/v1/sources/${encodeURIComponent(editing.id)}`, {method:'PUT',body:JSON.stringify({name,kind,status:editing.status})});
    else { const result=await api('/v1/sources',{method:'POST',body:JSON.stringify({name,kind})}); setCredential(result); }
    setName('');setKind('iot');setEditing(null);await onChanged();
  } catch(e) {setError(e.message);} }
  async function toggle(source) {try {await api(`/v1/sources/${encodeURIComponent(source.id)}`,{method:'PUT',body:JSON.stringify({name:source.name,kind:source.kind,status:source.status==='active'?'disabled':'active'})});await onChanged();}catch(e){setError(e.message);}}
  function remove(source) {requestConfirm({title:'Hapus sumber?',description:`${source.name} tidak dapat mengirim data lagi. Riwayat data tetap tersimpan.`,onConfirm:async()=>{try{await api(`/v1/sources/${encodeURIComponent(source.id)}`,{method:'DELETE'});if(selected===source.id){setSelected(null);setEvents([]);}await onChanged();}catch(e){setError(e.message);}}});}
  async function viewEvents(source) {try {setEvents(await api(`/v1/sources/${encodeURIComponent(source.id)}/events`));setSelected(source.id);}catch(e){setError(e.message);}}
  async function editMedia(source) {try{setMediaSettings({id:source.id,...await api(`/v1/sources/${encodeURIComponent(source.id)}/media-settings`)});setError('');}catch(e){setError(e.message);}}
  async function saveMedia(e) {e.preventDefault();try {const {id,...settings}=mediaSettings;await api(`/v1/sources/${encodeURIComponent(id)}/media-settings`,{method:'PUT',body:JSON.stringify(settings)});setMediaSettings(null);setError('');}catch(e){setError(e.message);}}
  return <div className="workers"><div className="workers-header"><div><div className="eyebrow">INTEGRASI</div><h1>Sumber eksternal</h1><p>Terima data dari perangkat atau layanan yang dapat mengirim HTTP.</p></div></div>
    <p className="source-note">Sumber menerima event JSON. Analisis gambar dan audio dapat diaktifkan per sumber. Gateway mengirim cuplikan; streaming langsung dan pairing otomatis belum tersedia.</p>
    <form className="source-form" onSubmit={submit}><label>Nama sumber<input value={name} required maxLength={100} onChange={e=>setName(e.target.value)} placeholder="Contoh: Sensor gudang"/></label><label>Jenis<select value={kind} onChange={e=>setKind(e.target.value)}><option value="iot">IoT / sensor</option><option value="camera">Kamera</option><option value="service">Layanan lain</option></select></label><button className="primary">{editing?'Simpan perubahan':'Tambah sumber'}</button>{editing && <button type="button" className="secondary" onClick={()=>{setEditing(null);setName('');setKind('iot');}}>Batal</button>}</form>
    {credential && <div className="credential"><strong>Sumber dibuat</strong><p>Salin token sekarang; token tidak akan ditampilkan lagi. Gunakan koneksi HTTPS saat mengirim data melalui jaringan.</p><label>Alamat penerima<input readOnly value={window.location.origin+credential.ingest_path} onFocus={e=>e.target.select()}/></label><label>Token<input readOnly value={credential.token} onFocus={e=>e.target.select()}/></label><p>Alamat localhost hanya dapat diakses dari mesin ini. Perangkat lain memerlukan gateway yang aman.</p><button className="secondary" onClick={()=>setCredential(null)}>Saya sudah menyimpan token</button></div>}
    <div className="error" role="alert">{error}</div><div className="worker-list">{!sources.length && <div className="worker-empty"><strong>Belum ada sumber</strong><p>Tambahkan sumber untuk mendapatkan alamat dan token pengiriman.</p></div>}{sources.map(source=><article className="worker-card" key={source.id}><div className="plan-top"><div><strong>{source.name}</strong><p>{source.kind} · {source.last_seen ? `Terakhir menerima data ${new Date(source.last_seen).toLocaleString('id-ID')}` : 'Belum menerima data'}</p></div><span className={`status ${source.status==='active'?'completed':''}`}>{source.status==='active'?'Aktif':'Nonaktif'}</span></div><div className="actions"><button className="secondary" onClick={()=>viewEvents(source)}>Lihat data</button><button className="secondary" onClick={()=>editMedia(source)}>Atur media</button><button className="secondary" onClick={()=>{setEditing(source);setName(source.name);setKind(source.kind);}}>Ubah</button><button className="secondary" onClick={()=>toggle(source)}>{source.status==='active'?'Nonaktifkan':'Aktifkan'}</button><button className="text-button" onClick={()=>remove(source)}>Hapus</button></div>{mediaSettings?.id===source.id && <form className="media-settings" onSubmit={saveMedia}><p>Media yang diaktifkan akan dikirim ke Baseten untuk dianalisis. Aktifkan hanya sesuai kebutuhan.</p><label><input type="checkbox" checked={mediaSettings.vision_enabled} onChange={e=>setMediaSettings({...mediaSettings,vision_enabled:e.target.checked})}/> Analisis gambar</label><textarea aria-label="Pertanyaan tentang gambar" maxLength={500} required value={mediaSettings.vision_prompt} onChange={e=>setMediaSettings({...mediaSettings,vision_prompt:e.target.value})}/><label><input type="checkbox" checked={mediaSettings.audio_enabled} onChange={e=>setMediaSettings({...mediaSettings,audio_enabled:e.target.checked})}/> Analisis audio</label><textarea aria-label="Pertanyaan tentang audio" maxLength={500} required value={mediaSettings.audio_prompt} onChange={e=>setMediaSettings({...mediaSettings,audio_prompt:e.target.value})}/><div className="actions"><button className="primary">Simpan pengaturan</button><button type="button" className="secondary" onClick={()=>setMediaSettings(null)}>Batal</button></div></form>}{selected===source.id && <div className="result"><strong>Data terbaru</strong>{!events.length && <p>Belum ada data yang diterima.</p>}{events.map(item=><details className="details" key={item.id}><summary>{item.event_type} · {new Date(item.received_at).toLocaleString('id-ID')}</summary><pre>{JSON.stringify(item.payload,null,2)}</pre></details>)}</div>}</article>)}</div>
  </div>;
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [instruction, setInstruction] = useState('');
  const [connections, setConnections] = useState([]);
  const [chats, setChats] = useState([]);
  const [current, setCurrent] = useState(() => sessionStorage.getItem('kanca-conversation'));
  const [messages, setMessages] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notice, setNotice] = useState('');
  const [externalSources, setExternalSources] = useState([]);
  const [view, setView] = useState('chat');
  const [theme, toggleTheme] = useTheme();
  const [pendingChat, setPendingChat] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const currentRef = useRef(current);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const rerunPending = useRef(false);

  const selectChat = useCallback(id => { currentRef.current = id; setCurrent(id); if (id) sessionStorage.setItem('kanca-conversation', id); else sessionStorage.removeItem('kanca-conversation'); }, []);
  const refresh = useCallback(async () => {
    const [sources, conversations, allTasks, external, notices, unread] = await Promise.all([api('/v1/connections'), api('/v1/conversations'), api('/v1/tasks'), api('/v1/sources'), api('/v1/notifications'), api('/v1/notifications/unread-count')]);
    let selected = currentRef.current;
    if (selected && !conversations.some(chat => chat.id === selected)) { selected = null; selectChat(null); }
    if (!selected && conversations.length) { selected = conversations[0].id; selectChat(selected); }
    const fresh = selected ? await api(`/v1/conversations/${encodeURIComponent(selected)}/messages`) : [];
    if (selected !== currentRef.current) return;
    setConnections(sources); setChats(conversations); setMessages(fresh); setTasks(allTasks); setExternalSources(external); setNotifications(notices); setUnreadCount(unread.count); setConnected(true);
  }, [selectChat]);

  useEffect(() => {
    let active = true;
    const poll = async () => { try { await refresh(); } catch (error) { if(active) { setConnected(false); setFeedback(error.message); } } };
    api('/v1/session').then(poll).catch(error => { if(active) setFeedback(error.message); });
    const timer = setInterval(poll, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [refresh]);

  useEffect(() => { document.querySelectorAll('.main .scroll').forEach(el => { el.scrollTop = 0; }); }, [view]);

  async function newChat() {
    try { const chat = await api('/v1/conversations', {method:'POST', body:JSON.stringify({})}); selectChat(chat.id); setView('chat'); setMessages([]); setInstruction(''); await refresh(); inputRef.current?.focus(); }
    catch(error) { setFeedback(error.message); }
  }
  async function select(id) { selectChat(id); setView('chat'); setMessages([]); try { await refresh(); } catch(error) { setFeedback(error.message); } }
  async function connect(type) { try { await api('/v1/connections', {method:'POST', body:JSON.stringify({type})}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function action(task, actionName, body) { try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/${actionName}`, {method:'POST', body:body ? JSON.stringify(body) : undefined}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function rerun(task) { if(rerunPending.current)return; rerunPending.current=true; try { setFeedback(''); setNotice(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/rerun`,{method:'POST'}); await refresh(); setView('workers'); setNotice('Rencana baru sudah dibuat. Periksa dan setujui untuk menjalankannya.'); } catch(error) { setFeedback(error.message); } finally { rerunPending.current=false; } }
  async function markRead(item) { try { await api(`/v1/notifications/${encodeURIComponent(item.id)}/read`,{method:'POST'}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function markAllRead() { try { await api('/v1/notifications/read-all',{method:'POST'}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function edit(task, interval, runs) { try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/schedule`, {method:'PATCH', body:JSON.stringify({version:task.version,schedule:{interval_seconds:interval,max_runs:runs}})}); await refresh(); return true; } catch(error) { setFeedback(error.message); return false; } }
  function archive(task) { setConfirmation({title:'Hapus tugas dari daftar?',description:'Tugas yang aktif akan dihentikan. Riwayatnya tetap disimpan.',onConfirm:async()=>{try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}`,{method:'DELETE'}); await refresh(); } catch(error) { setFeedback(error.message); }}}); }
  async function moveChat(chat) {try{await api(`/v1/conversations/${encodeURIComponent(chat.id)}`,{method:'PATCH',body:JSON.stringify({status:chat.status==='draft'?'active':'draft'})});await refresh();}catch(error){setFeedback(error.message);}}
  function deleteChat(chat) {setConfirmation({title:'Hapus percakapan?',description:'Percakapan akan dihapus dari daftar. Tugas yang sudah dibuat tetap berjalan dan tersedia di Tugas latar belakang.',onConfirm:async()=>{try{await api(`/v1/conversations/${encodeURIComponent(chat.id)}`,{method:'DELETE'});if(currentRef.current===chat.id){selectChat(null);setMessages([]);}await refresh();}catch(error){setFeedback(error.message);}}});}
  async function send(event) {
    event?.preventDefault(); const text = instruction.trim();
    if (!connected || !text || busy) return;
    setBusy(true); setFeedback('');
    try {
      let target = currentRef.current;
      if (!target) { const chat = await api('/v1/conversations', {method:'POST', body:JSON.stringify({})}); target = chat.id; selectChat(target); }
      setPendingChat(target);
      setInstruction('');
      await api(`/v1/conversations/${encodeURIComponent(target)}/messages`, {method:'POST', body:JSON.stringify({content:text})});
      setFeedback(''); await refresh();
      if (target === currentRef.current) scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight, behavior:'smooth'});
    } catch(error) { setFeedback(error.message); setInstruction(text); } finally { setBusy(false); setPendingChat(null); }
  }

  return <div className="app"><aside className="sidebar">
    <Brand/>
    <div className="sidebar-content">
    <section className="sidebar-nav"><button className="side-button new-button nav-row" onClick={newChat} disabled={!connected}><span className="nav-icon"><Icon name="plus"/></span><span className="nav-label">Chat baru</span></button><button className="side-button nav-row" aria-current={view==='workers'?'page':undefined} onClick={()=>setView('workers')}><span className="nav-icon"><Icon name="clock"/></span><span className="nav-label">Tugas</span><span className="task-count" aria-label={`${tasks.filter(t=>t.status==='scheduled'||t.status==='running').length} tugas aktif`}>{tasks.filter(t=>t.status==='scheduled'||t.status==='running').length}</span></button><button className="side-button nav-row" aria-current={view==='sources'?'page':undefined} onClick={()=>setView('sources')}><span className="nav-icon"><Icon name="plug"/></span><span className="nav-label">Integrasi</span></button></section>
    <section className="history-section"><p className="side-label">Riwayat percakapan</p>{!chats.length && <p className="meta">Belum ada percakapan</p>}{['active','draft'].map(status=>{const group=chats.filter(chat=>chat.status===status);return group.length>0 && <div className="history-group" key={status}><p className="history-label">{status==='draft'?'Draft':'Percakapan'}</p>{group.map(chat=><div className={`chat-row ${chat.id===current && view==='chat'?'selected':''}`} key={chat.id}><button className="chat-select" aria-current={chat.id===current && view==='chat'?'page':undefined} onClick={()=>select(chat.id)} title={chat.title}>{chat.title}</button><details className="chat-menu"><summary aria-label={`Opsi untuk ${chat.title}`}><Icon name="dots" size={16}/></summary><div className="chat-menu-items"><button onClick={e=>{e.currentTarget.closest('details').open=false;moveChat(chat);}}>{status==='draft'?'Kembalikan':'Pindah ke draft'}</button><button className="menu-danger" onClick={e=>{e.currentTarget.closest('details').open=false;deleteChat(chat);}}>Hapus</button></div></details></div>)}</div>})}</section>
    <section><p className="side-label">Sumber simulasi</p>{[['business_demo','Bisnis demo'],['device_demo','Perangkat demo']].map(([type,name]) => { const active = connections.some(c => c.type === type && c.status === 'connected'); return <div className="connector" key={type}><span><i className={`dot ${active?'on':''}`}/>{name}</span><button className="secondary" disabled={!connected || active} onClick={() => connect(type)}>{active?'Terhubung':'Hubungkan'}</button></div>; })}</section>
    <div className="side-note">Dibuat untuk membantumu tetap tenang.<br/>Data dan tindakan masih simulasi.<br/><a href="/docs" target="_blank" rel="noreferrer">Dokumentasi API ↗</a></div>
    </div>
  </aside><main className="main"><header className="topbar"><Brand className="brand brand-topbar"/><div className="topbar-title"><strong>{view==='workers'?'Tugas latar belakang':view==='notifications'?'Notifikasi':view==='sources'?'Sumber eksternal':'Ruang percakapan'}</strong><p>{view==='workers'?'Kelola pemantauanmu di satu tempat':view==='notifications'?'Pembaruan tugasmu':view==='sources'?'Kelola perangkat dan layanan':'Tempat untuk mendelegasikan tugasmu'}</p></div><div className="topbar-actions">{view==='chat' && <ChatTopics chats={chats} current={current} onSelect={select} onNew={newChat}/>}<span className="badge">{connected?'Terhubung':'Belum terhubung'}</span><button className="icon-button theme-toggle" type="button" onClick={toggleTheme} aria-label={theme==='dark'?'Aktifkan mode terang':'Aktifkan mode gelap'} title={theme==='dark'?'Mode terang':'Mode gelap'}><Icon name={theme==='dark'?'sun':'moon'}/></button><button className="notification-button" onClick={()=>setView('notifications')} aria-label={`Notifikasi, ${unreadCount} belum dibaca`} aria-current={view==='notifications'?'page':undefined} title="Notifikasi"><Icon name="bell"/>{unreadCount>0 && <span className="notification-count" aria-hidden="true">{unreadCount>99?'99+':unreadCount}</span>}</button></div></header>
    {view==='workers' ? <div className="scroll"><Workers tasks={tasks} onAction={action} onEdit={edit} onArchive={archive} onCreate={newChat} onRerun={rerun}/><div className="workers-error" role="status">{notice}</div><div className="workers-error error" role="alert">{feedback}</div></div> : view==='notifications' ? <div className="scroll"><Notifications items={notifications} onRead={markRead} onReadAll={markAllRead} unreadCount={unreadCount} onRerun={rerun}/><div className="workers-error error" role="alert">{feedback}</div></div> : view==='sources' ? <div className="scroll"><Sources sources={externalSources} onChanged={refresh} requestConfirm={setConfirmation}/></div> : <>
    <div className="scroll" ref={scrollRef}><div className="content"><div className="welcome"><div className="eyebrow">Selamat datang di Kanca ✳</div><h1>Halo, ada yang bisa aku bantu hari ini?</h1><p>Beritahu apa yang ingin kamu pantau. Pemeriksaan dan tindakan aman langsung berjalan; tindakan berisiko menunggu persetujuanmu.</p></div>
      <div className="suggestions">{[['thermometer','Periksa suhu ruangan'],['list','Periksa pesanan'],['clock','Pantau pesanan']].map(([icon,label],index) => <button key={label} onClick={() => {setInstruction(prompts[index]);inputRef.current?.focus();}}><Icon name={icon} size={17}/>{label}</button>)}</div><div className="separator"/>
      <div aria-live="polite">{!messages.length && !busy && <p className="meta">Belum ada pesan. Mulai dengan mengirim instruksi di bawah.</p>}{messages.map(item => <div className="message" key={item.id}><div className={`avatar ${item.role === 'user' ? 'user' : ''}`}>{item.role === 'user' ? 'K' : 'k.'}</div><div className="message-body"><div className="message-head">{item.role === 'user' ? 'Kamu' : 'Kanca'} <span>{new Date(item.created_at).toLocaleString('id-ID')}</span></div><div className="bubble">{item.content}</div>{item.task && <TaskCard task={item.task} onAction={action} onRerun={rerun}/>}</div></div>)}{busy && pendingChat===current && <div className="message" role="status" aria-label="Kanca sedang mengetik"><div className="avatar">k.</div><div className="message-body"><div className="message-head">Kanca</div><div className="typing"><span/><span/><span/></div></div></div>}</div><div className="error" role="alert">{feedback}</div>
    </div></div><div className="composer-wrap"><form className="composer" onSubmit={send}><textarea ref={inputRef} value={instruction} onChange={e=>setInstruction(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}} placeholder="Ceritakan apa yang ingin kamu lakukan..." aria-label="Instruksi untuk Kanca" maxLength={4000}/><div className="composer-bottom"><span>Enter untuk kirim · Shift + Enter untuk baris baru</span><button className="send" aria-label="Kirim instruksi" disabled={!connected || busy}><Icon name="up"/></button></div></form><p className="footer">Kanca dapat membuat kesalahan. Periksa rencana sebelum menyetujui.</p></div>
  </>}</main><nav className="mobile-bottom-nav" aria-label="Navigasi utama">{[['chat','Chat'],['workers','Tugas'],['notifications','Notifikasi'],['sources','Integrasi']].map(([tab,label]) => <button key={tab} className="tab-button" onClick={()=>setView(tab)} aria-current={view===tab?'page':undefined}><Icon name={{chat:'chat',workers:'clock',notifications:'bell',sources:'plug'}[tab]}/><span className="nav-label">{label}</span>{tab==='notifications'&&unreadCount>0 && <span className="tab-badge" aria-hidden="true">{unreadCount>99?'99+':unreadCount}</span>}{tab==='workers'&&tasks.some(t=>t.status==='scheduled'||t.status==='running') && <span className="tab-dot" aria-hidden="true"/>}</button>)}</nav>{confirmation && <ConfirmDialog config={confirmation} onClose={()=>setConfirmation(null)}/>}</div>;
}
