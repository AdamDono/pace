// Enhanced Quill Editor - Tables, Emojis, Embed, Source Code, 3D Models
// Usage: initQuillEnhanced('editor-id', 'textarea-id', 'placeholder')

function initQuillEnhanced(editorId, textareaId, placeholder = 'Start typing...') {
    // Register table module if available
    if (typeof QuillBetterTable !== 'undefined') {
        try {
            Quill.register({'modules/better-table': QuillBetterTable}, true);
        } catch(e) {}
    }

    // Emoji list
    const emojis = ['😀','😃','😄','😁','😅','😂','🙂','😊','😇','🥰','😍','😘','😋','😎','🤓','🤔','🤗','🤩','😏','😌','😔','😢','😭','😱','😡','🤬','💀','👍','👎','👏','🙏','💪','🎉','🎊','🎈','🎁','🏆','⭐','✨','💯','🔥','💧','❤️','💛','💚','💙','💜','🖤','🤍','📚','📖','📝','✏️','📊','📈','🎓','🎯','🎨','🎭','🎬','🎮','🎲','💻','📱','⚡','🌟','🚀'];

    // Create emoji picker modal if it doesn't exist
    if (!document.getElementById('emoji-modal')) {
        const modal = document.createElement('div');
        modal.id = 'emoji-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:20px;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.3);z-index:10000;max-width:400px;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:15px;">
                <h3 style="margin:0;font-size:16px;font-weight:bold;">😀 Pick Emoji</h3>
                <button onclick="closeEmojiModal()" style="background:none;border:none;font-size:24px;cursor:pointer;">&times;</button>
            </div>
            <div id="emoji-grid" style="display:grid;grid-template-columns:repeat(8,1fr);gap:8px;max-height:300px;overflow-y:auto;"></div>
        `;
        document.body.appendChild(modal);

        const overlay = document.createElement('div');
        overlay.id = 'emoji-overlay';
        overlay.style.cssText = 'display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9999;';
        overlay.onclick = closeEmojiModal;
        document.body.appendChild(overlay);

        // Populate emojis
        const grid = document.getElementById('emoji-grid');
        emojis.forEach(emoji => {
            const btn = document.createElement('div');
            btn.textContent = emoji;
            btn.style.cssText = 'font-size:24px;cursor:pointer;padding:8px;border-radius:6px;text-align:center;transition:all 0.2s;';
            btn.onmouseover = () => btn.style.background = '#f0f0f0';
            btn.onmouseout = () => btn.style.background = '';
            btn.onclick = () => insertEmoji(emoji);
            grid.appendChild(btn);
        });
    }

    // ── Video Modal ───────────────────────────────────────────────────────────
    if (!document.getElementById('video-modal')) {
        const modal = document.createElement('div');
        modal.id = 'video-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:26px;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.3);z-index:10001;width:520px;max-width:95vw;font-family:system-ui,sans-serif;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 style="margin:0;font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px;color:#111827;">
                    🎥 Insert YouTube Video
                </h3>
                <button onclick="closeVideoModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:#6b7280;">&times;</button>
            </div>
            
            <div style="margin-bottom:14px;">
                <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">YouTube Video Link *</label>
                <input id="video-modal-url" type="url" placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..." 
                    style="width:100%;padding:10px 12px;border:1.5px solid #d1d5db;border-radius:8px;font-size:14px;box-sizing:border-box;outline:none;"
                    oninput="handleVideoUrlChange(this.value)">
                <p id="video-modal-status" style="font-size:12px;margin:4px 0 0;color:#6b7280;">Paste any YouTube URL or video link</p>
            </div>

            <div style="margin-bottom:16px;">
                <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Video Title / Description (Displays alongside video)</label>
                <input id="video-modal-desc" type="text" placeholder="e.g. Master loops and conditionals in this short video" 
                    style="width:100%;padding:10px 12px;border:1.5px solid #d1d5db;border-radius:8px;font-size:14px;box-sizing:border-box;outline:none;">
            </div>

            <div style="display:flex;gap:10px;justify-content:flex-end;">
                <button onclick="closeVideoModal()" style="padding:9px 18px;background:#e5e7eb;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;color:#374151;">Cancel</button>
                <button onclick="insertVideoFromModal()" style="padding:9px 20px;background:#ef4444;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;display:flex;align-items:center;gap:6px;">
                    ▶️ Insert Video & Link
                </button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Create Embed modal if it doesn't exist
    if (!document.getElementById('embed-modal')) {
        const modal = document.createElement('div');
        modal.id = 'embed-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:30px;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.3);z-index:10000;width:500px;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
                <h3 style="margin:0;font-size:16px;font-weight:bold;">🔗 Embed Interactive Content</h3>
                <button onclick="closeEmbedModal()" style="background:none;border:none;font-size:24px;cursor:pointer;">&times;</button>
            </div>
            <p style="color:#666;font-size:14px;margin-bottom:8px;">Paste an embed URL or full <code>&lt;iframe&gt;</code> code:</p>
            <p style="color:#999;font-size:12px;margin-bottom:15px;">Supports: Lumi.education, H5P.org, YouTube embeds, or any iframe URL.</p>
            <textarea id="embed-input" placeholder="https://lumi.education/run/... or <iframe src=\"...\" ...></iframe>" style="width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;font-size:14px;margin-bottom:20px;min-height:100px;font-family:monospace;"></textarea>
            <div style="display:flex;gap:10px;justify-content:flex-end;">
                <button onclick="closeEmbedModal()" style="padding:10px 20px;background:#e5e7eb;border:none;border-radius:8px;cursor:pointer;font-weight:600;">Cancel</button>
                <button onclick="insertEmbed()" style="padding:10px 20px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;">Insert</button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // ── 3D Model Modal ────────────────────────────────────────────────────────
    if (!document.getElementById('model3d-modal')) {
        const modal = document.createElement('div');
        modal.id = 'model3d-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:30px;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.3);z-index:10000;width:520px;max-width:95vw;font-family:system-ui,sans-serif;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h3 style="margin:0;font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px;">
                    🧊 Insert 3D Model
                </h3>
                <button onclick="closeModel3DModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;">&times;</button>
            </div>

            <!-- Tab switcher -->
            <div style="display:flex;gap:4px;background:#f3f4f6;border-radius:10px;padding:4px;margin-bottom:20px;">
                <button id="model3d-tab-upload" onclick="switchModel3DTab('upload')"
                    style="flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:white;color:#1d4ed8;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
                    📁 Upload File
                </button>
                <button id="model3d-tab-url" onclick="switchModel3DTab('url')"
                    style="flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#6b7280;">
                    🔗 Paste URL
                </button>
            </div>

            <!-- Upload tab -->
            <div id="model3d-panel-upload">
                <div id="model3d-dropzone"
                    style="border:2px dashed #c7d2fe;border-radius:12px;padding:32px;text-align:center;background:#f5f3ff;cursor:pointer;transition:all 0.2s;"
                    onclick="document.getElementById('model3d-file-input').click()"
                    ondragover="event.preventDefault();this.style.borderColor='#6366f1';this.style.background='#ede9fe';"
                    ondragleave="this.style.borderColor='#c7d2fe';this.style.background='#f5f3ff';"
                    ondrop="handleModel3DDrop(event)">
                    <div style="font-size:36px;margin-bottom:8px;">🧊</div>
                    <p style="margin:0;font-weight:600;color:#4f46e5;font-size:14px;">Click to upload or drag & drop</p>
                    <p style="margin:4px 0 0;color:#9ca3af;font-size:12px;">Supports: .glb, .gltf, .obj</p>
                </div>
                <input type="file" id="model3d-file-input" accept=".glb,.gltf,.obj" style="display:none;" onchange="handleModel3DFile(this.files[0])">
                <div id="model3d-upload-status" style="margin-top:12px;display:none;"></div>
            </div>

            <!-- URL tab -->
            <div id="model3d-panel-url" style="display:none;">
                <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">3D Model URL or Embed Code</label>
                <textarea id="model3d-url-input" rows="4" placeholder="Paste a .glb/.gltf/.obj URL, a Sketchfab URL, or full &lt;iframe&gt; embed code here..."
                    style="width:100%;padding:12px;border:1.5px solid #e5e7eb;border-radius:8px;font-size:13px;outline:none;box-sizing:border-box;font-family:monospace;resize:vertical;"
                    onfocus="this.style.borderColor='#6366f1'" onblur="this.style.borderColor='#e5e7eb'"></textarea>
                <p style="color:#9ca3af;font-size:12px;margin:6px 0 0;">Supports: .glb, .gltf, .obj direct links — <em>or</em> paste a full Sketchfab/iframe embed snippet for direct insertion.</p>
            </div>

            <!-- Caption -->
            <div style="margin-top:16px;">
                <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Caption (optional)</label>
                <input id="model3d-caption-input" type="text" placeholder="E.g. Heart anatomy – rotate to explore"
                    style="width:100%;padding:10px;border:1.5px solid #e5e7eb;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;"
                    onfocus="this.style.borderColor='#6366f1'" onblur="this.style.borderColor='#e5e7eb'">
            </div>

            <!-- Height -->
            <div style="margin-top:12px;">
                <label style="font-size:13px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">Viewer Height</label>
                <select id="model3d-height-select" style="padding:10px;border:1.5px solid #e5e7eb;border-radius:8px;font-size:14px;outline:none;background:white;">
                    <option value="400">Small (400px)</option>
                    <option value="520" selected>Medium (520px)</option>
                    <option value="650">Large (650px)</option>
                    <option value="800">Full (800px)</option>
                </select>
            </div>

            <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:24px;">
                <button onclick="closeModel3DModal()" style="padding:10px 22px;background:#e5e7eb;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;">Cancel</button>
                <button id="model3d-insert-btn" onclick="insertModel3D()"
                    style="padding:10px 22px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;display:flex;align-items:center;gap:6px;">
                    🧊 Insert 3D Viewer
                </button>
            </div>
        `;
        document.body.appendChild(modal);
    }
    // ── End 3D Modal ──────────────────────────────────────────────────────────

    // Create HTML Source Code modal if it doesn't exist
    if (!document.getElementById('source-code-modal')) {
        const modal = document.createElement('div');
        modal.id = 'source-code-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:0;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.3);z-index:10000;width:90%;max-width:1200px;height:80vh;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:20px;border-bottom:1px solid #e5e7eb;">
                <h3 style="margin:0;font-size:18px;font-weight:bold;display:flex;align-items:center;gap:10px;">
                    <span style="font-size:24px;">&lt;/&gt;</span> Source Code
                </h3>
                <button onclick="closeSourceCodeModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:#666;">&times;</button>
            </div>
            <div id="html-editor-container" style="height:calc(80vh - 140px);border:none;"></div>
            <div style="display:flex;gap:10px;justify-content:flex-end;padding:20px;border-top:1px solid #e5e7eb;background:#f9fafb;">
                <button onclick="closeSourceCodeModal()" style="padding:10px 24px;background:#e5e7eb;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;">Cancel</button>
                <button onclick="applySourceCode()" style="padding:10px 24px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:14px;">Save</button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Initialize Quill
    const modules = {
        toolbar: {
            container: [
                [{ 'header': [1, 2, 3, 4, 5, 6, false] }],
                ['bold', 'italic', 'underline'],
                [{ 'color': [] }, { 'background': [] }],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                ['link', 'image', 'video'],
                ['emoji', 'table', 'embed', 'model3d', 'source'],
                ['clean']
            ],
            handlers: {
                'video': () => showVideoModal(quill),
                'emoji': () => showEmojiModal(quill),
                'table': () => insertTable(quill),
                'embed': () => showEmbedModal(quill),
                'model3d': () => showModel3DModal(quill),
                'source': () => showSourceCodeModal(quill)
            }
        }
    };
    
    // Add better-table if available
    if (typeof QuillBetterTable !== 'undefined') {
        modules['better-table'] = {
            operationMenu: {
                items: { unmergeCells: { text: 'Unmerge cells' } }
            }
        };
        modules.keyboard = {
            bindings: QuillBetterTable.keyboardBindings
        };
    }
    
    const quill = new Quill('#' + editorId, {
        theme: 'snow',
        placeholder: placeholder,
        modules: modules
    });

    const textarea = document.getElementById(textareaId);
    if (textarea && textarea.value) {
        quill.root.innerHTML = textarea.value;
    }

    // Automatically relocate toolbar to designated sticky container if present
    const stickySlot = document.querySelector(`[data-quill-toolbar-for="${editorId}"]`) ||
                       document.getElementById('sticky-quill-toolbar-slot');
    if (stickySlot) {
        const toolbarModule = quill.getModule('toolbar');
        if (toolbarModule && toolbarModule.container) {
            stickySlot.appendChild(toolbarModule.container);
        }
    }

    // Sync Quill content to textarea on change
    quill.on('text-change', function(delta, oldDelta, source) {
        if (!textarea) return;
        
        // If custom HTML flag is set, NEVER sync (preserve custom HTML)
        if (quill.root.getAttribute('data-custom-html') === 'true') {
            console.log('🔒 Custom HTML protected, not syncing');
            return; // Don't sync at all
        }
        
        // Normal sync only for user changes
        if (source === 'user') {
            textarea.value = quill.root.innerHTML;
        }
    });
    
    // Ensure content is synced on form submit
    const form = textarea ? textarea.closest('form') : null;
    if (form) {
        form.addEventListener('submit', (e) => {
            if (textarea) {
                // If custom HTML flag is set, DON'T override textarea
                if (!quill.root.getAttribute('data-custom-html')) {
                    textarea.value = quill.root.innerHTML;
                    console.log('📤 Normal sync on submit');
                } else {
                    console.log('📤 Preserving custom HTML on submit');
                }
                console.log('📤 Submitting content length:', textarea.value.length);
                console.log('📤 First 200 chars:', textarea.value.substring(0, 200));
            }
        });
    }

    // Store current quill instance
    window.currentQuill = quill;

    // Style the model3d toolbar button
    _styleModel3DButton();

    return quill;
}

// Helper: style the 🧊 button in the Quill toolbar
function _styleModel3DButton() {
    const apply = () => {
        const btns = document.querySelectorAll('.ql-model3d');
        btns.forEach(btn => {
            btn.title = 'Insert 3D Model (.glb, .gltf, .obj)';
            const style = window.getComputedStyle(btn, '::before');
            if (!style || !style.content || style.content === 'none' || style.content === '""' || style.content === 'normal') {
                btn.innerHTML = '🧊';
            }
        });
    };
    setTimeout(apply, 100);
    setTimeout(apply, 400);
}

// ─── Emoji helpers ────────────────────────────────────────────────────────────
function showEmojiModal(quill) {
    window.currentQuill = quill;
    document.getElementById('emoji-modal').style.display = 'block';
    document.getElementById('emoji-overlay').style.display = 'block';
}

function closeEmojiModal() {
    document.getElementById('emoji-modal').style.display = 'none';
    document.getElementById('emoji-overlay').style.display = 'none';
}

function insertEmoji(emoji) {
    if (window.currentQuill) {
        const range = window.currentQuill.getSelection(true);
        window.currentQuill.insertText(range.index, emoji);
        window.currentQuill.setSelection(range.index + emoji.length);
    }
    closeEmojiModal();
}

// ─── Table ────────────────────────────────────────────────────────────────────
function insertTable(quill) {
    if (typeof QuillBetterTable !== 'undefined') {
        const tableModule = quill.getModule('better-table');
        if (tableModule) {
            tableModule.insertTable(3, 3);
        }
    } else {
        alert('Table feature not available');
    }
}

// ─── Video helpers ────────────────────────────────────────────────────────────
function showVideoModal(quill) {
    window.currentQuill = quill;
    const urlInput = document.getElementById('video-modal-url');
    const descInput = document.getElementById('video-modal-desc');
    const status = document.getElementById('video-modal-status');
    if (urlInput) urlInput.value = '';
    if (descInput) descInput.value = '';
    if (status) {
        status.innerHTML = 'Paste any YouTube URL or video link';
        status.style.color = '#6b7280';
    }
    const modal = document.getElementById('video-modal');
    if (modal) modal.style.display = 'block';
    const overlay = document.getElementById('emoji-overlay');
    if (overlay) overlay.style.display = 'block';
    if (urlInput) setTimeout(() => urlInput.focus(), 60);
}

function closeVideoModal() {
    const modal = document.getElementById('video-modal');
    if (modal) modal.style.display = 'none';
    const overlay = document.getElementById('emoji-overlay');
    if (overlay) overlay.style.display = 'none';
}

function handleVideoUrlChange(val) {
    const status = document.getElementById('video-modal-status');
    if (!status) return;
    val = (val || '').trim();
    if (!val) {
        status.innerHTML = 'Paste any YouTube URL or video link';
        status.style.color = '#6b7280';
        return;
    }
    let vId = null;
    if (val.includes('youtube.com/watch?v=')) {
        vId = val.split('watch?v=')[1].split('&')[0];
    } else if (val.includes('youtu.be/')) {
        vId = val.split('youtu.be/')[1].split('?')[0].split('&')[0];
    } else if (val.includes('youtube.com/embed/')) {
        vId = val.split('embed/')[1].split('?')[0].split('&')[0];
    }
    if (vId) {
        status.innerHTML = `✅ YouTube video detected (ID: <code>${vId}</code>). Player & clickable link will display with text!`;
        status.style.color = '#16a34a';
    } else if (val.startsWith('http')) {
        status.innerHTML = 'ℹ️ Video link ready to embed.';
        status.style.color = '#2563eb';
    }
}

function insertVideoFromModal() {
    const rawUrl = (document.getElementById('video-modal-url').value || '').trim();
    const desc = (document.getElementById('video-modal-desc').value || '').trim();
    if (!rawUrl || !window.currentQuill) return;

    let embedUrl = rawUrl;
    let isYouTube = false;

    if (rawUrl.includes('youtube.com/watch?v=')) {
        const vId = rawUrl.split('watch?v=')[1].split('&')[0];
        embedUrl = `https://www.youtube.com/embed/${vId}`;
        isYouTube = true;
    } else if (rawUrl.includes('youtu.be/')) {
        let vId = rawUrl.split('youtu.be/')[1];
        if (vId.includes('?')) vId = vId.split('?')[0];
        if (vId.includes('&')) vId = vId.split('&')[0];
        embedUrl = `https://www.youtube.com/embed/${vId}`;
        isYouTube = true;
    } else if (rawUrl.includes('youtube.com/embed/')) {
        embedUrl = rawUrl;
        isYouTube = true;
    }

    const range = window.currentQuill.getSelection(true);
    const index = range ? range.index : window.currentQuill.getLength();

    let captionHtml = desc 
        ? `<p class="ql-align-center" style="text-align: center; margin: 18px 0 8px 0; font-size: 15px; color: #111827;">🎥 <strong>Watch:</strong> <span style="color: #111827; font-style: italic;">${desc}</span></p>`
        : '';

    let videoHtml = `${captionHtml}<div class="ql-video-wrapper" style="width: 100%; max-width: 800px; margin: 0 auto 18px auto; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); background: #000;"><iframe src="${embedUrl}" class="ql-video" style="width: 100%; height: 100%; border: 0;" frameborder="0" allowfullscreen="true" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe></div><p><br></p>`;

    window.currentQuill.clipboard.dangerouslyPasteHTML(index, videoHtml);
    window.currentQuill.root.setAttribute('data-custom-html', 'true');

    // Sync to textarea
    const textarea = document.getElementById('content-editor') ||
                     document.getElementById('content') ||
                     document.getElementById('announcement-content') ||
                     document.getElementById('course-description');
    if (textarea) {
        textarea.value = window.currentQuill.root.innerHTML;
    }

    closeVideoModal();
}

// ─── Embed helpers ────────────────────────────────────────────────────────────
function showEmbedModal(quill) {
    window.currentQuill = quill;
    document.getElementById('embed-modal').style.display = 'block';
    document.getElementById('emoji-overlay').style.display = 'block';
}

function closeEmbedModal() {
    document.getElementById('embed-modal').style.display = 'none';
    document.getElementById('emoji-overlay').style.display = 'none';
    document.getElementById('embed-input').value = '';
}

function insertEmbed() {
    const input = document.getElementById('embed-input').value.trim();
    if (!input || !window.currentQuill) return;

    let url = input;
    // Extract URL from iframe tag if the user pasted full iframe HTML
    if (input.includes('<iframe')) {
        const match = input.match(/src=["']([^"']+)["']/);
        if (match) url = match[1];
    }

    // Auto-convert YouTube links to embed format
    if (url.includes('youtube.com/watch?v=')) {
        const vId = url.split('watch?v=')[1].split('&')[0];
        url = `https://www.youtube.com/embed/${vId}`;
    } else if (url.includes('youtu.be/')) {
        let vId = url.split('youtu.be/')[1];
        if (vId.includes('?')) vId = vId.split('?')[0];
        if (vId.includes('&')) vId = vId.split('&')[0];
        url = `https://www.youtube.com/embed/${vId}`;
    }

    const range = window.currentQuill.getSelection(true);
    const embedCode = `<div class="h5p-embed-container" style="position:relative;width:100%;padding-bottom:56.25%;height:0;overflow:hidden;margin:20px 0;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.1);background:#f9fafb;"><iframe src="${url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen allow="geolocation *; microphone *; camera *; midi *; encrypted-media *" title="Embedded Interactive Content"></iframe></div><p><br></p>`;

    // Insert the HTML
    window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, embedCode);

    // Mark as custom HTML to prevent Quill from stripping styles
    window.currentQuill.root.setAttribute('data-custom-html', 'true');

    // Update the hidden textarea immediately
    const textarea = document.getElementById('content-editor') ||
                     document.getElementById('content') ||
                     document.getElementById('announcement-content') ||
                     document.getElementById('course-description');
    if (textarea) {
        textarea.value = window.currentQuill.root.innerHTML;
        console.log('✅ Embed inserted and textarea updated');
    }

    console.log('✅ Embed URL:', url);
    closeEmbedModal();
}

// ─── 3D Model helpers ─────────────────────────────────────────────────────────
let _model3dActiveTab = 'upload';
let _model3dUploadedUrl = null; // set after file upload

function showModel3DModal(quill) {
    window.currentQuill = quill;
    _model3dUploadedUrl = null;
    // Reset UI
    const urlInput = document.getElementById('model3d-url-input');
    if (urlInput) urlInput.value = '';
    document.getElementById('model3d-caption-input').value = '';
    document.getElementById('model3d-height-select').value = '520';
    document.getElementById('model3d-upload-status').style.display = 'none';
    document.getElementById('model3d-upload-status').innerHTML = '';
    document.getElementById('model3d-file-input').value = '';
    switchModel3DTab('upload');
    document.getElementById('model3d-modal').style.display = 'block';
    document.getElementById('emoji-overlay').style.display = 'block';
}

function closeModel3DModal() {
    document.getElementById('model3d-modal').style.display = 'none';
    document.getElementById('emoji-overlay').style.display = 'none';
}

function switchModel3DTab(tab) {
    _model3dActiveTab = tab;
    const uploadPanel = document.getElementById('model3d-panel-upload');
    const urlPanel = document.getElementById('model3d-panel-url');
    const tabUpload = document.getElementById('model3d-tab-upload');
    const tabUrl = document.getElementById('model3d-tab-url');

    if (tab === 'upload') {
        uploadPanel.style.display = 'block';
        urlPanel.style.display = 'none';
        tabUpload.style.cssText = 'flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:white;color:#1d4ed8;box-shadow:0 1px 3px rgba(0,0,0,0.1);';
        tabUrl.style.cssText = 'flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#6b7280;';
    } else {
        uploadPanel.style.display = 'none';
        urlPanel.style.display = 'block';
        tabUpload.style.cssText = 'flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#6b7280;';
        tabUrl.style.cssText = 'flex:1;padding:8px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;background:white;color:#1d4ed8;box-shadow:0 1px 3px rgba(0,0,0,0.1);';
    }
}

function handleModel3DDrop(event) {
    event.preventDefault();
    const dz = document.getElementById('model3d-dropzone');
    dz.style.borderColor = '#c7d2fe';
    dz.style.background = '#f5f3ff';
    const file = event.dataTransfer.files[0];
    if (file) handleModel3DFile(file);
}

function handleModel3DFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['glb','gltf','obj'].includes(ext)) {
        alert('Only .glb, .gltf, or .obj files are supported.');
        return;
    }
    // Show uploading state
    const status = document.getElementById('model3d-upload-status');
    status.style.display = 'block';
    status.innerHTML = `<div style="display:flex;align-items:center;gap:8px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:10px;font-size:13px;color:#0369a1;">
        <span style="animation:spin 1s linear infinite;display:inline-block;">⏳</span>
        Uploading <strong>${file.name}</strong>...
    </div>`;
    document.getElementById('model3d-insert-btn').disabled = true;

    // Cache local blob/file in memory on parent window
    window._quill3dBlobs = window._quill3dBlobs || {};
    const localBlobUrl = URL.createObjectURL(file);
    window._quill3dBlobs[localBlobUrl] = file;
    window._lastUploaded3DFile = file;

    // Figure out the upload URL from the page context
    let uploadUrl = window._quill3dUploadUrl || null;
    if (!uploadUrl) {
        const match = window.location.pathname.match(/\/course\/(\d+)(?:\/module\/\d+)?\/section\/(\d+)/);
        if (match) {
            uploadUrl = `/teacher/course/${match[1]}/section/${match[2]}/quill-upload-3d`;
        }
    }

    if (!uploadUrl) {
        _model3dUploadedUrl = localBlobUrl;
        status.innerHTML = `<div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:10px;font-size:13px;color:#92400e;">
            ⚠️ Using local file preview.
        </div>`;
        document.getElementById('model3d-insert-btn').disabled = false;
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    const csrfToken = document.querySelector('input[name="csrf_token"]') ?
        document.querySelector('input[name="csrf_token"]').value : '';
    if (csrfToken) formData.append('csrf_token', csrfToken);

    fetch(uploadUrl, {
        method: 'POST',
        headers: csrfToken ? {'X-CSRFToken': csrfToken} : {},
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            _model3dUploadedUrl = data.url;
            window._quill3dBlobs[data.url] = file;
            status.innerHTML = `<div style="display:flex;align-items:center;gap:8px;background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:10px;font-size:13px;color:#166534;">
                ✅ <strong>${file.name}</strong> uploaded successfully!
            </div>`;
        } else {
            _model3dUploadedUrl = localBlobUrl;
            status.innerHTML = `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px;font-size:13px;color:#991b1b;">
                ⚠️ Upload failed (${data.message}), using local file.
            </div>`;
        }
        document.getElementById('model3d-insert-btn').disabled = false;
    })
    .catch(err => {
        _model3dUploadedUrl = localBlobUrl;
        status.innerHTML = `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px;font-size:13px;color:#991b1b;">
            ⚠️ Upload error (${err.message}), using local file.
        </div>`;
        document.getElementById('model3d-insert-btn').disabled = false;
    });
}

function insertModel3D() {
    if (!window.currentQuill) return;

    let rawInput = '';
    if (_model3dActiveTab === 'upload') {
        rawInput = _model3dUploadedUrl || '';
    } else {
        rawInput = (document.getElementById('model3d-url-input').value || '').trim();
    }

    if (!rawInput) {
        alert(_model3dActiveTab === 'upload'
            ? 'Please upload a 3D file first.'
            : 'Please paste a 3D model URL or embed code.');
        return;
    }

    const caption = (document.getElementById('model3d-caption-input').value || '').trim();
    const height = document.getElementById('model3d-height-select').value || '520';

    // ── Detect if input is iframe HTML or an embed URL ───────────────────────
    const isIframeHtml = rawInput.trimStart().startsWith('<');
    const isEmbedUrl = /sketchfab\.com|lumi\.education|h5p\.org|marmoset\.co|p3d\.in|vectary\.com/i.test(rawInput);

    if (isIframeHtml || isEmbedUrl) {
        closeModel3DModal();

        let iframeEl = '';

        if (isIframeHtml) {
            // Extract ONLY the <iframe> element and discard any <p> or <a> attribution blocks
            const tmp = document.createElement('div');
            tmp.innerHTML = rawInput;
            const iframe = tmp.querySelector('iframe');
            if (iframe) {
                iframe.setAttribute('width', '100%');
                iframe.setAttribute('height', height);
                iframe.setAttribute('frameborder', '0');
                iframe.setAttribute('allowfullscreen', 'true');
                iframe.setAttribute('allow', 'autoplay; fullscreen; xr-spatial-tracking');
                iframe.style.width = '100%';
                iframe.style.height = height + 'px';
                iframe.style.display = 'block';
                iframe.style.border = 'none';
                iframeEl = iframe.outerHTML;
            } else {
                iframeEl = rawInput;
            }
        } else {
            // Check if it's a Sketchfab link and ensure /embed is present
            let src = rawInput;
            const sfMatch = src.match(/sketchfab\.com\/(?:3d-models\/[^/]+-|models\/)?([a-f0-9]{32})/i);
            if (sfMatch && sfMatch[1] && !src.includes('/embed')) {
                src = `https://sketchfab.com/models/${sfMatch[1]}/embed`;
            }
            iframeEl = `<iframe src="${src}" width="100%" height="${height}" frameborder="0" allowfullscreen allow="autoplay; fullscreen; xr-spatial-tracking" style="width:100%;height:${height}px;display:block;border:none;"></iframe>`;
        }

        // Description / caption centered at the TOP
        const captionHtml = caption
            ? `<p class="ql-align-center" style="text-align:center;margin:0 0 10px 0;font-size:15px;color:#111827;font-weight:600;">${caption}</p>`
            : '';

        // Clean responsive container without any sketchfab author attribution text
        const wrapperHtml = `<div style="width:100%;max-width:800px;margin:4px auto 18px auto;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.08);">${iframeEl}</div>`;

        const fullHtml = `${captionHtml}${wrapperHtml}<p><br></p>`;

        const range = window.currentQuill.getSelection(true) || { index: 0 };
        window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, fullHtml);
        window.currentQuill.root.setAttribute('data-custom-html', 'true');

        const textarea = document.getElementById('content-editor') ||
                         document.getElementById('content') ||
                         document.getElementById('announcement-content') ||
                         document.getElementById('course-description');
        if (textarea) textarea.value = window.currentQuill.root.innerHTML;
        return;
    }

    // ── Normal .glb / .gltf / .obj URL — open the Hotspot Editor ────────────
    document.getElementById('model3d-modal').style.display = 'none';
    if (typeof openHotspotEditor === 'function') {
        openHotspotEditor(rawInput, caption, height);
    } else {
        alert('Hotspot editor script is not loaded properly.');
    }
}

// ─── Source Code Editor ───────────────────────────────────────────────────────
let htmlEditor = null;

function showSourceCodeModal(quill) {
    console.log('🔧 Opening source code modal...');
    window.currentQuill = quill;
    const modal = document.getElementById('source-code-modal');
    const overlay = document.getElementById('emoji-overlay');
    
    if (!modal) {
        console.error('❌ Source code modal not found!');
        return;
    }
    
    modal.style.display = 'block';
    overlay.style.display = 'block';
    
    const currentHTML = quill.root.innerHTML;
    console.log('📄 Current HTML:', currentHTML.substring(0, 200));
    
    // Initialize Monaco editor if not already initialized
    if (!htmlEditor) {
        if (typeof monaco === 'undefined') {
            console.error('❌ Monaco editor not loaded!');
            alert('Monaco editor is not loaded. Please refresh the page.');
            closeSourceCodeModal();
            return;
        }
        
        console.log('✅ Creating Monaco editor...');
        try {
            htmlEditor = monaco.editor.create(document.getElementById('html-editor-container'), {
                value: currentHTML,
                language: 'html',
                theme: 'vs',
                automaticLayout: true,
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                wordWrap: 'on',
                formatOnPaste: true,
                formatOnType: true
            });
            console.log('✅ Monaco editor created');
        } catch (e) {
            console.error('❌ Error creating Monaco:', e);
            alert('Error creating editor: ' + e.message);
        }
    } else {
        // Update content
        console.log('✅ Updating Monaco content...');
        htmlEditor.setValue(currentHTML);
    }
}

function closeSourceCodeModal() {
    document.getElementById('source-code-modal').style.display = 'none';
    document.getElementById('emoji-overlay').style.display = 'none';
}

function applySourceCode() {
    if (!htmlEditor || !window.currentQuill) {
        console.error('❌ No editor or quill instance');
        closeSourceCodeModal();
        return;
    }
    
    const htmlContent = htmlEditor.getValue();
    console.log('📝 Applying HTML:', htmlContent.substring(0, 100) + '...');
    
    // Find the textarea - try multiple methods
    let textarea = null;
    
    // Method 1: Look for content-editor or announcement-content
    textarea = document.getElementById('content-editor') || 
               document.getElementById('announcement-content') ||
               document.getElementById('course-description') ||
               document.getElementById('assignment-description');
    
    // Method 2: Find in form
    if (!textarea) {
        const form = window.currentQuill.container.closest('form');
        if (form) {
            const textareas = form.querySelectorAll('textarea');
            for (let ta of textareas) {
                const style = window.getComputedStyle(ta);
                if (style.display === 'none' || ta.offsetParent === null) {
                    textarea = ta;
                    break;
                }
            }
        }
    }
    
    if (textarea) {
        // CRITICAL: Update textarea (this is what saves to database)
        textarea.value = htmlContent;
        console.log('✅ Textarea updated:', textarea.id, 'Length:', htmlContent.length);
        
        // Set the flag BEFORE updating visual display
        window.currentQuill.root.setAttribute('data-custom-html', 'true');
        
        // Update visual display - completely replace Quill content
        window.currentQuill.root.innerHTML = htmlContent;
        
        console.log('✅ Visual editor updated');
        console.log('🔒 Custom HTML flag set - textarea is protected');
    } else {
        console.error('❌ No textarea found!');
        console.log('Available textareas:', document.querySelectorAll('textarea'));
    }
    
    closeSourceCodeModal();
}
