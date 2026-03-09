/**
 * SystemaX Chat Widget  v1.0
 * ─────────────────────────
 * Standalone embeddable chat widget — zero dependencies, vanilla JS.
 * Exposes window.SystemXChat.
 *
 * Usage:
 *   <link rel="stylesheet" href="widget.css">
 *   <script src="widget.js"></script>
 *   <script>
 *     window.SystemXChat.init({
 *       tenantSlug: "my-company",
 *       apiBaseUrl: "https://api.example.com",
 *       title: "AI Yordamchi",
 *     });
 *   </script>
 */
(function (global, doc) {
  'use strict';

  // ── Defaults ────────────────────────────────────────────────────────────────

  var DEFAULTS = {
    title: 'AI Yordamchi',
    primaryColor: '#2563eb',
    welcomeMessage: "Salom! Sizga qanday yordam bera olaman?",
    leadCaptureMessage: "Mutaxassisimiz bilan bog\u2018lanish uchun ma\u2018lumotlaringizni qoldiring.",
    placeholder: 'Xabar yozing\u2026',
  };

  var LEAD_TRIGGER_INTENTS = ['measurement', 'operator'];
  var LEAD_TRIGGER_MIN_MESSAGES = 2;

  // ── Utilities ────────────────────────────────────────────────────────────────

  function genUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    // UUID v4 polyfill
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function getOrCreateSessionId(key) {
    try {
      var stored = localStorage.getItem(key);
      if (stored) return stored;
      var id = genUUID();
      localStorage.setItem(key, id);
      return id;
    } catch (_) {
      // localStorage unavailable (private browsing with strict settings)
      return genUUID();
    }
  }

  function escapeHtml(text) {
    var div = doc.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  function normalizePhone(raw) {
    var digits = raw.replace(/\D/g, '');
    if (/^998\d{9}$/.test(digits)) return '+' + digits;         // +998XXXXXXXXX
    if (/^0\d{9}$/.test(digits))   return '+998' + digits.slice(1); // 0XXXXXXXXX
    if (/^\d{9}$/.test(digits))    return '+998' + digits;      // bare 9 digits
    return null;  // invalid
  }

  function darkenHex(hex, amount) {
    // Subtract `amount` from each RGB channel, clamp to 0.
    var r = Math.max(0, parseInt(hex.slice(1, 3), 16) - amount);
    var g = Math.max(0, parseInt(hex.slice(3, 5), 16) - amount);
    var b = Math.max(0, parseInt(hex.slice(5, 7), 16) - amount);
    return '#' + [r, g, b].map(function (c) { return c.toString(16).padStart(2, '0'); }).join('');
  }

  // ── API ──────────────────────────────────────────────────────────────────────

  function apiPost(baseUrl, path, tenantSlug, body) {
    return fetch(baseUrl.replace(/\/$/, '') + path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-Slug': tenantSlug,
      },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          throw new Error(data.detail || ('HTTP ' + res.status));
        });
      }
      return res.json();
    });
  }

  // ── Widget singleton ─────────────────────────────────────────────────────────

  var SystemXChat = {
    _config: null,
    _sessionId: null,
    _el: {},
    _open: false,
    _loading: false,
    _leadCaptureShown: false,
    _messageCount: 0,
    _unreadCount: 0,
    _streaming: false,
    _streamBubble: null,

    // ── Public: init ──────────────────────────────────────────────────────────

    init: function (options) {
      if (this._config) {
        console.warn('SystemXChat: already initialized. Call _reset() first.');
        return;
      }
      if (!options || !options.tenantSlug) {
        console.error('SystemXChat: tenantSlug is required.');
        return;
      }
      if (!options.apiBaseUrl) {
        console.error('SystemXChat: apiBaseUrl is required.');
        return;
      }

      this._config = Object.assign({}, DEFAULTS, options);

      var storageKey = 'sx_session_' + this._config.tenantSlug;
      this._sessionId = getOrCreateSessionId(storageKey);

      this._injectStyles();
      this._buildDOM();
      this._attachEvents();

      if (this._config.welcomeMessage) {
        this._appendMessage('bot', this._config.welcomeMessage);
      }
    },

    // ── Public: reset (for demo page re-init) ────────────────────────────────

    _reset: function () {
      var root = doc.getElementById('sx-chat-root');
      if (root && root.parentNode) root.parentNode.removeChild(root);
      this._config = null;
      this._sessionId = null;
      this._el = {};
      this._open = false;
      this._loading = false;
      this._leadCaptureShown = false;
      this._messageCount = 0;
      this._unreadCount = 0;
      this._streaming = false;
      this._streamBubble = null;
    },

    // ── Style injection ───────────────────────────────────────────────────────

    _injectStyles: function () {
      var cfg = this._config;
      var dark = darkenHex(cfg.primaryColor, 30);
      var styleEl = doc.getElementById('sx-chat-style');
      if (!styleEl) {
        styleEl = doc.createElement('style');
        styleEl.id = 'sx-chat-style';
        doc.head.appendChild(styleEl);
      }
      styleEl.textContent =
        ':root{--sx-primary:' + cfg.primaryColor +
        ';--sx-primary-dark:' + dark + ';}';
    },

    // ── DOM construction ──────────────────────────────────────────────────────

    _buildDOM: function () {
      var cfg = this._config;

      // Root container
      var root = doc.createElement('div');
      root.id = 'sx-chat-root';

      // ── Chat window ──────────────────────────────────────────────────────
      var win = doc.createElement('div');
      win.id = 'sx-chat-window';
      win.setAttribute('role', 'dialog');
      win.setAttribute('aria-label', escapeHtml(cfg.title));
      win.style.display = 'none';

      // Header
      var header = doc.createElement('div');
      header.id = 'sx-chat-header';

      var titleEl = doc.createElement('span');
      titleEl.id = 'sx-chat-title';
      titleEl.textContent = cfg.title;

      var closeBtn = doc.createElement('button');
      closeBtn.id = 'sx-close-btn';
      closeBtn.setAttribute('aria-label', 'Yopish');
      closeBtn.innerHTML =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round">' +
        '<line x1="18" y1="6" x2="6" y2="18"/>' +
        '<line x1="6" y1="6" x2="18" y2="18"/></svg>';

      header.appendChild(titleEl);
      header.appendChild(closeBtn);

      // Messages area
      var messages = doc.createElement('div');
      messages.id = 'sx-messages';
      messages.setAttribute('role', 'log');
      messages.setAttribute('aria-live', 'polite');
      messages.setAttribute('aria-label', 'Chat xabarlari');

      // Lead capture section
      var leadCapture = doc.createElement('div');
      leadCapture.id = 'sx-lead-capture';
      leadCapture.style.display = 'none';

      var leadMsg = doc.createElement('p');
      leadMsg.id = 'sx-lead-msg';
      leadMsg.textContent = cfg.leadCaptureMessage;

      var leadName = doc.createElement('input');
      leadName.type = 'text';
      leadName.id = 'sx-lead-name';
      leadName.placeholder = 'Ismingiz';
      leadName.autocomplete = 'name';
      leadName.setAttribute('maxlength', '100');

      var leadPhone = doc.createElement('input');
      leadPhone.type = 'tel';
      leadPhone.id = 'sx-lead-phone';
      leadPhone.placeholder = '+998 XX XXX XX XX';
      leadPhone.autocomplete = 'tel';
      leadPhone.setAttribute('maxlength', '20');

      var leadActions = doc.createElement('div');
      leadActions.id = 'sx-lead-actions';

      var leadSubmit = doc.createElement('button');
      leadSubmit.id = 'sx-lead-submit';
      leadSubmit.className = 'sx-btn-primary';
      leadSubmit.textContent = 'Yuborish';

      var leadCancel = doc.createElement('button');
      leadCancel.id = 'sx-lead-cancel';
      leadCancel.className = 'sx-btn-secondary';
      leadCancel.textContent = 'Bekor qilish';

      leadActions.appendChild(leadSubmit);
      leadActions.appendChild(leadCancel);

      var leadStatus = doc.createElement('p');
      leadStatus.id = 'sx-lead-status';

      leadCapture.appendChild(leadMsg);
      leadCapture.appendChild(leadName);
      leadCapture.appendChild(leadPhone);
      leadCapture.appendChild(leadActions);
      leadCapture.appendChild(leadStatus);

      // Input area
      var inputArea = doc.createElement('div');
      inputArea.id = 'sx-input-area';

      var textarea = doc.createElement('textarea');
      textarea.id = 'sx-input';
      textarea.placeholder = cfg.placeholder;
      textarea.rows = 1;
      textarea.setAttribute('aria-label', 'Xabar maydoni');
      textarea.setAttribute('maxlength', '2000');

      var sendBtn = doc.createElement('button');
      sendBtn.id = 'sx-send-btn';
      sendBtn.setAttribute('aria-label', 'Yuborish');
      sendBtn.innerHTML =
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<line x1="22" y1="2" x2="11" y2="13"/>' +
        '<polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';

      var contactBtn = doc.createElement('button');
      contactBtn.id = 'sx-contact-btn';
      contactBtn.setAttribute('title', "Mutaxassis bilan bog\u2018lanish");
      contactBtn.textContent = 'Aloqa';

      inputArea.appendChild(textarea);
      inputArea.appendChild(sendBtn);
      inputArea.appendChild(contactBtn);

      win.appendChild(header);
      win.appendChild(messages);
      win.appendChild(leadCapture);
      win.appendChild(inputArea);

      // ── FAB ─────────────────────────────────────────────────────────────
      var fab = doc.createElement('button');
      fab.id = 'sx-fab';
      fab.setAttribute('aria-label', 'Chatni ochish');

      var fabIconOpen = doc.createElement('span');
      fabIconOpen.id = 'sx-fab-open';
      fabIconOpen.innerHTML =
        '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

      var fabIconClose = doc.createElement('span');
      fabIconClose.id = 'sx-fab-close';
      fabIconClose.style.display = 'none';
      fabIconClose.innerHTML =
        '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round">' +
        '<line x1="18" y1="6" x2="6" y2="18"/>' +
        '<line x1="6" y1="6" x2="18" y2="18"/></svg>';

      fab.appendChild(fabIconOpen);
      fab.appendChild(fabIconClose);

      root.appendChild(win);
      root.appendChild(fab);
      doc.body.appendChild(root);

      this._el = {
        root: root,
        win: win,
        messages: messages,
        fab: fab,
        fabIconOpen: fabIconOpen,
        fabIconClose: fabIconClose,
        input: textarea,
        sendBtn: sendBtn,
        closeBtn: closeBtn,
        contactBtn: contactBtn,
        leadCapture: leadCapture,
        leadName: leadName,
        leadPhone: leadPhone,
        leadSubmit: leadSubmit,
        leadCancel: leadCancel,
        leadStatus: leadStatus,
      };
    },

    // ── Event wiring ──────────────────────────────────────────────────────────

    _attachEvents: function () {
      var self = this;
      var el = this._el;

      el.fab.addEventListener('click', function () { self._toggleChat(); });
      el.closeBtn.addEventListener('click', function () { self._closeChat(); });

      el.sendBtn.addEventListener('click', function () { self._handleSend(); });
      el.input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          self._handleSend();
        }
      });
      // Auto-grow textarea up to 100px
      el.input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 100) + 'px';
      });

      el.contactBtn.addEventListener('click', function () { self._showLeadCapture(); });
      el.leadSubmit.addEventListener('click', function () { self._handleLeadSubmit(); });
      el.leadCancel.addEventListener('click', function () { self._hideLeadCapture(); });
    },

    // ── Chat open/close ───────────────────────────────────────────────────────

    _toggleChat: function () {
      if (this._open) this._closeChat(); else this._openChat();
    },

    _openChat: function () {
      this._open = true;
      this._unreadCount = 0;
      var badge = doc.getElementById('sx-fab-badge');
      if (badge) badge.style.display = 'none';
      this._el.win.style.display = 'flex';
      this._el.fabIconOpen.style.display = 'none';
      this._el.fabIconClose.style.display = '';
      this._el.fab.setAttribute('aria-label', 'Chatni yopish');
      this._scrollToBottom();
      this._el.input.focus();
    },

    _closeChat: function () {
      this._open = false;
      this._el.win.style.display = 'none';
      this._el.fabIconOpen.style.display = '';
      this._el.fabIconClose.style.display = 'none';
      this._el.fab.setAttribute('aria-label', 'Chatni ochish');
    },

    // ── Message sending ───────────────────────────────────────────────────────

    _handleSend: function () {
      var text = this._el.input.value.trim();
      if (!text || this._loading) return;
      this._el.input.value = '';
      this._el.input.style.height = 'auto';
      this._sendMessage(text);
    },

    _sendMessage: function (text) {
      this._appendMessage('user', text);
      this._messageCount++;
      this._setLoading(true);

      // Use streaming when ReadableStream + TextDecoder are available
      var supportsStream = (
        typeof ReadableStream !== 'undefined' &&
        typeof TextDecoder !== 'undefined' &&
        typeof fetch !== 'undefined'
      );
      if (supportsStream) {
        this._sendMessageStream(text);
      } else {
        this._sendMessageFetch(text);
      }
    },

    // ── Streaming path (SSE via fetch ReadableStream) ─────────────────────────

    _sendMessageStream: function (text) {
      var self = this;
      var cfg = this._config;

      self._streamBubble = self._createStreamBubble();
      self._streaming = true;

      fetch(cfg.apiBaseUrl.replace(/\/$/, '') + '/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Slug': cfg.tenantSlug,
        },
        body: JSON.stringify({ session_id: self._sessionId, message: text }),
      }).then(function (res) {
        if (!res.ok || !res.body) throw new Error('stream_unavailable');
        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buf = '';

        function read() {
          reader.read().then(function (result) {
            if (result.done) {
              self._finalizeStream();
              return;
            }
            buf += decoder.decode(result.value, { stream: true });
            var parts = buf.split('\n\n');
            buf = parts.pop();  // keep incomplete trailing chunk
            parts.forEach(function (part) {
              var line = part.trim();
              if (!line.startsWith('data: ')) return;
              try {
                var evt = JSON.parse(line.slice(6));
                self._handleStreamEvent(evt);
              } catch (_) {}
            });
            read();
          }).catch(function () { self._finalizeStream(/*error=*/true); });
        }
        read();
      }).catch(function () {
        // Streaming unavailable → fall back to standard non-stream POST
        self._removeStreamBubble();
        self._streaming = false;
        self._sendMessageFetch(text);
      });
    },

    _handleStreamEvent: function (evt) {
      if (evt.type === 'token') {
        this._appendStreamToken(evt.data);
      } else if (evt.type === 'done') {
        this._finalizeStream(false, evt.intent);
      } else if (evt.type === 'error') {
        this._finalizeStream(true, null, evt.message);
      }
    },

    _createStreamBubble: function () {
      var row = doc.createElement('div');
      row.className = 'sx-msg sx-msg-bot';
      var bubble = doc.createElement('div');
      bubble.className = 'sx-bubble';
      // Show loading dots while waiting for the first token
      bubble.innerHTML =
        '<div class="sx-loading">' +
        '<span></span><span></span><span></span></div>';
      row.appendChild(bubble);
      this._el.messages.appendChild(row);
      this._scrollToBottom();
      return { row: row, bubble: bubble, text: '' };
    },

    _appendStreamToken: function (token) {
      if (!this._streamBubble) return;
      var b = this._streamBubble;
      if (b.text === '') {
        b.bubble.innerHTML = '';  // Replace loading dots with first token
      }
      b.text += token;
      b.bubble.innerHTML = escapeHtml(b.text).replace(/\n/g, '<br>');
      this._scrollToBottom();
    },

    _removeStreamBubble: function () {
      if (this._streamBubble && this._streamBubble.row.parentNode) {
        this._streamBubble.row.parentNode.removeChild(this._streamBubble.row);
      }
      this._streamBubble = null;
    },

    _finalizeStream: function (isError, intent, errorMsg) {
      this._streaming = false;
      this._setLoading(false);
      if (isError) {
        this._removeStreamBubble();
        this._appendMessage('error', errorMsg || "Xatolik yuz berdi. Iltimos qayta urinib ko\u2018ring.");
      }
      this._streamBubble = null;
      // Lead capture trigger (same logic as non-stream)
      if (!isError &&
          !this._leadCaptureShown &&
          this._messageCount >= LEAD_TRIGGER_MIN_MESSAGES &&
          intent &&
          LEAD_TRIGGER_INTENTS.indexOf(intent) !== -1) {
        var self = this;
        setTimeout(function () { self._showLeadCapture(); }, 800);
      }
    },

    // ── Non-streaming fallback path (POST /api/chat/message) ─────────────────

    _sendMessageFetch: function (text) {
      var self = this;
      var cfg = this._config;

      var loadingEl = this._appendLoading();

      apiPost(cfg.apiBaseUrl, '/api/chat/message', cfg.tenantSlug, {
        session_id: self._sessionId,
        message: text,
      }).then(function (data) {
        self._removeEl(loadingEl);
        self._setLoading(false);

        var reply = (data && data.reply) ? data.reply : '';
        if (reply) self._appendMessage('bot', reply);

        var intent = data && data.intent;
        if (
          !self._leadCaptureShown &&
          self._messageCount >= LEAD_TRIGGER_MIN_MESSAGES &&
          intent &&
          LEAD_TRIGGER_INTENTS.indexOf(intent) !== -1
        ) {
          setTimeout(function () { self._showLeadCapture(); }, 800);
        }

      }).catch(function (err) {
        self._removeEl(loadingEl);
        self._setLoading(false);
        self._appendMessage('error', "Xatolik yuz berdi. Iltimos qayta urinib ko\u2018ring.");
        console.warn('[SystemXChat] API error:', err.message);
      });
    },

    // ── Message rendering ─────────────────────────────────────────────────────

    _appendMessage: function (role, text) {
      var row = doc.createElement('div');
      row.className = 'sx-msg sx-msg-' + role;

      var bubble = doc.createElement('div');
      bubble.className = 'sx-bubble';
      // Safe: escapeHtml then restore newlines as <br>
      bubble.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');

      row.appendChild(bubble);
      this._el.messages.appendChild(row);
      this._scrollToBottom();

      // Unread badge: increment when a bot message arrives while chat is closed
      if (role === 'bot' && !this._open) {
        this._unreadCount++;
        this._renderBadge();
      }

      return row;
    },

    _appendLoading: function () {
      var row = doc.createElement('div');
      row.className = 'sx-msg sx-msg-bot';
      row.innerHTML =
        '<div class="sx-bubble sx-loading">' +
        '<span></span><span></span><span></span>' +
        '</div>';
      this._el.messages.appendChild(row);
      this._scrollToBottom();
      return row;
    },

    _setLoading: function (state) {
      this._loading = state;
      this._el.sendBtn.disabled = state;
      this._el.input.disabled = state;
    },

    _removeEl: function (el) {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    },

    _scrollToBottom: function () {
      var m = this._el.messages;
      m.scrollTop = m.scrollHeight;
    },

    _renderBadge: function () {
      var fab = this._el.fab;
      var badge = doc.getElementById('sx-fab-badge');
      if (!badge) {
        fab.style.position = 'relative';
        badge = doc.createElement('span');
        badge.id = 'sx-fab-badge';
        badge.style.cssText =
          'position:absolute;top:-4px;right:-4px;' +
          'background:#ef4444;color:#fff;border-radius:50%;' +
          'width:18px;height:18px;font-size:11px;font-weight:700;' +
          'display:flex;align-items:center;justify-content:center;' +
          'pointer-events:none;line-height:1;';
        fab.appendChild(badge);
      }
      badge.textContent = this._unreadCount > 9 ? '9+' : String(this._unreadCount);
      badge.style.display = 'flex';
    },

    // ── Lead capture ──────────────────────────────────────────────────────────

    _showLeadCapture: function () {
      this._leadCaptureShown = true;
      this._el.leadCapture.style.display = 'block';
      this._el.leadName.focus();
      this._scrollToBottom();
    },

    _hideLeadCapture: function () {
      this._el.leadCapture.style.display = 'none';
      this._el.leadStatus.textContent = '';
      this._el.leadStatus.className = '';
      this._el.leadName.value = '';
      this._el.leadPhone.value = '';
    },

    _handleLeadSubmit: function () {
      var el = this._el;
      var name = el.leadName.value.trim();
      var phone = normalizePhone(el.leadPhone.value.trim());

      el.leadStatus.className = 'sx-status-error';

      if (!name || name.length < 2) {
        el.leadStatus.textContent = 'Iltimos, ismingizni kiriting.';
        el.leadName.focus();
        return;
      }
      if (!phone) {
        el.leadStatus.textContent = "Telefon raqamni to'g'ri kiriting (+998XXXXXXXXX).";
        el.leadPhone.focus();
        return;
      }

      var self = this;
      var cfg = this._config;

      el.leadSubmit.disabled = true;
      el.leadStatus.className = '';
      el.leadStatus.textContent = 'Yuborilmoqda\u2026';

      apiPost(cfg.apiBaseUrl, '/api/leads', cfg.tenantSlug, {
        name: name,
        phone: phone,  // E.164 normalized
        source: 'chat',
        channel_user_id: self._sessionId,
      }).then(function () {
        el.leadStatus.className = 'sx-status-ok';
        el.leadStatus.textContent = "Rahmat! Operatorimiz tez orada bog\u2018lanadi.";
        el.leadSubmit.disabled = false;
        self._appendMessage('bot', "Rahmat! Ma\u02bclumo tlaringizni qabul qildik. Tez orada bog\u2018lanamiz.");
        setTimeout(function () { self._hideLeadCapture(); }, 3000);
      }).catch(function (err) {
        el.leadStatus.className = 'sx-status-error';
        el.leadStatus.textContent = "Xatolik yuz berdi. Qayta urinib ko\u2018ring.";
        el.leadSubmit.disabled = false;
        console.warn('[SystemXChat] Lead submit error:', err.message);
      });
    },
  };

  global.SystemXChat = SystemXChat;

})(window, document);
