class ChatApp {
  constructor() {
    this.ws = null;
    this.sessionId = 'session_' + Date.now();
    this.currentCharName = '旺财';
    this.reconnectTimer = null;
    this.init();
  }

  init() {
    this.bindElements();
    this.bindEvents();
    this.handleResponsive();
    this.connectWebSocket();
  }

  bindElements() {
    this.sidebar = document.getElementById('sidebar');
    this.sidebarOverlay = document.getElementById('sidebarOverlay');
    this.openSidebarBtn = document.getElementById('openSidebar');
    this.closeSidebarBtn = document.getElementById('closeSidebar');
    this.chatMessages = document.getElementById('chatMessages');
    this.emptyState = document.getElementById('emptyState');
    this.chatInput = document.getElementById('chatInput');
    this.sendBtn = document.getElementById('sendBtn');
    this.statusIndicator = document.getElementById('statusIndicator');
    this.statusText = document.getElementById('statusText');
    this.currentCharNameEl = document.getElementById('currentCharName');
    this.currentCharDescEl = document.getElementById('currentCharDesc');
    this.toast = document.getElementById('toast');

    this.characterSelect = document.getElementById('characterSelect');
    this.charName = document.getElementById('charName');
    this.charDesc = document.getElementById('charDesc');
    this.charIdentity = document.getElementById('charIdentity');
    this.charTraits = document.getElementById('charTraits');
    this.charRules = document.getElementById('charRules');
    this.charKnowledge = document.getElementById('charKnowledge');

    this.maxContextLength = document.getElementById('maxContextLength');
    this.keepRecent = document.getElementById('keepRecent');
    this.memoryDigest = document.getElementById('memoryDigest');
    this.memoryKeyInfo = document.getElementById('memoryKeyInfo');

    this.skillsList = document.getElementById('skillsList');
    this.sessionsList = document.getElementById('sessionsList');

    this.modelPreset = document.getElementById('modelPreset');
    this.modelApiUrl = document.getElementById('modelApiUrl');
    this.modelName = document.getElementById('modelName');
    this.modelApiKey = document.getElementById('modelApiKey');
    this.modelTemperature = document.getElementById('modelTemperature');
    this.modelMaxTokens = document.getElementById('modelMaxTokens');
    this.testResult = document.getElementById('testResult');
    this.feishuTestResult = document.getElementById('feishuTestResult');
    this.feishuSendResult = document.getElementById('feishuSendResult');
    this.feishuLookupInput = document.getElementById('feishuLookupInput');
    this.feishuLookupBtn = document.getElementById('feishuLookupBtn');
    this.feishuLookupResult = document.getElementById('feishuLookupResult');

    this.feishuEnabled = document.getElementById('feishuEnabled');
    this.feishuAppId = document.getElementById('feishuAppId');
    this.feishuAppSecret = document.getElementById('feishuAppSecret');
    this.feishuReceiveId = document.getElementById('feishuReceiveId');
    this.feishuReceiveIdType = document.getElementById('feishuReceiveIdType');
  }

  bindEvents() {
    this.openSidebarBtn.addEventListener('click', () => this.openSidebar());
    this.closeSidebarBtn.addEventListener('click', () => this.closeSidebar());
    this.sidebarOverlay.addEventListener('click', () => this.closeSidebar());

    window.addEventListener('resize', () => this.handleResponsive());

    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      });
    });

    this.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    this.sendBtn.addEventListener('click', () => this.sendMessage());

    document.getElementById('saveCharacter').addEventListener('click', () => this.saveCharacter());
    document.getElementById('deleteCharacter').addEventListener('click', () => this.deleteCharacter());
    document.getElementById('newCharacter').addEventListener('click', () => this.newCharacter());
    this.characterSelect.addEventListener('change', () => this.switchCharacter());

    document.getElementById('generateDigest').addEventListener('click', () => this.generateDigest());
    document.getElementById('refreshMemory').addEventListener('click', () => this.refreshMemory());
    document.getElementById('clearMemory').addEventListener('click', () => this.clearMemory());

    document.getElementById('reloadSkills').addEventListener('click', () => this.reloadSkills());

    document.getElementById('saveModelConfig').addEventListener('click', () => this.saveModelConfig());
    document.getElementById('testModelBtn').addEventListener('click', () => this.testModel());
    this.modelPreset.addEventListener('change', () => this.applyModelPreset());

    document.getElementById('saveFeishuConfig').addEventListener('click', () => this.saveFeishuConfig());
    document.getElementById('testFeishuBtn').addEventListener('click', () => this.testFeishu());
    document.getElementById('sendTestMsgBtn').addEventListener('click', () => this.sendTestFeishuMsg());
    this.feishuLookupBtn.addEventListener('click', () => this.lookupFeishuUser());
  }

  connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    if (this.ws) {
      this.ws.close();
    }

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.setConnected(true);
      this.loadCharacters();
      this.loadConfig();
      this.loadSkills();
      this.loadFeishuConfig();
    };

    this.ws.onclose = () => {
      this.setConnected(false);
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (e) {
        console.error('Parse error:', e);
      }
    };
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 3000);
  }

  openSidebar() {
    this.sidebar.classList.add('open');
    this.sidebarOverlay.classList.add('show');
  }

  closeSidebar() {
    this.sidebar.classList.remove('open');
    this.sidebarOverlay.classList.remove('show');
  }

  handleResponsive() {
    if (window.innerWidth >= 1024) {
      this.sidebar.classList.add('open');
      this.sidebarOverlay.classList.remove('show');
    } else {
      this.sidebar.classList.remove('open');
      this.sidebarOverlay.classList.remove('show');
    }
  }

  setConnected(connected) {
    this.statusIndicator.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
    this.statusText.textContent = connected ? '已连接' : '已断开';
  }

  send(type, data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...data }));
    }
  }

  handleMessage(data) {
    switch (data.type) {
      case 'chunk':
        this.appendChunk(data.content);
        break;
      case 'done':
        this.finalizeMessage();
        break;
      case 'clear_stream':
        this.clearStream();
        break;
      case 'error':
        this.showError(data.message);
        break;
      case 'characters':
        this.renderCharacters(data.data);
        break;
      case 'character_switched':
        if (data.success) {
          this.showToast('已切换到角色：' + data.name);
          this.loadCharacterDetail(data.name);
        }
        break;
      case 'character_detail':
        this.fillCharacterForm(data.data);
        break;
      case 'character_saved':
        this.showToast('角色已保存');
        this.loadCharacters();
        break;
      case 'character_deleted':
        this.showToast(data.success ? '角色已删除' : '删除失败');
        this.loadCharacters();
        break;
      case 'config':
        this.fillConfig(data.data);
        break;
      case 'config_saved':
        this.showToast('配置已保存');
        break;
      case 'test_model_result':
        this.renderTestResult(data);
        break;
      case 'memory':
        this.renderMemory(data.data);
        break;
      case 'skills_list':
        this.renderSkills(data.data);
        break;
      case 'skills_reloaded':
        this.showToast('技能已重新加载');
        this.renderSkills(data.data);
        break;
      case 'sessions_list':
        this.renderSessions(data.data);
        break;
      case 'session_deleted':
        this.showToast(data.success ? '会话已删除' : '删除失败');
        this.send('get_sessions_list', {});
        break;
      case 'feishu_config':
        this.fillFeishuConfig(data.data);
        break;
      case 'feishu_config_saved':
        this.showToast('飞书配置已保存');
        break;
      case 'test_feishu_result':
        this.feishuTestResult.style.display = 'block';
        this.feishuTestResult.innerHTML = data.success
          ? '<strong style="color:var(--success)">✅ ' + data.msg + '</strong>'
          : '<strong style="color:var(--danger)">❌ ' + data.msg + '</strong>';
        break;
    }
  }

  sendMessage() {
    const text = this.chatInput.value.trim();
    if (!text) return;

    if (this.emptyState) {
      this.emptyState.style.display = 'none';
    }
    this.appendMessage('user', text);
    this.chatInput.value = '';
    this.chatInput.style.height = 'auto';

    this.appendMessage('assistant', '', true);
    this.send('chat', { message: text, session_id: this.sessionId });
  }

  renderContent(text) {
    if (!text) return '';
    text = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    text = text.replace(/\[IMG\](.*?)\[\/IMG\]/g, '<br><img src="$1" style="max-width:280px;max-height:280px;border-radius:8px;margin:4px 0;cursor:pointer" onclick="window.open(this.src)" loading="lazy"><br>');
    text = text.replace(/\n/g, '<br>');
    return text;
  }

  appendMessage(role, content, streaming = false) {
    if (streaming) {
      let existing = this.chatMessages.querySelector('.message.streaming');
      if (existing) {
        existing.innerHTML = '';
        existing.className = 'message ' + role + ' streaming';
        return existing;
      }
    }

    const div = document.createElement('div');
    div.className = 'message ' + role;
    if (streaming) div.classList.add('streaming');
    div.innerHTML = this.renderContent(content);
    this.chatMessages.appendChild(div);
    this.scrollToBottom();
    return div;
  }

  appendChunk(chunk) {
    let el = this.chatMessages.querySelector('.message.streaming');
    if (!el) {
      el = this.appendMessage('assistant', '', true);
    }
    el.innerHTML += this.renderContent(chunk);
    this.scrollToBottom();
  }

  clearStream() {
    const el = this.chatMessages.querySelector('.message.streaming');
    if (el) {
      el.innerHTML = '';
    }
  }

  finalizeMessage() {
    const el = this.chatMessages.querySelector('.message.streaming');
    if (el) {
      el.classList.remove('streaming');
    }
    this.scrollToBottom();
  }

  showError(msg) {
    const div = document.createElement('div');
    div.className = 'message system';
    div.textContent = '⚠️ ' + msg;
    this.chatMessages.appendChild(div);
    this.scrollToBottom();
  }

  scrollToBottom() {
    setTimeout(() => {
      this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }, 10);
  }

  showToast(msg) {
    this.toast.textContent = msg;
    this.toast.classList.add('show');
    setTimeout(() => this.toast.classList.remove('show'), 2500);
  }

  loadCharacters() {
    this.send('get_characters', {});
  }

  renderCharacters(chars) {
    this.characterSelect.innerHTML = '';
    chars.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.display_name;
      opt.selected = c.current;
      this.characterSelect.appendChild(opt);
    });

    const current = chars.find(c => c.current);
    if (current) {
      this.currentCharName = current.display_name;
      this.currentCharNameEl.textContent = current.display_name;
      this.currentCharDescEl.textContent = current.description;
      this.loadCharacterDetail(current.name);
    }
  }

  loadCharacterDetail(name) {
    this.send('get_character_detail', { name });
  }

  fillCharacterForm(profile) {
    if (!profile) return;
    this.charName.value = profile.name || '';
    this.charDesc.value = profile.description || '';
    this.charIdentity.value = profile.identity || '';
    this.charTraits.value = (profile.traits || []).join('、');
    this.charRules.value = (profile.rules || []).join('\n');
    this.charKnowledge.value = (profile.knowledge || []).join('\n');
  }

  switchCharacter() {
    const name = this.characterSelect.value;
    this.send('switch_character', { name });
  }

  saveCharacter() {
    const name = this.charName.value.trim();
    if (!name) {
      this.showToast('请输入角色名称');
      return;
    }
    const profile = {
      name: name,
      description: this.charDesc.value.trim(),
      identity: this.charIdentity.value.trim(),
      traits: this.charTraits.value.split(/[、,，]/).map(s => s.trim()).filter(Boolean),
      rules: this.charRules.value.split('\n').map(s => s.trim()).filter(Boolean),
      knowledge: this.charKnowledge.value.split('\n').map(s => s.trim()).filter(Boolean),
      example_dialogs: [],
    };
    this.send('save_character', { name, profile });
  }

  deleteCharacter() {
    const name = this.characterSelect.value;
    if (name === 'default') {
      this.showToast('不能删除默认角色');
      return;
    }
    if (confirm('确定删除角色"' + name + '"？')) {
      this.send('delete_character', { name });
    }
  }

  newCharacter() {
    this.charName.value = '新角色';
    this.charDesc.value = '';
    this.charIdentity.value = '';
    this.charTraits.value = '';
    this.charRules.value = '';
    this.charKnowledge.value = '';
  }

  loadConfig() {
    this.send('get_config', {});
  }

  fillConfig(config) {
    if (!config) return;
    if (config.llm) {
      this.modelApiUrl.value = config.llm.api_url || '';
      this.modelName.value = config.llm.model_name || '';
      this.modelApiKey.value = config.llm.api_key || '';
      this.modelTemperature.value = config.llm.temperature || 0.7;
      this.modelMaxTokens.value = config.llm.max_tokens || 2048;
    }
    if (config.memory) {
      this.maxContextLength.value = config.memory.max_context_length || 5000;
      this.keepRecent.value = config.memory.keep_recent_messages || 6;
    }
  }

  applyModelPreset() {
    const presets = {
      nvidia_llama:     { url: 'https://integrate.api.nvidia.com/v1', model: 'nvidia/llama-3.1-nemotron-70b-instruct' },
      nvidia_mistral:   { url: 'https://integrate.api.nvidia.com/v1', model: 'mistralai/mistral-large' },
      nvidia_deepseek:  { url: 'https://integrate.api.nvidia.com/v1', model: 'deepseek-ai/deepseek-r1' },
      nvidia_qwen:      { url: 'https://integrate.api.nvidia.com/v1', model: 'qwen/qwen2.5-coder-32b-instruct' },
      openai:           { url: 'https://api.openai.com/v1',           model: 'gpt-4o' },
      openai_gpt4:      { url: 'https://api.openai.com/v1',           model: 'gpt-4-turbo' },
      openai_o3:        { url: 'https://api.openai.com/v1',           model: 'o3-mini' },
      claude:           { url: 'https://api.anthropic.com/v1',        model: 'claude-3-5-sonnet-20241022' },
      deepseek:         { url: 'https://api.deepseek.com/v1',         model: 'deepseek-chat' },
      qwen:             { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
      ollama:           { url: 'http://127.0.0.1:11434/v1',           model: 'llama3' },
      llamacpp:         { url: 'http://127.0.0.1:8080/v1',            model: 'llama-2-7b-chat' },
    };
    const val = this.modelPreset.value;
    if (val && presets[val]) {
      this.modelApiUrl.value = presets[val].url;
      this.modelName.value = presets[val].model;
    }
  }

  saveModelConfig() {
    const config = {
      llm: {
        api_url: this.modelApiUrl.value.trim(),
        model_name: this.modelName.value.trim(),
        api_key: this.modelApiKey.value.trim(),
        temperature: parseFloat(this.modelTemperature.value) || 0.7,
        max_tokens: parseInt(this.modelMaxTokens.value) || 2048,
      },
      memory: {
        max_context_length: parseInt(this.maxContextLength.value) || 5000,
        keep_recent_messages: parseInt(this.keepRecent.value) || 6,
      },
    };
    this.send('save_config', { config });
  }

  testModel() {
    const config = {
      api_url: this.modelApiUrl.value.trim(),
      model_name: this.modelName.value.trim(),
      api_key: this.modelApiKey.value.trim(),
    };
    this.testResult.style.display = 'block';
    this.testResult.innerHTML = '⏳ 正在测试连接...';
    this.send('test_model', { config });
  }

  renderTestResult(data) {
    this.testResult.style.display = 'block';
    if (data.success) {
      this.testResult.innerHTML = `<strong style="color:var(--success)">✅ 连接成功</strong><br>模型回复：${data.response}`;
    } else {
      this.testResult.innerHTML = `<strong style="color:var(--danger)">❌ 连接失败</strong><br>${data.error}`;
    }
  }

  refreshMemory() {
    this.send('get_memory', { session_id: this.sessionId });
  }

  renderMemory(data) {
    if (!data) return;
    if (this.memoryDigest) {
      this.memoryDigest.textContent = data.digest || '暂无，点"生成重点摘要"按钮让 AI 总结';
    }
    this.memoryKeyInfo.innerHTML = '';
    if (data.key_info && data.key_info.length > 0) {
      data.key_info.forEach(k => {
        const li = document.createElement('li');
        li.textContent = k;
        this.memoryKeyInfo.appendChild(li);
      });
    } else {
      this.memoryKeyInfo.innerHTML = '<li style="color:var(--text-secondary)">暂无关键信息</li>';
    }

    const renderMemoList = (el, items, label) => {
      if (!el) return;
      el.innerHTML = '';
      if (!items || items.length === 0) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:12px">暂无记录</div>';
        return;
      }
      items.slice().reverse().forEach(m => {
        const d = document.createElement('div');
        d.style.cssText = 'padding:6px 0;border-bottom:1px solid var(--border);font-size:12px';
        const tags = m.tags && m.tags.length ? ' [' + m.tags.join(', ') + ']' : '';
        d.innerHTML = `<div style="color:var(--text-muted);font-size:10px">${m.time || ''}${tags}</div>`
                    + `<div style="color:var(--text-primary)">${m.content}</div>`;
        el.appendChild(d);
      });
    };
    renderMemoList(document.getElementById('sessionMemos'), data.memos, '会话');
    renderMemoList(document.getElementById('globalMemos'), data.global_memos, '长期');
  }

  generateDigest() {
    this.send('summarize_now', { session_id: this.sessionId });
    if (this.memoryDigest) {
      this.memoryDigest.textContent = '⏳ 正在生成摘要...';
    }
  }

  clearMemory() {
    if (confirm('确定清除当前会话记忆？')) {
      this.send('command', { command: 'clear_memory', params: { session_id: this.sessionId } });
      if (this.memoryDigest) this.memoryDigest.textContent = '已清除';
      this.memoryKeyInfo.innerHTML = '<li style="color:var(--text-secondary)">已清除</li>';
      this.showToast('记忆已清除');
    }
  }

  loadSkills() {
    this.send('get_skills', {});
  }

  loadFeishuConfig() {
    this.send('get_feishu_config', {});
  }

  renderSkills(skills) {
    if (!skills) return;
    this.skillsList.innerHTML = '';
    if (skills.length === 0) {
      this.skillsList.innerHTML = '<div style="color:var(--text-secondary)">暂无技能</div>';
      return;
    }
    skills.forEach(s => {
      const div = document.createElement('div');
      div.className = 'skill-item';
      div.innerHTML = `
        <div>
          <div class="skill-name">${s.name}</div>
          <div class="skill-desc">${s.description}</div>
          <div class="skill-triggers">触发: ${(s.triggers || []).join(', ')}</div>
        </div>
      `;
      this.skillsList.appendChild(div);
    });
  }

  reloadSkills() {
    this.send('reload_skills', {});
  }

  renderSessions(sessions) {
    if (!sessions) return;
    this.sessionsList.innerHTML = '';
    if (sessions.length === 0) {
      this.sessionsList.innerHTML = '<div style="color:var(--text-secondary)">暂无历史会话</div>';
      return;
    }
    sessions.forEach(s => {
      const div = document.createElement('div');
      div.className = 'session-item';
      div.innerHTML = `
        <div>
          <div class="session-id">${s.session_id}</div>
          <div class="session-meta">
            消息数: ${s.message_count} | ${s.has_summary ? '有摘要' : '无摘要'} | 关键信息: ${s.key_info_count}条
          </div>
        </div>
        <button class="btn danger" style="padding:4px 8px;font-size:11px" data-sid="${s.session_id}">删除</button>
      `;
      div.querySelector('button').addEventListener('click', () => {
        if (confirm('确定删除此会话？')) {
          this.send('delete_session', { session_id: s.session_id });
        }
      });
      this.sessionsList.appendChild(div);
    });
  }

  fillFeishuConfig(config) {
    if (!config) return;
    this.feishuEnabled.checked = config.enabled || false;
    this.feishuAppId.value = config.app_id || '';
    this.feishuAppSecret.placeholder = config.app_secret ? '已配置，留空则不修改' : '输入 App Secret';
    this.feishuAppSecret.value = '';
    this.feishuReceiveId.value = config.receive_id || '';
    this.feishuReceiveIdType.value = config.receive_id_type || 'open_id';
  }

  saveFeishuConfig() {
    const config = {
      enabled: this.feishuEnabled.checked,
      app_id: this.feishuAppId.value.trim(),
      app_secret: this.feishuAppSecret.value.trim(),
      receive_id: this.feishuReceiveId.value.trim(),
      receive_id_type: this.feishuReceiveIdType.value,
    };
    if (!config.app_secret) delete config.app_secret;
    this.send('save_feishu_config', { config });
  }

  testFeishu() {
    this.feishuTestResult.style.display = 'block';
    this.feishuTestResult.innerHTML = '⏳ 正在测试飞书连接...';
    this.send('test_feishu', {});
  }

  async lookupFeishuUser() {
    const el = this.feishuLookupResult;
    const input = this.feishuLookupInput.value.trim();
    if (!input) { el.style.display = 'block'; el.innerHTML = '<span style="color:var(--danger)">请输入邮箱或手机号</span>'; return; }
    el.style.display = 'block';
    el.innerHTML = '⏳ 查询中...';
    const isEmail = input.includes('@');
    try {
      const resp = await fetch('/api/feishu/lookup-user', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(isEmail ? { email: input } : { mobile: input }),
      });
      const data = await resp.json();
      if (data.success) {
        el.innerHTML = '<strong style="color:var(--success)">✅ 找到用户</strong><br>'
          + 'Open ID: <code>' + data.open_id + '</code><br>'
          + (data.user_id ? 'User ID: <code>' + data.user_id + '</code><br>' : '')
          + '<button class="btn" style="margin-top:6px;padding:4px 10px;font-size:12px" onclick="window.fillReceiveId(\'' + data.open_id + '\')">填入 receive_id</button>';
      } else {
        el.innerHTML = '<strong style="color:var(--danger)">❌ 查询失败</strong><br>' + (data.error || JSON.stringify(data));
      }
    } catch (e) {
      el.innerHTML = '<strong style="color:var(--danger)">❌ 请求异常</strong><br>' + e.message;
    }
  }

  async sendTestFeishuMsg() {
    const el = this.feishuSendResult;
    el.style.display = 'block';
    el.innerHTML = '⏳ 正在发送...';
    try {
      const resp = await fetch('/api/feishu/test-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: '测试消息 - 旺财通讯正常 ' + new Date().toLocaleString(),
          receiveId: this.feishuReceiveId.value.trim() || undefined,
          receiveIdType: this.feishuReceiveIdType.value || undefined,
        }),
      });
      const data = await resp.json();
      if (data.success) {
        el.innerHTML = '<strong style="color:var(--success)">✅ 发送成功</strong><br>'
          + '响应码: ' + data.response_code
          + '<br><pre style="font-size:11px;margin-top:4px">' + JSON.stringify(data.response, null, 2) + '</pre>';
      } else {
        el.innerHTML = '<strong style="color:var(--danger)">❌ 发送失败</strong><br>' + (data.error || JSON.stringify(data));
      }
    } catch (e) {
      el.innerHTML = '<strong style="color:var(--danger)">❌ 请求异常</strong><br>' + e.message;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const app = new ChatApp();
  window.fillReceiveId = (oid) => { app.feishuReceiveId.value = oid; };
});
