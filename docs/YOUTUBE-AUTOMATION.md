# YouTube 자동화 (Article → Korean Short)

**상태:** 프로토타입 동작 확인 (2026-07-20). 기사 1건 → 세로 쇼츠 MP4 생성까지
end-to-end 검증 완료. YouTube 업로드는 OAuth 시크릿 연결 후 활성화.

Migukstory의 강점(**시각화 우선** 서비스 저널리즘)을 그대로 세로 영상으로 옮기는
파이프라인입니다. 스톡 b-roll 짜깁기가 아니라, 이미 발행된 기사의 표·타임라인·
단계 설명을 슬라이드로 렌더링하고 한국어 나레이션을 붙입니다.

```
기사(.md)
  → article_to_script   기사 → 한국어 대본 + 장면 분해
  → render_slides        Chromium 헤드리스 → 1080×1920 PNG 슬라이드
  → synth_tts            edge-tts 한국어 나레이션(무료, 키 불필요)
  → assemble_video       ffmpeg → 세로 MP4 (Ken Burns 줌 + 자막)
  → upload_youtube       YouTube Data API v3 업로드 (OAuth refresh token)
```

전 과정 무인 실행(프롬프트 없음) — 레포 최상위 지침(완전 자동화)에 부합.

---

## 1. 왜 이 형식인가

- **YouTube Shorts / Reels / TikTok** 공통 세로 규격(1080×1920).
- 이민·세금·건강보험 같은 **고관여 정보성** 주제는 "표로 비교", "단계별 절차"가
  핵심인데, 이게 그대로 쇼츠 장면이 됩니다 (기사 = 이미 시각화 우선으로 작성됨).
- 얼굴 없는(faceless) 채널 → 인물 촬영·편집 없이 매일 자동 생산 가능.
- 젊은 신생 사이트의 **디스커버리 채널 확장**: 검색(GSC) + 뉴스레터에 이어
  YouTube/Shorts라는 새 유입 경로.

한 편 = 45~60초, 6~8장면(훅 → 핵심요약 → 비교표 → 단계 → CTA).

---

## 2. 로컬에서 한 편 만들기

```bash
pip install -r scripts/youtube/requirements.txt
# 슬라이드용 Chromium + 한글 폰트 (macOS는 이미 있음, Ubuntu는 아래)
sudo apt-get install -y ffmpeg chromium-browser fonts-nanum fonts-noto-cjk

# 최신 발행글로 한 편 (업로드 안 함)
python -m scripts.youtube.make_video --latest

# 특정 슬러그로
python -m scripts.youtube.make_video uscis-signature-rule-july-10-2026-korean

# 만들고 바로 업로드 (비공개)
python -m scripts.youtube.make_video --latest --upload --privacy private
```

결과물: `build/youtube/<slug>/<slug>.mp4` (git 무시됨).
단계별로 따로 실행할 수도 있습니다 (`article_to_script` → `render_slides` →
`synth_tts` → `assemble_video` → `upload_youtube`, 각각 `python -m ...`).

### 나레이션 관련
- **음성은 무료** — edge-tts(마이크로소프트 Edge 읽어주기 엔진, ko-KR-SunHiNeural).
  API 키 불필요. GitHub Actions 러너에서 정상 동작.
- egress가 `speech.platform.bing.com`을 막는 샌드박스에서는 `--allow-silent-fallback`
  로 예상 길이만큼 무음 트랙을 만들어 파이프라인을 완성시킵니다(자막은 슬라이드에
  구워져 있어 무음이어도 내용 전달은 됨).
- `--claude` + `ANTHROPIC_API_KEY` → 각 장면 나레이션을 구어체로 다듬음(사실은 불변,
  말맛만). 키 없으면 결정론적 기본 대본 사용.

---

## 3. GitHub Actions

`.github/workflows/youtube-short.yml`

- **수동 실행(workflow_dispatch):** 슬러그 입력(비우면 최신글) + 공개범위 선택.
- **자동(workflow_call):** `daily-post.yml`이 발행 후 호출하도록 연결 가능(선택).
- OAuth 시크릿이 **없어도** MP4를 만들어 **빌드 아티팩트로 첨부** → 채널 연결 전에도
  영상 품질을 눈으로 검증 가능(안전한 no-op).

### daily-post.yml에 자동 연결(선택)
발행마다 쇼츠까지 자동으로 만들고 싶으면 `daily-post.yml` 끝에 추가:

```yaml
  youtube:
    needs: publish
    if: needs.publish.outputs.published == 'true'
    uses: ./.github/workflows/youtube-short.yml
    with:
      slug: ''          # 최신 발행글
      privacy: 'private' # 검토 후 수동 공개 권장(초기)
    secrets: inherit
```

> **권장 초기 운영:** `privacy: private`로 쌓아두고 사람이 한 번 훑은 뒤 공개.
> 채널이 안정되면 `unlisted` → `public`으로 단계 상향. Google의 대량·저품질 업로드
> 리스크를 피하려면 **하루 1~2편**부터. (Data API 업로드 쿼터: 1편 ≈ 1,600 units /
> 기본 10,000/day = 하루 약 6편이 상한.)

---

## 4. YouTube 업로드 연결 (1회성 OAuth)

CI에서 브라우저 없이 업로드하려면 **refresh token** 한 번만 발급받아 시크릿으로
저장하면 됩니다.

1. **Google Cloud 프로젝트** 생성 → **YouTube Data API v3** 사용 설정.
2. **OAuth 동의 화면** 구성(External). 앱을 **게시(Production)** 상태로 두면
   refresh token이 만료되지 않음. (Testing 상태면 7일마다 만료.)
3. **OAuth 클라이언트 ID** 생성 — 유형 **Desktop app**. Client ID / Secret 확보.
4. 로컬에서 refresh token 발급(아래 스니펫, 한 번만):

   ```bash
   pip install google-auth-oauthlib
   python - <<'PY'
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_config(
       {"installed": {
           "client_id": "YOUR_CLIENT_ID",
           "client_secret": "YOUR_CLIENT_SECRET",
           "auth_uri": "https://accounts.google.com/o/oauth2/auth",
           "token_uri": "https://oauth2.googleapis.com/token"}},
       scopes=["https://www.googleapis.com/auth/youtube.upload"])
   creds = flow.run_local_server(port=0)   # 브라우저에서 채널 소유 계정으로 승인
   print("REFRESH TOKEN:", creds.refresh_token)
   PY
   ```

5. **GitHub 레포 시크릿** 3개 등록:
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`

   (대안: `YT_OAUTH_JSON` = `{"client_id","client_secret","refresh_token"}`의
   base64 한 덩어리.)

이후 워크플로우가 매 실행마다 refresh token으로 access token을 자동 교환해 업로드합니다.

---

## 5. 편집 품질 게이트 (레포 규칙 준수)

기사 파이프라인과 동일한 원칙을 영상에도 적용:

- [ ] 훅(첫 장면)이 한인에게 **지금 중요한 이유**를 3초 안에 전달하는가.
- [ ] 표/단계/타임라인 중 **최소 1개 시각 요소**가 들어갔는가(기사에서 자동 추출).
- [ ] 프레임 enum·카테고리 색상이 기사 카테고리와 일치하는가(`config.py`가 자동).
- [ ] 제목 ≤ 100자, 설명에 **정식 기사 링크**(canonical) 포함 — 사이트로 트래픽 환류.
- [ ] 공개 전 사람이 1편이라도 확인(초기 운영). 중복 주제 영상 남발 금지(기사 중복
      금지 규칙과 동일 취지 — 같은 스토리로 여러 편 만들지 않음).

---

## 6. 한계 / 다음 단계

**현재 프로토타입에서 동작:**
- ✅ 기사 → 대본(결정론적 추출) → 슬라이드(한글 렌더) → 무음/음성 → MP4 조립.
- ✅ 카테고리 색상·뱃지, 비교표/단계 슬라이드, 자막 굽기, Ken Burns 줌.
- ✅ 업로드 스크립트(자격증명 연결 시 즉시 동작), 시크릿 게이트 워크플로우.

**아직/개선 여지:**
- ⏳ **실 음성 검증**: edge-tts는 Actions에서 동작하지만, 개발 샌드박스는 egress
  차단이라 무음 폴백으로만 확인됨. 첫 Actions 실행에서 음성 확인 필요.
- ⏳ **daily-post 자동 연결**은 선택 사항으로 문서화만 함(안전상 수동 공개 권장).
- 🔜 Claude 대본 폴리시(`--claude`)를 기본 켜기 — 훅/호흡이 더 자연스러워짐.
- 🔜 롱폼(가로 16:9) 변형: 같은 슬라이드를 가로로 재배치 + 더 긴 나레이션.
- 🔜 배경음(로열티프리) 1트랙 추가 시 `--music`으로 자동 덕킹 믹스.
- 🔜 썸네일 자동 생성(훅 슬라이드 재활용).

**비용:** 슬라이드(Chromium)·음성(edge-tts)·조립(ffmpeg)·Actions(퍼블릭 레포 무료)
모두 **$0**. 업로드도 무료(쿼터 내). Claude 폴리시만 선택적으로 API 비용 발생.
