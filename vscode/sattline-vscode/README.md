# SattLine LSP VS Code Client

This extension launches the Python `sattlint_lsp` server over stdio, associates `.s`, `.x`, `.l`, `.z`, and `.g` files with the `sattline` language, and provides built-in TextMate syntax highlighting for SattLine source.

It is implemented as a plain JavaScript VS Code extension, so there is no npm or TypeScript build step.

## Usage

Copy or symlink this folder under your VS Code user extensions directory as `local.sattline-vscode-0.1.0`, then reload the editor window.

## Large Repos

If a large multi-program workspace pushes the language server too hard, start with this settings baseline:

```json
{
    "sattlineLsp.workspaceDiagnosticsMode": "off",
    "sattlineLsp.scanRootOnly": true,
    "sattlineLsp.maxCachedEntrySnapshots": 1,
    "sattlineLsp.entryFile": "Programs/Main.s",
    "sattlineLsp.enableVariableDiagnostics": false
}
```

`maxCachedEntrySnapshots` bounds how many entry-root workspace snapshots stay resident at once. `entryFile` keeps library editing anchored to one program in multi-program workspaces. After changing these settings, run `SattLine: Restart Language Server`.

## Packaging

If you want a `.vsix` from WSL, run:

```bash
cd vscode/sattline-vscode
npm run package:vsix
```

That writes `sattline-vscode-0.1.0.vsix` into this directory.
