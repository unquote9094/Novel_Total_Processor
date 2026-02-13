"""EPUB XHTML 템플릿 및 CSS 정의
Reference: txt-to-epub-converter-main based 'Duokan' style
"""

from ebooklib import epub
from typing import Optional
from pathlib import Path

def get_css() -> str:
    """프리미엄 스타일 CSS 반환 (Duokan Style + KoPubBatang)"""
    return """@namespace epub "http://www.idpf.org/2007/ops";

body {
    font-family: "KoPubBatang", "KoPub Batang", "Apple SD Gothic Neo", "Malgun Gothic", serif;
    margin-top: 5%;
    margin-bottom: 5%;
    margin-left: 5%;
    margin-right: 5%;
    line-height: 1.8;
    text-align: justify;
    word-break: break-all;
}

h1 {
    font-size: 1.6em;
    font-weight: bold;
    margin-top: 2em;
    margin-bottom: 1em;
    text-align: center;
    page-break-after: avoid;
}

h2 {
    font-size: 1.3em;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
    text-align: center;
    page-break-after: avoid;
}

p {
    margin-top: 0.5em;
    margin-bottom: 0.5em;
    text-indent: 1em;
}

/* 표지 및 타이틀 페이지 스타일 */
.title-page {
    text-align: center;
    margin-top: 30%;
}

.title-main {
    font-size: 2.2em;
    font-weight: bold;
    margin-bottom: 0.5em;
}

.title-sub {
    font-size: 1.2em;
    color: #555;
    margin-bottom: 2em;
}

.title-icon {
    font-size: 3em;
    margin-top: 2em;
    margin-bottom: 2em;
}

/* 이미지 스타일 */
img {
    max-width: 100%;
    height: auto;
}

.cover-image {
    height: 100%;
    width: auto;
    max-width: 100%;
}
"""

def create_volume_page(title: str, file_name: str, lang: str = 'ko') -> epub.EpubItem:
    """권/부(Volume) 타이틀 페이지 생성"""
    content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}">
<head>
    <title>{title}</title>
    <link href="../Styles/style.css" rel="stylesheet" type="text/css"/>
</head>
<body>
    <div class="title-page">
        <div class="title-main">{title}</div>
        <div class="title-icon">📖</div>
    </div>
</body>
</html>"""
    
    return epub.EpubItem(
        uid=Path(file_name).stem,
        file_name=file_name,
        media_type="application/xhtml+xml",
        content=content
    )

def create_chapter_page(title: str, body: str, file_name: str, subtitle: Optional[str] = None, lang: str = 'ko') -> epub.EpubItem:
    """챕터 본문 페이지 생성"""
    # 본문 HTML 변환
    body_html = ""
    for line in body.splitlines():
        line = line.strip()
        if line:
            body_html += f"<p>{line}</p>\n"
            
    # 소제목 처리
    subtitle_html = f"<h2>{subtitle}</h2>" if subtitle else ""
    
    content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}">
<head>
    <title>{title}</title>
    <link href="../Styles/style.css" rel="stylesheet" type="text/css"/>
</head>
<body>
    <h1>{title}</h1>
    {subtitle_html}
    {body_html}
</body>
</html>"""
    
    return epub.EpubItem(
        uid=Path(file_name).stem,
        file_name=file_name,
        media_type="application/xhtml+xml",
        content=content
    )

def create_cover_html(file_name: str = "Text/cover.xhtml", image_path: str = "../Images/cover.jpg") -> epub.EpubItem:
    """표지용 HTML 페이지 생성"""
    content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Cover</title>
    <style type="text/css">
        body {{ margin: 0; padding: 0; text-align: center; }}
        div {{ text-align: center; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <div>
        <img src="{image_path}" alt="Cover"/>
    </div>
</body>
</html>"""

    return epub.EpubItem(
        uid=Path(file_name).stem,
        file_name=file_name,
        media_type="application/xhtml+xml",
        content=content
    )
