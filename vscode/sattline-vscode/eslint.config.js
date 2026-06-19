const globals = require("globals");

module.exports = [
    {
        files: ["extension.js"],
        languageOptions: {
            ecmaVersion: 2021,
            sourceType: "script",
            globals: {
                ...globals.node,
                ...globals.es2021,
                vscode: "readonly",
            },
        },
        rules: {
            "no-undef": "error",
        },
    },
];
