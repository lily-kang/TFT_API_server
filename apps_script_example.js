/**
 * Google Apps Script에서 구문 수정 API 호출 예제
 * 
 * 사용법:
 * 1. 스크립트 편집기에서 이 코드를 복사
 * 2. API_BASE_URL을 실제 서버 주소로 변경
 * 3. 함수 실행 또는 스프레드시트에서 호출
 */

// API 서버 주소 (실제 서버 주소로 변경 필요)
const API_BASE_URL = 'http://your-server-address:8000';

/**
 * 구문 수정 API 호출 함수
 * @param {string} requestId - 요청 ID (행 번호, job_id 등)
 * @param {string} text - 수정할 텍스트
 * @param {Object} masterMetrics - 마스터 지표
 * @param {Object} toleranceAbs - 절대값 허용 오차 (선택사항)
 * @param {Object} toleranceRatio - 비율 허용 오차 (선택사항)
 * @param {string} referentialClauses - 참조용 절 정보 (선택사항)
 * @returns {Object} 구문 수정 결과
 */
function callSyntaxFixAPI(requestId, text, masterMetrics, toleranceAbs = null, toleranceRatio = null, referentialClauses = '') {
  try {
    // 요청 데이터 구성
    const requestData = {
      request_id: requestId,
      text: text,
      master: masterMetrics,
      tolerance_abs: toleranceAbs || {
        AVG_SENTENCE_LENGTH: 1.97
      },
      tolerance_ratio: toleranceRatio || {
        All_Embedded_Clauses_Ratio: 0.202,
        CEFR_NVJD_A1A2_lemma_ratio: 0.104
      },
      referential_clauses: referentialClauses
    };

    // API 호출 옵션
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      payload: JSON.stringify(requestData)
    };

    // API 호출
    console.log(`[${requestId}] 구문 수정 API 호출 시작...`);
    const response = UrlFetchApp.fetch(`${API_BASE_URL}/pipeline/syntax-fix`, options);
    
    // 응답 확인
    if (response.getResponseCode() !== 200) {
      throw new Error(`API 호출 실패: HTTP ${response.getResponseCode()}`);
    }

    // 응답 데이터 파싱
    const result = JSON.parse(response.getContentText());
    
    console.log(`[${requestId}] 구문 수정 완료 - 성공: ${result.success}, 시간: ${result.processing_time.toFixed(2)}초`);
    
    return result;

  } catch (error) {
    console.error(`[${requestId}] API 호출 오류:`, error.toString());
    return {
      request_id: requestId,
      success: false,
      error_message: error.toString(),
      original_text: text,
      fixed_text: null,
      processing_time: 0
    };
  }
}

/**
 * 스프레드시트에서 구문 수정 실행 (예제)
 * 사용법: 스프레드시트에서 =syntaxFix(A2, B2, C2, D2, E2) 형태로 호출
 */
function syntaxFix(text, avgSentenceLength, embeddedClausesRatio, cefr_a1a2_ratio, rowId = '') {
  if (!text || text.toString().trim() === '') {
    return 'ERROR: 텍스트가 비어있습니다';
  }

  const requestId = rowId || `row_${new Date().getTime()}`;
  
  const masterMetrics = {
    AVG_SENTENCE_LENGTH: parseFloat(avgSentenceLength) || 8.85,
    All_Embedded_Clauses_Ratio: parseFloat(embeddedClausesRatio) || 0.176,
    CEFR_NVJD_A1A2_lemma_ratio: parseFloat(cefr_a1a2_ratio) || 0.583
  };

  const result = callSyntaxFixAPI(requestId, text.toString(), masterMetrics);
  
  if (result.success) {
    return result.fixed_text;
  } else {
    return `ERROR: ${result.error_message}`;
  }
}

/**
 * 배치 처리 예제 (여러 행을 한번에 처리)
 */
function batchSyntaxFix() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();
  
  // 데이터 범위 (예: A2:E10, A열=텍스트, B열=평균문장길이, C열=내포절비율, D열=A1A2비율, E열=결과)
  const dataRange = sheet.getRange(2, 1, lastRow - 1, 5);
  const values = dataRange.getValues();
  
  console.log(`배치 처리 시작: ${values.length}개 행`);
  
  for (let i = 0; i < values.length; i++) {
    const row = values[i];
    const [text, avgLength, clauseRatio, cefrRatio] = row;
    
    if (!text || text.toString().trim() === '') {
      continue;
    }
    
    const requestId = `batch_row_${i + 2}`;
    const masterMetrics = {
      AVG_SENTENCE_LENGTH: parseFloat(avgLength) || 8.85,
      All_Embedded_Clauses_Ratio: parseFloat(clauseRatio) || 0.176,
      CEFR_NVJD_A1A2_lemma_ratio: parseFloat(cefrRatio) || 0.583
    };

    const result = callSyntaxFixAPI(requestId, text.toString(), masterMetrics);
    
    // 결과를 E열에 입력
    if (result.success) {
      sheet.getRange(i + 2, 5).setValue(result.fixed_text);
    } else {
      sheet.getRange(i + 2, 5).setValue(`ERROR: ${result.error_message}`);
    }
    
    // API 호출 간격 조절 (너무 빠른 호출 방지)
    Utilities.sleep(1000);
  }
  
  console.log('배치 처리 완료');
}

/**
 * 단일 테스트 실행 함수
 */
function testSyntaxAPI() {
  const testText = `Iceland is a country full of natural beauty. This unique location has waterfalls, hot springs, and even volcanoes. Some volcanoes are still active, which means they can still erupt with lava. People come from around the world to visit these places.

Iceland also has many glaciers. These rivers of ice form when one layer of snow presses down on another. Over many years, the snow turns into solid ice. The glaciers slowly move across the land, shaping it as they go.`;

  const masterMetrics = {
    AVG_SENTENCE_LENGTH: 8.85,
    All_Embedded_Clauses_Ratio: 0.176,
    CEFR_NVJD_A1A2_lemma_ratio: 0.583
  };

  console.log('테스트 시작...');
  const result = callSyntaxFixAPI('test_001', testText, masterMetrics);
  
  console.log('=== 테스트 결과 ===');
  console.log('성공 여부:', result.success);
  console.log('처리 시간:', result.processing_time + '초');
  console.log('생성된 후보 수:', result.candidates_generated);
  console.log('통과한 후보 수:', result.candidates_passed);
  
  if (result.success) {
    console.log('원본 텍스트:', result.original_text.substring(0, 100) + '...');
    console.log('수정된 텍스트:', result.fixed_text.substring(0, 100) + '...');
    console.log('원본 지표:', result.original_metrics);
    console.log('수정 후 지표:', result.fixed_metrics);
  } else {
    console.log('오류 메시지:', result.error_message);
  }
}

/**
 * API 서버 상태 확인
 */
function checkAPIStatus() {
  try {
    const response = UrlFetchApp.fetch(`${API_BASE_URL}/health`);
    if (response.getResponseCode() === 200) {
      console.log('✅ API 서버 정상 작동');
      return true;
    } else {
      console.log('❌ API 서버 응답 오류:', response.getResponseCode());
      return false;
    }
  } catch (error) {
    console.log('❌ API 서버 연결 실패:', error.toString());
    return false;
  }
} 