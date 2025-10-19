/**
 * Universal Code Execution System
 * Supports: JavaScript, Python, HTML/CSS, SQL, Java, C++
 */

class CodeExecutor {
    constructor() {
        this.pyodideLoaded = false;
        this.sqlJsLoaded = false;
        this.pyodide = null;
        this.sqlJs = null;
    }

    async execute(code, language) {
        const handlers = {
            'javascript': () => this.executeJavaScript(code),
            'python': () => this.executePython(code),
            'html': () => this.executeHTML(code),
            'sql': () => this.executeSQL(code),
            'java': () => this.executeServerSide(code, 'java'),
            'cpp': () => this.executeServerSide(code, 'cpp')
        };

        const handler = handlers[language.toLowerCase()];
        if (!handler) {
            return {
                success: false,
                error: `Execution not supported for ${language}`
            };
        }

        try {
            return await handler();
        } catch (error) {
            return {
                success: false,
                error: error.message || String(error)
            };
        }
    }

    // ========== JavaScript Execution ==========
    executeJavaScript(code) {
        try {
            let output = [];
            let errors = [];

            // Override console methods
            const originalLog = console.log;
            const originalError = console.error;
            const originalWarn = console.warn;

            console.log = (...args) => output.push(args.map(a => String(a)).join(' '));
            console.error = (...args) => errors.push(args.map(a => String(a)).join(' '));
            console.warn = (...args) => output.push('[WARN] ' + args.map(a => String(a)).join(' '));

            // Execute code in try-catch
            try {
                const result = eval(code);
                if (result !== undefined) {
                    output.push(`=> ${String(result)}`);
                }
            } catch (err) {
                errors.push(err.message);
            } finally {
                // Restore console
                console.log = originalLog;
                console.error = originalError;
                console.warn = originalWarn;
            }

            return {
                success: errors.length === 0,
                output: output.join('\n') || '(No output)',
                error: errors.length > 0 ? errors.join('\n') : null
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    // ========== Python Execution (Pyodide) ==========
    async executePython(code) {
        try {
            // Load Pyodide if not already loaded
            if (!this.pyodideLoaded) {
                if (typeof loadPyodide === 'undefined') {
                    // Load Pyodide script
                    await this.loadScript('https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js');
                }
                this.pyodide = await loadPyodide({
                    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/'
                });
                this.pyodideLoaded = true;
            }

            // Capture stdout
            let output = '';
            this.pyodide.setStdout({
                batched: (text) => { output += text; }
            });

            // Run Python code
            await this.pyodide.runPythonAsync(code);

            return {
                success: true,
                output: output || '(No output)'
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    // ========== HTML/CSS Execution (Live Preview) ==========
    executeHTML(code) {
        try {
            // Create a safe iframe for rendering
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width: 100%; height: 400px; border: 1px solid #ddd; border-radius: 8px; background: white;';
            iframe.sandbox = 'allow-scripts allow-same-origin';

            // Write HTML to iframe
            iframe.srcdoc = code;

            return {
                success: true,
                output: '✅ HTML rendered successfully',
                htmlPreview: iframe.outerHTML
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    // ========== SQL Execution (sql.js) ==========
    async executeSQL(code) {
        try {
            // Load sql.js if not already loaded
            if (!this.sqlJsLoaded) {
                await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/sql-wasm.js');
                
                const SQL = await initSqlJs({
                    locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
                });
                this.sqlJs = new SQL.Database();
                this.sqlJsLoaded = true;

                // Create a sample table for testing
                this.sqlJs.run(`
                    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);
                    INSERT INTO users VALUES (1, 'Alice', 25), (2, 'Bob', 30), (3, 'Charlie', 35);
                `);
            }

            // Execute SQL
            const results = this.sqlJs.exec(code);
            
            if (results.length === 0) {
                return {
                    success: true,
                    output: '✅ Query executed successfully (no results returned)'
                };
            }

            // Format results as table
            let output = '';
            results.forEach(result => {
                output += `Columns: ${result.columns.join(', ')}\n`;
                output += '-'.repeat(50) + '\n';
                result.values.forEach(row => {
                    output += row.join(' | ') + '\n';
                });
                output += `\n${result.values.length} row(s) returned\n`;
            });

            return {
                success: true,
                output: output
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    // ========== Server-Side Execution (Java, C++) ==========
    async executeServerSide(code, language) {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
            
            const response = await fetch('/api/execute-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ code, language })
            });

            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Server execution failed');
            }

            return {
                success: result.success,
                output: result.output,
                error: result.error
            };
        } catch (error) {
            return {
                success: false,
                error: `Server execution failed: ${error.message}`
            };
        }
    }

    // ========== Utility: Load External Script ==========
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
}

// Global instance
window.codeExecutor = new CodeExecutor();

// Helper function for easy execution
window.runCodeInEditor = async function(code, language, outputElementId) {
    const outputEl = document.getElementById(outputElementId);
    if (!outputEl) {
        console.error(`Output element ${outputElementId} not found`);
        return;
    }

    // Show loading
    outputEl.innerHTML = '<div class="text-yellow-400 animate-pulse">⏳ Running code...</div>';
    outputEl.parentElement.classList.remove('hidden');

    // Execute
    const result = await window.codeExecutor.execute(code, language);

    // Display result
    if (result.success) {
        let html = '<div class="text-green-400 font-semibold">✅ Success!</div>';
        
        if (result.htmlPreview) {
            html += `<div class="mt-3">${result.htmlPreview}</div>`;
        } else {
            html += `<pre class="mt-2 text-gray-300 whitespace-pre-wrap">${escapeHtml(result.output)}</pre>`;
        }
        
        outputEl.innerHTML = html;
    } else {
        outputEl.innerHTML = `
            <div class="text-red-400 font-semibold">❌ Error</div>
            <pre class="mt-2 text-red-300 whitespace-pre-wrap">${escapeHtml(result.error)}</pre>
        `;
    }
};

// HTML escape utility
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

console.log('✅ Universal Code Executor loaded');
