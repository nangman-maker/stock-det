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
st.write("종목코드 6자리를 입력하세요. (예: 005930, 069500)")

# ==========================================
# 📥 사용자 입력
# ==========================================
col1, col2 = st.columns(2)
with col1:
    # 기본값: 삼성전자(005930)
    TICKER = st.text_input("종목코드 (6자리)", value="005930")
with col2:
    ENTRY_PRICE = st.number_input("내 평단가 (없으면 0)", value=0, step=100)

# 날짜 기본값: 오늘
ENTRY_DATE = st.date_input("진입 날짜", value=datetime.now())

# ⚙️ 설정값 (사이드바) - 준수님 전용 세팅 (20 / 3.0 / 3.0)
with st.sidebar:
    st.header("⚙️ 전략 설정")
    st.info("준수님 전용 기본값(20/3.0/3.0)이 적용되었습니다.")
    ATR_PERIOD = st.slider("ATR 기간", 10, 30, 20)          
    ATR_FACTOR = st.slider("진입 Factor", 1.0, 5.0, 3.0, 0.1)       
    ATR_STOP_MULT = st.slider("청산 Multiplier", 1.0, 5.0, 3.0, 0.1) 
    ADX_THRESHOLD = st.slider("ADX 기준", 15, 30, 25)

# ==========================================
# 🛠️ [수정됨] 종목명 가져오기 (주식 + ETF 통합)
# ==========================================
@st.cache_data  # 속도 향상을 위해 캐싱 적용
def get_stock_name(ticker):
    try:
        # 1차 시도: 일반 주식(KRX) 명단 검색
        df_krx = fdr.StockListing('KRX')
        chk_stock = df_krx[df_krx['Code'] == ticker]
        if not chk_stock.empty:
            return chk_stock['Name'].values[0]

        # 2차 시도: ETF(ETF/KR) 명단 검색 (여기가 추가됨!)
        df_etf = fdr.StockListing('ETF/KR')
        chk_etf = df_etf[df_etf['Code'] == ticker]
        if not chk_etf.empty:
            return chk_etf['Name'].values[0]
            
        return None
    except:
        return None

# ==========================================
# 📈 분석 로직 실행
# ==========================================
if st.button("🔍 진단 시작", type="primary"):
    with st.spinner(f"[{TICKER}] 데이터를 분석 중입니다..."):
        
        # 1. 종목명 확인
        stock_name = get_stock_name(TICKER)
        if not stock_name:
            st.error(f"❌ 종목코드 [{TICKER}]를 찾을 수 없습니다. (상장폐지 혹은 코드 오타)")
            st.stop()

        # 2. 데이터 수집 (최근 2년치)
        start_fetch_date = (pd.to_datetime(ENTRY_DATE) - timedelta(days=730)).strftime('%Y-%m-%d')
        df = fdr.DataReader(TICKER, start_fetch_date)

        if df.empty:
            st.error("❌ 차트 데이터를 가져올 수 없습니다.")
            st.stop()

        # 3. 지표 계산
        # ATR
        df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=ATR_PERIOD)
        
        # SuperTrend
        st_ind = ta.supertrend(df['High'], df['Low'], df['Close'], length=ATR_PERIOD, multiplier=ATR_FACTOR)
        df = pd.concat([df, st_ind], axis=1)
        
        # ADX
        adx = df.ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=ATR_PERIOD)
        df = pd.concat([df, adx], axis=1)

        # 4. 현재 상태 추출
        last_row = df.iloc[-1]
        current_price = last_row['Close']
        current_atr = last_row['atr']
        
        # ADX 컬럼 찾기 (라이브러리가 ADX_20 등으로 만듦)
        adx_col = f'ADX_{ATR_PERIOD}' 
        current_adx = last_row[adx_col] if adx_col in df.columns else last_row.get('ADX_14', 0)
        
        # SuperTrend 방향 찾기
        dir_col = f'SUPERTd_{ATR_PERIOD}_{ATR_FACTOR}'
        if dir_col not in df.columns:
            # 소수점 등으로 이름이 다를 경우 유사 컬럼 검색
            cols = [c for c in df.columns if c.startswith(f'SUPERTd_{ATR_PERIOD}')]
            dir_col = cols[0] if cols else None
            
        current_trend = last_row[dir_col] if dir_col else 0

        # ==========================================
        # 📊 결과 리포트
        # ==========================================
        st.divider()
        st.subheader(f"📌 {stock_name} ({TICKER}) 진단 결과")
        
        # 상단 메트릭
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
            st.error("🔴 [진입 금지] 하락 추세입니다. 쳐다보지 마세요.")

        # 🛡️ 보유자 대응 (순정 래칫 전략)
        if ENTRY_PRICE > 0:
            st.divider()
            st.subheader("🛡️ 보유자 대응 가이드 (Ratchet)")
            
            # 진입일 이후 데이터만 잘라서 최고가 계산
            my_df = df[df.index >= pd.to_datetime(ENTRY_DATE)].copy()
            
            if not my_df.empty:
                highest_price = my_df['High'].max()
                # 래칫 손절가 = 최고가 - (ATR * Multiplier)
                ts_exit_price = highest_price - (current_atr * ATR_STOP_MULT)
                roi = ((current_price - ENTRY_PRICE) / ENTRY_PRICE) * 100
                
                col_a, col_b = st.columns(2)
                col_a.info(f"💰 내 수익률: {roi:+.2f}%")
                col_b.write(f"🛑 **손절/익절 라인:** {ts_exit_price:,.0f}원")
                st.caption(f"(보유 기간 중 최고가 {highest_price:,.0f}원 기준 -{ATR_STOP_MULT}배 적용)")
                
                # 매도 시그널 판단
                if current_price < ts_exit_price:
                    st.error(f"🚨 [긴급 매도] 가격이 {ts_exit_price:,.0f}원을 깼습니다! 원칙대로 청산하세요.")
                elif current_trend == -1:
                    st.error("🚨 [매도] 추세가 하락으로 바뀌었습니다. 청산하세요.")
                else:
                    gap = current_price - ts_exit_price
                    st.success(f"✅ [홀딩] 아직 팝니다. 여유폭 {gap:,.0f}원 남았습니다.")
            else:
                st.warning("⚠️ 진입 날짜가 차트 데이터보다 미래이거나 데이터가 없습니다.")
