import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

# ==========================================
# 🎨 앱 디자인 및 설정
# ==========================================
st.set_page_config(page_title="종목 추세 진단기 (ETF 포함)", page_icon="🚀")

st.header("🚀 추세 추종: 주식/ETF 진단")
st.write("종목코드 6자리를 입력하세요. (예: 005930, 418660)")

# ==========================================
# 📥 사용자 입력
# ==========================================
col1, col2 = st.columns(2)
with col1:
    # 418660 등 ETF 코드도 문제없습니다.
    TICKER = st.text_input("종목코드 (6자리)", value="005930")
with col2:
    ENTRY_PRICE = st.number_input("내 평단가 (없으면 0)", value=0, step=100)

ENTRY_DATE = st.date_input("진입 날짜", value=datetime.now())

# ⚙️ 설정값 (사이드바) - 준수님 전용 세팅
with st.sidebar:
    st.header("⚙️ 전략 설정")
    st.info("준수님 전용 기본값(20/3.0/3.0) 적용됨")
    ATR_PERIOD = st.slider("ATR 기간", 10, 30, 20)          
    ATR_FACTOR = st.slider("진입 Factor", 1.0, 5.0, 3.0, 0.1)       
    ATR_STOP_MULT = st.slider("청산 Multiplier", 1.0, 5.0, 3.0, 0.1) 
    ADX_THRESHOLD = st.slider("ADX 기준", 15, 30, 25)

# ==========================================
# 🛠️ [수정됨] 종목명 찾기 (에러나도 죽지 않게 수정)
# ==========================================
@st.cache_data
def get_stock_name(ticker):
    # 1. KRX (주식) 확인
    try:
        df_krx = fdr.StockListing('KRX')
        chk = df_krx[df_krx['Code'] == ticker]
        if not chk.empty:
            return chk['Name'].values[0]
    except:
        pass # 에러나면 다음으로 넘어감

    # 2. ETF/KR 확인 (여기가 문제였음: Code -> Symbol로 변경)
    try:
        df_etf = fdr.StockListing('ETF/KR')
        # ETF는 컬럼명이 'Symbol'일 수 있음
        col_name = 'Symbol' if 'Symbol' in df_etf.columns else 'Code'
        chk = df_etf[df_etf[col_name] == ticker]
        if not chk.empty:
            return chk['Name'].values[0]
    except:
        pass
        
    return None

# ==========================================
# 📈 분석 로직 실행
# ==========================================
if st.button("🔍 진단 시작", type="primary"):
    with st.spinner(f"[{TICKER}] 데이터 조회 중..."):
        
        # 1. 종목명 확인 (못 찾아도 괜찮음! 일단 넘어감)
        stock_name = get_stock_name(TICKER)
        display_name = stock_name if stock_name else TICKER # 이름 없으면 코드로 표시

        # 2. 데이터 수집 (최근 2년)
        # 이름 명단에 없어도, 여기서 데이터 긁어지면 장땡입니다.
        start_fetch_date = (pd.to_datetime(ENTRY_DATE) - timedelta(days=730)).strftime('%Y-%m-%d')
        df = fdr.DataReader(TICKER, start_fetch_date)

        # 데이터가 비어있으면 진짜 없는 종목
        if df.empty:
            st.error(f"❌ 종목코드 [{TICKER}]의 차트 데이터를 찾을 수 없습니다.")
            st.stop()
            
        # 데이터가 있으면 이름 못 찾았어도 성공 처리
        if not stock_name:
            st.warning(f"⚠️ 종목명은 못 찾았지만, 차트 데이터는 찾았습니다! ({TICKER})")

        # 3. 지표 계산
        df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=ATR_PERIOD)
        st_ind = ta.supertrend(df['High'], df['Low'], df['Close'], length=ATR_PERIOD, multiplier=ATR_FACTOR)
        df = pd.concat([df, st_ind], axis=1)
        adx = df.ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=ATR_PERIOD)
        df = pd.concat([df, adx], axis=1)

        # 4. 현재 상태 추출
        last_row = df.iloc[-1]
        current_price = last_row['Close']
        current_atr = last_row['atr']
        
        # 컬럼명 안전하게 찾기
        adx_col = f'ADX_{ATR_PERIOD}' 
        current_adx = last_row[adx_col] if adx_col in df.columns else last_row.get('ADX_14', 0)
        
        dir_col = f'SUPERTd_{ATR_PERIOD}_{ATR_FACTOR}'
        if dir_col not in df.columns:
            cols = [c for c in df.columns if c.startswith(f'SUPERTd_{ATR_PERIOD}')]
            dir_col = cols[0] if cols else None
            
        current_trend = last_row[dir_col] if dir_col else 0

        # ==========================================
        # 📊 결과 리포트
        # ==========================================
        st.divider()
        st.subheader(f"📌 {display_name} 진단 결과")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{current_price:,.0f}원")
        m2.metric("추세 방향", "📈 상승장" if current_trend == 1 else "📉 하락장", 
                  delta="매수 구간" if current_trend == 1 else "매도 구간", delta_color="normal")
        m3.metric(f"추세 강도 (ADX)", f"{current_adx:.1f}", 
                  "🔥 강력함" if current_adx >= ADX_THRESHOLD else "💤 약함")

        # 📢 신규 진입 판독
        st.subheader("📢 신규 진입 판독")
        if current_trend == 1 and current_adx >= ADX_THRESHOLD:
            st.success("🟢 [매수 추천] 추세가 상승이고, 힘(ADX)도 강력합니다!")
        elif current_trend == 1 and current_adx < ADX_THRESHOLD:
            st.warning("🟡 [관망] 상승 추세긴 하지만, 아직 힘이 부족합니다.")
        else:
            st.error("🔴 [진입 금지] 하락 추세입니다.")

        # 🛡️ 보유자 대응
        if ENTRY_PRICE > 0:
            st.divider()
            st.subheader("🛡️ 보유자 대응 (Ratchet)")
            
            my_df = df[df.index >= pd.to_datetime(ENTRY_DATE)].copy()
            if not my_df.empty:
                highest_price = my_df['High'].max()
                ts_exit_price = highest_price - (current_atr * ATR_STOP_MULT)
                roi = ((current_price - ENTRY_PRICE) / ENTRY_PRICE) * 100
                
                col_a, col_b = st.columns(2)
                col_a.info(f"💰 수익률: {roi:+.2f}%")
                col_b.write(f"🛑 **청산 라인:** {ts_exit_price:,.0f}원")
                st.caption(f"(최고가 {highest_price:,.0f}원 기준)")
                
                if current_price < ts_exit_price:
                    st.error(f"🚨 [긴급 매도] 청산 라인({ts_exit_price:,.0f}원) 붕괴! 탈출하세요.")
                elif current_trend == -1:
                    st.error("🚨 [매도] 추세 하락 전환! 청산하세요.")
                else:
                    gap = current_price - ts_exit_price
                    st.success(f"✅ [홀딩] 버티세요. 여유폭 {gap:,.0f}원")
