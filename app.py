import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

# ==========================================
# 🎨 앱 디자인 및 설정
# ==========================================
st.set_page_config(page_title="추세 진단기", page_icon="🚀")

st.title("🚀 추세 판결기: 주식 진단")
st.write("종목 티커를 입력하세요")

# ==========================================
# 📥 사용자 입력 (모바일 터치 최적화)
# ==========================================
col1, col2 = st.columns(2)
with col1:
    TICKER = st.text_input("종목코드 (6자리)", value="035420")
with col2:
    ENTRY_PRICE = st.number_input("내 평단가 (없으면 0)", value=0, step=100)

ENTRY_DATE = st.date_input("진입 날짜", value=datetime(2026, 1, 9))

# ⚙️ 설정값 (사이드바에 숨김)
with st.sidebar:
    st.header("⚙️ 전략 설정")
    ATR_PERIOD = st.slider("ATR 기간", 10, 30, 20)
    ATR_FACTOR = st.slider("진입 Factor", 1.0, 5.0, 3.0, 0.1)
    ATR_STOP_MULT = st.slider("청산 Multiplier", 1.0, 5.0, 3.0, 0.1)
    ADX_THRESHOLD = st.slider("ADX 기준", 15, 30, 25)

# ==========================================
# 📈 분석 로직
# ==========================================
def get_stock_name(ticker):
    try:
        df_krx = fdr.StockListing('KRX')
        name = df_krx[df_krx['Code'] == ticker]['Name'].values[0]
        return name
    except:
        return None

if st.button("🔍 진단 시작", type="primary"):
    with st.spinner('데이터를 분석 중입니다...'):
        # 1. 종목명 확인
        stock_name = get_stock_name(TICKER)
        if not stock_name:
            st.error("❌ 종목코드를 확인해주세요.")
            st.stop()

        # 2. 데이터 수집
        start_fetch_date = (pd.to_datetime(ENTRY_DATE) - timedelta(days=730)).strftime('%Y-%m-%d')
        df = fdr.DataReader(TICKER, start_fetch_date)

        if df.empty:
            st.error("❌ 데이터를 가져올 수 없습니다.")
            st.stop()

        # 3. 지표 계산
        df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=ATR_PERIOD)
        st_ind = ta.supertrend(df['High'], df['Low'], df['Close'], length=ATR_PERIOD, multiplier=ATR_FACTOR)
        df = pd.concat([df, st_ind], axis=1)
        adx = df.ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=14)
        df = pd.concat([df, adx], axis=1)

        # 4. 현재 상태
        last_row = df.iloc[-1]
        current_price = last_row['Close']
        current_adx = last_row['ADX_14']
        current_atr = last_row['atr']
        
        # SuperTrend 컬럼 찾기
        dir_col = f'SUPERTd_{ATR_PERIOD}_{ATR_FACTOR}'
        if dir_col not in df.columns:
            dir_col = [c for c in df.columns if c.startswith(f'SUPERTd_{ATR_PERIOD}')][0]
        current_trend = last_row[dir_col]

        # ==========================================
        # 📊 결과 리포트 출력
        # ==========================================
        st.divider()
        st.subheader(f"{stock_name} ({TICKER})")
        
        # 메트릭 표시
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{current_price:,.0f}원")
        m2.metric("추세", "📈상승" if current_trend == 1 else "📉하락", 
                  delta="Buy" if current_trend == 1 else "Sell", delta_color="normal")
        m3.metric("에너지(ADX)", f"{current_adx:.1f}", 
                  "강함" if current_adx >= ADX_THRESHOLD else "약함")

        # 📢 신규 진입 판독
        st.subheader("📢 신규 진입 판독")
        if current_trend == 1 and current_adx >= ADX_THRESHOLD:
            st.success("🟢 [진입 추천] 조건이 완벽합니다! (추세+에너지)")
        elif current_trend == 1 and current_adx < ADX_THRESHOLD:
            st.warning("🟡 [관망] 상승 추세지만 힘이 부족합니다.")
        else:
            st.error("🔴 [진입 금지] 하락 추세입니다.")

        # 🛡️ 보유자 대응
        if ENTRY_PRICE > 0:
            st.divider()
            st.subheader("🛡️ 보유자 대응")
            
            my_df = df[df.index >= pd.to_datetime(ENTRY_DATE)].copy()
            if not my_df.empty:
                highest_price = my_df['High'].max()
                ts_exit_price = highest_price - (current_atr * ATR_STOP_MULT)
                roi = ((current_price - ENTRY_PRICE) / ENTRY_PRICE) * 100
                
                st.info(f"내 평단가: {ENTRY_PRICE:,.0f}원 (수익률: {roi:+.2f}%)")
                st.write(f"🛑 **손절 라인:** {ts_exit_price:,.0f}원")
                
                if current_price < ts_exit_price:
                    st.error("🚨 [매도 신호] 손절 라인 터치! 탈출하세요.")
                elif current_trend == -1:
                    st.error("🚨 [매도 신호] 추세 꺾임! 탈출하세요.")
                else:
                    gap = current_price - ts_exit_price
                    st.success(f"✅ [홀딩] 쫄지 마세요. 안전마진 {gap:,.0f}원 남음")
