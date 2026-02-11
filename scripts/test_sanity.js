/**
 * test_sanity.js
 * 프로젝트 기본 건전성 검사
 */

const checks = [
    {
        name: "0. Basic Environment Check",
        fn: async () => {
            // Node 버전 확인
            if (process.version.startsWith('v0')) {
                throw new Error("Node version too old");
            }
        }
    },
    {
        name: "1. Required Files Check",
        fn: async () => {
            const fs = await import('fs');
            const path = await import('path');

            const requiredFiles = [
                '.agent/constitution.md',
                'docs/ISSUES.md'
            ];

            for (const file of requiredFiles) {
                const filePath = path.join(process.cwd(), file);
                if (!fs.existsSync(filePath)) {
                    throw new Error(`Missing required file: ${file}`);
                }
            }
        }
    }
];

// 테스트 실행기
(async () => {
    console.log(`\n🛡️  [Safety Belt] Running ${checks.length} checks...\n`);
    let passed = 0;
    let failed = 0;

    for (const check of checks) {
        try {
            process.stdout.write(`   👉 Checking [${check.name}] ... `);
            await check.fn();
            console.log("\x1b[32mOK\x1b[0m");
            passed++;
        } catch (e) {
            console.log("\x1b[31mFAIL\x1b[0m");
            console.error(`      └─ ❌ Error: ${e.message}`);
            failed++;
        }
    }

    console.log(`\n📊 Result: ${passed} Passed, ${failed} Failed.`);

    if (failed > 0) {
        console.error("\x1b[31m⛔ Some tests failed.\x1b[0m");
        process.exit(1);
    } else {
        console.log("\x1b[32m✅ All Systems Operational.\x1b[0m");
        process.exit(0);
    }
})();
