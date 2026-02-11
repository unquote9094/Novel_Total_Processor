/**
 * init-project.js
 * 새 프로젝트 초기화 부트스트랩 스크립트
 * 
 * 사용법:
 *   node E:\DEVz\_templates\project-template\init-project.js "프로젝트명"
 * 
 * 또는 현재 폴더에서:
 *   node init-project.js "프로젝트명"
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// ES Module에서 __dirname 대체
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ANSI 색상 코드
const colors = {
    reset: "\x1b[0m",
    green: "\x1b[32m",
    yellow: "\x1b[33m",
    blue: "\x1b[34m",
    red: "\x1b[31m",
    cyan: "\x1b[36m"
};

function log(msg, color = colors.reset) {
    console.log(`${color}${msg}${colors.reset}`);
}

/**
 * 폴더/파일 복사 (재귀)
 */
function copyRecursive(src, dest, projectName) {
    if (!fs.existsSync(src)) return;

    const stat = fs.statSync(src);

    if (stat.isDirectory()) {
        if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
        }

        const files = fs.readdirSync(src);
        for (const file of files) {
            // init-project.js 자신은 제외
            if (file === 'init-project.js') continue;

            copyRecursive(
                path.join(src, file),
                path.join(dest, file),
                projectName
            );
        }
    } else {
        // 파일 복사 + 템플릿 치환
        let content = fs.readFileSync(src, 'utf8');

        // {{PROJECT_NAME}} 치환
        content = content.replace(/\{\{PROJECT_NAME\}\}/g, projectName);

        // 소문자+하이픈 버전 치환 (package.json용)
        const projectNameLower = projectName.toLowerCase().replace(/\s+/g, '-');
        content = content.replace(/\{\{PROJECT_NAME_LOWER\}\}/g, projectNameLower);

        fs.writeFileSync(dest, content, 'utf8');
    }
}

function main() {
    const args = process.argv.slice(2);

    if (args.length === 0) {
        log('❌ Usage: node init-project.js "프로젝트명"', colors.red);
        log('   Example: node init-project.js "Stealth-Clicker"', colors.yellow);
        return;
    }

    const projectName = args[0];
    const targetDir = process.cwd();
    // 템플릿 경로 (이 스크립트가 있는 폴더)
    const templateDir = __dirname;

    log(`\n🚀 Initializing Project: ${projectName}\n`, colors.blue);
    log(`   Template: ${templateDir}`, colors.cyan);
    log(`   Target: ${targetDir}`, colors.cyan);

    // 1. 템플릿 복사
    log('\n1️⃣ Copying template files...', colors.green);

    const foldersToCopy = ['.agent', '.gemini', 'docs', 'scripts'];

    for (const folder of foldersToCopy) {
        const srcPath = path.join(templateDir, folder);
        const destPath = path.join(targetDir, folder);

        if (fs.existsSync(srcPath)) {
            copyRecursive(srcPath, destPath, projectName);
            log(`   ✅ Copied ${folder}/`, colors.green);
        }
    }

    // 2. package.json 생성 (없으면)
    const pkgPath = path.join(targetDir, 'package.json');
    if (!fs.existsSync(pkgPath)) {
        log('\n2️⃣ Creating package.json...', colors.green);

        const projectNameLower = projectName.toLowerCase().replace(/\s+/g, '-');
        const pkg = {
            name: projectNameLower,
            version: "0.1.0",
            type: "module",
            description: `${projectName} 프로젝트`,
            main: "index.js",
            scripts: {
                "start-task": "node scripts/start-task.js",
                "finish": "node scripts/finish-task.js",
                "sync-issues": "node scripts/sync-issues.js",
                "test": "node scripts/test_sanity.js"
            }
        };

        fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2), 'utf8');
        log('   ✅ Created package.json', colors.green);
    } else {
        log('\n2️⃣ package.json already exists. Skipping.', colors.yellow);
    }

    // 3. src/ 폴더 생성
    const srcDir = path.join(targetDir, 'src');
    if (!fs.existsSync(srcDir)) {
        log('\n3️⃣ Creating src/ folder...', colors.green);
        fs.mkdirSync(srcDir, { recursive: true });
        log('   ✅ Created src/', colors.green);
    }

    // 4. 완료 메시지
    log('\n✨ Project Initialized Successfully!', colors.blue);
    log('\n📌 다음 단계:', colors.yellow);
    log('   1. git init (아직 안 했으면)', colors.cyan);
    log('   2. gh repo create --public (GitHub 저장소 생성)', colors.cyan);
    log('   3. npm run start-task -- feat "첫 번째 기능"', colors.cyan);
}

main();
