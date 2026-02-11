import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

// ANSI 색상 코드
const colors = {
    reset: "\x1b[0m",
    green: "\x1b[32m",
    yellow: "\x1b[33m",
    blue: "\x1b[34m",
    red: "\x1b[31m"
};

function log(msg, color = colors.reset) {
    console.log(`${color}${msg}${colors.reset}`);
}

function run(command) {
    try {
        log(`> ${command}`, colors.yellow);
        return execSync(command, {
            encoding: 'utf8',
            env: { ...process.env, GH_PAGER: '', PAGER: 'cat', CI: 'true' }
        }).trim();
    } catch (error) {
        log(`❌ Command failed: ${command}`, colors.red);
        process.exit(1);
    }
}

function main() {
    // 1. 인자 확인 (타입 + 타이틀)
    const args = process.argv.slice(2);
    if (args.length < 2) {
        log('❌ Usage: npm run start-task -- <type> "Task Title"', colors.red);
        log('   Types: bug, feat, enhance', colors.yellow);
        log('   Example: npm run start-task -- bug "소설 제목 미추출"', colors.yellow);
        return;
    }
    const type = args[0].toLowerCase();
    const title = args[1];

    // 타입별 prefix와 label 매핑
    const typeMap = {
        'bug': { prefix: '[버그]', label: 'bug' },
        'feat': { prefix: '[기능]', label: 'enhancement' },
        'enhance': { prefix: '[개선]', label: 'enhancement' },
        'fix': { prefix: '[수정]', label: 'bug' },
        'refactor': { prefix: '[리팩토링]', label: 'refactor' },
        'chore': { prefix: '[관리]', label: 'chore' },
        'docs': { prefix: '[문서]', label: 'documentation' },
        'style': { prefix: '[스타일]', label: 'style' },
        'test': { prefix: '[테스트]', label: 'test' }
    };

    if (!typeMap[type]) {
        log(`❌ Unknown type: "${type}".\n   Available: bug, feat, enhance, fix, refactor, chore, docs, style, test`, colors.red);
        return;
    }

    const { prefix, label } = typeMap[type];
    const fullTitle = `${prefix} ${title}`;

    log('\n🚀 Creating GitHub Issue...\n', colors.blue);

    // [PES] 0. Constitution 읽기
    const constitutionPath = path.join(process.cwd(), '.agent', 'constitution.md');
    if (fs.existsSync(constitutionPath)) {
        log('📜 [AGENT CONSTITUTION] Loading...', colors.yellow);
    }

    // 타입별 이슈 본문 생성 (고등학생도 이해할 수 있는 상세 템플릿)
    const today = new Date().toISOString().split('T')[0];

    const educationTemplate = `## 🎓 배경 지식 (Context)
> 이 작업이 왜 필요한지, 관련된 기본 개념은 무엇인지, **개발을 처음 배우는 고등학생에게 설명하듯이** 상세하게 작성하세요.
> (예: "로그인 기능이란 사용자가 누구인지 확인하는 절차입니다. 현재는 이 기능이 없어서...")

## 🎯 목표 (Goal)
> 이 작업을 통해 달성하고자 하는 것이 무엇인지 구체적으로 설명하세요.
> (예: "사용자가 아이디/비번을 입력하고 로그인 버튼을 누르면 메인 페이지로 이동해야 합니다.")

## 🛠️ 기술적 계획 (Technical Plan)
> 어떤 파일을 어떻게 수정할 것인지 상세히 적으세요.
> - **수정할 파일**: \`src/auth/Login.js\`
> - **변경 내용**:
>   1. \`checkLogin\` 함수 내부에 유효성 검사 로직 추가
>   2. API 호출 에러 처리 추가

## ✅ 완료 조건 (Definition of Done)
- [ ] 조건 1
- [ ] 조건 2

## 📝 진행 기록
| 날짜 | 내용 |
|:---|:---|
| ${today} | 이슈 생성 |`;

    let issueBody;
    if (type === 'bug' || type === 'fix') {
        issueBody = `## 🚨 버그 리포트 (Bug Report)
` + educationTemplate;
    } else {
        issueBody = `## ✨ 기능 명세서 (Feature Spec)
` + educationTemplate;
    }

    // 임시 파일로 body 저장 (PowerShell 호환)
    const tempBodyPath = path.join(process.cwd(), '.issue_body_temp.md');
    fs.writeFileSync(tempBodyPath, issueBody, 'utf8');

    // GitHub 이슈 생성
    const url = run(`gh issue create --title "${fullTitle}" --label "${label}" --body-file "${tempBodyPath}"`);

    // 임시 파일 삭제
    fs.unlinkSync(tempBodyPath);

    // URL에서 이슈 번호 추출
    const issueNum = url.split('/').pop();
    log(`✅ Issue Created: #${issueNum} (${url})`, colors.green);
    log(`   Title: ${fullTitle}`, colors.yellow);

    // ISSUES.md 동기화 호출
    log('\n2️⃣ Syncing ISSUES.md...', colors.green);
    try {
        execSync('node scripts/sync-issues.js', { stdio: 'inherit' });
    } catch (e) {
        log('⚠️ Sync failed, but issue was created.', colors.yellow);
    }

    log('\n✨ Ready to Work!', colors.blue);
    log(`   커밋 시 #${issueNum} 사용하세요.`, colors.yellow);
}

main();
