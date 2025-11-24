import streamlit as st
import pandas as pd
import mplfinance as mpf
import datetime
import matplotlib.pyplot as plt
import akshare as ak
import pandas_ta as ta
import numpy as np

# --- 核心分析逻辑 (合并自 advanced_analysis.py) ---

def get_stock_data(symbol, start_date, end_date):
    """获取数据"""
    print(f"正在获取 {symbol} 的数据...")
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        df.set_index('日期', inplace=True)
        df = df.rename(columns={'开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'})
        return df
    except Exception as e:
        print(f"获取数据出错: {e}")
        return None

def calculate_advanced_indicators(df):
    """
    计算高级技术指标：MACD, KDJ, 布林带
    """
    # 1. MACD (12, 26, 9)
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None:
        # 动态查找列名，避免硬编码导致的 KeyError
        macd_col = [c for c in macd.columns if c.startswith('MACD_')][0]
        signal_col = [c for c in macd.columns if c.startswith('MACDs_')][0]
        hist_col = [c for c in macd.columns if c.startswith('MACDh_')][0]
        
        df['MACD'] = macd[macd_col]
        df['MACD_signal'] = macd[signal_col]
        df['MACD_hist'] = macd[hist_col]

    # 2. Bollinger Bands (20, 2)
    bbands = df.ta.bbands(length=20, std=2)
    if bbands is not None:
        # 动态查找列名
        bbu_col = [c for c in bbands.columns if c.startswith('BBU')][0]
        bbm_col = [c for c in bbands.columns if c.startswith('BBM')][0]
        bbl_col = [c for c in bbands.columns if c.startswith('BBL')][0]
        
        df['BBU'] = bbands[bbu_col]
        df['BBM'] = bbands[bbm_col]
        df['BBL'] = bbands[bbl_col]

    # 3. KDJ (9, 3)
    kdj = df.ta.kdj(length=9, signal=3)
    if kdj is not None:
        # 动态查找列名
        k_col = [c for c in kdj.columns if c.startswith('K_')][0]
        d_col = [c for c in kdj.columns if c.startswith('D_')][0]
        j_col = [c for c in kdj.columns if c.startswith('J_')][0]
        
        df['K'] = kdj[k_col]
        df['D'] = kdj[d_col]
        df['J'] = kdj[j_col]
    
    # 4. 均线
    df['MA20'] = df.ta.sma(length=20)
    
    return df

def run_strategy_backtest(df, initial_capital=100000):
    """
    策略回测：布林带趋势突破策略
    """
    cash = initial_capital
    position = 0
    commission_rate = 0.0003 # 万三佣金
    
    trade_log = []
    equity_curve = []
    buy_signals = []
    sell_signals = []
    
    for i in range(len(df)):
        price = df.iloc[i]['Close']
        date = df.index[i]
        
        # 信号标记 (默认 NaN)
        buy_mark = np.nan
        sell_mark = np.nan
        
        # 确保有足够数据计算指标
        if i < 20:
            equity_curve.append(cash)
            buy_signals.append(np.nan)
            sell_signals.append(np.nan)
            continue
            
        # 获取当日指标
        bbu = df.iloc[i]['BBU'] # 上轨
        bbm = df.iloc[i]['BBM'] # 中轨 (MA20)
        macd = df.iloc[i]['MACD']
        
        # --- 交易逻辑 ---
        
        # 买入条件: 空仓 + 收盘价突破上轨 + MACD为正
        if position == 0:
            if price > bbu and macd > 0:
                # 全仓买入 (按100股取整)
                shares = int(cash / price / 100) * 100
                if shares > 0:
                    cost = shares * price
                    fee = cost * commission_rate
                    cash -= (cost + fee)
                    position = shares
                    trade_log.append({'日期': date, '操作': '买入', '价格': price, '数量': shares})
                    buy_mark = price * 0.98 # 图表标记位置
        
        # 卖出条件: 持仓 + 收盘价跌破中轨 (止盈/止损)
        elif position > 0:
            if price < bbm:
                revenue = position * price
                fee = revenue * commission_rate
                cash += (revenue - fee)
                trade_log.append({'日期': date, '操作': '卖出', '价格': price, '数量': position})
                position = 0
                sell_mark = price * 1.02 # 图表标记位置
        
        # 记录资产净值
        current_equity = cash + (position * price)
        equity_curve.append(current_equity)
        
        buy_signals.append(buy_mark)
        sell_signals.append(sell_mark)
        
    df['Equity'] = equity_curve
    df['Buy_Signal'] = buy_signals
    df['Sell_Signal'] = sell_signals
    
    # 计算回测指标
    total_return = (equity_curve[-1] - initial_capital) / initial_capital * 100
    
    return df, trade_log, total_return

def get_top_gainers(top_n=10):
    """获取实时涨幅榜前N名"""
    source = "EastMoney"
    try:
        # 尝试使用东方财富接口 (数据最全)
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"东方财富接口失败: {e}, 尝试使用新浪接口...")
        try:
            source = "Sina"
            # 备用：使用新浪接口
            df = ak.stock_zh_a_spot()
            # 新浪接口列名映射与补充
            # 新浪列: ['代码', '名称', '最新价', '涨跌额', '涨跌幅', '买入', '卖出', '昨收', '今开', '最高', '最低', '成交量', '成交额', '时间戳']
            # 补充缺失列，防止后续报错
            for col in ['换手率', '量比', '市盈率-动态']:
                df[col] = 0.0
        except Exception as e2:
            print(f"新浪接口也失败: {e2}")
            return None, None

    try:
        # 按涨跌幅排序 (降序)
        # 确保涨跌幅列是数值型
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        df = df.sort_values(by='涨跌幅', ascending=False)
        # 取前N名
        top_df = df.head(top_n).copy()
        return top_df, source
    except Exception as e:
        print(f"处理涨幅榜数据出错: {e}")
        return None, None

# --- Streamlit 界面逻辑 ---

# 设置页面配置
st.set_page_config(page_title="A股智能分析工具", layout="wide")

st.title("📈 A股智能分析与回测系统")

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

# 侧边栏导航
page = st.sidebar.radio("功能选择", ["个股详细分析", "🔥 实时涨幅榜分析"])

if page == "🔥 实时涨幅榜分析":
    st.header("🚀 实时涨幅榜前10名分析")
    st.markdown("获取当前市场涨幅最高的股票，并进行横向技术指标对比。")
    
    if st.button("刷新数据", type="primary"):
        with st.spinner("正在获取实时行情..."):
            top_df, source = get_top_gainers(10)
            
            if top_df is not None:
                if source == "Sina":
                    st.warning("⚠️ 注意：由于主数据源连接失败，当前使用备用数据源（新浪）。部分字段（换手率、量比、市盈率）可能不可用。")
                
                # 展示基础数据
                st.subheader("📋 基础行情数据")
                st.dataframe(top_df[['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '换手率', '量比', '市盈率-动态']])
                
                st.subheader("📊 涨势横向对比")
                
                # 准备对比数据
                comparison_data = []
                
                # 进度条
                progress_text = "正在进行技术分析..."
                my_bar = st.progress(0, text=progress_text)
                
                total_stocks = len(top_df)
                
                for i, (idx, row) in enumerate(top_df.iterrows()):
                    symbol = row['代码']
                    name = row['名称']
                    
                    # 获取个股历史数据进行技术分析
                    # 获取最近100天数据用于计算指标
                    end_str = datetime.datetime.now().strftime("%Y%m%d")
                    start_str = (datetime.datetime.now() - datetime.timedelta(days=150)).strftime("%Y%m%d")
                    
                    stock_df = get_stock_data(symbol, start_str, end_str)
                    
                    if stock_df is not None and not stock_df.empty:
                        # 计算指标
                        stock_df = calculate_advanced_indicators(stock_df)
                        latest = stock_df.iloc[-1]
                        
                        # 收集关键指标
                        comparison_data.append({
                            '代码': symbol,
                            '名称': name,
                            '最新价': row['最新价'],
                            '涨跌幅%': row['涨跌幅'],
                            'RSI(14)': round(latest['RSI'], 2) if 'RSI' in latest else None,
                            'MACD': round(latest['MACD'], 3) if 'MACD' in latest else None,
                            '布林位置': '上轨上方' if latest['Close'] > latest['BBU'] else ('中轨上方' if latest['Close'] > latest['BBM'] else '弱势区域'),
                            'KDJ状态': '金叉' if latest['K'] > latest['D'] else '死叉'
                        })
                    
                    # 更新进度
                    my_bar.progress((i + 1) / total_stocks, text=f"正在分析 {name} ({symbol})...")
                
                my_bar.empty()
                
                # 展示对比表格
                if comparison_data:
                    comp_df = pd.DataFrame(comparison_data)
                    st.table(comp_df)
                    
                    # 简单的可视化对比
                    st.subheader("📈 涨幅 vs RSI 散点图")
                    st.caption("RSI > 70 表示超买，可能回调；RSI < 30 表示超卖。")
                    
                    # 使用 matplotlib 绘制散点图
                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    # 处理中文显示问题，这里用英文标签或代码代替
                    scatter = ax.scatter(comp_df['RSI(14)'], comp_df['涨跌幅%'], c=comp_df['涨跌幅%'], cmap='viridis')
                    plt.colorbar(scatter, label='Change %')
                    
                    # 添加标签
                    for i, txt in enumerate(comp_df['代码']):
                        ax.annotate(txt, (comp_df['RSI(14)'][i], comp_df['涨跌幅%'][i]), xytext=(5, 5), textcoords='offset points')
                        
                    ax.set_xlabel('RSI (14)')
                    ax.set_ylabel('Change %')
                    ax.axvline(x=70, color='red', linestyle='--', label='Overbought (70)')
                    ax.axvline(x=30, color='green', linestyle='--', label='Oversold (30)')
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    
                    st.pyplot(fig)
                else:
                    st.warning("无法获取个股详细数据进行对比。")
            else:
                st.error("获取实时行情失败。可能是由于网络连接问题或数据源（东方财富/新浪）暂时不可用。请稍后再试，或检查网络环境。")

elif page == "个股详细分析":
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
