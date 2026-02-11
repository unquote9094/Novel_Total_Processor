import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

// ANSI 색상 코드
const colors = {
    reset: "\x1b[0m",
    green: "\x1b[32m",
    yellow: "\x1b[33m",
    cyan: "\x1b[36m"
};

function log(msg, color = colors.reset) {
    console.log(`${color}${msg}${colors.reset}`);
}

function main() {
    log('\n🔄 Syncing GitHub Issues...\n', colors.cyan);

    // GitHub Issue 목록 가져오기
    let issues = [];
    try {
        const result = execSync('gh issue list --state all --limit 30 --json number,title,labels,state', {
            encoding: 'utf8',
            env: { ...process.env, GH_PAGER: '', PAGER: 'cat', CI: 'true' },
            timeout: 10000
        });
        issues = JSON.parse(result);
    } catch (error) {
        log('❌ Failed to fetch issues from GitHub.', colors.yellow);
        log('   Make sure you are logged in: gh auth login', colors.yellow);
        return;
    }

    // ISSUES.md 생성
    const now = new Date().toISOString().replace('T', ' ').split('.')[0];
    let content = `# 🐛 GitHub Issues (Auto-Synced)

> **⚠️ 이 파일은 읽기 전용입니다!**
> 수정하지 마세요. \`npm run sync-issues\`로 자동 갱신됩니다.

---

## 📊 현재 상태

`;

    if (issues.length === 0) {
        content += `| # | 제목 | 라벨 | 상태 |\n|:---:|:---|:---:|:---:|\n| - | (이슈 없음) | - | - |\n`;
    } else {
        // Open 이슈 먼저, 그 다음 Closed
        const openIssues = issues.filter(i => i.state === 'OPEN');
        const closedIssues = issues.filter(i => i.state === 'CLOSED').slice(0, 10);

        content += `### 🟢 열린 이슈 (${openIssues.length}개)\n\n`;
        content += `| # | 제목 | 라벨 |\n|:---:|:---|:---:|\n`;

        for (const issue of openIssues) {
            const labels = issue.labels.map(l => l.name).join(', ') || '-';
            content += `| ${issue.number} | ${issue.title} | ${labels} |\n`;
        }

        if (closedIssues.length > 0) {
            content += `\n### ⚪ 최근 닫힌 이슈 (최대 10개)\n\n`;
            content += `| # | 제목 | 라벨 |\n|:---:|:---|:---:|\n`;

            for (const issue of closedIssues) {
                const labels = issue.labels.map(l => l.name).join(', ') || '-';
                content += `| ${issue.number} | ${issue.title} | ${labels} |\n`;
            }
        }
    }

    content += `\n---\n\n> **마지막 동기화**: ${now}\n`;

    // 파일 저장
    const issuesPath = path.join(process.cwd(), 'docs', 'ISSUES.md');
    const docsDir = path.dirname(issuesPath);

    if (!fs.existsSync(docsDir)) {
        fs.mkdirSync(docsDir, { recursive: true });
    }

    fs.writeFileSync(issuesPath, content, 'utf8');
    log(`✅ Synced ${issues.length} issues to docs/ISSUES.md`, colors.green);
}

main();
