# SattLine LSP VS Code Client

This extension launches the Python `sattlint_lsp` server over stdio, associates `.s`, `.x`, `.l`, and `.z` files with the `sattline` language, and provides built-in TextMate syntax highlighting for SattLine source.

It is implemented as a plain JavaScript VS Code extension, so there is no npm or TypeScript build step.

## Usage

Copy or symlink this folder under your VS Code user extensions directory as `local.sattline-vscode-0.1.0`, then reload the editor window.

## Packaging

If you want a `.vsix` from WSL, run:

```bash
cd vscode/sattline-vscode
npm run package:vsix
```

That writes `sattline-vscode-0.1.0.vsix` into this directory.
