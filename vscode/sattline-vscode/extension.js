const childProcess = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const vscode = require('vscode');

const LANGUAGE_ID = 'sattline';
const RESTART_COMMAND = 'sattlineLsp.restartServer';
const STOPPED_BEFORE_REPLYING_MESSAGE = 'Language server stopped before replying.';
const DID_CHANGE_DEBOUNCE_MS = 250;
const PROGRAM_EXTENSIONS = new Set(['.s', '.x']);

function getErrorMessage(error) {
    if (error instanceof Error && error.message) {
        return error.message;
    }
    return String(error || 'Unknown error');
}

function isTransientLifecycleError(error) {
    const message = getErrorMessage(error);
    return message.includes(STOPPED_BEFORE_REPLYING_MESSAGE) || message.includes('SattLine language server is not running.');
}

function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function onceProcessSettled(child) {
    return new Promise((resolve) => {
        let settled = false;
        const finish = () => {
            if (settled) {
                return;
            }
            settled = true;
            resolve();
        };
        child.once('exit', finish);
        child.once('close', finish);
        child.once('error', finish);
    });
}

function isSattlineDocument(document) {
    if (!document || document.uri.scheme !== 'file') {
        return false;
    }
    return PROGRAM_EXTENSIONS.has(path.extname(document.uri.fsPath || '').toLowerCase());
}

function createDocumentSelector() {
    return [
        { scheme: 'file', pattern: '**/*.s' },
        { scheme: 'file', pattern: '**/*.x' },
    ];
}

function toRange(range) {
    return new vscode.Range(
        new vscode.Position(range.start.line, range.start.character),
        new vscode.Position(range.end.line, range.end.character),
    );
}

function toCompletionItem(item) {
    const completion = new vscode.CompletionItem(item.label);
    completion.detail = item.detail;
    completion.kind = item.kind;
    return completion;
}

function toMarkdownString(contents) {
    if (typeof contents === 'string') {
        return new vscode.MarkdownString(contents);
    }
    if (contents && typeof contents.value === 'string') {
        return new vscode.MarkdownString(contents.value);
    }
    return new vscode.MarkdownString('');
}

function toLspRange(range) {
    return {
        start: { line: range.start.line, character: range.start.character },
        end: { line: range.end.line, character: range.end.character },
    };
}

function toLspContentChange(change) {
    if (!change.range) {
        return { text: change.text };
    }
    return {
        range: toLspRange(change.range),
        rangeLength: change.rangeLength,
        text: change.text,
    };
}

async function pathExists(targetPath) {
    try {
        await fs.access(targetPath);
        return true;
    } catch {
        return false;
    }
}

function expandWorkspaceTokens(value, folder) {
    if (!folder) {
        return value;
    }
    return value.replace(/\$\{workspaceFolder\}/g, folder.uri.fsPath);
}

async function resolvePythonCommand(folder) {
    const lspConfig = vscode.workspace.getConfiguration('sattlineLsp', folder);
    const configured = (lspConfig.get('pythonPath') || '').trim();
    if (configured) {
        return expandWorkspaceTokens(configured, folder);
    }

    const pythonConfig = vscode.workspace.getConfiguration('python', folder);
    const interpreter = (pythonConfig.get('defaultInterpreterPath') || '').trim();
    if (interpreter) {
        return expandWorkspaceTokens(interpreter, folder);
    }

    if (folder) {
        const candidates = [
            path.join(folder.uri.fsPath, '.venv', 'Scripts', 'python.exe'),
            path.join(folder.uri.fsPath, '.venv', 'bin', 'python'),
        ];
        for (const candidate of candidates) {
            if (await pathExists(candidate)) {
                return candidate;
            }
        }
    }

    return process.platform === 'win32' ? 'python' : 'python3';
}

function getPrimaryWorkspaceFolder() {
    const editorUri = vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.uri;
    if (editorUri) {
        const folder = vscode.workspace.getWorkspaceFolder(editorUri);
        if (folder) {
            return folder;
        }
    }
    return vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
}

function buildInitializationOptions(folder) {
    const config = vscode.workspace.getConfiguration('sattlineLsp', folder);
    return {
        entryFile: config.get('entryFile') || '',
        mode: config.get('mode') || 'draft',
        scanRootOnly: config.get('scanRootOnly') || false,
        enableVariableDiagnostics: config.get('enableVariableDiagnostics', true),
        workspaceDiagnosticsMode: config.get('workspaceDiagnosticsMode', 'background'),
        maxCompletionItems: config.get('maxCompletionItems', 100),
    };
}

class StdioLspBridge {
    constructor(context) {
        this.context = context;
        this.outputChannel = vscode.window.createOutputChannel('SattLine LSP');
        this.diagnostics = vscode.languages.createDiagnosticCollection('sattline');
        this.process = undefined;
        this.buffer = Buffer.alloc(0);
        this.pending = new Map();
        this.sequence = 1;
        this.ready = undefined;
        this.lifecycle = Promise.resolve();
        this.workspaceFolder = undefined;
        this.pendingDidChangeTimers = new Map();
        this.pendingDidChangeDocuments = new Map();
        context.subscriptions.push(this.outputChannel, this.diagnostics);
    }

    disposePendingDidChanges() {
        for (const timer of this.pendingDidChangeTimers.values()) {
            clearTimeout(timer);
        }
        this.pendingDidChangeTimers.clear();
        this.pendingDidChangeDocuments.clear();
    }

    clearPendingDidChange(uri) {
        const timer = this.pendingDidChangeTimers.get(uri);
        if (timer) {
            clearTimeout(timer);
            this.pendingDidChangeTimers.delete(uri);
        }
    }

    async start() {
        return this.runLifecycleStep(() => this.startInternal());
    }

    async startInternal() {
        if (this.ready) {
            await this.ready;
            return;
        }

        this.workspaceFolder = getPrimaryWorkspaceFolder();
        const pythonCommand = await resolvePythonCommand(this.workspaceFolder);
        const cwd = this.workspaceFolder ? this.workspaceFolder.uri.fsPath : this.context.extensionPath;
        this.outputChannel.appendLine(`Starting SattLine LSP with ${pythonCommand} -m sattlint_lsp.server`);

        this.process = childProcess.spawn(pythonCommand, ['-m', 'sattlint_lsp.server'], {
            cwd,
            stdio: 'pipe',
        });
        const processRef = this.process;

        this.process.stdout.on('data', (chunk) => this.handleData(chunk));
        this.process.stderr.on('data', (chunk) => {
            this.outputChannel.append(chunk.toString('utf8'));
        });
        this.process.on('exit', (code, signal) => {
            this.outputChannel.appendLine(`SattLine LSP exited with code=${code} signal=${signal || 'none'}`);
            if (this.process !== processRef) {
                return;
            }
            for (const entry of this.pending.values()) {
                entry.reject(new Error(STOPPED_BEFORE_REPLYING_MESSAGE));
            }
            this.pending.clear();
            this.ready = undefined;
            this.process = undefined;
            this.buffer = Buffer.alloc(0);
        });

        const startup = (async () => {
            await this.initialize();
            await this.openVisibleDocuments();
        })();
        this.ready = startup;

        try {
            await startup;
        } catch (error) {
            if (this.process === processRef && processRef.exitCode === null && !processRef.killed) {
                processRef.kill();
            }
            throw error;
        }
    }

    async stop() {
        return this.runLifecycleStep(() => this.stopInternal());
    }

    async stopInternal() {
        const currentProcess = this.process;
        this.ready = undefined;
        this.disposePendingDidChanges();

        if (!currentProcess) {
            return;
        }

        const exitPromise = onceProcessSettled(currentProcess);

        try {
            await Promise.race([this.sendRequest('shutdown', null), delay(1000)]);
        } catch {
            // Ignore shutdown failures during teardown.
        }

        try {
            this.sendNotification('exit', null);
        } catch {
            // Ignore exit notification failures during teardown.
        }

        if (currentProcess.exitCode === null && !currentProcess.killed) {
            currentProcess.kill();
        }

        await exitPromise;

        if (this.process === currentProcess) {
            this.process = undefined;
            this.buffer = Buffer.alloc(0);
        }
    }

    async restart() {
        return this.runLifecycleStep(async () => {
            this.diagnostics.clear();
            await this.stopInternal();
            try {
                await this.startInternal();
            } catch (error) {
                if (!isTransientLifecycleError(error)) {
                    throw error;
                }
                this.outputChannel.appendLine(`Retrying SattLine LSP restart after transient lifecycle failure: ${getErrorMessage(error)}`);
                await this.stopInternal();
                await this.startInternal();
            }
        });
    }

    runLifecycleStep(step) {
        const run = this.lifecycle.then(step, step);
        this.lifecycle = run.catch(() => undefined);
        return run;
    }

    async initialize() {
        const rootUri = this.workspaceFolder ? this.workspaceFolder.uri.toString() : null;
        await this.sendRequest('initialize', {
            processId: process.pid,
            clientInfo: { name: 'SattLine VS Code Client', version: '0.1.0' },
            rootUri,
            capabilities: {
                textDocument: {
                    definition: {},
                    hover: { contentFormat: ['markdown', 'plaintext'] },
                    references: {},
                    rename: {},
                    completion: {
                        completionItem: {
                            documentationFormat: ['plaintext'],
                        },
                    },
                    publishDiagnostics: {},
                },
            },
            initializationOptions: buildInitializationOptions(this.workspaceFolder),
        });
        this.sendNotification('initialized', {});
    }

    async openVisibleDocuments() {
        for (const document of vscode.workspace.textDocuments) {
            if (isSattlineDocument(document)) {
                this.didOpen(document);
            }
        }
    }

    didOpen(document) {
        this.clearPendingDidChange(document.uri.toString());
        this.pendingDidChangeDocuments.delete(document.uri.toString());
        this.sendNotification('textDocument/didOpen', {
            textDocument: {
                uri: document.uri.toString(),
                languageId: LANGUAGE_ID,
                version: document.version,
                text: document.getText(),
            },
        });
    }

    sendDidChange(pendingChange) {
        this.sendNotification('textDocument/didChange', {
            textDocument: {
                uri: pendingChange.document.uri.toString(),
                version: pendingChange.document.version,
            },
            contentChanges: pendingChange.contentChanges.length ? pendingChange.contentChanges : [{ text: pendingChange.document.getText() }],
        });
    }

    didChange(event) {
        const uri = event.document.uri.toString();
        const pendingChange = this.pendingDidChangeDocuments.get(uri) || {
            document: event.document,
            contentChanges: [],
        };
        pendingChange.document = event.document;
        pendingChange.contentChanges.push(...event.contentChanges.map(toLspContentChange));
        this.pendingDidChangeDocuments.set(uri, pendingChange);
        this.clearPendingDidChange(uri);
        const timer = setTimeout(() => {
            this.pendingDidChangeTimers.delete(uri);
            const pendingDocument = this.pendingDidChangeDocuments.get(uri);
            this.pendingDidChangeDocuments.delete(uri);
            if (pendingDocument) {
                this.sendDidChange(pendingDocument);
            }
        }, DID_CHANGE_DEBOUNCE_MS);
        this.pendingDidChangeTimers.set(uri, timer);
    }

    flushDidChange(document) {
        const uri = document.uri.toString();
        const pendingDocument = this.pendingDidChangeDocuments.get(uri) || {
            document,
            contentChanges: [{ text: document.getText() }],
        };
        this.clearPendingDidChange(uri);
        this.pendingDidChangeDocuments.delete(uri);
        this.sendDidChange(pendingDocument);
    }

    didSave(document) {
        this.flushDidChange(document);
        this.sendNotification('textDocument/didSave', {
            textDocument: {
                uri: document.uri.toString(),
            },
        });
    }

    didClose(document) {
        this.clearPendingDidChange(document.uri.toString());
        this.pendingDidChangeDocuments.delete(document.uri.toString());
        this.sendNotification('textDocument/didClose', {
            textDocument: {
                uri: document.uri.toString(),
            },
        });
        this.diagnostics.delete(document.uri);
    }

    async requestDefinitions(document, position) {
        await this.start();
        this.flushDidChange(document);
        const result = await this.sendRequest('textDocument/definition', {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
        });
        if (!result) {
            return undefined;
        }
        const locations = Array.isArray(result) ? result : [result];
        return locations.map((location) => new vscode.Location(vscode.Uri.parse(location.uri), toRange(location.range)));
    }

    async requestCompletion(document, position) {
        await this.start();
        this.flushDidChange(document);
        const result = await this.sendRequest('textDocument/completion', {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
        });
        if (!result) {
            return [];
        }
        const items = Array.isArray(result) ? result : result.items || [];
        return items.map(toCompletionItem);
    }

    async requestHover(document, position) {
        await this.start();
        this.flushDidChange(document);
        const result = await this.sendRequest('textDocument/hover', {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
        });
        if (!result || !result.contents) {
            return undefined;
        }
        const contents = Array.isArray(result.contents)
            ? result.contents.map(toMarkdownString)
            : [toMarkdownString(result.contents)];
        const range = result.range ? toRange(result.range) : undefined;
        return new vscode.Hover(contents, range);
    }

    async requestReferences(document, position) {
        await this.start();
        this.flushDidChange(document);
        const result = await this.sendRequest('textDocument/references', {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
            context: { includeDeclaration: true },
        });
        if (!result) {
            return undefined;
        }
        const locations = Array.isArray(result) ? result : [result];
        return locations.map((location) => new vscode.Location(vscode.Uri.parse(location.uri), toRange(location.range)));
    }

    async requestRename(document, position, newName) {
        await this.start();
        this.flushDidChange(document);
        const result = await this.sendRequest('textDocument/rename', {
            textDocument: { uri: document.uri.toString() },
            position: { line: position.line, character: position.character },
            newName,
        });
        if (!result || !result.changes) {
            return undefined;
        }

        const edit = new vscode.WorkspaceEdit();
        for (const [uri, edits] of Object.entries(result.changes)) {
            const targetUri = vscode.Uri.parse(uri);
            for (const item of edits || []) {
                edit.replace(targetUri, toRange(item.range), item.newText || '');
            }
        }
        return edit;
    }

    sendNotification(method, params) {
        this.tryWriteMessage({ jsonrpc: '2.0', method, params });
    }

    sendRequest(method, params) {
        const id = this.sequence++;
        const promise = new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
        });
        this.writeMessage({ jsonrpc: '2.0', id, method, params });
        return promise;
    }

    writeMessage(message) {
        if (!this.tryWriteMessage(message)) {
            throw new Error('SattLine language server is not running.');
        }
    }

    tryWriteMessage(message) {
        if (!this.process || !this.process.stdin.writable) {
            return false;
        }
        const body = Buffer.from(JSON.stringify(message), 'utf8');
        const header = Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, 'utf8');
        this.process.stdin.write(header);
        this.process.stdin.write(body);
        return true;
    }

    handleData(chunk) {
        this.buffer = Buffer.concat([this.buffer, Buffer.from(chunk)]);

        while (true) {
            const separatorIndex = this.buffer.indexOf('\r\n\r\n');
            if (separatorIndex < 0) {
                return;
            }

            const headerText = this.buffer.slice(0, separatorIndex).toString('utf8');
            const match = /Content-Length:\s*(\d+)/i.exec(headerText);
            if (!match) {
                this.buffer = Buffer.alloc(0);
                return;
            }

            const contentLength = Number(match[1]);
            const messageStart = separatorIndex + 4;
            const messageEnd = messageStart + contentLength;
            if (this.buffer.length < messageEnd) {
                return;
            }

            const payload = this.buffer.slice(messageStart, messageEnd).toString('utf8');
            this.buffer = this.buffer.slice(messageEnd);
            this.handleMessage(JSON.parse(payload));
        }
    }

    handleMessage(message) {
        if (Object.prototype.hasOwnProperty.call(message, 'id')) {
            const pending = this.pending.get(message.id);
            if (!pending) {
                return;
            }
            this.pending.delete(message.id);
            if (message.error) {
                pending.reject(new Error(message.error.message || 'Language server request failed.'));
                return;
            }
            pending.resolve(message.result);
            return;
        }

        if (message.method === 'textDocument/publishDiagnostics' && message.params) {
            const uri = vscode.Uri.parse(message.params.uri);
            const diagnostics = (message.params.diagnostics || []).map((diagnostic) => {
                const item = new vscode.Diagnostic(
                    toRange(diagnostic.range),
                    diagnostic.message,
                    diagnostic.severity === 1 ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning,
                );
                item.source = diagnostic.source || 'sattlint';
                return item;
            });
            this.diagnostics.set(uri, diagnostics);
        }
    }
}

function registerLanguageFeatures(context, bridge) {
    const selector = createDocumentSelector();

    context.subscriptions.push(
        vscode.languages.registerDefinitionProvider(selector, {
            provideDefinition(document, position) {
                return bridge.requestDefinitions(document, position);
            },
        }),
    );

    context.subscriptions.push(
        vscode.languages.registerHoverProvider(selector, {
            provideHover(document, position) {
                return bridge.requestHover(document, position);
            },
        }),
    );

    context.subscriptions.push(
        vscode.languages.registerReferenceProvider(selector, {
            provideReferences(document, position) {
                return bridge.requestReferences(document, position);
            },
        }),
    );

    context.subscriptions.push(
        vscode.languages.registerRenameProvider(selector, {
            provideRenameEdits(document, position, newName) {
                return bridge.requestRename(document, position, newName);
            },
        }),
    );

    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            selector,
            {
                provideCompletionItems(document, position) {
                    return bridge.requestCompletion(document, position);
                },
            },
            '.',
        ),
    );
}

async function activate(context) {
    const bridge = new StdioLspBridge(context);

    registerLanguageFeatures(context, bridge);

    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument((document) => {
            if (isSattlineDocument(document)) {
                bridge.didOpen(document);
            }
        }),
        vscode.workspace.onDidChangeTextDocument((event) => {
            if (isSattlineDocument(event.document)) {
                bridge.didChange(event);
            }
        }),
        vscode.workspace.onDidSaveTextDocument((document) => {
            if (isSattlineDocument(document)) {
                bridge.didSave(document);
            }
        }),
        vscode.workspace.onDidCloseTextDocument((document) => {
            if (isSattlineDocument(document)) {
                bridge.didClose(document);
            }
        }),
        vscode.workspace.onDidChangeConfiguration(async (event) => {
            if (event.affectsConfiguration('sattlineLsp') || event.affectsConfiguration('python.defaultInterpreterPath')) {
                try {
                    await bridge.restart();
                } catch (error) {
                    void vscode.window.showErrorMessage(`SattLine language server restart failed: ${getErrorMessage(error)}`);
                }
            }
        }),
        vscode.commands.registerCommand(RESTART_COMMAND, async () => {
            try {
                await bridge.restart();
                void vscode.window.showInformationMessage('SattLine language server restarted.');
            } catch (error) {
                void vscode.window.showErrorMessage(`SattLine language server restart failed: ${getErrorMessage(error)}`);
            }
        }),
        {
            dispose() {
                return bridge.stop();
            },
        },
    );

    await bridge.start();
}

async function deactivate() {
    return undefined;
}

module.exports = {
    activate,
    deactivate,
};
