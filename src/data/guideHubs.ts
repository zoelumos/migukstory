export type GuideHub = {
	slug: string;
	title: string;
	deck: string;
	oneSentence: string;
	who: string[];
	checklist: string[];
	queries: string[];
	category?: string;
	disclaimer?: string;
};

export const GUIDE_HUBS: GuideHub[] = [
	{
		slug: 'immigration',
		title: '미국 이민·비자 가이드 허브',
		deck: 'USCIS, 영주권, 시민권, 가족초청, H-1B·OPT 변화를 한인 독자가 실행할 수 있는 체크리스트로 정리합니다.',
		oneSentence: '이민 글은 “내 케이스에 오늘 무엇을 해야 하나”를 먼저 답해야 검색에서 이깁니다.',
		who: ['영주권·시민권 신청자', 'F-1/OPT/H-1B 체류자', '가족초청·취업이민 대기자'],
		checklist: ['USCIS 원문 날짜 확인', '내 양식 번호와 접수 단계 확인', '마감·유예·인터뷰 필요 여부 확인', '관련 서류 PDF/계정 캡처 보관'],
		queries: ['I-485 신분조정', 'I-130 가족초청', '시민권 시험 면제', '비자 bulletin', 'OPT STEM OPT'],
		category: 'immigration',
		disclaimer: '이민법 자문이 아니며 개별 케이스는 변호사와 확인하세요.',
	},
	{
		slug: 'tax',
		title: '미국 세금·FBAR 가이드 허브',
		deck: 'IRS, FBAR, ITIN, 해외계좌, 주 이동 세금 이슈를 한인 가정·자영업자 관점으로 정리합니다.',
		oneSentence: '한미 세금 검색은 “신고해야 하나, 언제까지, 어떤 서류로”를 바로 답해야 합니다.',
		who: ['한국 계좌가 있는 미국 거주자', '한인 자영업자', '유학생·취업비자 세금보고자'],
		checklist: ['거주자/비거주자 세법상 신분 확인', '한국 금융계좌 최고잔액 확인', 'IRS/FinCEN 마감일 확인', '주세와 연방세 차이 확인'],
		queries: ['FBAR 한국 계좌', 'ITIN W-7', '1040-ES 예정세', 'IRS IP PIN', '한미 상속세'],
		category: 'tax',
		disclaimer: '세무 자문이 아니며 CPA/EA와 개별 상황을 확인하세요.',
	},
	{
		slug: 'retirement',
		title: 'Medicare·Social Security·은퇴 허브',
		deck: 'Medicare, Social Security, 401(k), IRA, 한미 연금 이슈를 은퇴 전후 체크리스트로 정리합니다.',
		oneSentence: '은퇴 검색은 가입 시점·자격·벌금·현금흐름을 한 번에 정리해야 합니다.',
		who: ['55세 이상 한인', '부모님 Medicare를 돕는 자녀', '401(k)/IRA를 가진 직장인'],
		checklist: ['Medicare Part A/B 자격 확인', 'Social Security 계정 생성', '401(k)·IRA 인출 규칙 확인', '한국 연금·거주 계획 영향 확인'],
		queries: ['영주권자 Medicare', 'Social Security 계정', '401k catch-up', 'IRA RMD', '한미 연금'],
		category: 'retirement',
	},
	{
		slug: 'real-estate',
		title: '미국 부동산·주거 가이드 허브',
		deck: '첫 주택, 모기지, 렌트, 재산세, 주택보험을 한인 바이어·세입자 관점으로 설명합니다.',
		oneSentence: '주거 검색은 월 비용과 closing 단계에서 실제로 돈이 새는 지점을 보여줘야 합니다.',
		who: ['첫 주택 구입자', '렌트에서 구매로 넘어가는 가정', '타주 이사 준비자'],
		checklist: ['pre-approval과 예산 확인', 'loan estimate 수수료 비교', '재산세·보험료 확인', 'closing disclosure 검토'],
		queries: ['첫 주택 구입 closing cost', 'loan estimate', '모기지 금리', '재산세', '주택보험'],
		category: 'real-estate',
	},
	{
		slug: 'health-insurance',
		title: '건강보험·ACA 가이드 허브',
		deck: 'ACA Marketplace, employer insurance, deductible, subsidy, Medicare 전 단계 보험 선택을 정리합니다.',
		oneSentence: '건강보험 검색은 보험료보다 총비용과 병원 네트워크를 먼저 따져야 합니다.',
		who: ['자영업자·프리랜서', '직장 보험 변경자', '유학생·새 이민자 가족'],
		checklist: ['보험료와 deductible 동시 비교', '주치의·병원 network 확인', 'subsidy 자격 확인', 'open enrollment/SEP 날짜 확인'],
		queries: ['ACA 보험료', 'deductible 뜻', '건강보험 subsidy', 'open enrollment', 'Medicare 전 보험'],
		category: 'health',
	},
	{
		slug: 'education',
		title: '교육·FAFSA·입시 가이드 허브',
		deck: 'FAFSA, 장학금, 대학입시, 한인 학부모가 헷갈리는 contributor·시민권/영주권 조건을 정리합니다.',
		oneSentence: '교육 검색은 부모 서류와 학생 자격을 분리해서 알려줘야 합니다.',
		who: ['고등학생·대학생 자녀를 둔 부모', 'FAFSA 작성 가정', '장학금 찾는 학생'],
		checklist: ['FAFSA 계정 확인', '부모 contributor 필요 여부 확인', '세금자료 연동 확인', '주정부/학교 마감일 확인'],
		queries: ['FAFSA 부모 contributor', '한인 장학금', '비시민권자 FAFSA', '대학 입시', '529 plan'],
		category: 'education',
	},
	{
		slug: 'korea-us',
		title: '한국-미국 크로스보더 생활 허브',
		deck: '송금, 상속, 국적·병역, 한국 귀국, 양국 서류 이슈를 한미 가족 관점으로 정리합니다.',
		oneSentence: '한미 크로스보더 검색은 미국 규정과 한국 규정을 동시에 체크해야 합니다.',
		who: ['한국 자산이 있는 미국 거주자', '이중국적·병역 이슈 가족', '귀국·역이민 준비자'],
		checklist: ['미국 신고 의무 확인', '한국 신고·증빙 확인', '환율·송금 기록 보관', '양국 전문가 상담 지점 표시'],
		queries: ['한국 송금 미국 세금', '한국 상속 미국 거주자', '국적 이탈', '병역 해외동포', '귀국 서류'],
		category: 'community',
		disclaimer: '양국 법·세무가 겹치는 영역은 전문가 확인이 필요합니다.',
	},
	{
		slug: 'first-90-days',
		title: '미국 정착 첫 90일 가이드 허브',
		deck: 'SSN, 은행, 크레딧, DMV, 보험, 학교 등록까지 새 이민자·유학생·주재원이 놓치기 쉬운 순서를 정리합니다.',
		oneSentence: '정착 검색은 “무엇을 먼저 해야 다음 단계가 막히지 않는가”가 핵심입니다.',
		who: ['미국에 막 도착한 가족', '유학생·주재원', '타주 이사자'],
		checklist: ['주소와 우편 수령 준비', 'SSN/ITIN 필요 여부 확인', '은행·크레딧 시작', 'DMV·보험·학교 등록 순서 정리'],
		queries: ['미국 정착 체크리스트', 'SSN 신청', '미국 은행 계좌', 'DMV 운전면허', '크레딧 시작'],
		category: 'community',
	},
];

export const getGuideHub = (slug: string) => GUIDE_HUBS.find((hub) => hub.slug === slug);
