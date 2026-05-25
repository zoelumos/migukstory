---
title: 'AI 보안, 구글조차 실시간으로 배우는 중 — 한인 사용자가 지금 점검해야 할 것'
description: '구글 클라우드 임원이 "전환기"라고 말한 AI 보안 공백기. 한인 자영업자·개발자·직장인이 API 키, 자동 청구, 보이스피싱 위험에서 손실을 막을 실질 점검 항목을 정리했습니다.'
pubDate: '2026-05-25'
tags: ['AI 보안', '구글', 'Gemini', 'API 키', '한인 자영업자']
category: 'ai'
ageGroup: 'all'
source: 'TechCrunch AI'
sourceUrl: 'https://techcrunch.com/2026/05/24/everyone-is-navigating-ai-security-in-real-time-even-google'
---

# AI 보안, 구글조차 실시간으로 배우는 중 — 한인 사용자가 지금 점검해야 할 것

TechCrunch AI는 5월 24일자 기사에서 구글 클라우드 최고운영책임자(COO) Francis de Souza의 발언을 인용해, AI 보안이 지금은 "전환기(transition period)"에 있고 그 시기를 지나야 더 나은 단계에 도달한다는 진단을 전했습니다. 업계 최정점에 있는 구글마저 완성된 정답을 들고 움직이는 것이 아니라, 실시간으로 위험을 보면서 대응을 다듬고 있다는 솔직한 자기 인식입니다.

이 발언이 단순한 수사가 아니라는 점은 같은 시기 보도된 일련의 사고로 확인됩니다. The Register와 CSO Online 등의 보도에 따르면, 구글 클라우드 사용자들이 Gemini API를 쓴 적도 없는데 다섯 자릿수 달러 청구서를 받는 사례가 잇따랐습니다. 예컨대 면접 준비 플랫폼 Prentus의 최고경영자 Rod Danan은 약 30분 사이에 $10,138 청구가 발생했고, 호주 시드니의 개발자 Isuru Fonseka는 $250 한도를 설정해 두었다고 믿었지만 실제로는 약 AUD $17,000이 부과됐다고 전해졌습니다. Truffle Security는 외부 스캔에서 노출된 활성 키 2,863개를 확인했다고 밝혔습니다.

원인은 기술적입니다. 원래 Google Maps용으로 공개되어 쓰이던 "Aiza"로 시작하는 API 키가, 별도 고지 없이 Gemini API에도 접근할 수 있게 권한이 확장됐다는 것이 보도의 핵심입니다. 게다가 노출된 키를 즉시 삭제해도 구() 형식 키는 권한 해지가 전체 인프라에 반영되기까지 최대 약 23분이 걸린다고 보도됐습니다(서비스 계정 자격 증명은 약 5초, 새로운 "AQ" 접두어 키는 약 1분). 구글은 신규 키 생성 시 제한을 의무화하고, 한 키가 Maps와 Gemini를 동시에 호출하지 못하도록 막는 등 일부 조치를 도입했지만, 일정 결제 이력 이상 계정의 한도가 자동으로 $20,000~$100,000까지 상향되는 정책은 유지한다고 전해졌습니다.

## 미주 한인에게 왜 중요한가

이 사안은 미주 한인 가운데 특히 세 그룹의 현실에 직접 닿습니다.

첫째, 한인 자영업자입니다. 식당·세탁소·미용실·소형 이커머스를 운영하는 분들이 예약 시스템, 지도 위젯, 챗봇, 자동 응대 도구를 도입하면서 Google Maps API 키를 웹사이트나 모바일 앱에 그대로 넣는 경우가 많습니다. 이번 보도가 보여 주듯, 과거에는 "공개되어도 큰 문제가 아니"라고 안내됐던 키가 시간이 지나면서 청구 위험이 큰 키로 바뀔 수 있습니다. 키마다 사용 가능한 API와 호출 도메인(HTTP 리퍼러) 제한이 걸려 있는지, Generative Language API가 자동으로 활성화돼 있지는 않은지 점검해야 합니다.

둘째, 한인 개발자·스타트업 창업자와 사이드 프로젝트를 운영하는 유학생·H-1B 근로자입니다. GitHub 공개 저장소에 무심코 올라간 키 한 줄이 며칠 만에 수천 달러 청구로 돌아올 수 있고, 이번 보도에서도 구글은 일부 사례에 한해 환불에 응했지만 "사기 증거가 없다"며 거절한 사례도 있었다고 합니다. 카드 회사 분쟁 절차(charge-back)가 신용 점수와 향후 클라우드 이용에 영향을 줄 수 있으므로, 한도 자동 상향 정책과 알림 채널을 미리 확인해 두는 편이 안전합니다.

셋째, 부모 세대·은퇴자와 한인 가정 전체입니다. 구글조차 "전환기"라고 부르는 이 시기의 본질은 "어제 안전했던 사용법이 오늘 위험해질 수 있다"는 것입니다. 한국어 음성·영상 합성 품질이 빠르게 올라가는 만큼, 자녀·손주를 사칭한 보이스피싱이나 한국어 은행 사칭 메시지가 동시에 정교해집니다. 가족 간 비상 호출용 암호 문구를 정해 두고, 의심 전화가 오면 끊고 저장된 번호로 다시 거는 습관을 공유하는 것이 현실적인 방어선입니다.

## 편집자 분석

이번 사안에서 가장 의미 있는 대목은 구글의 권고 자체가 아니라, COO가 공개 석상에서 "전환기"라는 표현을 쓴 점입니다. 일반적으로 클라우드 사업자는 "완성된 보안 플랫폼"을 강조해야 영업이 됩니다. 그럼에도 권한 확장의 사후 고지, 한도 자동 상향, 권한 해지 지연 같은 "운영상의 빈틈"이 동시에 드러난 상황에서, 책임을 사용자에게만 돌리지 않고 업계 공통의 학습 단계로 명명한 점은 주목할 만합니다. 그러나 한인 독자 입장에서 이 표현은 사용자에게 위로가 아니라 경고로 읽혀야 합니다. 사업자가 학습 중이라는 말은 곧, 비용·정보 손실의 1차 충격을 떠안는 쪽이 여전히 개인 사용자와 소상공인이라는 뜻이기 때문입니다. 결과적으로 "기다리면 정리해 주겠지"라는 태도보다, 키 제한·결제 알림·입력 금지 정보 목록 같은 자체 규칙을 가족·직원과 문서로 공유해 두는 편이 실질적인 보호막이 됩니다.

## 한인 사용자 점검 체크리스트

- Google Cloud 콘솔에서 사용 중인 API 키의 권한과 호출 도메인 제한을 다시 확인합니다.
- Generative Language API가 본인이 의도하지 않은 프로젝트에서 활성화돼 있는지 확인합니다.
- 결제 알림(budget alert)과 청구 한도, 자동 한도 상향 가능성을 사전에 점검합니다.
- 공개 저장소·웹페이지 소스에 노출된 키가 없는지 검색하고, 의심 시 즉시 회전(rotate)합니다.
- 사내 또는 매장 직원과 "AI에 절대 입력하지 않을 정보 목록"(고객 연락처, 결제 정보, 이민 서류, 의료 기록 등)을 문서로 공유합니다.
- 가족 단위로 보이스피싱 대비 암호 문구와 재확인 절차를 정합니다.

법적·재정적 책임이 걸린 결정이나 환불 분쟁, 이민·세무 관련 문서 처리에는 AI 답변만 믿지 말고 변호사·CPA·이민 전문가 상담을 권장합니다.

## 핵심 요약

- 구글 클라우드 COO Francis de Souza는 AI 보안이 "전환기"에 있고 업계 전체가 실시간으로 학습 중이라고 밝혔습니다.
- 같은 시기 Google Maps용 API 키가 별도 고지 없이 Gemini API 권한을 갖게 되어, 사용자 다수가 다섯 자릿수 청구를 받는 사례가 보도됐습니다.
- 한인 자영업자·개발자·가정은 키 제한, 결제 알림, AI 입력 금지 정보 목록, 가족 간 보이스피싱 대비 문구를 지금 정비해 두는 것이 안전합니다.

## 출처 (Sources)

- [TechCrunch AI — Everyone is navigating AI security in real time — even Google](https://techcrunch.com/2026/05/24/everyone-is-navigating-ai-security-in-real-time-even-google)
- [The Register — Google users fight for refunds as unauthorized API usage bills soar](https://www.theregister.com/ai-ml/2026/05/13/google-users-fight-for-refunds-as-unauthorized-api-usage-bills-soar/)
- [CSO Online — 'Silent' Google API key change exposed Gemini AI data](https://www.csoonline.com/article/4138749/silent-google-api-key-change-exposed-gemini-ai-data.html)
- [Truffle Security — Google API Keys Weren't Secrets. But then Gemini Changed the Rules.](https://trufflesecurity.com/blog/google-api-keys-werent-secrets-but-then-gemini-changed-the-rules)
