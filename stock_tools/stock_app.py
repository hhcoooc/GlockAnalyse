import streamlit as st
import pandas as pd
import mplfinance as mpf
import datetime
import matplotlib.pyplot as plt
from advanced_analysis import get_stock_data, calculate_advanced_indicators, run_strategy_backtest

# 设置页面配置
st.set_page_config(page_title="A股智能分析工具", layout="wide")

st.title("📈 A股智能分析与回测系统")
st.markdown("输入股票代码，一键获取**技术指标分析**、**买卖信号**及**历史回测报告**。")

# 侧边栏输入
with st.sidebar:
    st.header("参数设置")
    symbol = st.text_input("股票代码", value="300034", help="请输入6位A股代码，如 600519")
    
    # 日期范围选择
    today = datetime.datetime.now()
    start_date_default = today - datetime.timedelta(days=365*2)
    
    date_range = st.date_input(
        "回测时间范围",
        value=(start_date_default, today),
        max_value=today
    )
    
    initial_capital = st.number_input("初始资金", value=100000, step=10000)
    
    run_btn = st.button("开始分析", type="primary")

def plot_streamlit_chart(df, symbol, trade_log):
    """
    专门为 Streamlit 适配的绘图函数
    """
    # 设置样式
    mc = mpf.make_marketcolors(up='r', down='g', edge='i', wick='i', volume='in', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)

    # 添加图表
    add_plots = []
    
    # 1. 布林带 (主图)
    if 'BBU' in df.columns:
        add_plots.append(mpf.make_addplot(df['BBU'], color='lightgray', width=0.8))
        add_plots.append(mpf.make_addplot(df['BBM'], color='orange', width=1.0))
        add_plots.append(mpf.make_addplot(df['BBL'], color='lightgray', width=0.8))
    
    # 2. 买卖信号 (主图)
    if 'Buy_Signal' in df.columns:
        add_plots.append(mpf.make_addplot(df['Buy_Signal'], type='scatter', markersize=100, marker='^', color='m'))
        add_plots.append(mpf.make_addplot(df['Sell_Signal'], type='scatter', markersize=100, marker='v', color='k'))

    # 3. KDJ (Panel 2)
    if 'K' in df.columns:
        add_plots.append(mpf.make_addplot(df['K'], panel=2, color='orange', ylabel='KDJ'))
        add_plots.append(mpf.make_addplot(df['D'], panel=2, color='blue'))
        add_plots.append(mpf.make_addplot(df['J'], panel=2, color='purple'))

    title = f"Analysis: {symbol}"
    
    # 使用 returnfig=True 获取 figure 对象
    fig, axlist = mpf.plot(df, type='candle', volume=True, addplot=add_plots, 
             style=s, title=title, panel_ratios=(4,1,2), 
             datetime_format='%Y-%m-%d', show_nontrading=False, returnfig=True, figsize=(12, 8))
    
    return fig

if run_btn:
    if len(date_range) != 2:
        st.error("请选择完整的开始和结束日期。")
    else:
        start_str = date_range[0].strftime("%Y%m%d")
        end_str = date_range[1].strftime("%Y%m%d")
        
        with st.spinner(f"正在获取 {symbol} 数据并进行量化分析..."):
            df = get_stock_data(symbol, start_str, end_str)
            
            if df is None or df.empty:
                st.error(f"未获取到 {symbol} 的数据，请检查代码是否正确。")
            else:
                # 1. 计算指标
                df = calculate_advanced_indicators(df)
                
                # 2. 运行回测
                df, trade_log, total_return = run_strategy_backtest(df, initial_capital)
                
                # --- 结果展示 ---
                
                # 顶部指标卡片
                col1, col2, col3 = st.columns(3)
                latest = df.iloc[-1]
                latest_close = latest['Close']
                prev_close = df.iloc[-2]['Close']
                change = (latest_close - prev_close) / prev_close * 100
                
                col1.metric("当前价格", f"{latest_close:.2f}", f"{change:.2f}%")
                col2.metric("策略收益率", f"{total_return:.2f}%", delta_color="normal")
                col3.metric("交易次数", f"{len(trade_log)}")
                
                # 图表区域
                st.subheader("📊 技术分析图表")
                fig = plot_streamlit_chart(df, symbol, trade_log)
                st.pyplot(fig)
                
                # 信号解读区域
                st.subheader("🤖 智能信号解读")
                
                # 综合打分逻辑 (复用 advanced_analysis 的逻辑)
                score = 0
                reasons = []
                if latest['Close'] > latest['BBM']:
                    score += 1
                    reasons.append("股价位于布林中轨上方 (强势)")
                if latest['Close'] > latest['BBU']:
                    score += 1
                    reasons.append("股价突破布林上轨 (极强/可能超买)")
                if latest['K'] > latest['D'] and latest['K'] < 80:
                    score += 1
                    reasons.append("KDJ 金叉且未钝化")
                elif latest['J'] > 100:
                    score -= 1
                    reasons.append("KDJ J值过高 (超买风险)")
                if latest['MACD'] > latest['MACD_signal']:
                    score += 1
                    reasons.append("MACD 处于多头状态")
                
                if score >= 3:
                    st.success(f"**综合结论: 信号偏强 (得分 {score}/4)**，建议关注。")
                elif score <= 1:
                    st.warning(f"**综合结论: 信号偏弱 (得分 {score}/4)**，建议观望。")
                else:
                    st.info(f"**综合结论: 震荡行情 (得分 {score}/4)**，方向不明。")
                    
                for r in reasons:
                    st.write(f"- {r}")
                
                # 交易记录
                with st.expander("查看详细交易记录"):
                    if trade_log:
                        log_df = pd.DataFrame(trade_log)
                        # 格式化日期
                        log_df['日期'] = log_df['日期'].apply(lambda x: x.strftime('%Y-%m-%d'))
                        st.table(log_df)
                    else:
                        st.write("在此期间无交易触发。")
