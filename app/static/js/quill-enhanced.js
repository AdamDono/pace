// Enhanced Quill Editor - Tables, Emojis, Embed, Source Code
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
                [{ 'header': [1, 2, 3, false] }],
                ['bold', 'italic', 'underline'],
                [{ 'color': [] }, { 'background': [] }],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                ['link', 'image'],
                ['emoji', 'table', 'embed', 'source'],
                ['clean']
            ],
            handlers: {
                'emoji': () => showEmojiModal(quill),
                'table': () => insertTable(quill),
                'embed': () => showEmbedModal(quill),
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

    const range = window.currentQuill.getSelection(true);
    const embedCode = `<div class="h5p-embed-container" style="position:relative;width:100%;padding-bottom:75%;height:0;overflow:hidden;margin:20px 0;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);background:#f9fafb;"><iframe src="${url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen allow="geolocation *; microphone *; camera *; midi *; encrypted-media *" title="Embedded Interactive Content"></iframe></div>`;

    // Insert the HTML
    window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, embedCode);

    // Mark as custom HTML to prevent Quill from stripping styles
    window.currentQuill.root.setAttribute('data-custom-html', 'true');

    // Update the hidden textarea immediately
    const textarea = document.getElementById('content-editor') ||
                     document.getElementById('announcement-content') ||
                     document.getElementById('course-description');
    if (textarea) {
        textarea.value = window.currentQuill.root.innerHTML;
        console.log('✅ Embed inserted and textarea updated');
    }

    console.log('✅ Embed URL:', url);
    closeEmbedModal();
}

// Source Code Editor
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
