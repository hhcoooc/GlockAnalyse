import streamlit as st
import pandas as pd
import mplfinance as mpf
import datetime
import matplotlib.pyplot as plt
import akshare as ak
import pandas_ta as ta
import numpy as np
try:
    from stock_tools import db_manager
except ImportError:
    import db_manager # For local run if path issues

# --- 核心分析逻辑 (合并自 advanced_analysis.py) ---

def get_main_force_flow(symbol):
    """获取个股主力资金流向 (最近5天)"""
    try:
        # akshare 接口: stock_individual_fund_flow
        # 需要判断市场
        market = 'sh' if symbol.startswith('6') else 'sz' # 简单判断，北交所可能不支持
        if symbol.startswith('8') or symbol.startswith('4') or symbol.startswith('9'):
             # 北交所暂不支持主力资金接口，返回空
             return None
             
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if df is None or df.empty:
            return None
            
        # 取最近5天
        recent = df.tail(5).copy()
        # 假设列名: 日期, 收盘价, 涨跌幅, 主力净流入, 主力净流入占比, 超大单净流入, ...
        # 需要根据实际返回列名调整
        return recent
    except Exception as e:
        print(f"获取主力资金失败: {e}")
        return None

def analyze_main_force(flow_df):
    """分析主力动向"""
    if flow_df is None or flow_df.empty:
        return "暂无主力数据"
    
    # 累加最近5日主力净流入
    # 注意：akshare返回的列名可能是中文
    try:
        net_inflow_col = [c for c in flow_df.columns if '主力净流入' in c and '占比' not in c][0]
        # 确保是数值
        # 有些接口返回的是带单位的字符串，需要清洗，这里假设是数值或可转数值
        # akshare通常返回数值
        
        total_inflow = flow_df[net_inflow_col].sum()
        
        # 获取最近一天的涨跌幅
        latest_change = flow_df.iloc[-1]['涨跌幅'] if '涨跌幅' in flow_df.columns else 0
        
        analysis = []
        if total_inflow > 0:
            analysis.append(f"近5日主力累计净流入 {total_inflow/10000:.2f} 万")
            if latest_change < 0:
                analysis.append("⚠️ 主力逆势吸筹 (股价跌但主力买)，疑似【偷偷买入】")
            else:
                analysis.append("🔥 主力资金持续流入，推动上涨")
        else:
            analysis.append(f"近5日主力累计净流出 {abs(total_inflow)/10000:.2f} 万")
            if latest_change > 0:
                analysis.append("⚠️ 主力借涨出货 (股价涨但主力卖)，疑似【偷偷卖出】")
            else:
                analysis.append("📉 主力资金持续流出，压制股价")
                
        return " | ".join(analysis)
    except Exception as e:
        return f"分析主力数据出错: {e}"

def add_market_prefix(symbol):
    """为新浪接口添加市场前缀"""
    symbol = str(symbol)
    if symbol.startswith('6'):
        return 'sh' + symbol
    elif symbol.startswith('0') or symbol.startswith('3'):
        return 'sz' + symbol
    elif symbol.startswith('8') or symbol.startswith('4') or symbol.startswith('9'):
        return 'bj' + symbol
    else:
        return 'sh' + symbol # 默认尝试 sh

def get_stock_data(symbol, start_date, end_date):
    """获取数据 (支持多源降级)"""
    print(f"正在获取 {symbol} 的数据...")
    
    # 确保 symbol 是纯数字字符串
    import re
    clean_symbol = re.sub(r'\D', '', str(symbol))
    
    # 尝试 1: 东方财富 (stock_zh_a_hist)
    try:
        df = ak.stock_zh_a_hist(symbol=clean_symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: raise Exception("Empty data from EastMoney")
        
        df['日期'] = pd.to_datetime(df['日期'])
        df.set_index('日期', inplace=True)
        df = df.rename(columns={'开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'})
        return df
    except Exception as e:
        print(f"东方财富接口失败: {e}, 尝试新浪接口...")
        
        # 尝试 2: 新浪财经 (stock_zh_a_daily)
        try:
            prefixed_symbol = add_market_prefix(clean_symbol)
            df = ak.stock_zh_a_daily(symbol=prefixed_symbol, start_date=start_date, end_date=end_date)
            if df.empty: return None
            
            # 统一列名格式
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df = df.rename(columns={
                'open': 'Open', 
                'high': 'High', 
                'low': 'Low', 
                'close': 'Close', 
                'volume': 'Volume'
            })
            
            # 确保所有OHLCV列都是数值型
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e2:
            print(f"新浪接口也失败: {e2}")
            return None

def calculate_advanced_indicators(df):
    """
    计算高级技术指标：MACD, KDJ, 布林带
    """
    # 确保数据量足够
    if df is None or len(df) < 2:
        return df

    # 1. MACD (12, 26, 9)
    try:
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            # 动态查找列名，避免硬编码导致的 KeyError
            macd_cols = [c for c in macd.columns if c.startswith('MACD_')]
            signal_cols = [c for c in macd.columns if c.startswith('MACDs_')]
            hist_cols = [c for c in macd.columns if c.startswith('MACDh_')]
            
            if macd_cols and signal_cols and hist_cols:
                df['MACD'] = macd[macd_cols[0]]
                df['MACD_signal'] = macd[signal_cols[0]]
                df['MACD_hist'] = macd[hist_cols[0]]
    except Exception as e:
        print(f"MACD calculation error: {e}")

    # 2. Bollinger Bands (20, 2)
    try:
        bbands = df.ta.bbands(length=20, std=2)
        if bbands is not None and not bbands.empty:
            # 动态查找列名
            bbu_cols = [c for c in bbands.columns if c.startswith('BBU')]
            bbm_cols = [c for c in bbands.columns if c.startswith('BBM')]
            bbl_cols = [c for c in bbands.columns if c.startswith('BBL')]
            
            if bbu_cols and bbm_cols and bbl_cols:
                df['BBU'] = bbands[bbu_cols[0]]
                df['BBM'] = bbands[bbm_cols[0]]
                df['BBL'] = bbands[bbl_cols[0]]
    except Exception as e:
        print(f"BBands calculation error: {e}")

    # 3. KDJ (9, 3)
    try:
        kdj = df.ta.kdj(length=9, signal=3)
        if kdj is not None and not kdj.empty:
            # 动态查找列名
            k_cols = [c for c in kdj.columns if c.startswith('K_')]
            d_cols = [c for c in kdj.columns if c.startswith('D_')]
            j_cols = [c for c in kdj.columns if c.startswith('J_')]
            
            if k_cols and d_cols and j_cols:
                df['K'] = kdj[k_cols[0]]
                df['D'] = kdj[d_cols[0]]
                df['J'] = kdj[j_cols[0]]
    except Exception as e:
        print(f"KDJ calculation error: {e}")
    
    # 4. 均线
    try:
        df['MA20'] = df.ta.sma(length=20)
    except:
        pass

    # 5. RSI (14)
    try:
        df['RSI'] = df.ta.rsi(length=14)
    except:
        pass
    
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
        # 如果是新浪数据源，代码可能带有前缀 (如 bj920000)，需要清洗为纯数字
        if source == "Sina":
            df['代码'] = df['代码'].astype(str).str.extract(r'(\d+)', expand=False)

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

# 初始化 Session State
if 'user' not in st.session_state:
    st.session_state.user = None

# --- 登录/注册 侧边栏 ---
with st.sidebar:
    if st.session_state.user:
        st.success(f"欢迎, {st.session_state.user['username']}!")
        if st.button("退出登录"):
            st.session_state.user = None
            st.rerun()
    else:
        st.header("用户登录/注册")
        tab1, tab2 = st.tabs(["登录", "注册"])
        
        with tab1:
            l_user = st.text_input("用户名", key="l_user")
            l_pass = st.text_input("密码", type="password", key="l_pass")
            if st.button("登录"):
                success, user = db_manager.login_user(l_user, l_pass)
                if success:
                    st.session_state.user = user
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
        
        with tab2:
            r_user = st.text_input("用户名", key="r_user")
            r_pass = st.text_input("密码", type="password", key="r_pass")
            if st.button("注册"):
                if r_user and r_pass:
                    success, msg = db_manager.register_user(r_user, r_pass)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("请输入用户名和密码")

st.title("📈 A股智能分析与回测系统")

# 检查预测结果 (仅登录用户)
if st.session_state.user:
    # 获取用户关注股票的最新价格用于验证
    # 这里为了性能，暂时只在用户进入"我的自选"页面时检查，或者简单获取一下
    # 简化处理：每次加载页面时，如果用户有待验证的预测，尝试获取当前价格验证
    # 为了不卡顿，我们可以只在用户点击"验证预测"时触发，或者后台静默处理
    pass 

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
nav_options = ["个股详细分析", "🔥 实时涨幅榜分析"]
if st.session_state.user:
    nav_options.insert(0, "👀 我的自选股")

# 显示用户战绩
if st.session_state.user:
    stats = db_manager.get_user_stats(st.session_state.user['id'])
    if stats and stats['total'] > 0:
        correct = stats['correct'] or 0
        total = stats['correct'] + stats['incorrect'] # 只计算已验证的
        if total > 0:
            win_rate = (correct / total) * 100
            st.sidebar.markdown("---")
            st.sidebar.markdown(f"### 🏆 预测战绩")
            st.sidebar.metric("胜率", f"{win_rate:.1f}%", f"{correct}/{total}")

page = st.sidebar.radio("功能选择", nav_options)

if st.session_state.user and page == "👀 我的自选股":
    st.header("👀 我的自选股监控")
    
    # 获取自选股列表
    watchlist = db_manager.get_watchlist(st.session_state.user['id'])
    
    if not watchlist:
        st.info("暂无自选股，请去【个股详细分析】页面添加。")
    else:
        # 验证预测结果
        if st.button("验证我的预测"):
            with st.spinner("正在验证预测结果..."):
                # 获取当前价格
                current_prices = {}
                # 优化：一次性获取所有行情，而不是循环调用接口
                try:
                    # 尝试使用 akshare 的实时接口
                    # 注意：ak.stock_zh_a_spot_em() 数据量大，网络不稳定时容易断开
                    # 改为循环获取单个股票的实时数据，虽然慢一点但更稳定
                    for item in watchlist:
                        sym = item['symbol']
                        try:
                            # 使用新浪接口获取单个股票实时数据 (更轻量)
                            # 需要加前缀
                            prefix_sym = add_market_prefix(sym)
                            df_spot = ak.stock_zh_a_daily(symbol=prefix_sym, start_date=datetime.datetime.now().strftime("%Y%m%d"), end_date=datetime.datetime.now().strftime("%Y%m%d"))
                            
                            # 如果取不到当天的(比如盘前)，尝试取最近收盘价
                            if df_spot is None or df_spot.empty:
                                # 回退：获取最近几天的历史数据取最后一行
                                end_s = datetime.datetime.now().strftime("%Y%m%d")
                                start_s = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y%m%d")
                                df_hist = get_stock_data(sym, start_s, end_s)
                                if df_hist is not None and not df_hist.empty:
                                    current_prices[sym] = float(df_hist.iloc[-1]['Close'])
                            else:
                                # 注意：stock_zh_a_daily 返回的是历史日线格式，不是实时tick
                                # 为了真正的实时，还是得用 stock_zh_a_spot_em 但为了稳定性，我们这里只做简单的回测验证
                                # 如果是盘中，stock_zh_a_spot_em 是最好的，但容易超时
                                # 我们尝试用 get_stock_data (已封装了重试逻辑)
                                end_s = datetime.datetime.now().strftime("%Y%m%d")
                                start_s = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y%m%d")
                                df_latest = get_stock_data(sym, start_s, end_s)
                                if df_latest is not None and not df_latest.empty:
                                    current_prices[sym] = float(df_latest.iloc[-1]['Close'])
                                    
                        except Exception as inner_e:
                            print(f"获取 {sym} 价格失败: {inner_e}")
                            
                except Exception as e:
                    st.error(f"获取实时行情失败: {e}")
                
                if current_prices:
                    msgs = db_manager.check_predictions(st.session_state.user['id'], current_prices)
                    if msgs:
                        for msg in msgs:
                            st.balloons()
                            st.success(msg)
                    else:
                        st.info("暂无新的预测结果验证。")

        # 展示自选股卡片
        for item in watchlist:
            symbol = item['symbol']
            name = item['stock_name']
            
            with st.expander(f"{name} ({symbol})", expanded=True):
                # 获取数据 (提前获取以便两列都能使用)
                end_str = datetime.datetime.now().strftime("%Y%m%d")
                start_str = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")
                df = get_stock_data(symbol, start_str, end_str)

                col1, col2 = st.columns([3, 1])
                with col1:
                    if df is not None:
                        latest = df.iloc[-1]
                        st.metric("最新收盘", f"{latest['Close']}", f"{(latest['Close'] - df.iloc[-2]['Close']):.2f}")
                        st.line_chart(df['Close'])
                        
                        # 主力动向
                        flow = get_main_force_flow(symbol)
                        analysis = analyze_main_force(flow)
                        st.markdown(f"**主力动向**: {analysis}")
                        
                        if flow is not None and not flow.empty:
                            # 可视化主力资金流向
                            try:
                                # 假设列名包含 '主力净流入'
                                net_inflow_col = [c for c in flow.columns if '主力净流入' in c and '占比' not in c][0]
                                date_col = [c for c in flow.columns if '日期' in c][0]
                                
                                # 数据处理：转换为万元
                                flow_dates = flow[date_col].astype(str).tolist() # 确保日期是字符串
                                flow_values = flow[net_inflow_col] / 10000 # 换算为万元
                                
                                # 使用 Matplotlib 绘制优化后的图表
                                fig_flow, ax_flow = plt.subplots(figsize=(6, 3)) # 稍微调高一点
                                
                                # 颜色逻辑：红涨绿跌
                                colors = ['#ff4d4d' if x > 0 else '#2ecc71' for x in flow_values]
                                bars = ax_flow.bar(flow_dates, flow_values, color=colors, alpha=0.8)
                                
                                # 设置标题和标签 (使用英文以避免乱码，或者配置中文字体)
                                ax_flow.set_title("Main Force Net Inflow (10k CNY)", fontsize=10, pad=10)
                                ax_flow.set_ylabel("Net Inflow (10k)", fontsize=8)
                                
                                # 优化 X 轴日期显示
                                plt.xticks(rotation=45, fontsize=8)
                                plt.yticks(fontsize=8)
                                
                                # 添加水平零线
                                ax_flow.axhline(0, color='black', linewidth=0.8, linestyle='-')
                                
                                # 在柱子上显示具体数值
                                for bar in bars:
                                    height = bar.get_height()
                                    # 根据正负值调整文字位置
                                    xy_pos = (bar.get_x() + bar.get_width() / 2, height)
                                    xy_text = (0, 3) if height > 0 else (0, -10)
                                    
                                    ax_flow.annotate(f'{int(height)}',
                                                    xy=xy_pos,
                                                    xytext=xy_text,
                                                    textcoords="offset points",
                                                    ha='center', va='bottom', fontsize=7)
                                
                                # 去掉顶部和右侧的边框
                                ax_flow.spines['top'].set_visible(False)
                                ax_flow.spines['right'].set_visible(False)
                                
                                st.pyplot(fig_flow)
                            except Exception as e:
                                st.error(f"绘图出错: {e}")
                        
                    else:
                        st.error("数据获取失败")
                
                with col2:
                    if st.button("🗑️ 移除", key=f"del_{symbol}"):
                        db_manager.remove_from_watchlist(st.session_state.user['id'], symbol)
                        st.rerun()
                    
                    if st.button("📊 详细分析", key=f"go_{symbol}"):
                        # 跳转逻辑比较复杂，这里简单提示用户去个股分析页
                        st.info(f"请切换到【个股详细分析】页面输入 {symbol} 查看详情")
                    
                    if df is not None:
                        st.divider()
                        st.markdown("**🎯 趋势预测**")
                        latest_price = float(df.iloc[-1]['Close'])
                        
                        if st.button("📈 看涨 (UP)", key=f"up_{symbol}", use_container_width=True):
                            if db_manager.add_prediction(st.session_state.user['id'], symbol, name, "UP", latest_price):
                                st.success("已记录看涨！")
                            else:
                                st.error("记录失败")
                        
                        if st.button("📉 看跌 (DOWN)", key=f"down_{symbol}", use_container_width=True):
                            if db_manager.add_prediction(st.session_state.user['id'], symbol, name, "DOWN", latest_price):
                                st.success("已记录看跌！")
                            else:
                                st.error("记录失败")

elif page == "🔥 实时涨幅榜分析":
    st.header("🚀 实时涨幅榜前10名分析")
    st.markdown("获取当前市场涨幅最高的股票，并进行横向技术指标对比。")
    
    # 初始化 Session State
    if 'top_gainers_data' not in st.session_state:
        st.session_state.top_gainers_data = None
        st.session_state.top_gainers_source = None

    if st.button("刷新数据", type="primary"):
        with st.spinner("正在获取实时行情..."):
            top_df, source = get_top_gainers(10)
            st.session_state.top_gainers_source = source
            
            if top_df is not None:
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
                    # 获取最近150天数据用于计算指标
                    end_str = datetime.datetime.now().strftime("%Y%m%d")
                    start_str = (datetime.datetime.now() - datetime.timedelta(days=150)).strftime("%Y%m%d")
                    
                    stock_df = get_stock_data(symbol, start_str, end_str)
                    
                    if stock_df is not None and not stock_df.empty:
                        # 计算指标
                        stock_df = calculate_advanced_indicators(stock_df)
                        latest = stock_df.iloc[-1]
                        
                        # 安全获取布林带状态
                        bb_status = "未知"
                        if 'BBU' in latest and 'BBM' in latest and 'Close' in latest:
                             if latest['Close'] > latest['BBU']:
                                 bb_status = '上轨上方'
                             elif latest['Close'] > latest['BBM']:
                                 bb_status = '中轨上方'
                             else:
                                 bb_status = '弱势区域'
                        
                        # 安全获取KDJ状态
                        kdj_status = "未知"
                        if 'K' in latest and 'D' in latest:
                            kdj_status = '金叉' if latest['K'] > latest['D'] else '死叉'

                        # 收集关键指标
                        comparison_data.append({
                            '代码': symbol,
                            '名称': name,
                            '最新价': row['最新价'],
                            '涨跌幅%': row['涨跌幅'],
                            'RSI(14)': round(latest['RSI'], 2) if 'RSI' in latest else None,
                            'MACD': round(latest['MACD'], 3) if 'MACD' in latest else None,
                            '布林位置': bb_status,
                            'KDJ状态': kdj_status
                        })
                    
                    # 更新进度
                    my_bar.progress((i + 1) / total_stocks, text=f"正在分析 {name} ({symbol})...")
                
                my_bar.empty()
                
                # 保存到 Session State
                st.session_state.top_gainers_data = {
                    'top_df': top_df,
                    'comparison_data': comparison_data
                }
            else:
                st.error("获取实时行情失败。可能是由于网络连接问题或数据源（东方财富/新浪）暂时不可用。请稍后再试，或检查网络环境。")

    # 从 Session State 渲染界面
    if st.session_state.top_gainers_data:
        data = st.session_state.top_gainers_data
        top_df = data['top_df']
        comparison_data = data['comparison_data']
        source = st.session_state.top_gainers_source
        
        if source == "Sina":
            st.warning("⚠️ 注意：由于主数据源连接失败，当前使用备用数据源（新浪）。部分字段（换手率、量比、市盈率）可能不可用。")
        
        # 展示基础数据
        st.subheader("📋 基础行情数据")
        st.dataframe(top_df[['代码', '名称', '最新价', '涨跌幅', '成交量', '成交额', '换手率', '量比', '市盈率-动态']])
        
        st.subheader("📊 涨势横向对比")
        
        # 展示对比表格
        if comparison_data:
            comp_df = pd.DataFrame(comparison_data)
            st.table(comp_df)
            
            # 简单的可视化对比
            st.subheader("📈 涨幅 vs RSI 散点图")
            st.caption("RSI > 70 表示超买，可能回调；RSI < 30 表示超卖。")
            
            # 过滤掉无效数据用于绘图
            plot_df = comp_df.dropna(subset=['RSI(14)', '涨跌幅%']).copy()
            
            if not plot_df.empty:
                # 使用 matplotlib 绘制散点图
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # 确保数据为数值型
                x_data = pd.to_numeric(plot_df['RSI(14)'])
                y_data = pd.to_numeric(plot_df['涨跌幅%'])
                
                # 处理中文显示问题，这里用英文标签或代码代替
                scatter = ax.scatter(x_data, y_data, c=y_data, cmap='viridis')
                plt.colorbar(scatter, label='Change %')
                
                # 添加标签
                # 重置索引以确保循环对齐
                plot_df = plot_df.reset_index(drop=True)
                for i in range(len(plot_df)):
                    txt = plot_df['代码'][i]
                    x_val = x_data.iloc[i]
                    y_val = y_data.iloc[i]
                    ax.annotate(txt, (x_val, y_val), xytext=(5, 5), textcoords='offset points')
                    
                ax.set_xlabel('RSI (14)')
                ax.set_ylabel('Change %')
                ax.axvline(x=70, color='red', linestyle='--', label='Overbought (70)')
                ax.axvline(x=30, color='green', linestyle='--', label='Oversold (30)')
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                st.pyplot(fig)
            else:
                st.info("没有足够的有效RSI数据进行绘图。")
        else:
            st.warning("无法获取个股详细数据进行对比。")

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

    # 初始化 Session State 用于存储分析结果
    if 'analysis_data' not in st.session_state:
        st.session_state.analysis_data = None

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
                    st.session_state.analysis_data = None
                else:
                    # 1. 计算指标
                    df = calculate_advanced_indicators(df)
                    
                    # 2. 运行回测
                    df, trade_log, total_return = run_strategy_backtest(df, initial_capital)
                    
                    # 存入 Session State
                    st.session_state.analysis_data = {
                        'symbol': symbol,
                        'df': df,
                        'trade_log': trade_log,
                        'total_return': total_return
                    }

    # 如果有分析数据，则渲染界面 (无论是否刚点击了 run_btn)
    if st.session_state.analysis_data:
        data = st.session_state.analysis_data
        symbol = data['symbol'] # 使用存储的 symbol，防止用户改了输入框但没点运行
        df = data['df']
        trade_log = data['trade_log']
        total_return = data['total_return']

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
        
        # --- 用户交互区域 (登录后可见) ---
        if st.session_state.user:
            st.divider()
            # 仅保留加入自选股按钮，预测功能移动到自选股页面
            if st.button("❤️ 加入自选股", key="btn_add_watchlist", type="primary", use_container_width=True):
                success, msg = db_manager.add_to_watchlist(st.session_state.user['id'], symbol, f"Stock {symbol}")
                if success: 
                    st.success(msg)
                else: 
                    st.warning(msg)
            st.caption("💡 提示：加入自选股后，请在【我的自选股】页面进行涨跌预测。")
            st.divider()

        # 图表区域
        st.subheader("📊 技术分析图表")
        fig = plot_streamlit_chart(df, symbol, trade_log)
        st.pyplot(fig)
        
        # 信号解读区域
        st.subheader("🤖 智能信号解读")
        
        # 主力动向分析
        st.markdown("### 💰 主力资金动向")
        flow = get_main_force_flow(symbol)
        analysis = analyze_main_force(flow)
        st.info(analysis)
        
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
