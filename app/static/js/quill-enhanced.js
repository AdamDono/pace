// Simple Enhanced Quill - Tables, Emojis, H5P
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

    // Create H5P modal if it doesn't exist
    if (!document.getElementById('h5p-modal')) {
        const modal = document.createElement('div');
        modal.id = 'h5p-modal';
        modal.style.cssText = 'display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:30px;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.3);z-index:10000;width:500px;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
                <h3 style="margin:0;font-size:16px;font-weight:bold;">🎮 Embed H5P</h3>
                <button onclick="closeH5PModal()" style="background:none;border:none;font-size:24px;cursor:pointer;">&times;</button>
            </div>
            <p style="color:#666;font-size:14px;margin-bottom:15px;">Paste H5P embed URL or full iframe code:</p>
            <textarea id="h5p-input" placeholder="https://h5p.org/h5p/embed/617 or <iframe...>" style="width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;font-size:14px;margin-bottom:20px;min-height:100px;font-family:monospace;"></textarea>
            <div style="display:flex;gap:10px;justify-content:flex-end;">
                <button onclick="closeH5PModal()" style="padding:10px 20px;background:#e5e7eb;border:none;border-radius:8px;cursor:pointer;font-weight:600;">Cancel</button>
                <button onclick="insertH5P()" style="padding:10px 20px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;">Insert</button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Initialize Quill
    const quill = new Quill('#' + editorId, {
        theme: 'snow',
        placeholder: placeholder,
        modules: {
            table: false,
            'better-table': typeof QuillBetterTable !== 'undefined' ? {
                operationMenu: {
                    items: { unmergeCells: { text: 'Unmerge cells' } }
                }
            } : undefined,
            keyboard: typeof QuillBetterTable !== 'undefined' ? {
                bindings: QuillBetterTable.keyboardBindings
            } : undefined,
            toolbar: {
                container: [
                    [{ 'header': [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline'],
                    [{ 'color': [] }, { 'background': [] }],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    ['link', 'image'],
                    ['emoji', 'table', 'h5p'],
                    ['clean']
                ],
                handlers: {
                    'emoji': () => showEmojiModal(quill),
                    'table': () => insertTable(quill),
                    'h5p': () => showH5PModal(quill)
                }
            }
        }
    });

    // Load existing content
    const textarea = document.getElementById(textareaId);
    if (textarea && textarea.value) {
        quill.root.innerHTML = textarea.value;
    }

    // Sync on change
    quill.on('text-change', () => {
        if (textarea) textarea.value = quill.root.innerHTML;
    });

    // Sync on form submit
    const form = textarea ? textarea.closest('form') : null;
    if (form) {
        form.addEventListener('submit', () => {
            if (textarea) textarea.value = quill.root.innerHTML;
        });
    }

    // Store current quill instance
    window.currentQuill = quill;

    return quill;
}

// Helper functions
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

function showH5PModal(quill) {
    window.currentQuill = quill;
    document.getElementById('h5p-modal').style.display = 'block';
    document.getElementById('emoji-overlay').style.display = 'block';
}

function closeH5PModal() {
    document.getElementById('h5p-modal').style.display = 'none';
    document.getElementById('emoji-overlay').style.display = 'none';
    document.getElementById('h5p-input').value = '';
}

function insertH5P() {
    const input = document.getElementById('h5p-input').value.trim();
    if (!input || !window.currentQuill) return;

    let url = input;
    // Extract URL from iframe if needed
    if (input.includes('<iframe')) {
        const match = input.match(/src=["']([^"']+)["']/);
        if (match) url = match[1];
    }

    const range = window.currentQuill.getSelection(true);
    const embedCode = `<div class="h5p-embed-container" style="position:relative;width:100%;padding-bottom:75%;height:0;overflow:hidden;margin:20px 0;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);background:#f9fafb;"><iframe src="${url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen allow="geolocation *; microphone *; camera *; midi *; encrypted-media *" title="H5P Interactive Content"></iframe></div>`;
    window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, embedCode);
    closeH5PModal();
}
