# kim-kyuyoung.github.io

공개 CV 사이트. <https://kim-kyuyoung.github.io>

## 무엇이 공개되는가

**이 저장소에 들어간 것은 전부 공개된다.** 정적 사이트에는 "로그인해야 보이는 영역"
같은 것이 없다. 화면에서 숨겨도 브라우저의 소스 보기로 그대로 읽힌다.

공개하는 것 — 프로필, 학술지 논문, 학회 발표, 경력, 학력
공개하지 않는 것 — **임상·사업화 프로젝트, 특허, 수상**

프로젝트와 특허는 이 저장소에 두지 않는다. 요청이 오면 개별 문서로 전달한다.

publications 와 talks 는 professional(브이픽스) 과 academic(박사과정) 으로 나눠 싣는다.
논문의 분류는 `data/overrides.yaml` 의 `professional_doi` 로 정한다. 거기 적은 DOI 만
professional 로 가고 나머지는 전부 academic 으로 간다. talks 는 `index.html` 에서
원하는 섹션에 직접 `<li>` 를 넣으면 된다.

## 구조

    index.html              사이트 전부. 직접 고치는 파일
    data/publications.yaml  논문 목록 (자동 생성. 손대지 않는다)
    data/overrides.yaml     논문 수집 보정 (추가 / 제외 / 수정)
    scripts/fetch_pubs.py   ORCID -> data/publications.yaml
    scripts/inject_pubs.py  data/publications.yaml -> index.html 의 publications 블록

배포되는 파일은 `index.html` 하나뿐이다. 스크립트와 데이터 파일은 사이트에 올라가지 않는다.

## 고치는 방법

`index.html` 을 열어서 고치고 push 하면 끝이다. 30초쯤 뒤 사이트에 반영된다.

    git add -A && git commit -m "update" && git push

단 아래 두 줄 **사이는 자동 생성 구간**이라 직접 고쳐도 다음 갱신 때 덮어써진다.

    <!-- publications:start -->
    <!-- publications:end -->

## 논문 목록

목록의 기준은 **ORCID 레코드**다. OpenAlex 는 인용수·저널명·저자 순서를 채우는 데만 쓴다.

OpenAlex 의 `author.orcid` 필터는 쓰지 않는다. OpenAlex author `A5074235764` 가
여러 명의 "Kyuyoung / Kyu-Young Kim" 을 한 사람으로 병합해 두고 거기에 이 ORCID 를
붙여 놓아서, 그 필터를 걸면 동명이인 논문 30여 편(유기화학·CMOS 회로·EUV 마스크·
LLM·양자광학)이 함께 딸려 온다. 그래서 ORCID 를 기준으로 뒤집었다.

**새 논문이 나오면 [orcid.org](https://orcid.org) 에 등록한다.** 매주 월요일 09:00 KST
에 자동으로 반영된다. ORCID 에 올리기 어려운 것만 `data/overrides.yaml` 의
`include_doi` 에 DOI 를 적는다.

## 로컬에서 확인

    pip install requests pyyaml
    python scripts/fetch_pubs.py    # 선택. 논문 새로 받기
    python scripts/inject_pubs.py
    start index.html
