"""
generate_index.py
─────────────────
루트 폴더의 *_summary.html 파일을 스캔해서
index.html 안의 PAPERS 배열을 자동으로 업데이트합니다.

[파일명 규칙]
  [연도] 논문제목_summary.html
  예) [2024] Attention Is All You Need_summary.html

[메타데이터 방식 - 두 가지 지원]
  1) 파일명에서 자동 추출 (연도)
  2) HTML <meta> 태그 (있으면 우선 적용)
     <meta name="paper-title"  content="논문 제목">
     <meta name="paper-year"   content="2024">
     <meta name="paper-tags"   content="태그1, 태그2">

[실행 방법]
  python3 generate_index.py

Netlify 빌드 시 netlify.toml 설정으로 자동 실행됩니다.
"""

import os
import re
import json
from html.parser import HTMLParser


ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(ROOT, 'index.html')


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self._in_head = True  # summary html은 head 태그 없을 수도 있어 기본 True
        # HTML 내 제목/저자/저널 텍스트도 추출
        self._capture_next = None
        self._title_div_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self._in_head = True
        if tag == 'meta':
            attr_dict = dict(attrs)
            name = attr_dict.get('name', '')
            content = attr_dict.get('content', '')
            if name.startswith('paper-'):
                key = name[len('paper-'):]
                self.meta[key] = content
        # 기존 summary 파일의 .title div 감지
        if tag == 'div':
            attr_dict = dict(attrs)
            cls = attr_dict.get('class', '')
            if 'title' in cls and 'section' not in cls:
                self._capture_next = 'title'

    def handle_endtag(self, tag):
        if tag == 'head':
            self._in_head = False

    def handle_data(self, data):
        if self._capture_next == 'title':
            text = data.strip()
            if text and 'title' not in self.meta:
                self.meta['_html_title'] = text
            self._capture_next = None


def extract_year_from_filename(filename):
    """파일명 [2024] ... 패턴에서 연도 추출"""
    m = re.match(r'^\[(\d{4})\]', filename)
    return m.group(1) if m else ''


def extract_title_from_filename(filename):
    """파일명에서 제목 추출: [2024] 제목_summary.html → 제목"""
    name = filename
    # 앞의 [연도] 제거
    name = re.sub(r'^\[\d{4}\]\s*', '', name)
    # _summary.html 제거
    name = re.sub(r'_summary\.html$', '', name, flags=re.IGNORECASE)
    # .html 제거
    name = re.sub(r'\.html$', '', name, flags=re.IGNORECASE)
    return name.strip()


def extract_meta(filepath):
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        html = f.read()
    parser = MetaParser()
    parser.feed(html)
    return parser.meta


def build_paper_entry(filename, meta):
    year = meta.get('year') or extract_year_from_filename(filename)
    title = (
        meta.get('title') or
        meta.get('_html_title') or
        extract_title_from_filename(filename)
    )
    tags_raw = meta.get('tags', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    return {
        'title': title,
        'year':  year,
        'tags':  tags,
        'file':  filename,
    }


def papers_to_js(papers):
    lines = []
    for p in papers:
        tags_js = json.dumps(p['tags'], ensure_ascii=False)
        file_js = json.dumps(p['file'], ensure_ascii=False)
        lines.append(
            '{' +
            f'title: {json.dumps(p["title"], ensure_ascii=False)}, ' +
            f'year: {json.dumps(p["year"], ensure_ascii=False)}, ' +
            f'tags: {tags_js}, ' +
            f'file: {file_js}' +
            '}'
        )
    return ',\n    '.join(lines)


def main():
    # 루트 폴더에서 *_summary.html 파일 스캔
    files = sorted([
        f for f in os.listdir(ROOT)
        if f.lower().endswith('_summary.html') or
           (f.lower().endswith('.html') and f != 'index.html')
    ])

    papers = []
    for fname in files:
        fpath = os.path.join(ROOT, fname)
        meta = extract_meta(fpath)
        entry = build_paper_entry(fname, meta)
        papers.append(entry)
        print(f'[ok] {fname[:60]}')
        print(f'     → {entry["title"][:60]}')

    if not papers:
        print('[info] 요약 HTML 파일이 없습니다.')

    # index.html 업데이트
    with open(INDEX_PATH, encoding='utf-8') as f:
        content = f.read()

    new_js = papers_to_js(papers) if papers else '// 논문 없음'
    pattern = r'(// AUTO_INJECT_START\n).*?(\s*// AUTO_INJECT_END)'
    replacement = rf'\g<1>    {new_js}\n    \g<2>'
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    if new_content == content:
        print('[warn] AUTO_INJECT 마커를 찾지 못했습니다.')
    else:
        with open(INDEX_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'[done] index.html 업데이트 완료 ({len(papers)}개 논문)')


if __name__ == '__main__':
    main()
