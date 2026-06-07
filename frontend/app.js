/**
 * PuranGPT v2 — Frontend
 * New: conversation memory, deep research, Sanskrit search,
 *      source/language badges, Nath & Darshana modes
 */
'use strict';

// ── Config & State ─────────────────────────────────────────────────────────
const CONFIG = {
  apiUrl:          localStorage.getItem('purangpt_api_url') || '',
  streamResponses: localStorage.getItem('purangpt_stream')  !== 'false',
  sessionId:       getOrCreateSession(),
  // 'auto' lets the backend route to whichever provider has a valid key
  model:           localStorage.getItem('purangpt_model') || 'auto',
  apiKeys:         JSON.parse(localStorage.getItem('purangpt_keys') || '{}'),
};

const STATE = {
  activeMode: 'chat',
  isGenerating: false,
  isRecording: false,
  historyCount: 0,
  userPrompts: [],
  promptIndex: -1,
  gretilTexts: 0,
};

function getOrCreateSession() {
  let id = localStorage.getItem('purangpt_session');
  if (!id) {
    id = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    localStorage.setItem('purangpt_session', id);
  }
  return id;
}

const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

// ── DOM refs ───────────────────────────────────────────────────────────────
const DOM = {
  btnNewChat:        $('btn-new-chat'),
  sessionList:       $('session-list'),
  modeBtns:          $$('.mode-btn, .bottom-nav-btn'),
  panels:            $$('.panel'),
  sidebar:           $('sidebar'),
  sidebarScrim:      $('sidebar-scrim'),
  mobileMenuBtn:     $('mobile-menu-btn'),
  statusDot:         $('status-dot'),
  statusText:        $('status-text'),
  messagesContainer: $('messages-container'),
  welcomeScreen:     $('welcome-screen'),
  chatInput:         $('chat-input'),
  sendBtn:           $('send-btn'),
  charCount:         $('char-count'),
  sourcesList:       $('sources-list'),
  sourcesPanel:      $('sources-panel'),
  puranFilter:       $('purana-list'),
  filterAll:         $('filter-all'),
  statTexts:         $('stat-texts'),
  statVerses:        $('stat-verses'),
  statModel:         $('stat-model'),
  instancesInput:    $('instances-input'),
  instancesSearchBtn:$('instances-search-btn'),
  instancesResults:  $('instances-results'),
  filterChips:       $$('.chip'),
  textsGrid:         $('texts-grid'),
  exploreSearchInput:$('explore-search-input'),
  exploreEmptyState: $('explore-empty-state'),
  settingsBtn:       $('settings-btn'),
  settingsModal:     $('settings-modal'),
  settingsClose:     $('settings-close'),
  settingsSave:      $('settings-save'),
  apiUrlInput:       $('api-url'),
  keyGroq:           $('key-groq'),
  keyTogether:       $('key-together'),
  keyDeepseek:       $('key-deepseek'),
  keyGemini:         $('key-gemini'),
  keyZhipu:          $('key-zhipu'),
  toastContainer:    $('toast-container'),
  suggestionCards:   $$('.suggestion-card'),
  // Sanskrit search panel
  sanskritInput:     $('sanskrit-input'),
  sanskritSearchBtn: $('sanskrit-search-btn'),
  sanskritResults:   $('sanskrit-results'),
  // Memory indicator
  memoryBadge:       $('memory-badge'),
  clearMemoryBtn:    $('clear-memory-btn'),
};

function getApiUrl() {
  if (CONFIG.apiUrl) return CONFIG.apiUrl;
  if (!window.location.port || window.location.port === '80' || window.location.port === '443') return window.location.origin;
  return 'http://localhost:8000';
}

function getApiHeaders(extra = {}) {
  const h = { ...extra };
  if (CONFIG.apiKeys?.groq) h['x-groq-key'] = CONFIG.apiKeys.groq;
  if (CONFIG.apiKeys?.together) h['x-together-key'] = CONFIG.apiKeys.together;
  if (CONFIG.apiKeys?.deepseek) h['x-deepseek-key'] = CONFIG.apiKeys.deepseek;
  if (CONFIG.apiKeys?.gemini) h['x-gemini-key'] = CONFIG.apiKeys.gemini;
  if (CONFIG.apiKeys?.zhipu) h['x-zhipu-key'] = CONFIG.apiKeys.zhipu;
  
  if (typeof getAuthToken === 'function') {
    const token = getAuthToken();
    if (token) {
      h['Authorization'] = `Bearer ${token}`;
    }
  }
  return h;
}

// ── Texts catalog (with source/language metadata) ─────────────────────────
const SACRED_TEXTS = [
  // Mahapuranas
  {id:'agni',           name:'Agni Purana',           sk:'अग्नि पुराण',        icon:'fire', cat:'mahapurana', trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'bhagavata',      name:'Bhagavata Purana',      sk:'भागवत पुराण',        icon:'music', cat:'mahapurana', trad:'vaishnava',         lang:'Sanskrit', bias:'⚠️'},
  {id:'brahma',         name:'Brahma Purana',         sk:'ब्रह्म पुराण',         icon:'flower-2', cat:'mahapurana', trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'brahmanda',      name:'Brahmanda Purana',      sk:'ब्रह्माण्ड पुराण',    icon:'globe', cat:'mahapurana', trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'garuda',         name:'Garuda Purana',         sk:'गरुड पुराण',          icon:'bird', cat:'mahapurana', trad:'vaishnava',         lang:'Sanskrit', bias:'⚠️'},
  {id:'kurma',          name:'Kurma Purana',          sk:'कूर्म पुराण',          icon:'shield', cat:'mahapurana', trad:'shaiva-vaishnava',  lang:'Sanskrit', bias:'✅'},
  {id:'linga_1',        name:'Linga Purana',          sk:'लिंग पुराण',           icon:'triangle', cat:'mahapurana', trad:'shaiva',           lang:'Sanskrit', bias:'✅'},
  {id:'markandeya',     name:'Markandeya Purana',     sk:'मार्कण्डेय पुराण',   icon:'link', cat:'mahapurana', trad:'shakta',           lang:'Sanskrit', bias:'✅'},
  {id:'matsya',         name:'Matsya Purana',         sk:'मत्स्य पुराण',         icon:'fish', cat:'mahapurana', trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'narada',         name:'Narada Purana',         sk:'नारद पुराण',           icon:'music-2', cat:'mahapurana', trad:'vaishnava',         lang:'Sanskrit', bias:'⚠️'},
  {id:'shiva_1_7',      name:'Shiva Purana',          sk:'शिव पुराण',            icon:'moon', cat:'mahapurana', trad:'shaiva',           lang:'Sanskrit', bias:'✅'},
  {id:'vamana',         name:'Vamana Purana',         sk:'वामन पुराण',           icon:'flower', cat:'mahapurana', trad:'vaishnava',         lang:'Sanskrit', bias:'⚠️'},
  {id:'vishnu_critical',name:'Vishnu Purana',         sk:'विष्णु पुराण',          icon:'feather', cat:'mahapurana', trad:'vaishnava',         lang:'Sanskrit', bias:'⚠️'},
  // Epics
  {id:'bhagavad_gita',  name:'Bhagavad Gita',         sk:'भगवद्गीता',            icon:'sparkles', cat:'epic',       trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'mahabharata',    name:'Mahabharata',           sk:'महाभारत',              icon:'swords', cat:'epic',       trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  {id:'ramayana',       name:'Valmiki Ramayana',      sk:'रामायण',               icon:'target', cat:'epic',       trad:'mixed',            lang:'Sanskrit', bias:'✅'},
  // Nath tradition
  {id:'yoga_vasistha',  name:'Yoga Vasistha',         sk:'योगवासिष्ठ',            icon:'waves', cat:'yoga',       trad:'advaita',          lang:'Sanskrit', bias:'✅'},
  {id:'gorakshashataka',name:'Gorakshashataka',       sk:'गोरक्षशतक',            icon:'flame', cat:'nath',       trad:'nath',             lang:'Sanskrit', bias:'✅'},
  {id:'hatha_yoga',     name:'Hatha Yoga Pradipika',  sk:'हठयोगप्रदीपिका',       icon:'activity', cat:'yoga',       trad:'nath',             lang:'Sanskrit', bias:'✅'},
  {id:'gheranda',       name:'Gheranda Samhita',      sk:'घेरण्डसंहिता',          icon:'heart-pulse', cat:'nath',       trad:'nath',             lang:'Sanskrit', bias:'✅'},
  {id:'shiva_samhita',  name:'Shiva Samhita',         sk:'शिवसंहिता',             icon:'zap', cat:'nath',       trad:'shaiva-nath',      lang:'Sanskrit', bias:'✅'},
  // Darshanas
  {id:'yoga_sutras',    name:'Yoga Sutras (Patanjali)',sk:'योगसूत्र',              icon:'brain', cat:'darshana',   trad:'darshana',         lang:'Sanskrit', bias:'✅'},
  {id:'samkhya_karika', name:'Samkhya Karika',        sk:'सांख्यकारिका',          icon:'layers', cat:'darshana',   trad:'darshana',         lang:'Sanskrit', bias:'✅'},
  {id:'brahma_sutras',  name:'Brahma Sutras (Vedanta)',sk:'ब्रह्मसूत्र',           icon:'book-open', cat:'darshana',   trad:'vedanta',          lang:'Sanskrit', bias:'✅'},
  {id:'upanishads_108', name:'108 Upanishads',        sk:'उपनिषद्',               icon:'circle-dot', cat:'upanishad',  trad:'vedic',            lang:'Sanskrit', bias:'✅'},
];

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  loadSettings();
  renderPuranaFilter();
  renderExploreGrid();
  bindEvents();
  _initScrollLock();
  await checkStatus();
  await fetchSessions();
  updateMemoryBadge();
  updateLimits();
}

// ── Mode Switching ─────────────────────────────────────────────────────────
function switchMode(m) {
  if (STATE.activeMode === m) return;
  STATE.activeMode = m;
  DOM.modeBtns.forEach(b => {
    b.classList.toggle('active', b.dataset.mode === m);
    b.setAttribute('aria-selected', String(b.dataset.mode === m));
  });
  DOM.panels.forEach(p => {
    p.classList.toggle('active', p.id === `panel-${m}`);
    p.hidden = p.id !== `panel-${m}`;
  });
  if (m === 'explore') renderExploreGrid();
  if (m === 'infer')   initInferPanel();
  updateLimits();
}

// ── Infer Panel ─────────────────────────────────────────────────────────────
let _inferInitialized = false;
function initInferPanel() {
  if (_inferInitialized) return;
  _inferInitialized = true;

  const btn   = $('infer-btn');
  const input = $('infer-input');
  if (!btn || !input) return;

  btn.addEventListener('click', () => runInference(input.value.trim()));
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runInference(input.value.trim()); } });

  document.querySelectorAll('.infer-example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.q;
      runInference(chip.dataset.q);
    });
  });
}

async function runInference(topic) {
  if (!topic) return;
  const resultsEl = $('infer-results');
  const statusEl  = $('infer-status');
  const sourcesEl = $('infer-sources');

  // Reset UI
  resultsEl.innerHTML = '';
  statusEl.hidden     = false;
  statusEl.textContent = 'Retrieving passages from all indexed texts…';
  sourcesEl.hidden    = true;
  sourcesEl.innerHTML = '';

  let fullText = '';

  try {
    const resp = await fetch(`${getApiUrl()}/api/infer`, {
      method: 'POST',
      headers: getApiHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ topic, top_k: 15 })
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        try {
          const raw = line.slice(5).trim();
          const evt = JSON.parse(raw.startsWith('{') ? raw : JSON.parse(raw));

          if (evt.type === 'status') {
            statusEl.textContent = evt.message;
          } else if (evt.type === 'sources') {
            if (evt.sources?.length) {
              statusEl.textContent = `Found ${evt.sources.length} source passages — synthesising…`;
              sourcesEl.hidden = false;
              sourcesEl.innerHTML = `<div class="infer-sources-label">Source passages (${evt.sources.length})</div>` +
                evt.sources.map(s => `<span class="infer-source-chip">${escapeHtml(s.text_name||s.purana||'')} ${s.reference ? '· ' + escapeHtml(s.reference) : ''}</span>`).join('');
            }
          } else if (evt.type === 'token') {
            statusEl.hidden = true;
            fullText += evt.content;
            resultsEl.innerHTML = renderMarkdown(fullText);
          } else if (evt.type === 'done') {
            statusEl.hidden = true;
            resultsEl.innerHTML = renderMarkdown(fullText);
          } else if (evt.type === 'error') {
            statusEl.textContent = '❌ ' + (evt.message || 'Error');
          }
        } catch (_) { /* skip malformed */ }
      }
    }
  } catch (err) {
    statusEl.textContent = '❌ Network error: ' + err.message;
  }
}

// Simple markdown renderer (headers, bold, bullets)
function renderMarkdown(md) {
  return md
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm,  '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,   '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/^- (.+)$/gm,     '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/gs, m => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(?!<[hul])(.)/gm, '<p>$&')
    .replace(/<p>(<[hul])/g, '$1');
}

// ── Status & Limits ─────────────────────────────────────────────────────────
async function updateLimits() {
  const badge = $('limit-badge');
  if (!badge) return;
  try {
    const res = await fetch(`${getApiUrl()}/api/user/usage`, { headers: await getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (data.is_byok) {
         badge.style.display = 'inline-block';
         badge.innerHTML = '✨ BYOK Unlimited';
         return;
      }
      
      let msgText = '';
      if (STATE.activeMode === 'deep') {
         const used = data.research.used;
         const limit = data.research.limit;
         msgText = limit === 'Unlimited' ? 'Research: Unlimited' : `Research: ${limit - used} left`;
         if (limit !== 'Unlimited' && used >= limit) {
             msgText = 'Research limit reached';
             badge.style.color = '#ff4444';
         } else {
             badge.style.color = 'var(--accent)';
         }
      } else {
         const used = data.messages.used;
         const limit = data.messages.limit;
         msgText = limit === 'Unlimited' ? 'Messages: Unlimited' : `Messages: ${limit - used} left`;
         if (limit !== 'Unlimited' && used >= limit) {
             msgText = 'Message limit reached';
             badge.style.color = '#ff4444';
         } else {
             badge.style.color = 'var(--accent)';
         }
      }
      badge.style.display = 'inline-block';
      badge.textContent = msgText;
    }
  } catch(e) {}
}

async function checkStatus() {
  setStatus('loading', 'Connecting…');
  try {
    const d = await (await fetch(`${getApiUrl()}/api/status`, {signal: AbortSignal.timeout(6000)})).json();
    const provider = d.llm_provider || 'unknown';
    const modelShort = (d.model || '').replace('llama-', '').replace('-versatile','').replace('-instruct','');
    const statusLabel = d.status === 'degraded'
      ? `${provider} · ${modelShort}`
      : `${provider} · ${modelShort}`;
    setStatus(d.status === 'degraded' ? 'degraded' : 'online', statusLabel);

    if (CONFIG.model === 'auto') {
        // Mocking logic to keep structure aligned
        const infoOpt = { textContent: `Auto → ${provider} (${modelShort})` };
        if (infoOpt) infoOpt.textContent = `Auto → ${provider} (${modelShort})`;
    }

    DOM.statTexts.textContent  = d.gretil_texts  ? `${d.gretil_texts} texts (GRETIL)` : (d.texts_indexed || '—');
    DOM.statVerses.textContent = d.total_chunks   ? `${(d.total_chunks/1000).toFixed(1)}k chunks` : (d.gretil_chars ? `${(d.gretil_chars/1e6).toFixed(1)}M chars` : '—');
    DOM.statModel.textContent  = d.model || provider;
    STATE.gretilTexts          = d.gretil_texts || 0;
  } catch {
    setStatus('offline', 'Server offline — run: python run.py');
  }
}

function setStatus(t, text) {
  DOM.statusDot.className    = `status-dot ${t}`;
  DOM.statusText.textContent = text;
}

// ── Memory Badge ───────────────────────────────────────────────────────────
function updateMemoryBadge() {
  if (!DOM.memoryBadge) return;
  const count = STATE.historyCount;
  DOM.memoryBadge.textContent = count > 0 ? `${count} msg${count !== 1 ? 's' : ''} in memory` : 'New session';
  DOM.memoryBadge.style.color = count > 0 ? 'var(--gold-main)' : 'var(--text-muted)';
}

async function clearMemory() {
  try {
    await fetch(`${getApiUrl()}/api/session/${CONFIG.sessionId}`, {method: 'DELETE'});
    createNewSession();
    showToast('Conversation memory cleared', 'success');
  } catch { showToast('Could not clear memory', 'error'); }
}

// ── Session Management ─────────────────────────────────────────────────────
async function fetchSessions() {
  try {
    const res = await fetch(`${getApiUrl()}/api/sessions`);
    if (res.ok) {
      const data = await res.json();
      renderSessions(data.sessions || []);
    }
  } catch (e) {
    console.error('Failed to fetch sessions', e);
  }
}

function renderSessions(sessions) {
  if (!DOM.sessionList) return;
  DOM.sessionList.innerHTML = sessions.map(s => `
    <div class="session-item ${s.id === CONFIG.sessionId ? 'active' : ''}" onclick="loadSession('${s.id}')">
      ${escapeHtml(s.title || 'New Chat')}
      <span class="session-item-date">${new Date(s.updated_at * 1000).toLocaleDateString()}</span>
    </div>
  `).join('');
}

async function loadSession(id) {
  CONFIG.sessionId = id;
  localStorage.setItem('purangpt_session', id);
  
  try {
    const res = await fetch(`${getApiUrl()}/api/session/${id}`);
    if (res.ok) {
      const data = await res.json();
      DOM.welcomeScreen.style.display = data.history.length ? 'none' : 'flex';
      DOM.messagesContainer.innerHTML = '';
      
      data.history.forEach((msg, idx) => {
        if (msg.role === 'user') {
          appendUserMessage(msg.content, idx);
        } else {
          const msgEl = appendAssistantMessage(msg.content);
          addMessageActions(msgEl.querySelector('.message-actions'), msg.content);
        }
      });
      
      STATE.historyCount = data.history.length;
      updateMemoryBadge();
      fetchSessions();
      switchMode('chat');
    }
  } catch (e) {
    console.error('Failed to load session', e);
  }
}

function createNewSession() {
  CONFIG.sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
  localStorage.setItem('purangpt_session', CONFIG.sessionId);
  DOM.messagesContainer.innerHTML = '';
  DOM.welcomeScreen.style.display = 'flex';
  STATE.historyCount = 0;
  updateMemoryBadge();
  fetchSessions();
  switchMode('chat');
}

// ── Purana Filter ──────────────────────────────────────────────────────────
function renderPuranaFilter() {
  DOM.puranFilter.innerHTML = SACRED_TEXTS.filter(t => t.cat === 'mahapurana').map(t => `
    <label class="filter-label">
      <input type="checkbox" class="filter-check purana-check" value="${t.id}" id="filter-${t.id}" />
      <span class="filter-text">${t.name}</span>
    </label>`).join('');
  DOM.filterAll.addEventListener('change', () => {
    $$('.purana-check').forEach(cb => {
      cb.checked  = false;
      cb.disabled = DOM.filterAll.checked;
    });
  });
}

// ── Explore Grid ───────────────────────────────────────────────────────────
function renderExploreGrid() {
  if (DOM.textsGrid.querySelector('.text-card')) return;
  const loading = $('explore-loading');
  if (loading) loading.remove();

  // Group by category
  const groups = {};
  SACRED_TEXTS.forEach(t => { (groups[t.cat] = groups[t.cat]||[]).push(t); });
  const catLabels = {mahapurana:'18 Mahapuranas', epic:'Epics', yoga:'Yogic Texts', nath:'Nath Tradition', darshana:'Six Darshanas', upanishad:'Upanishads'};

  DOM.textsGrid.innerHTML = Object.entries(groups).map(([cat, texts]) => `
    <div class="text-group">
      <div class="text-group-label">${catLabels[cat]||cat}</div>
      <div class="text-group-cards">${texts.map(t => `
        <article class="text-card" tabindex="0" data-id="${t.id}" id="text-card-${t.id}"
                 onclick="openTextDetail('${t.id}')"
                 onkeydown="if(event.key==='Enter') openTextDetail('${t.id}')">
          <div class="text-card-icon"><i data-lucide="${t.icon}" style="width:18px;height:18px;stroke-width:1.5"></i></div>
          <div class="text-card-name">${t.name}</div>
          <div class="text-card-sanskrit">${t.sk}</div>
          <div class="text-card-meta">
            <span class="source-badge lang-badge">${t.lang}</span>
            <span class="source-badge bias-badge ${t.bias === '✅' ? 'bias-ok' : 'bias-warn'}">${t.bias === '✅' ? 'Verified' : 'Sectarian'}</span>
            <span class="source-badge trad-badge">${t.trad}</span>
          </div>
        </article>`).join('')}
      </div>
    </div>`).join('');

  if (window._lucideRefresh) window._lucideRefresh();

  // Attach search listener
  if (DOM.exploreSearchInput) {
    DOM.exploreSearchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase().trim();
      const groups = DOM.textsGrid.querySelectorAll('.text-group');
      let totalVisible = 0;

      groups.forEach(group => {
        let groupVisible = 0;
        const cards = group.querySelectorAll('.text-card');
        cards.forEach(card => {
          const text = (card.dataset.name || card.textContent || '').toLowerCase();
          if (text.includes(term) || term === '') {
            card.style.display = 'flex';
            groupVisible++;
            totalVisible++;
          } else {
            card.style.display = 'none';
          }
        });
        group.style.display = groupVisible > 0 ? 'block' : 'none';
      });

      if (totalVisible === 0) {
        DOM.textsGrid.hidden = true;
        if (DOM.exploreEmptyState) DOM.exploreEmptyState.hidden = false;
      } else {
        DOM.textsGrid.hidden = false;
        if (DOM.exploreEmptyState) DOM.exploreEmptyState.hidden = true;
      }
    });
  }
}

async function openTextDetail(id, citationRef = null, line_idx = null) {
  const t = SACRED_TEXTS.find(x => x.id === id);
  if (!t) return;

  // Try opening reader
  try {
    let page = 1;
    let targetLineInPage = -1;
    if (line_idx !== null && line_idx >= 0) {
      page = Math.floor(line_idx / 100) + 1;
      targetLineInPage = line_idx % 100;
    }

    const res = await fetch(`${getApiUrl()}/api/text/${id}?page=${page}&size=100`);
    if (res.ok) {
      const data = await res.json();
      openReader(data, t, targetLineInPage);
      return;
    }
  } catch (e) {
    console.log("Could not load text reader, falling back to chat", e);
  }

  // Fallback to chat
  switchMode('chat');
  if (citationRef) {
    DOM.chatInput.value = `Can you provide more details, context, and a translation of the passage referenced here: ${citationRef}?`;
  } else {
    DOM.chatInput.value = `Give me a comprehensive scholarly introduction to the ${t.name} (${t.sk}): its age, authorship traditions, structure, sectarian allegiance (${t.trad}), main themes, and most significant contributions to Indian philosophy and religious tradition.`;
  }
  adjustInputHeight();
  handleSend();
}

// ── Reader Mode ────────────────────────────────────────────────────────────
let currentReaderTextId = null;
let currentReaderPage = 1;
let currentReaderTotal = 1;
let currentReaderTitle = '';

function openReader(data, t, targetLineInPage = -1) {
  switchMode('reader');

  currentReaderTextId = data.text_id;
  currentReaderPage = data.page;
  currentReaderTotal = data.total_pages;
  currentReaderTitle = t.name;

  const titleEl = document.getElementById('reader-title');
  if(titleEl) titleEl.textContent = t.name;
  
  renderReaderPage(data, targetLineInPage);
}

function renderReaderPage(data, targetLineInPage = -1) {
  const pageInfo = document.getElementById('reader-page-info');
  if(pageInfo) pageInfo.textContent = `Page ${data.page} / ${data.total_pages}`;
  
  const prevBtn = document.getElementById('reader-prev-btn');
  if(prevBtn) prevBtn.disabled = data.page <= 1;
  
  const nextBtn = document.getElementById('reader-next-btn');
  if(nextBtn) nextBtn.disabled = data.page >= data.total_pages;

  const linesHtml = data.lines.map((l, i) => 
    `<div class="reader-line ${i === targetLineInPage ? 'highlight' : ''}" id="reader-line-${i}">${escapeHtml(l) || '&nbsp;'}</div>`
  ).join('');
  
  const contentEl = document.getElementById('reader-lines');
  if(contentEl) contentEl.innerHTML = linesHtml;
  
  const readerScroll = document.getElementById('reader-content');
  if(readerScroll) {
    if (targetLineInPage >= 0) {
      setTimeout(() => {
        const el = document.getElementById(`reader-line-${targetLineInPage}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    } else {
      readerScroll.scrollTop = 0;
    }
  }
}

async function fetchReaderPage(page) {
  document.getElementById('reader-loading').style.display = 'flex';
  document.getElementById('reader-lines').innerHTML = '';
  try {
    const res = await fetch(`${getApiUrl()}/api/text/${currentReaderTextId}?page=${page}&size=100`);
    if (res.ok) {
      const data = await res.json();
      currentReaderPage = data.page;
      renderReaderPage(data);
    }
  } finally {
    document.getElementById('reader-loading').style.display = 'none';
  }
}

document.getElementById('reader-prev-btn')?.addEventListener('click', () => {
  if (currentReaderPage > 1) fetchReaderPage(currentReaderPage - 1);
});
document.getElementById('reader-next-btn')?.addEventListener('click', () => {
  if (currentReaderPage < currentReaderTotal) fetchReaderPage(currentReaderPage + 1);
});
document.getElementById('reader-back-btn')?.addEventListener('click', () => {
  switchMode('explore');
});

document.getElementById('reader-content')?.addEventListener('mouseup', () => {
  const selection = window.getSelection();
  const text = selection.toString().trim();
  const btn = document.getElementById('reader-ask-btn');
  if (!btn) return;
  if (text.length > 0) {
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    btn.style.left = rect.left + (rect.width / 2) + 'px';
    btn.style.top = rect.top - 20 + 'px';
    btn.hidden = false;
    btn.onclick = () => {
      btn.hidden = true;
      selection.removeAllRanges();
      switchMode('chat');
      DOM.chatInput.value = `Explain this passage from ${currentReaderTitle}:\n\n"${text}"\n\nWhat is its meaning and significance?`;
      adjustInputHeight();
      handleSend();
    };
  } else {
    btn.hidden = true;
  }
});


// ── Chat ───────────────────────────────────────────────────────────────────
function sendSuggestion(btn) {
  DOM.chatInput.value = btn.textContent.trim();
  adjustInputHeight();
  handleSend();
}

function handleSend() {
  sendMessage();
}

async function sendMessage(truncateIndex = null) {
  const query = DOM.chatInput.value.trim();
  if (!query || STATE.isGenerating) return;

  STATE.userPrompts.push(query);
  STATE.promptIndex = -1;

  hideWelcome();
  appendUserMessage(query);
  DOM.chatInput.value = '';
  adjustInputHeight();
  updateCharCount();

  const modeRadio = document.querySelector('input[name="scholar-mode"]:checked');
  const mode      = modeRadio ? modeRadio.value : 'scholar';

  DOM.sourcesList.innerHTML   = '';
  DOM.sourcesPanel.style.display = 'none';

  const typingId = showTypingIndicator();
  STATE.isGenerating   = true;
  DOM.sendBtn.disabled = true;

  // Show deep research multi-step UI
  if (mode === 'deep') {
    await runDeepResearch(query, typingId, truncateIndex);
  } else {
    await streamChat(query, mode, typingId, truncateIndex);
  }
}

// ── Deep Research Mode ─────────────────────────────────────────────────────
async function runDeepResearch(query, typingId, truncateIndex = null) {
  try {
    const ctrl = new AbortController();
    const payload = {query, mode:'deep', session_id:CONFIG.sessionId, stream:true, model:CONFIG.model};
    if (truncateIndex !== null) payload.truncate_history_from_index = truncateIndex;
    
    const resp = await fetch(`${getApiUrl()}/api/chat`, {
      method:  'POST',
      headers: getApiHeaders({'Content-Type':'application/json', 'Accept':'text/event-stream'}),
      body:    JSON.stringify(payload),
      signal:  ctrl.signal,
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    removeTypingIndicator(typingId);

    // Create research progress panel
    const progressId = 'research-' + Date.now();
    DOM.messagesContainer.insertAdjacentHTML('beforeend', `
      <div class="message assistant deep-research" id="${progressId}">
        <div class="message-avatar research-avatar">R</div>
        <div class="message-content">
          <div class="research-status" id="${progressId}-status">
            <span class="research-spinner"></span> Initiating deep research…
          </div>
          <div class="research-sub-questions" id="${progressId}-sqs" style="display:none"></div>
          <div class="message-bubble" id="${progressId}-bubble"></div>
          <div class="message-actions" id="${progressId}-actions"></div>
        </div>
      </div>`);
    scrollToBottom();

    const statusEl = $(`${progressId}-status`);
    const sqsEl    = $(`${progressId}-sqs`);
    const bubbleEl = $(`${progressId}-bubble`);

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', accText = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        try {
          const evt = JSON.parse(raw);
          if (evt.type === 'status') {
            statusEl.innerHTML = `<span class="research-spinner"></span> ${escapeHtml(evt.message)}`;
          } else if (evt.type === 'sub_questions') {
            sqsEl.style.display = 'block';
            sqsEl.innerHTML = `<div class="sq-label">Research sub-questions</div>` +
              evt.questions.map((q,i) => `<div class="sq-item"><span class="sq-num">${i+1}</span>${escapeHtml(q)}</div>`).join('');
          } else if (evt.type === 'token') {
            accText += evt.content;
            if (accText.includes('[SUGGESTIONS]')) {
               const parts = accText.split('[SUGGESTIONS]');
               bubbleEl.innerHTML = renderMarkdown(parts[0]);
            } else {
               bubbleEl.innerHTML = renderMarkdown(accText);
            }
          } else if (evt.type === 'sources') {
            statusEl.style.display = 'none';
            renderSourcesWithMeta(evt.sources||[]);
          } else if (evt.type === 'done') {
            if (accText.includes('[SUGGESTIONS]')) {
               const parts = accText.split('[SUGGESTIONS]');
               const sugText = parts[1] || '';
               const suggestions = sugText.split('\n').map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(l => l.length > 0);
               
               const sugHtml = suggestions.map(s => `<button class="suggestion-pill" onclick="sendSuggestion(this)">${escapeHtml(s)}</button>`).join('');
               if (sugHtml) {
                 const sugDiv = document.createElement('div');
                 sugDiv.className = 'suggestions-container';
                 sugDiv.innerHTML = `<div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:4px;font-weight:600">Follow-up questions:</div>${sugHtml}`;
                 const msgEl = document.getElementById(progressId);
                 if(bubbleEl) bubbleEl.parentElement.appendChild(sugDiv);
               }
             }
              if (evt.grounding_quality) {
                const qStr = evt.grounding_quality;
                const badge = document.createElement('div');
                badge.className = `provenance-badge ${qStr}`;
                badge.innerHTML = qStr === 'grounded' ? 'Grounded' : qStr === 'partial' ? '⚠️ Partially Grounded' : 'General Knowledge';
                if (bubbleEl && bubbleEl.parentElement) {
                  bubbleEl.parentElement.insertBefore(badge, bubbleEl);
                }
              }
              addMessageActions($(`${progressId}-actions`), accText);
            STATE.historyCount += 2;
            updateMemoryBadge();
            fetchSessions();
          }
        } catch {}
      }
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    if (err.name !== 'AbortError') {
        appendErrorMessage(err.message);
        if (err.message.includes('upgrade')) {
            setTimeout(() => { window.location.href = '/pricing.html'; }, 2000);
        } else if (err.message.includes('Guest limit') || err.message.includes('Guest rate limit')) {
            setTimeout(() => { window.location.href = '/login.html'; }, 2000);
        }
    }
  } finally {
    STATE.isGenerating   = false;
    DOM.sendBtn.disabled = false;
    _resetScrollLock();
  }
}

// ── Standard Stream Chat ───────────────────────────────────────────────────
async function streamChat(query, mode, typingId, truncateIndex = null) {
  try {
    const payload = {query, mode, session_id:CONFIG.sessionId, stream:true, model:CONFIG.model};
    if (truncateIndex !== null) payload.truncate_history_from_index = truncateIndex;
    
    const resp = await fetch(`${getApiUrl()}/api/chat`, {
      method:  'POST',
      headers: getApiHeaders({'Content-Type':'application/json', 'Accept':'text/event-stream'}),
      body:    JSON.stringify(payload),
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({detail:resp.statusText}));
      throw new Error(e.detail||`HTTP ${resp.status}`);
    }

    removeTypingIndicator(typingId);
    const msgEl    = appendAssistantMessage('', true);
    const bubbleEl = msgEl.querySelector('.message-bubble');

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', accText = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream:true});
      const lines = buf.split('\n');
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        try {
          const evt = JSON.parse(raw);
          if (evt.type === 'token') {
            accText += evt.content;
            if (accText.includes('[SUGGESTIONS]')) {
               const parts = accText.split('[SUGGESTIONS]');
               bubbleEl.innerHTML = renderMarkdown(parts[0]);
            } else {
               bubbleEl.innerHTML = renderMarkdown(accText);
            }
          } else if (evt.type === 'sources') {
            renderSourcesWithMeta(evt.sources||[]);
          } else if (evt.type === 'done') {
             if (accText.includes('[SUGGESTIONS]')) {
               const parts = accText.split('[SUGGESTIONS]');
               const sugText = parts[1] || '';
               const suggestions = sugText.split('\n').map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(l => l.length > 0);
               
               const sugHtml = suggestions.map(s => `<button class="suggestion-pill" onclick="sendSuggestion(this)">${escapeHtml(s)}</button>`).join('');
               if (sugHtml) {
                 const sugDiv = document.createElement('div');
                 sugDiv.className = 'suggestions-container';
                 sugDiv.innerHTML = `<div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:4px;font-weight:600">Follow-up questions:</div>${sugHtml}`;
                 bubbleEl.parentElement.appendChild(sugDiv);
               }
            }
            if (evt.grounding_quality) {
               const qStr = evt.grounding_quality;
               const badge = document.createElement('div');
               badge.className = `provenance-badge ${qStr}`;
               badge.innerHTML = qStr === 'grounded' ? 'Grounded' : qStr === 'partial' ? '⚠️ Partially Grounded' : 'General Knowledge';
               if (bubbleEl && bubbleEl.parentElement) {
                 bubbleEl.parentElement.insertBefore(badge, bubbleEl);
               }
             }
            addMessageActions(msgEl.querySelector('.message-actions'), accText);
            if (evt.history_len) {
              STATE.historyCount = evt.history_len;
              updateMemoryBadge();
            }
            fetchSessions();
          } else if (evt.type === 'error') {
            appendErrorMessage(evt.message);
          }
        } catch {}
      }
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    if (err.name !== 'AbortError') appendErrorMessage(err.message);
  } finally {
    STATE.isGenerating   = false;
    DOM.sendBtn.disabled = false;
    _resetScrollLock();
  }
}

// ── Sanskrit Search ────────────────────────────────────────────────────────
async function searchSanskrit() {
  const query = DOM.sanskritInput?.value?.trim();
  if (!query) return;

  DOM.sanskritResults.innerHTML = `
    <div class="skt-loading">
      <div class="loading-spinner"></div>
      <span id="skt-search-status">Analyzing query and searching GRETIL corpus (${STATE.gretilTexts} scholarly texts)…</span>
    </div>`;

  try {
    const res  = await fetch(`${getApiUrl()}/api/sanskrit-search`, {
      method:'POST', headers: getApiHeaders({'Content-Type':'application/json', 'Accept':'text/event-stream'}),
      body: JSON.stringify({query, max_results:30}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        try {
          const evt = JSON.parse(raw);
          if (evt.type === 'query_translated') {
            const statusEl = document.getElementById('skt-search-status');
            if (statusEl) {
              statusEl.innerHTML = `Translated <strong>"${escapeHtml(evt.original)}"</strong> to Sanskrit terms: <em>${escapeHtml(evt.terms.join(', '))}</em>. Searching…`;
            }
          } else if (evt.type === 'search_complete') {
            renderSanskritResults(evt, evt.original || query);
          } else if (evt.type === 'translation_ready') {
            const tEl = document.getElementById(`skt-trans-${evt.result_index}`);
            if (tEl) {
              tEl.innerHTML = `<span class="trans-label">AI Translation:</span> ${escapeHtml(evt.translation)}`;
              tEl.classList.remove('loading');
              // Attach translation to the ask button
              const btn = document.getElementById(`skt-ask-${evt.result_index}`);
              if (btn) btn.dataset.translation = evt.translation;
            }
          }
        } catch (e) { console.error('SSE parse error', e); }
      }
    }
  } catch (err) {
    DOM.sanskritResults.innerHTML = `
      <div class="skt-error">
        <strong>Search failed:</strong> ${escapeHtml(err.message)}
        ${STATE.gretilTexts === 0 ? '<br><em>GRETIL corpus not yet loaded. Make sure the server is running.</em>' : ''}
      </div>`;
  }
}

function renderSanskritResults(data, originalQuery) {
  if (!data.results?.length) {
    DOM.sanskritResults.innerHTML = `
      <div class="skt-empty">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" style="margin-bottom:12px;opacity:0.3"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        <p>No matches found for "<strong>${escapeHtml(originalQuery)}</strong>" in ${data.corpus_size} texts.</p>
        <p style="margin-top:8px;font-size:0.8rem;color:var(--text-muted)">
          Try IAST transliteration (e.g. "śiva", "dharma", "yoga") or Devanagari.
        </p>
      </div>`;
    return;
  }

  // Attach flat index for DOM reference
  data.results.forEach((r, i) => r._index = i);

  const grouped = data.results.reduce((acc, r) => {
    (acc[r.text_name] = acc[r.text_name]||[]).push(r);
    return acc;
  }, {});

  DOM.sanskritResults.innerHTML = `
    <div class="skt-summary">
      Found <strong>${data.total}</strong> matches across <strong>${Object.keys(grouped).length}</strong> texts
      <span class="source-tier-badge">${data.source_tier}</span>
    </div>
    ${Object.entries(grouped).map(([name, hits]) => `
      <div class="skt-group">
        <div class="skt-group-header">
          <span class="skt-group-name">${escapeHtml(name)}</span>
          <span class="skt-meta">
            ${langBadge(hits[0]?.language)} ${biasBadge(hits[0]?.bias)} ${tradBadge(hits[0]?.tradition)}
          </span>
          <span class="skt-count">${hits.length} hit${hits.length!==1?'s':''}</span>
        </div>
        <div class="skt-edition">Edition: ${escapeHtml(hits[0]?.edition||'GRETIL')}</div>
        ${hits.map(h => `
          <div class="skt-result" id="skt-res-${h._index}">
            <div class="skt-ref">Line ${h.line_num} · ${escapeHtml(h.reference||'')}</div>
            <div class="skt-excerpt devanagari-text">${highlightQuery(escapeHtml(h.excerpt), data.query)}</div>
            ${h._index < 5 ? `
              <div class="skt-translation loading" id="skt-trans-${h._index}">
                <div class="loading-spinner" style="width:12px;height:12px;display:inline-block;border-width:2px;"></div>
                Translating via AI…
              </div>
            ` : ''}
            <button class="skt-ask-btn" id="skt-ask-${h._index}" onclick="askAboutSanskrit('${escapeHtml(h.text_name).replace(/'/g,"\\'")}','${escapeHtml(h.matched_line.slice(0,60)).replace(/'/g,"\\'")}', this)">
              Ask about this passage
            </button>
          </div>`).join('')}
      </div>`).join('')}`;
}

function askAboutSanskrit(textName, passage, btn) {
  const translation = btn ? btn.dataset.translation : null;
  switchMode('chat');
  DOM.chatInput.value = `Explain this Sanskrit passage from ${textName}: "${passage}"${translation ? `\n\nContext translation: "${translation}"` : ''}\n\nGive the meaning word-by-word, the full context in the text, and its significance.`;
  adjustInputHeight();
  handleSend();
}

// ── Find Instances ─────────────────────────────────────────────────────────
async function findInstances() {
  const query = DOM.instancesInput.value.trim();
  if (!query) return;

  DOM.instancesResults.innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;padding:40px;color:var(--text-muted);">
      <div class="loading-spinner"></div>
      <span>Searching GRETIL corpus + vector index…</span>
    </div>`;

  try {
    const res  = await fetch(`${getApiUrl()}/api/instances`, {
      method: 'POST',
      headers: getApiHeaders({'Content-Type':'application/json'}),
      body: JSON.stringify({query, max_results:100, model:CONFIG.model})
    });
    const data = await res.json();

    if (data.llm_answer) {
      DOM.instancesResults.innerHTML = `
        <div class="instances-note">
          Answered from Puranic knowledge base. 
          ${STATE.gretilTexts > 0 ? `GRETIL Sanskrit corpus (${STATE.gretilTexts} texts) also searched.` : ''}
        </div>
        <div class="message-bubble" style="border-radius:16px;padding:24px;">
          ${renderMarkdown(data.llm_answer)}
        </div>`;
    } else {
      renderInstancesResults(data.instances||[], query);
    }
  } catch (err) {
    DOM.instancesResults.innerHTML = `<div class="instances-placeholder"><p>Error: ${escapeHtml(err.message)}</p></div>`;
  }
}

function renderInstancesResults(instances, query) {
  if (!instances.length) {
    DOM.instancesResults.innerHTML = `
      <div class="instances-placeholder">
        <div class="placeholder-icon"></div>
        <p>No indexed results for "<strong>${escapeHtml(query)}</strong>"</p>
      </div>`;
    return;
  }
  const grouped = instances.reduce((acc,i) => {
    const k = i.text_name || i.purana || 'Unknown';
    (acc[k]=acc[k]||[]).push(i);
    return acc;
  },{});

  DOM.instancesResults.innerHTML = `
    <div class="results-summary">Found <strong>${instances.length}</strong> instances across <strong>${Object.keys(grouped).length}</strong> texts</div>
    ${Object.entries(grouped).sort((a,b)=>b[1].length-a[1].length).map(([name,items]) => `
      <div class="result-group">
        <div class="result-group-header">
          <span>${escapeHtml(name)}</span>
          ${langBadge(items[0]?.language)} ${biasBadge(items[0]?.bias)}
          <span class="result-group-count">${items.length} instance${items.length!==1?'s':''}</span>
        </div>
        ${items.map(inst => `
          <article class="result-card">
            <div class="result-ref">${escapeHtml(inst.reference||inst.ref||'')}</div>
            <div class="result-text">${highlightQuery(escapeHtml(inst.excerpt||inst.text||''), query)}</div>
          </article>`).join('')}
      </div>`).join('')}`;
}

// ── Source rendering with metadata badges ──────────────────────────────────
function renderSourcesWithMeta(sources) {
  if (!sources?.length) return;
  DOM.sourcesPanel.style.display = 'block';
  DOM.sourcesList.innerHTML = sources.map((src, i) => {
    const name    = src.text_name || src.purana || '';
    const ref     = src.reference || (src.line_num ? `Line ${src.line_num}` : '');
    const snippet = (src.excerpt || src.text || '').slice(0, 160);
    const citStr  = ref ? `${name} · ${ref}` : name;
    const textId  = src.text_id || src.purana_key || '';
    return `
    <div class="source-card" title="Click to open in Explore" onclick="openSourceInExplore('${escapeHtml(textId)}','${escapeHtml(name)}')">
      <div class="source-card-header">
        <div class="source-name">${escapeHtml(name)}</div>
        <div class="source-card-actions">
          <button class="src-btn src-btn-cite" title="Copy citation" onclick="event.stopPropagation();copyCitation('${escapeHtml(citStr)}',this)"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></button>
          <button class="src-btn src-btn-ask"  title="Ask about this passage" onclick="event.stopPropagation();askAboutSource('${escapeHtml(name)}','${escapeHtml(ref)}')"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></button>
        </div>
      </div>
      <div class="source-ref">${escapeHtml(ref)}</div>
      <div class="source-badges">
        ${langBadge(src.language)} ${biasBadge(src.bias)} ${tradBadge(src.tradition)}
        ${src.edition ? `<span class="source-badge edition-badge" title="${escapeHtml(src.edition)}">${escapeHtml(src.edition.slice(0,22))}</span>` : ''}
      </div>
      ${snippet ? `<div class="source-snippet">${escapeHtml(snippet)}…</div>` : ''}
    </div>`;
  }).join('');
  if (window._lucideRefresh) window._lucideRefresh();
}

// Open a source text in the Explore panel
function openSourceInExplore(textId, textName) {
  // Switch to explore mode
  switchMode('explore');

  // Find the matching text card and scroll to it
  setTimeout(() => {
    const grid = $('texts-grid');
    if (!grid) return;

    // Try to find and highlight the matching card
    const cards = grid.querySelectorAll('.text-card');
    let found = null;
    for (const card of cards) {
      const cardId   = card.dataset.id   || '';
      const cardName = card.dataset.name || card.querySelector('.text-name')?.textContent || '';
      if (
        (textId && cardId.toLowerCase().includes(textId.toLowerCase().replace(/_/g,' ').split(' ')[0])) ||
        (textName && cardName.toLowerCase().includes(textName.toLowerCase().split(' ')[0]))
      ) {
        found = card;
        break;
      }
    }

    if (found) {
      // Remove any prior highlight
      grid.querySelectorAll('.text-card.source-highlight').forEach(c => c.classList.remove('source-highlight'));
      found.classList.add('source-highlight');
      found.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      // Fallback: open reader directly if we have a text_id
      if (textId) openTextInReader(textId, textName);
    }
  }, 200);
}

// Open a text directly in the reader panel
async function openTextInReader(textId, textName) {
  try {
    const resp = await fetch(`${getApiUrl()}/api/text/${encodeURIComponent(textId)}?page=1&size=100`);
    if (!resp.ok) return;
    const data = await resp.json();
    const t = SACRED_TEXTS.find(x => x.id === textId) || { name: textName, icon: '' };
    openReader(data, t);
  } catch(e) { /* silently fail */ }
}

function copyCitation(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = '✅';
    btn.style.color = '#4caf50';
    setTimeout(() => { btn.textContent = orig; btn.style.color = ''; }, 1500);
  }).catch(() => {
    btn.textContent = '❌';
    setTimeout(() => { btn.innerHTML = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>'; }, 1500);
  });
}

function langBadge(lang) {
  if (!lang) return '';
  const colors = {Sanskrit:'#7c5cbf',Hindi:'#c45e2a',English:'#2a6db5'};
  const col = colors[lang]||'#555';
  return `<span class="source-badge" style="background:${col}20;color:${col};border:1px solid ${col}50">🇮🇳 ${lang}</span>`;
}
function biasBadge(bias) {
  if (!bias) return '';
  const ok = bias.startsWith('✅');
  return `<span class="source-badge ${ok?'bias-ok':'bias-warn'}">${bias.slice(0,20)}</span>`;
}
function tradBadge(trad) {
  if (!trad) return '';
  const colors = {shaiva:'#6B9FD4',vaishnava:'#E8C96B',shakta:'#D47B7B',nath:'#8E8E8E',advaita:'#7BC47B',vedic:'#C4B87B',darshana:'#A07BC4',mixed:'#C4965A'};
  const col = colors[trad] || '#8A7E65';
  return `<span class="source-badge trad-badge"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${col};margin-right:4px;vertical-align:middle;flex-shrink:0"></span>${trad}</span>`;
}

function askAboutSource(name, ref) {
  switchMode('chat');
  DOM.chatInput.value = `Explain this passage in detail: ${name}${ref?`, ${ref}`:''}`;
  adjustInputHeight();
  DOM.chatInput.focus();
}

// ── Message UI ─────────────────────────────────────────────────────────────
function hideWelcome() {
  const ws = $('welcome-screen');
  if (ws) ws.style.display = 'none';
}

function appendUserMessage(text, index) {
  const idx = index !== undefined ? index : STATE.historyCount;
  DOM.messagesContainer.insertAdjacentHTML('beforeend', `
    <div class="message user" data-index="${idx}">
      <div class="message-avatar user-avatar">P</div>
      <div class="message-content">
         <div class="message-bubble">
           <div class="user-text">${escapeHtml(text)}</div>
           <div class="user-actions-float">
             <button class="action-float-btn" onclick="resendUserMessage(this, ${idx})" title="Resend">↩</button>
             <button class="action-float-btn" onclick="editUserMessage(this, ${idx})" title="Edit"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
           </div>
         </div>
      </div>
    </div>`);
  scrollToBottom();
}

function editUserMessage(btn, idx) {
  const bubble = btn.closest('.message-bubble');
  const textEl = bubble.querySelector('.user-text');
  const currentText = textEl.textContent;
  
  bubble.innerHTML = `
    <textarea class="edit-textarea">${currentText}</textarea>
    <div class="edit-actions">
       <button class="btn btn-primary btn-sm" onclick="saveEditedMessage(this, ${idx})">Save & Resend</button>
       <button class="btn btn-secondary btn-sm" onclick="cancelEditMessage(this, \`${escapeHtml(currentText).replace(/`/g, '\\`')}\`, ${idx})">Cancel</button>
    </div>
  `;
}

function cancelEditMessage(btn, origText, idx) {
  const bubble = btn.closest('.message-bubble');
  bubble.innerHTML = `
    <div class="user-text">${origText}</div>
    <div class="user-actions-float">
      <button class="action-float-btn" onclick="resendUserMessage(this, ${idx})" title="Resend">↩</button>
      <button class="action-float-btn" onclick="editUserMessage(this, ${idx})" title="Edit"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
    </div>
  `;
}

function resendUserMessage(btn, idx) {
  const bubble = btn.closest('.message-bubble');
  const userMsgEl = bubble.closest('.message.user');
  const newText = bubble.querySelector('.user-text').textContent;
  
  let nextEl = userMsgEl.nextElementSibling;
  while(nextEl) {
    const toRemove = nextEl;
    nextEl = nextEl.nextElementSibling;
    toRemove.remove();
  }
  
  userMsgEl.remove();
  STATE.historyCount = idx;
  DOM.chatInput.value = newText;
  sendMessage(idx);
}

function saveEditedMessage(btn, idx) {
  const bubble = btn.closest('.message-bubble');
  const newText = bubble.querySelector('.edit-textarea').value.trim();
  if (!newText) return;
  
  const userMsgEl = bubble.closest('.message.user');
  let nextEl = userMsgEl.nextElementSibling;
  while(nextEl) {
    const toRemove = nextEl;
    nextEl = nextEl.nextElementSibling;
    toRemove.remove();
  }
  
  userMsgEl.remove();
  STATE.historyCount = idx;
  DOM.chatInput.value = newText;
  sendMessage(idx);
}

function appendAssistantMessage(text, streaming=false) {
  const id = `msg-${Date.now()}`;
  DOM.messagesContainer.insertAdjacentHTML('beforeend', `
    <div class="message assistant" id="${id}">
      <div class="message-avatar" style="font-family:var(--font-devanagari)">ॐ</div>
      <div class="message-content">
        <div class="message-bubble">${streaming?'<span class="streaming-cursor">▌</span>':renderMarkdown(text)}</div>
        <div class="message-actions"></div>
      </div>
    </div>`);
  scrollToBottom();
  return $(id);
}

function addMessageActions(el, text) {
  if (!el) return;
  el.innerHTML = `
    <button class="msg-action-btn" onclick="copyText(this)" title="Copy"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy</button>
    <button class="msg-action-btn" onclick="askDeeper(this)" title="Deep research"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v6M8 11h6"/></svg> Deep Research</button>
    <button class="msg-action-btn" onclick="searchSanskritFor(this)" title="Find in Sanskrit"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l6 6M5 14l6-6 2 2M2 6h20M7 2h10"/></svg> Sanskrit</button>`;
}

function appendErrorMessage(msg) {
  DOM.messagesContainer.insertAdjacentHTML('beforeend', `
    <div class="message assistant">
      <div class="message-avatar error-avatar">!</div>
      <div class="message-content">
        <div class="message-bubble" style="border-color:rgba(224,82,82,.4);color:var(--text-secondary)">${escapeHtml(msg)}</div>
      </div>
    </div>`);
  scrollToBottom();
}

function showTypingIndicator() {
  const id = `typing-${Date.now()}`;
  DOM.messagesContainer.insertAdjacentHTML('beforeend', `
    <div class="typing-indicator" id="${id}">
      <div class="message-avatar" style="font-family:var(--font-devanagari)">ॐ</div>
      <div class="typing-bubble">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    </div>`);
  scrollToBottom();
  return id;
}
function removeTypingIndicator(id) { $(id)?.remove(); }

// ── Message Action handlers ────────────────────────────────────────────────
async function copyText(btn) {
  const text = btn.closest('.message').querySelector('.message-bubble')?.innerText||'';
  try {
    await navigator.clipboard.writeText(text);
    showToast('Copied!', 'success');
  } catch { showToast('Copy failed','error'); }
}

function askDeeper(btn) {
  const text = btn.closest('.message').querySelector('.message-bubble')?.innerText?.slice(0,200)||'';
  DOM.chatInput.value = text;
  adjustInputHeight();
  // Switch to deep mode
  const deepRadio = document.getElementById('mode-deep');
  if (deepRadio) deepRadio.checked = true;
  switchMode('chat');
  handleSend();
}

function searchSanskritFor(btn) {
  const text = btn.closest('.message').querySelector('.message-bubble')?.innerText||'';
  // Extract first Sanskrit-ish word
  const match = text.match(/\b([A-ZĀĪŪṬḌṆŚṢ][a-zāīūṭḍṇśṣ]+)\b/);
  if (match) {
    switchMode('sanskrit');
    if (DOM.sanskritInput) DOM.sanskritInput.value = match[1];
    searchSanskrit();
  }
}

// ── Markdown ───────────────────────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return '';

  return text
    // Devanagari shlokas
    .replace(/^([ऀ-ॿ।॥\s]{10,})$/gm,
      m => `<span class="shloka">${escapeHtml(m.trim())}</span>`)

    // Citation: *(Text · Section · Ch. X)*
    .replace(/\*\(([^)]{4,120}(?:·|Purana|Gita|Sutra|Upanishad|Mahabharata|Ramayana|Veda|Samhita|Shastra|Sharma|Gorakh|Katha|Bhagavat)[^)]*)\)\*/g,
      (_,ref) => `<span class="citation-link" onclick="openCitationLink(event,'${ref.replace(/'/g,"\\'")}')"><em>${escapeHtml(ref)}</em></span>`)

    // Citation: (Text name)
    .replace(/\(([^)]{5,100}(?:Purana|Gita|Sutra|Upanishad|Mahabharata|Ramayana|Veda|Samhita|Shastra)[^)]*)\)/g,
      (_,ref) => `<span class="citation-link" onclick="openCitationLink(event,'${ref.replace(/'/g,"\\'")}')">${escapeHtml(ref)}</span>`)

    // Headings
    .replace(/^### (.+)$/gm, (_,h) => `<h3 class="md-h3">${h}</h3>`)
    .replace(/^## (.+)$/gm,  (_,h) => `<h2 class="md-h2">${h}</h2>`)

    // Bold / italic
    .replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>')
    .replace(/\*([^*\n]+)\*/g,'<em>$1</em>')

    // Blockquotes → styled as researched quotes
    .replace(/^> (.+)$/gm,
      (_,q) => `<blockquote class="researched-quote">${q}</blockquote>`)

    // Lists
    .replace(/^[•\-] (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`)

    // Code
    .replace(/`([^`]+)`/g,'<code>$1</code>')

    // Paragraphs
    .replace(/\n\n+/g,'</p><p>')
    .replace(/\n/g,'<br>')
    .replace(/^/,'<p>').replace(/$/,'</p>');
}

function openCitationLink(event, ref) {
  event.stopPropagation();
  const refLower = ref.toLowerCase();
  const match = SACRED_TEXTS.find(t =>
    refLower.includes(t.name.toLowerCase().split(' ')[0]) ||
    refLower.includes((t.id||'').replace(/_/g,' '))
  );
  if (match) {
    openSourceInExplore(match.id, match.name);
  } else {
    switchMode('chat');
    DOM.chatInput.value = `Explain this citation in detail: ${ref}`;
    adjustInputHeight();
    handleSend();
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
async function showCitationTooltip(event, textId, textName, ref) {
  const tooltip = document.getElementById('citation-tooltip');
  if (!tooltip) return;
  
  // Position tooltip near the click
  const rect = event.target.getBoundingClientRect();
  tooltip.style.left = `${Math.max(10, rect.left - 170 + rect.width/2)}px`;
  tooltip.style.top = `${rect.bottom + window.scrollY + 10}px`;
  
  document.getElementById('tooltip-title').textContent = ref;
  document.getElementById('tooltip-loading').style.display = 'flex';
  document.getElementById('tooltip-text-container').style.display = 'none';
  tooltip.hidden = false;
  
  try {
    const res = await fetch(`${getApiUrl()}/api/citation-lookup?ref=${encodeURIComponent(ref)}`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('tooltip-loading').style.display = 'none';
      document.getElementById('tooltip-text-container').style.display = 'block';
      document.getElementById('tooltip-sanskrit').textContent = data.sanskrit;
      document.getElementById('tooltip-translation').textContent = data.translation;
      
      const openBtn = document.getElementById('tooltip-open-doc');
      openBtn.onclick = () => {
        tooltip.hidden = true;
        openTextDetail(data.text_id, ref, data.line_num);
      };
    } else {
      throw new Error("Lookup failed");
    }
  } catch (e) {
    document.getElementById('tooltip-loading').style.display = 'none';
    document.getElementById('tooltip-text-container').style.display = 'block';
    document.getElementById('tooltip-sanskrit').textContent = "Text not found in exact corpus.";
    document.getElementById('tooltip-translation').textContent = "Click 'Open in Document' to read the full text or chat to explore further.";
    document.getElementById('tooltip-open-doc').onclick = () => {
      tooltip.hidden = true;
      openTextDetail(textId, ref);
    };
  }
}

// Close tooltip when clicking outside
document.addEventListener('click', (e) => {
  const tooltip = document.getElementById('citation-tooltip');
  if (tooltip && !tooltip.hidden && !tooltip.contains(e.target) && !e.target.closest('.citation')) {
    tooltip.hidden = true;
  }
});
document.getElementById('tooltip-close')?.addEventListener('click', () => {
  document.getElementById('citation-tooltip').hidden = true;
});

// ── Scroll-lock ─────────────────────────────────────────────────────────────
// Auto-scroll is paused the moment the user scrolls up during generation.
// A "↓ Jump to latest" pill appears so they can resume at will.
let _scrollLocked = false;

function scrollToBottom() {
  if (_scrollLocked) return;
  DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
}

function _initScrollLock() {
  const container = DOM.messagesContainer;

  // Create the jump pill (hidden by default)
  if (!$('scroll-jump-btn')) {
    const btn = document.createElement('button');
    btn.id        = 'scroll-jump-btn';
    btn.innerHTML = '↓ Jump to latest';
    btn.className = 'scroll-jump-btn';
    btn.setAttribute('aria-label', 'Jump to latest message');
    btn.addEventListener('click', () => {
      _scrollLocked = false;
      btn.classList.remove('visible');
      container.scrollTop = container.scrollHeight;
    });
    // Insert relative to the chat panel, not the scroll container
    const chatPanel = $('panel-chat') || document.body;
    chatPanel.appendChild(btn);
  }

  // Watch for intent to scroll upwards during generation
  const lockScrollHandler = () => {
    if (!STATE.isGenerating) return;
    const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;
    if (!atBottom) {
      _scrollLocked = true;
      const btn = $('scroll-jump-btn');
      if (btn) btn.classList.add('visible');
    }
  };

  container.addEventListener('wheel', lockScrollHandler, { passive: true });
  container.addEventListener('touchmove', lockScrollHandler, { passive: true });

  // Native scroll handler just for unlocking when reaching bottom
  container.addEventListener('scroll', () => {
    if (!STATE.isGenerating) return;
    const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;
    if (atBottom && _scrollLocked) {
      _scrollLocked = false;
      const btn = $('scroll-jump-btn');
      if (btn) btn.classList.remove('visible');
    }
  }, { passive: true });
}

// Hide the pill and reset lock when generation finishes
function _resetScrollLock() {
  _scrollLocked = false;
  const btn = $('scroll-jump-btn');
  if (btn) btn.classList.remove('visible');
}
function adjustInputHeight() {
  DOM.chatInput.style.height = 'auto';
  DOM.chatInput.style.height = Math.min(DOM.chatInput.scrollHeight, 200) + 'px';
}
function updateCharCount() {
  const n = DOM.chatInput.value.length;
  DOM.charCount.textContent = `${n}/2000`;
  DOM.charCount.style.color = n > 1800 ? 'var(--saffron)' : 'var(--text-muted)';
}
function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function highlightQuery(text, q) {
  if (!q||!text) return text;
  const words = q.toLowerCase().split(/\s+/).filter(w=>w.length>2);
  let r = text;
  words.forEach(w => { r = r.replace(new RegExp(`(${w})`, 'gi'), '<mark>$1</mark>'); });
  return r;
}
function showToast(msg, type='info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  DOM.toastContainer.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toast-out .3s ease forwards';
    el.addEventListener('animationend', () => el.remove());
  }, 3500);
}

// ── Settings ───────────────────────────────────────────────────────────────
function loadSettings() {
  if (DOM.apiUrlInput) DOM.apiUrlInput.value = CONFIG.apiUrl || getApiUrl();
  
  if (DOM.keyGroq) DOM.keyGroq.value = CONFIG.apiKeys.groq || '';
  if (DOM.keyTogether) DOM.keyTogether.value = CONFIG.apiKeys.together || '';
  if (DOM.keyDeepseek) DOM.keyDeepseek.value = CONFIG.apiKeys.deepseek || '';
  if (DOM.keyGemini) DOM.keyGemini.value = CONFIG.apiKeys.gemini || '';
  if (DOM.keyZhipu) DOM.keyZhipu.value = CONFIG.apiKeys.zhipu || '';

  // Ensure CONFIG.model is a valid value present in both selects
  const VALID_MODELS = [
    'auto', 'groq-llama-3.3-70b', 'groq-llama-3.1-8b-instant', 'gemini-2.5-flash',
    'deepseek-chat', 'deepseek-reasoner',
    'together-Qwen/Qwen2.5-72B-Instruct-Turbo',
    'together-meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo',
    'zhipu-glm-5.1',
  ];
  if (!VALID_MODELS.includes(CONFIG.model)) {
    CONFIG.model = 'auto';
    localStorage.setItem('purangpt_model', CONFIG.model);
  }

  const modelSelect = $('model-select');
  if (modelSelect) modelSelect.value = CONFIG.model;

  // const topbarModelSelect = $('topbar-model-select');
  // if (topbarModelSelect) topbarModelSelect.value = CONFIG.model;
}
function saveSettings() {
  const modelSelect      = $('model-select');

  CONFIG.apiUrl = DOM.apiUrlInput?.value?.trim() || '';
  localStorage.setItem('purangpt_api_url', CONFIG.apiUrl);

  CONFIG.apiKeys = {
    groq: DOM.keyGroq?.value?.trim() || '',
    together: DOM.keyTogether?.value?.trim() || '',
    deepseek: DOM.keyDeepseek?.value?.trim() || '',
    gemini: DOM.keyGemini?.value?.trim() || '',
    zhipu: DOM.keyZhipu?.value?.trim() || '',
  };
  localStorage.setItem('purangpt_keys', JSON.stringify(CONFIG.apiKeys));

  if (modelSelect && modelSelect.value) {
    CONFIG.model = modelSelect.value;
    localStorage.setItem('purangpt_model', CONFIG.model);
    // Keep topbar in sync
    // if (topbarModelSelect) topbarModelSelect.value = CONFIG.model;
  }

  DOM.settingsModal.hidden = true;
  showToast('Settings saved — model: ' + CONFIG.model, 'success');
  checkStatus();
}

// ── Events ─────────────────────────────────────────────────────────────────
function bindEvents() {
  DOM.btnNewChat?.addEventListener('click', createNewSession);
  DOM.modeBtns.forEach(b => b.addEventListener('click', () => switchMode(b.dataset.mode)));

  DOM.mobileMenuBtn?.addEventListener('click', () => {
    DOM.sidebar?.classList.add('open');
    DOM.sidebarScrim?.classList.add('open');
  });

  DOM.sidebarScrim?.addEventListener('click', () => {
    DOM.sidebar?.classList.remove('open');
    DOM.sidebarScrim?.classList.remove('open');
  });

  DOM.chatInput.addEventListener('input', () => { adjustInputHeight(); updateCharCount(); });
  DOM.chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { 
      e.preventDefault(); 
      sendMessage(); 
    }
    if (e.key === 'ArrowUp') {
      if (STATE.userPrompts.length > 0 && STATE.promptIndex < STATE.userPrompts.length - 1) {
        STATE.promptIndex++;
        DOM.chatInput.value = STATE.userPrompts[STATE.userPrompts.length - 1 - STATE.promptIndex];
        adjustInputHeight();
        updateCharCount();
        e.preventDefault();
      }
    }
    if (e.key === 'ArrowDown') {
      if (STATE.promptIndex > 0) {
        STATE.promptIndex--;
        DOM.chatInput.value = STATE.userPrompts[STATE.userPrompts.length - 1 - STATE.promptIndex];
        adjustInputHeight();
        updateCharCount();
        e.preventDefault();
      } else if (STATE.promptIndex === 0) {
        STATE.promptIndex = -1;
        DOM.chatInput.value = '';
        adjustInputHeight();
        updateCharCount();
        e.preventDefault();
      }
    }
  });
  DOM.sendBtn.addEventListener('click', sendMessage);

  DOM.suggestionCards.forEach(c => c.addEventListener('click', () => {
    DOM.chatInput.value = c.dataset.query;
    adjustInputHeight();
    updateCharCount();
    sendMessage();
  }));

  DOM.instancesSearchBtn?.addEventListener('click', findInstances);
  DOM.instancesInput?.addEventListener('keydown', e => { if (e.key==='Enter') findInstances(); });

  DOM.sanskritSearchBtn?.addEventListener('click', searchSanskrit);
  DOM.sanskritInput?.addEventListener('keydown', e => { if (e.key==='Enter') searchSanskrit(); });

  DOM.filterChips.forEach(c => c.addEventListener('click', () => {
    DOM.filterChips.forEach(x => x.classList.remove('active'));
    c.classList.add('active');
  }));

  DOM.settingsBtn?.addEventListener('click', () => { DOM.settingsModal.hidden = false; });
  DOM.settingsClose?.addEventListener('click', () => { DOM.settingsModal.hidden = true; });
  DOM.settingsSave?.addEventListener('click', saveSettings);
  DOM.settingsModal?.addEventListener('click', e => { if(e.target===DOM.settingsModal) DOM.settingsModal.hidden=true; });

  // Handle iOS Keyboard resizing
  if (window.Capacitor && window.Capacitor.Plugins.Keyboard) {
    const Keyboard = window.Capacitor.Plugins.Keyboard;
    Keyboard.addListener('keyboardWillShow', (info) => {
      document.body.style.paddingBottom = `${info.keyboardHeight}px`;
      scrollToBottom();
    });
    Keyboard.addListener('keyboardWillHide', () => {
      document.body.style.paddingBottom = '0px';
    });
  }

  DOM.clearMemoryBtn?.addEventListener('click', clearMemory);

  // Removed topbarModelSelect listener

  document.addEventListener('keydown', e => {
    if (e.key==='Escape' && !DOM.settingsModal?.hidden) DOM.settingsModal.hidden=true;
  });

  setInterval(checkStatus, 60_000);
}

document.addEventListener('DOMContentLoaded', init);

// Integration with auth.js
if (typeof onAuthStateChange === 'function') {
    onAuthStateChange((user, profile) => {
        const signInBtn = document.getElementById('btn-sign-in');
        const sidebarSignIn = document.getElementById('sidebar-sign-in');
        const profileBtn = document.getElementById('user-profile-btn');
        
        if (!user) {
            if(signInBtn) signInBtn.style.display = 'block';
            if(sidebarSignIn) sidebarSignIn.style.display = 'block';
            if(profileBtn) profileBtn.style.display = 'none';
            
            // Check if they are a guest
            if (localStorage.getItem('purangpt_guest') === 'true') {
                if (document.getElementById('messages-container').children.length === 0) {
                    const msgEl = appendAssistantMessage('', false);
                    msgEl.querySelector('.message-bubble').innerHTML = `
                        <div style="background: rgba(255,165,0,0.1); border: 1px solid rgba(255,165,0,0.3); padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                            <strong>Guest Session Active</strong><br>
                            You are signed in as a guest. You are limited to 10 free messages in this session, and your history will not be saved.
                        </div>
                    `;
                }
            }
        } else {
            if(signInBtn) signInBtn.style.display = 'none';
            if(sidebarSignIn) sidebarSignIn.style.display = 'none';
            if(profileBtn) {
                profileBtn.style.display = 'flex';
                document.getElementById('topbar-avatar').src = user.user_metadata?.avatar_url || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23666'%3E%3Cpath d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'/%3E%3C/svg%3E";
                if(profile && window.innerWidth > 600) {
                    document.getElementById('topbar-name').innerText = (user.user_metadata?.full_name || 'User').split(' ')[0];
                    document.getElementById('topbar-name').style.display = 'inline';
                    document.getElementById('topbar-plan').innerText = profile.role;
                }
            }
            
            // Load BYOK keys if authenticated
            if (profile) {
                getAuthHeaders().then(headers => {
                    fetch('/api/user/keys', { headers }).then(r => r.json()).then(data => {
                         // We don't overwrite user's local keys if they exist unless they are empty
                    }).catch(e => console.error("Could not fetch keys", e));
                });
            }
        }
    });
}
