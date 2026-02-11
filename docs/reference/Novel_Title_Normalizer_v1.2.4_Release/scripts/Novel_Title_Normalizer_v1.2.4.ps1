# scripts/Novel_Title_Normalizer_v1.2.4.ps1
# 📘 소설 제목 정리기 v1.2.4 (Novel Title Normalizer)
# 이 스크립트는 3가지 기능을 하나로 합친 통합 도구입니다:
# 1. 파일 목록 추출 (Extract)
# 2. AI 매핑 생성 (Gemini API)
# 3. 이름 변경 적용 (Rename)

param (
    [string]$Mode = "All" # All, Extract, Map, Rename
)

# 🛑 기본 설정
$ErrorActionPreference = "Stop" # 에러나면 바로 멈춤 (안전 제일)

# 📂 경로 설정 (EXE 변환 시 호환성 확보)
if ($PSScriptRoot -and (Test-Path $PSScriptRoot)) {
    $ScriptRoot = $PSScriptRoot
}
else {
    # EXE로 실행될 때 $PSScriptRoot가 비어있거나 임시 폴더일 수 있음
    $ScriptRoot = [System.AppDomain]::CurrentDomain.BaseDirectory
}

# 📂 프로젝트 루트 찾기 (scripts 폴더 안에 있으면 부모 폴더가 루트)
if ($ScriptRoot -match "[\\/]scripts$") {
    $ProjectRoot = Split-Path $ScriptRoot -Parent
}
else {
    $ProjectRoot = $ScriptRoot
}
Write-Host "📂 실행 위치: $ScriptRoot" -ForegroundColor DarkGray
Write-Host "📂 프로젝트 루트: $ProjectRoot" -ForegroundColor DarkGray

# UTF-8 입출력 강제 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 🛠️ 필요한 라이브러리 로드 (GUI 등)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Web

# ==============================================================================
# 🔑 0. 전역 유틸리티 및 설정
# ==============================================================================

# .env 파일 로드 함수
function Get-ApiKey {
    # .env 위치 후보군 (EXE 실행 위치, 상위 폴더, 현재 폴더)
    $EnvCandidates = @(
        (Join-Path $ProjectRoot ".env"),
        (Join-Path $ProjectRoot "..\.env"),
        (Join-Path $ScriptRoot ".env")
    )

    $ApiKey = $null

    foreach ($path in $EnvCandidates) {
        if (Test-Path $path) {
            foreach ($line in Get-Content $path) {
                if ($line -match "^\s*GOOGLE_API_KEY\s*=\s*(.+)$") {
                    $ApiKey = $matches[1].Trim()
                    break
                }
            }
            if ($ApiKey) { break }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        $ApiKey = $env:GOOGLE_API_KEY
    }

    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        # [Interactive] 키가 없으면 사용자에게 요청
        Write-Warning "`n⚠️ .env 파일을 찾을 수 없거나 API 키가 설정되지 않았습니다."
        $enteredKey = Read-Host "🔑 Google API Key를 입력하세요 (입력 없이 엔터 시 종료)"
        
        if (-not [string]::IsNullOrWhiteSpace($enteredKey)) {
            $ApiKey = $enteredKey.Trim()
            
            # .env 파일 생성 및 저장
            $envPath = Join-Path $ProjectRoot ".env"
            try {
                "GOOGLE_API_KEY=$ApiKey" | Out-File -FilePath $envPath -Encoding UTF8
                Write-Host "✅ API 키가 저장되었습니다: $envPath" -ForegroundColor Green
            }
            catch {
                Write-Warning "⚠️ .env 파일 저장 실패 (권한 문제 등): $_"
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        Write-Error "❌ 오류: 유효한 Google API Key가 없습니다."
        return $null
    }
    return $ApiKey
}

# ==============================================================================
# 📂 1. 파일 목록 추출 함수 (Extract-Files)
# ==============================================================================
function Extract-Files {
    Write-Host "`n🔍 [1단계] 대상 폴더 선택" -ForegroundColor Cyan
    Write-Host "   👉 잠시 후 폴더 선택 창이 열립니다."
    Write-Host "   👉 정리할 파일들이 들어있는 '폴더'를 선택해 주세요."

    $folderDialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $folderDialog.Description = "정리할 파일이 있는 폴더를 선택하세요"
    $folderDialog.ShowNewFolderButton = $false
    
    # 기본 경로 설정 (downloads 폴더가 있다면)
    $downloadsDir = Join-Path $ProjectRoot "downloads"
    if (Test-Path $downloadsDir) { 
        # 상대 경로 문제를 피하기 위해 절대 경로로 변환
        $folderDialog.SelectedPath = (Resolve-Path $downloadsDir).Path 
    }

    Write-Host "   창이 열리기를 기다리는 중..." -ForegroundColor DarkGray
    
    if ($folderDialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $TargetFolder = $folderDialog.SelectedPath
        Write-Host "   ✅ 선택됨: $TargetFolder" -ForegroundColor Green
    }
    else {
        Write-Warning "폴더가 선택되지 않았습니다. 취소합니다."
        return $null
    }

    # 출력 파일명 생성 (file_list_폴더이름.txt)
    # 날짜 대신 선택한 폴더의 이름(예: 2026-01-31)을 따라갑니다.
    $folderName = Split-Path $TargetFolder -Leaf
    $outputFileName = "file_list_$folderName.txt"
    
    # ═══════════════════════════════════════════════════════════════
    # 📂 출력 위치 선택
    # ═══════════════════════════════════════════════════════════════
    Write-Host "`n📂 파일 목록을 어디에 저장할까요?" -ForegroundColor Cyan
    Write-Host "   [1] 선택한 폴더의 상위 폴더" -ForegroundColor Yellow
    Write-Host "   [2] 실행 파일이 있는 위치" -ForegroundColor Yellow
    $locationChoice = Read-Host "`n선택 (기본값: 1)"
    if (-not $locationChoice) { $locationChoice = "1" }
    
    if ($locationChoice -eq "2") {
        # 실행 파일 위치 (여기는 ScriptRoot 유지 가능하지만 편의상 ProjectRoot)
        $outputDir = $ProjectRoot
    }
    else {
        # 선택한 폴더의 상위 폴더
        $parentFolder = Split-Path $TargetFolder -Parent
        $outputDir = $parentFolder
    }
    # ═══════════════════════════════════════════════════════════════
    
    $OutputFile = Join-Path $outputDir $outputFileName

    Write-Host "`n📂 [2단계] 파일 목록 추출 중..." -ForegroundColor Cyan
    Write-Host "   저장 위치: $OutputFile"

    # 제외할 확장자 목록
    $excludeExts = @(".exe", ".bat", ".ps1", ".js", ".json", ".lnk", ".db")

    $files = Get-ChildItem -Path $TargetFolder -File -Recurse | Where-Object { 
        $excludeExts -notcontains $_.Extension 
    }

    if ($files.Count -eq 0) {
        Write-Warning "❌폴더에 파일이 없습니다."
        return $null
    }

    # 파일 쓰기
    $stream = [System.IO.StreamWriter]::new($OutputFile, $false, [System.Text.Encoding]::UTF8)
    
    # 메타데이터 기록
    $stream.WriteLine("# SourceDirectory: $TargetFolder")
    $stream.WriteLine("# Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $stream.WriteLine("")

    foreach ($f in $files) {
        # 너무 작은 파일(1KB 미만) 무시 (v1.0.1: 512바이트로 기준 완화)
        if ($f.Length -lt 512) { continue }

        # 용량 표시
        $sizeMB = [math]::Round($f.Length / 1MB, 2)
        $sizeInfo = if ($sizeMB -ge 1) { "$sizeMB MB" } else { "$([math]::Round($f.Length / 1KB, 1)) KB" }
        
        # 기록 (이름 | 용량)
        $stream.WriteLine("$($f.Name) | $sizeInfo")
    }

    $stream.Close()
    Write-Host "   ✅ $($files.Count)개 파일 추출 완료." -ForegroundColor Green
    
    return @{
        "FileList"     = $OutputFile
        "TargetFolder" = $TargetFolder
    }
}

# ==============================================================================
# 🧠 2. AI 매핑 생성 함수 (Generate-Mapping)
# ==============================================================================
function Generate-Mapping {
    param ([string]$InputFile, [string]$OutputFile)

    # [Interactive] 입력 파일이 없으면 물어보기
    if (-not $InputFile -or -not (Test-Path $InputFile)) {
        $recentLists = @(Get-ChildItem -Path $ProjectRoot -Filter "file_list_*.txt" | Sort-Object LastWriteTime -Descending)
        # Downloads 폴더도 확인
        if (Test-Path (Join-Path $ProjectRoot "downloads")) {
            $recentLists += @(Get-ChildItem -Path (Join-Path $ProjectRoot "downloads") -Filter "file_list_*.txt" | Sort-Object LastWriteTime -Descending)
        }

        if ($recentLists) {
            Write-Host "`n🔍 최근 생성된 파일 목록:"
            # 중복 제거 (이름 기준) - Select-Object 대신 Group-Object 사용 (속성 보존)
            $uniqueLists = $recentLists | Group-Object Name | ForEach-Object { $_.Group[0] }
            $uniqueLists = @($uniqueLists) # Force Array

            for ($i = 0; $i -lt $uniqueLists.Count; $i++) {
                Write-Host "   [$($i+1)] $($uniqueLists[$i].Name)  ($($uniqueLists[$i].LastWriteTime.ToString('MM-dd HH:mm')))"
            }
            $choice = Read-Host "`n번호를 선택하거나 파일 경로를 직접 입력하세요 (기본값: 1)"
            if (-not $choice) { $choice = "1" }
            if ($choice -match "^\d+$" -and [int]$choice -le $uniqueLists.Count) {
                # 인덱스 주의 ($i는 0부터 시작, choice는 1부터)
                # Select-Object가 객체를 완전히 보존하지 않을 수 있어서 원본 리스트에서 다시 찾거나 해야 함.
                # 편의상 이름으로 원본 경로 찾기
                $selectedName = $uniqueLists[[int]$choice - 1].Name
                $InputFile = ($recentLists | Where-Object { $_.Name -eq $selectedName } | Select-Object -First 1).FullName
            }
            else {
                $InputFile = $choice.Trim('"')
            }
        }
        else {
            $InputFile = Read-Host "`n파일 목록 경로를 입력하세요 (file_list_....txt)"
            $InputFile = $InputFile.Trim('"')
        }
    }

    if ([string]::IsNullOrWhiteSpace($InputFile) -or -not (Test-Path $InputFile)) {
        Write-Error "입력 파일을 찾을 수 없습니다: $InputFile"
        return $false
    }

    # [Interactive] 출력 파일이 없으면 자동 생성
    if (-not $OutputFile) {
        $dir = [System.IO.Path]::GetDirectoryName($InputFile)
        $name = [System.IO.Path]::GetFileName($InputFile)
        $mappingName = $name.Replace("file_list_", "mapping_result_")
        if ($name -eq $mappingName) { $mappingName = "mapping_result_" + $name }
        $OutputFile = Join-Path $dir $mappingName
    }

    $ApiKey = Get-ApiKey # API 키 로드

    # 상수 설정
    $ChunkSize = 10
    $DelayMs = 2000
    $MaxRetries = 10
    $Models = @("gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3-pro-preview")

    # 프롬프트 (사용자가 수정한 버전 그대로 적용)
    $SystemPrompt = @"
You are a Professional File Renaming Expert.
(너는 파일 이름 변경 전문가야.)
Your goal is to normalize messy filenames into a strict, readable standard format.
(너의 목표는 지저분한 파일 이름들을 깔끔하고 읽기 편한 표준 형식으로 바꾸는 거야.)

### 🛡️ Core Principles
1. **Preserve Tags**: Keep '[AI번역]', '(AI)' etc.
2. **Remove Hanja**: Delete ALL Chinese characters.
3. **Remove Metadata**: Leading '[Author]', '(Genre)', '[텍본]' etc. (작가의 닉네임을 삭제한다!)
4. **Text Cleanup**: 
   - Replace spaces with underscores '_'.
   - Fix separators: No '_-_', ' - '. Use simple delimiters.

### 📏 Naming Standard
**Format**: 'Title(Range.Status_Addon.Range.Status).ext'

#### 1. Range & Status
- **Separator**: '~' (e.g., '1-100' -> '1~100').
- **Implicit Start**: If '-225', assume '1~225'.
- **Status Keywords**:
  - '완', '完', '완결' -> '완결' (다른 애드온이 있어도 완결 우선 처리)
  - '연재', '미완', '中' -> '연재' (2 chars)
  - '3부 연재중' -> '3부_연재' (Volume_Status)
  - '외포완' -> '완결_외전' (완결 포함 외전 라는 뜻임. 완결 우선 처리)
  - '외', '外' -> '외전'
  - '프롤', '프롤로그' -> '프롤'
  - '포함', '포' -> (삭제함)
  - 한자 제목은 한글로 번역해서 반영할것
  - '후기', '후일담', '에필', '외전' ... 등등 -> (다른 애드온 보다 연재를 더 먼저 우선시하고 애드온도 2글자에 맞춰서 단어 그대로 반영할것)
  - (숫자와 외전만 있다면 예를들어 1-200외전 -> 1~200.완결_외전 으로 변경. 많은 화수와 외전이 있다는건 본편이 완결이라는 뜻이기 때문)
  - (외x, 외o, 특외x, 외전x, 에필o, 후기x... 등등) 외x -> 완결, 에필o -> 완결_에필 // 후기x -> 완결 // 특외o -> 완결_특별외전
    (애드온에 o, x 는 완결은 이미 되어있고, 외전이 포함된것 o 과 안된것 x 이므로 파일명에 포함된것을 반영할것)
  - 개정판, 개정 -> 투자의_신으로_살겠다-개정판(1~225.완결).txt  (파일명 뒤에 - 과 함께 붙임)
  - 권 -> 책 한권을 의미 하므로 유지하며, 파일명에 적절하게 반영할것
  (중요!!!)
  - '1-2126화 본편 1352화 外 746화 에필 28화 完' -> (1~2126.완결_본편.1~1352_외전.1~746_에필.1~28)
  (중요!!!)
  - '1-500외전 501-530선계여의 531-630 完' -> (1~500.완결_외전.501~530_선계여의.531~630)
  (중요!!!)
  - '300외전35완결' -> (1~300.완결_외전.1~35)
  - 화수.완결여부_애드온.화수_애드온.화수 -> (화수와 애드온은 '애드온.화수'를 한세트로 보고 세트마다 '_' 로 구분 // 첫 세트는 '화수.완결여부'로 시작)

#### 2. Special Rules
- **Adult Content (#)**: 
  - IF '19금', '성인', '(19)', '19)' , '(18)' , '야설', '야겜', '야동', (성인물 관련 단어들..) exists:
  - [TS], TS, ts -> '#TS_' 로 변경 (예제 : [TS]몸 파는 드래곤(124까지).txt   -----------------   #TS_몸_파는_드래곤(1~124.연재).txt)
  - Place '#' at the **VERY START** of the filename. 
  - Do NOT add an underscore after '#'.
  - Example: '#Title(1~100.완결).txt'
- **Epilogue**: '에필로그' '에포' -> '에필' (2 chars).
- **Special/Side**: '특별 외전' -> '특별외전'. '트리센_저택(특별외전).epub'
- **유명한 소설 : '$작가-파일의작품명'  (예제: [김용]설산비호 -> $김용-설산비호, 파운데이션 -> $아이작_아시모프-파운데이션, 1.Twilight.StephenieMeyer -> $Stephenie_Meyer-1_Twilight
- (유명한 소설은 $ 표시를 가장 앞에 붙이고, 가능하면 작가이름도 포함할것)

#### 3. Split Files & Series
- Keep '.z01', '.part1' base names identical.

#### 4. Output Format
**CRITICAL**: Output ONLY the mapping lines. NO explanations, NO code, NO headers.
Each line MUST be: 'original_filename   -----------------   new_filename'

⚠️ **ABSOLUTE RULE - ORIGINAL FILENAME PRESERVATION** ⚠️
The ORIGINAL filename (LEFT side of '-----------------') MUST be COPIED EXACTLY as given in the input.
DO NOT change ANY character. DO NOT convert Hanja to Hangul. DO NOT add/remove spaces or punctuation.
Copy it BYTE-FOR-BYTE, CHARACTER-FOR-CHARACTER.
If input is '도화만리(桃花萬里) 1-528.txt', output MUST start with '도화만리(桃花萬里) 1-528.txt   -----------------'
NEVER EVER modify the original filename. This is NON-NEGOTIABLE.

### 🧩 Examples
Input: [퓨전] 이혼 후 코인대박 1-252 完.txt
Output: [퓨전] 이혼 후 코인대박 1-252 完.txt   -----------------   이혼_후_코인대박(1~252.완결).txt

Input: 19.따먹히는 순애 금태양 0-317 完.txt
Output: 19.따먹히는 순애 금태양 0-317 完.txt   -----------------   #따먹히는_순애_금태양(0~317.완결).txt

Input: 트리센 저택 특별 외전.epub
Output: 트리센 저택 특별 외전.epub   -----------------   트리센_저택(특별외전).epub

Input: 투자의 신으로 살겠다 -225 완.txt
Output: 투자의 신으로 살겠다 -225 완.txt   -----------------   투자의_신으로_살겠다(1~225.완결).txt

Input: 천하제일인의 소꿉친구 1-1385 (3부 연재중).zip
Output: 천하제일인의 소꿉친구 1-1385 (3부 연재중).zip   -----------------   천하제일인의_소꿉친구(1~1385.3부_연재).zip

Input: [무장] 갓 오브 블랙필드 1-581 1부-외전-2부 완.txt
Output: [무장] 갓 오브 블랙필드 1-581 1부-외전-2부 완.txt   -----------------   갓_오브_블랙필드(1~581.완결_1부_외전_2부).txt

(중요!!)
Input: 귀환용사의골목식당300외전35완결.txt
Output: 귀환용사의골목식당300외전35완결.txt   -----------------   귀환용사의_골목식당(1~300.완결_외전.1~35).txt
(중요!!)
Input: [은열]무당기협 1-500외전 501-530선계여의 531-630 完.txt
Output: [은열]무당기협 1-500외전 501-530선계여의 531-630 完.txt   -----------------   무당기협(1~500.완결_외전.501~530_선계여의.531~630).txt
(중요!!)
Input: [시준] 광룡이계전생 1-361 1부 完 2부 146 完.txt
Output: [시준] 광룡이계전생 1-361 1부 完 2부 146 完.txt   -----------------   광룡이계전생(1부.1~361.완결_2부.1~146).txt
(중요!!)
Input: 마탄의 사수 1-2126화 본편 1352화 外 746화 에필 28화 完.zip
Output: 마탄의 사수 1-2126화 본편 1352화 外 746화 에필 28화 完.zip   -----------------   마탄의_사수(1~2126.완결_본편.1~1352_외전.1~746_에필.1~28).zip
(중요!!!)
Input: 회귀한 천재 마공사 1-358(본편 完), 1-17(외전 完)@강원산.txt
Output: 회귀한 천재 마공사 1-358(본편 完), 1-17(외전 完)@강원산.txt   -----------------   회귀한_천재_마공사(1~358.완결_외전.1~17.완결).txt
(중요!!!)
Input: [록소] 공작저로 간 반쪽짜리 치유술사 160완 10외.epub
Output: [록소] 공작저로 간 반쪽짜리 치유술사 160완 10외.epub   -----------------   공작저로_간_반쪽짜리_치유술사(1~160.완결_외전.1~10).epub
(중요!!!)
Input: 돌아오니 SSS급 몬스터 1-240 완 두루마리.txt
Output: 돌아오니 SSS급 몬스터 1-240 완 두루마리.txt   -----------------   돌아오니_SSS급_몬스터(1~240.완결).txt
(중요!!!)
Input: 약 만드는 시한부 악녀님 1-164(본편 완) 외전 1-22(미완).txt
Output: 약 만드는 시한부 악녀님 1-164(본편 완) 외전 1-22(미완).txt   -----------------   약_만드는_시한부_악녀님(1~164.완결_외전.1~22_연재).txt
(중요!!!)
Input: 전추수선：재40K우주수도덕경 1-545 (AI번역) 패러디 워해머.txt
Output: 전추수선：재40K우주수도덕경 1-545 (AI번역) 패러디 워해머.txt   -----------------   [AI번역]전추수선_재40K우주수도덕경(1~545.연재).txt
(중요!!!)
Input: 화영지아시초대목 1195 (AI번역) 패러디 나루토.txt
Output: 화영지아시초대목 1195 (AI번역) 패러디 나루토.txt   -----------------   [AI번역]화영지아시초대목(1~1195_패러디_나루토).txt
(중요!!!)
Input: [공금]스토커 공녀 - 프롤로그-120화(완)ⓨ.epub
Output: [공금]스토커 공녀 - 프롤로그-120화(완)ⓨ.epub   -----------------   스토커_공녀(프롤~120.완결).epub
"@

    # 파일 읽기
    $RawContent = Get-Content $InputFile -Encoding UTF8
    $Lines = @()
    foreach ($line in $RawContent) {
        if (-not [string]::IsNullOrWhiteSpace($line) -and -not $line.StartsWith("#")) {
            $Lines += $line
        }
    }

    Write-Host "`n🚀 AI 매핑 생성 시작..." -ForegroundColor Cyan
    Write-Host "📄 입력: $InputFile"
    Write-Host "💾 출력: $OutputFile"
    Write-Host "📂 처리할 파일: $($Lines.Count)개"

    $FinalResults = @()

    # 청크 루프
    for ($i = 0; $i -lt $Lines.Count; $i += $ChunkSize) {
        $end = [math]::Min($i + $ChunkSize, $Lines.Count)
        $chunkRaw = $Lines[$i..($end - 1)]
        $chunkFilenames = $chunkRaw | ForEach-Object { ($_ -split "\|")[0].Trim() }

        Write-Host "   처리 중... 청크 $([math]::Floor($i / $ChunkSize) + 1) ($($chunkFilenames.Count)개)" -ForegroundColor Yellow

        $CurrentPrompt = "$SystemPrompt`n`n### Task`nRename the following files:`n" + ($chunkFilenames -join "`n")
        $ChunkSuccess = $false

        # 내부 헬퍼 함수: API 호출 전담
        function Invoke-GeminiAPI {
            param (
                [string]$PromptText,
                [int]$RetryCount
            )
        
            # 모델 로테이션
            $ModelIndex = $RetryCount % $Models.Count
            $ModelName = $Models[$ModelIndex]
            $Url = "https://generativelanguage.googleapis.com/v1beta/models/${ModelName}:generateContent?key=$ApiKey"
        
            $Body = @{ contents = @( @{ parts = @( @{ text = $PromptText } ) } ) }
            $JsonBody = $Body | ConvertTo-Json -Depth 10

            try {
                Write-Host "      🤖 모델 [${ModelName}] 시도 ($($RetryCount + 1))..." -NoNewline
                
                # [Fix] WebClient를 사용하여 UTF-8 강제 처리 (환경 무관하게 확실함)
                $WebClient = New-Object System.Net.WebClient
                $WebClient.Encoding = [System.Text.Encoding]::UTF8
                $WebClient.Headers.Add("Content-Type", "application/json; charset=utf-8")
                
                # UploadData는 바이트 배열을 반환하므로 확실하게 디코딩 가능
                $ResponseBytes = $WebClient.UploadData($Url, "POST", [System.Text.Encoding]::UTF8.GetBytes($JsonBody))
                $RawContent = [System.Text.Encoding]::UTF8.GetString($ResponseBytes)
                
                $Response = $RawContent | ConvertFrom-Json
            
                if ($Response.candidates -and $Response.candidates[0].content.parts) {
                    Write-Host " ✅ 성공!" -ForegroundColor Green
                    return $Response.candidates[0].content.parts[0].text
                }
                throw "Invalid Response"
            }
            catch {
                Write-Host " ❌ 실패" -ForegroundColor Red
            
                $errorMsg = $_.Exception.Message
                if ($_.Exception.Response) {
                    $detailedError = ""
                    # PowerShell 7+ (Core)
                    if ($_.Exception.Response.Content) {
                        $detailedError = $_.Exception.Response.Content.ReadAsStringAsync().Result
                    }
                    # PowerShell 5.1 (Legacy)
                    elseif ($_.Exception.Response.GetResponseStream) {
                        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                        $detailedError = $reader.ReadToEnd()
                        $reader.Close()
                    }

                    if ($detailedError -match "overloaded" -or $_.Exception.Response.StatusCode -eq 503) {
                        Write-Warning "      ⚠️ 과부하(503): 잠시 대기..."
                    }
                    else {
                        Write-Warning "      ⚠️ API 오류: $errorMsg"
                    }
                }
                throw # 상위로 에러 전파
            }
        }

        # API 호출 루프
        for ($attempt = 0; $attempt -lt $MaxRetries; $attempt++) {
            try {
                # 함수 호출로 대체
                $ApiResult = Invoke-GeminiAPI -PromptText $CurrentPrompt -RetryCount $attempt
            
                # 후처리 (Post-Processing)
                $ProcessedText = Post-Process -Text $ApiResult
            
                # ═══════════════════════════════════════════════════════════════
                # 🛡️ AI 원본 무시: AI가 반환한 "원본"을 버리고, 우리가 가진 원본 사용
                # ═══════════════════════════════════════════════════════════════
                $aiLines = @($ProcessedText -split "`n" | Where-Object { $_.Trim() -ne "" })
                $correctedLines = @()
                
                for ($idx = 0; $idx -lt $aiLines.Count; $idx++) {
                    $aiLine = $aiLines[$idx]
                    if ($aiLine.Contains("-----------------")) {
                        $parts = $aiLine -split "-----------------"
                        $newName = $parts[$parts.Count - 1].Trim()
                        # AI가 반환한 원본 무시, 우리가 가진 원본 사용
                        if ($idx -lt $chunkFilenames.Count) {
                            $correctedLines += "$($chunkFilenames[$idx])   -----------------   $newName"
                        }
                        else {
                            $correctedLines += $aiLine
                        }
                    }
                    else {
                        $correctedLines += $aiLine
                    }
                }
                $ProcessedText = $correctedLines -join "`n"
                # ═══════════════════════════════════════════════════════════════
            
                # 검증
                $OutputCount = ($ProcessedText -split "`n" | Where-Object { $_.Trim() -ne "" }).Count
                if ($OutputCount -ne $chunkFilenames.Count) {
                    throw "Count Mismatch"
                }

                $FinalResults += $ProcessedText
                $ChunkSuccess = $true
                break
            }
            catch {
                $statusMsg = if ($_.Exception.Message -eq "Count Mismatch") { "개수 불일치" } else { $_.Exception.Message }
                Write-Host " ⚠️ [재시도] $statusMsg" -ForegroundColor Yellow
                Start-Sleep -Milliseconds $DelayMs
            }
        }

        if (-not $ChunkSuccess) {
            Write-Error "      ❌ 해당 청크 처리에 모두 실패했습니다. 원본을 유지합니다."
            foreach ($f in $chunkFilenames) { $FinalResults += "$f   -----------------   [ERROR_FAILED]_$f" }
        }

        Start-Sleep -Milliseconds $DelayMs
    }

    # 결과 저장
    $FinalString = $FinalResults -join "`n"
    # Fix: Count actual lines inside the chunks, not just the chunk count
    $OutputCount = ($FinalString -split "`n" | Where-Object { $_.Trim() -ne "" }).Count

    Write-Host "------------------------------------------------"
    Write-Host "📊 입력 파일 수: $($Lines.Count)"
    Write-Host "📊 출력 매핑 수: $OutputCount"

    if ($Lines.Count -ne $OutputCount) {
        Write-Warning "⚠️ 경고: 개수가 일치하지 않습니다! ($($Lines.Count) vs $OutputCount)"
    }
    else {
        Write-Host "✅ 무결성 검사 통과"
    }

    $FinalString | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "✅ 완료! 저장됨: $OutputFile"
    return $true
}

# --- 도우미 함수: 후처리 ---
function Post-Process {
    param ([string]$Text)
    $ResultLines = @()
    $RawLines = $Text -split "`n"
    
    foreach ($line in $RawLines) {
        $l = $line.Trim()
        if (-not $l.Contains("-----------------")) { continue }
        if ($l.Contains("Original Filename")) { continue }
        
        $parts = $l -split "-----------------"
        if ($parts.Count -lt 2) { continue }
        
        $original = $parts[0].Trim()
        $newName = $parts[$parts.Count - 1].Trim()
        
        if (-not $newName) { $ResultLines += $l; continue }

        # 규칙 적용
        $newName = $newName.Replace(", ", "_").Replace(",", "_")
        $newName = $newName.Replace("포함", "").Replace("및", "").Replace("본편", "")
        if ($newName.Contains("#")) { $newName = "#" + $newName.Replace("#", "") }
        $newName = $newName.Replace("에필로그", "에필")
        $newName = $newName -replace "_-_", "-"
        $newName = $newName -replace "__", "_"
        $newName = $newName -replace "_\)", ")"
        $newName = $newName -replace "\(_", "("
        if ($newName.StartsWith("#_")) { $newName = "#" + $newName.Substring(2) }
        $newName = $newName -replace "^#\s*", "#"

        $ResultLines += "$original   -----------------   $newName"
    }
    return ($ResultLines -join "`n")
}


# ==============================================================================
# 📝 3. 이름 변경 적용 함수 (Apply-Rename)
# ==============================================================================
function Apply-Rename {
    param ([string]$MappingFile, [string]$TargetFolder)

    Write-Host "`n📝 [3단계] 검토 및 변경" -ForegroundColor Cyan
    
    # [Interactive] 매핑 파일이 없으면 물어보기
    if (-not $MappingFile -or -not (Test-Path $MappingFile)) {
        $recentFiles = @(Get-ChildItem -Path $ProjectRoot -Filter "mapping_result_*.txt" | Sort-Object LastWriteTime -Descending)
        if (Test-Path (Join-Path $ProjectRoot "downloads")) {
            $recentFiles += @(Get-ChildItem -Path (Join-Path $ProjectRoot "downloads") -Filter "mapping_result_*.txt" | Sort-Object LastWriteTime -Descending)
        }

        if ($recentFiles) {
            Write-Host "`n🔍 최근 발견된 매핑 파일:"
            # 중복 제거 (이름 기준)
            $uniqueFiles = $recentFiles | Group-Object Name | ForEach-Object { $_.Group[0] }
            $uniqueFiles = @($uniqueFiles) # Force Array

            for ($i = 0; $i -lt $uniqueFiles.Count; $i++) {
                Write-Host "   [$($i+1)] $($uniqueFiles[$i].Name)  ($($uniqueFiles[$i].LastWriteTime.ToString('MM-dd HH:mm')))"
            }
            $choice = Read-Host "`n번호를 선택하거나 파일 경로를 직접 입력하세요 (기본값: 1)"
            if (-not $choice) { $choice = "1" }
            if ($choice -match "^\d+$" -and [int]$choice -le $uniqueFiles.Count) {
                # 인덱스 주의 ($i는 0부터 시작, choice는 1부터)
                # 편의상 이름으로 원본 경로 찾기 (가장 최근 것)
                $selectedName = $uniqueFiles[[int]$choice - 1].Name
                $MappingFile = ($recentFiles | Where-Object { $_.Name -eq $selectedName } | Select-Object -First 1).FullName
            }
            else {
                $MappingFile = $choice.Trim('"')
            }
        }
        else {
            $MappingFile = Read-Host "`n매핑 파일 경로를 입력하세요 (mapping_result_....txt)"
            $MappingFile = $MappingFile.Trim('"')
        }
    }
    if (-not (Test-Path $MappingFile)) { Write-Error "매핑 파일을 찾을 수 없습니다: $MappingFile"; return }

    # [Interactive] 대상 폴더가 없으면 물어보기
    if (-not $TargetFolder -or -not (Test-Path $TargetFolder)) {
        # 매핑 파일 이름에서 폴더명 추측 (mapping_result_폴더명.txt)
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($MappingFile)
        if ($baseName -match "mapping_result_(.+)") {
            $guessedFolder = $matches[1]
            # 1. 스크립트 실행 위치 기준
            $candidate1 = Join-Path $ProjectRoot "downloads\$guessedFolder"
            # 2. EXE/스크립트 위치 기준
            $candidate2 = Join-Path $ProjectRoot $guessedFolder
            # 3. Downloads/ 기준 (일반적 구조)
            $candidate3 = Join-Path $ScriptRoot "downloads\$guessedFolder"

            if (Test-Path $candidate1) { $TargetFolder = $candidate1 }
            elseif (Test-Path $candidate2) { $TargetFolder = $candidate2 }
            elseif (Test-Path $candidate3) { $TargetFolder = $candidate3 }
        }

        if (-not $TargetFolder) {
            $TargetFolder = Read-Host "`n📂 소설 파일들이 있는 대상 폴더 경로를 입력하세요"
            $TargetFolder = $TargetFolder.Trim('"')
        }
    }
    
    if (-not (Test-Path $TargetFolder)) { Write-Error "대상 폴더가 없습니다: $TargetFolder"; return }
    
    Write-Host "   📂 대상 폴더: $TargetFolder"
    Write-Host "   📄 매핑 파일: $MappingFile"

    # 사용자 확인
    Invoke-Item $MappingFile
    $confirm = Read-Host "`n❓ 메모장이 열렸습니다. 내용을 검토하고 [Enter]를 누르면 변경을 시작합니다 (중단하려면 Ctrl+C)"
    
    Write-Host "🚀 이름 변경 시작..."
    $lines = Get-Content $MappingFile -Encoding UTF8
    $count = 0; $skipped = 0; $errors = 0;
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 📚 [핵심] 사전(Dictionary) 생성 - 폴더의 실제 파일을 먼저 전부 읽음
    # ═══════════════════════════════════════════════════════════════════════════
    Write-Host "📂 폴더 내 파일 인덱싱 중..." -ForegroundColor Cyan
    $fileIndex = @{}
    $allFiles = Get-ChildItem -LiteralPath $TargetFolder -File
    foreach ($f in $allFiles) {
        $fileIndex[$f.Name] = $f.FullName
    }
    Write-Host "   ✅ $($fileIndex.Count)개 파일 인덱스 완료" -ForegroundColor Green
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 불법 문자 목록 (Windows 파일명에 사용 불가)
    $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
    
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
        if ($line.Contains("-----------------")) {
            $parts = $line -split "-----------------"
            if ($parts.Count -ge 2) {
                $originalName = $parts[0].Trim()
                $newName = $parts[$parts.Count - 1].Trim()
                
                if ($newName -eq "UNKNOWN" -or $newName -eq $originalName) { 
                    Write-Host "   ⏭️ [건너뜀] 변경 필요 없음: $originalName" -ForegroundColor DarkGray
                    $skipped++; continue 
                }
                if ($newName.Contains("[ERROR_FAILED]")) { Write-Warning "실패 항목 건너뜀: $originalName"; $skipped++; continue }
                
                # ═══════════════════════════════════════════════════════════════
                # 🧹 파일명 정제 (불법 문자 제거)
                # ═══════════════════════════════════════════════════════════════
                foreach ($c in $invalidChars) {
                    $newName = $newName.Replace([string]$c, '')
                }
                # ═══════════════════════════════════════════════════════════════

                # ═══════════════════════════════════════════════════════════════
                # 🔍 사전에서 직접 조회 (추측/정규식 없음, 100% 정확)
                # ═══════════════════════════════════════════════════════════════
                if ($fileIndex.ContainsKey($originalName)) {
                    $sourcePath = $fileIndex[$originalName]
                }
                elseif ($fileIndex.ContainsKey($newName)) {
                    # ✅ 이미 처리됨: 원래 이름은 없지만 새 이름이 이미 존재함
                    Write-Host "   ⏭️ [이미 완료] $originalName -> $newName" -ForegroundColor DarkGray
                    $skipped++
                    continue
                }
                else {
                    Write-Warning "   ❌ 파일 없음: 원본도 없고 새 이름도 없음: $originalName"
                    $errors++
                    continue
                }
                # ═══════════════════════════════════════════════════════════════

                $destPath = Join-Path $TargetFolder $newName
                
                # 중복 처리
                if (Test-Path -LiteralPath $destPath) {
                    $base = [System.IO.Path]::GetFileNameWithoutExtension($newName)
                    $ext = [System.IO.Path]::GetExtension($newName)
                    $cnt = 1
                    while (Test-Path -LiteralPath $destPath) {
                        $destPath = Join-Path $TargetFolder "$base-$($cnt.ToString('00'))$ext"
                        $cnt++
                    }
                    $newName = [System.IO.Path]::GetFileName($destPath)
                }

                try {
                    Rename-Item -LiteralPath $sourcePath -NewName $newName -ErrorAction Stop
                    Write-Host "✅ [완료] $originalName -> $newName" -ForegroundColor Green
                    $count++
                }
                catch {
                    Write-Host "   ❌ 변경 실패 '$originalName': $_" -ForegroundColor Red
                    $errors++
                }
            }
        }
    }
    
    Write-Host "`n🎉 작업 완료! (성공: $count, 건너뜀: $skipped, 실패: $errors)" -ForegroundColor Green
}


# ==============================================================================
# 🏃‍♂️ 전체 실행 래퍼 (Run-All-Steps)
# ==============================================================================
function Run-All-Steps {
    # 1. 파일 추출
    $extractResult = Extract-Files
    if (-not $extractResult) { return }

    $FileList = $extractResult.FileList
    $TargetDir = $extractResult.TargetFolder

    # 2. AI 매핑
    $MappingFile = $FileList.Replace("file_list_", "mapping_result_")
    Generate-Mapping -InputFile $FileList -OutputFile $MappingFile

    # 3. 이름 변경
    Apply-Rename -MappingFile $MappingFile -TargetFolder $TargetDir
    
    Write-Host "`n✅ 전체 작업이 완료되었습니다." -ForegroundColor Green
    Pause
}

# ==============================================================================
# 🎮 메인 실행 로직 (대화형 메뉴)
# ==============================================================================

while ($true) {
    Clear-Host
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "      📘 소설 제목 정리기 v1.2.4 (Novel Title Normalizer)" -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " 1. 🚀 전체 자동 실행 (파일 추출 -> AI 매핑 -> 이름 변경)"
    Write-Host " 2. 📂 파일 목록 추출 (Extract Only)"
    Write-Host " 3. 🤖 AI 매핑 생성 (Generate Mapping)"
    Write-Host " 4. 📝 이름 변경 적용 (Apply Rename)"
    Write-Host " 0. ❌ 종료 (Exit)"
    Write-Host "================================================================" -ForegroundColor Cyan
    
    $choice = Read-Host " 작업 번호를 선택하세요"
    
    switch ($choice) {
        "1" { try { Run-All-Steps } catch { Write-Host "❌ 에러: $_" -ForegroundColor Red } finally { Pause } }
        "2" { try { Extract-Files } catch { Write-Host "❌ 에러: $_" -ForegroundColor Red } finally { Pause } }
        "3" { try { Generate-Mapping } catch { Write-Host "❌ 에러: $_" -ForegroundColor Red } finally { Pause } }
        "4" { try { Apply-Rename } catch { Write-Host "❌ 에러: $_" -ForegroundColor Red } finally { Pause } }
        "0" { Write-Host "👋 프로그램을 종료합니다."; exit }
        default { Write-Warning "잘못된 입력입니다. 다시 선택해주세요."; Start-Sleep -Seconds 1 }
    }
}
