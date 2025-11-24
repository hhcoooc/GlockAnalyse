import akshare as ak
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
import numpy as np
import datetime

def get_stock_data(symbol, start_date, end_date):
    """获取数据 (同 simple_analysis.py)"""
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
        # MACD 默认列名通常包含参数，如 MACD_12_26_9
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
        # BBU (Upper), BBM (Mid), BBL (Lower)
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
    策略逻辑：
    - 买入：收盘价突破布林带上轨 (强势突破) 且 MACD > 0 (趋势向上)
    - 卖出：收盘价跌破布林带中轨 (趋势转弱)
    """
    cash = initial_capital
    position = 0
    commission_rate = 0.0003 # 万三佣金
    
    trade_log = []
    equity_curve = []
    buy_signals = []
    sell_signals = []
    
    print("\n开始回测策略...")
    
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
    win_rate = 0
    if len(trade_log) > 0:
        wins = 0
        # 简单计算胜率 (卖出价 > 买入价)
        # 注意：这里简化处理，实际需配对买卖记录
        pass 
        
    return df, trade_log, total_return

def plot_advanced_chart(df, symbol, trade_log, total_return):
    """
    绘制包含买卖信号的高级图表
    """
    # 设置样式
    mc = mpf.make_marketcolors(up='r', down='g', edge='i', wick='i', volume='in', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)

    # 添加图表
    add_plots = []
    
    # 1. 布林带 (主图)
    add_plots.append(mpf.make_addplot(df['BBU'], color='lightgray', width=0.8))
    add_plots.append(mpf.make_addplot(df['BBM'], color='orange', width=1.0)) # 中轨也是 MA20
    add_plots.append(mpf.make_addplot(df['BBL'], color='lightgray', width=0.8))
    
    # 2. 买卖信号 (主图)
    # 过滤掉 NaN 值以避免绘图警告 (mplfinance 处理 NaN 有时会有问题，但通常 scatter 可以忽略)
    add_plots.append(mpf.make_addplot(df['Buy_Signal'], type='scatter', markersize=100, marker='^', color='m'))
    add_plots.append(mpf.make_addplot(df['Sell_Signal'], type='scatter', markersize=100, marker='v', color='k'))

    # 3. KDJ (Panel 2)
    add_plots.append(mpf.make_addplot(df['K'], panel=2, color='orange', ylabel='KDJ'))
    add_plots.append(mpf.make_addplot(df['D'], panel=2, color='blue'))
    add_plots.append(mpf.make_addplot(df['J'], panel=2, color='purple'))

    title = f"Advanced Analysis: {symbol} | Return: {total_return:.2f}%"
    
    mpf.plot(df, type='candle', volume=True, addplot=add_plots, 
             style=s, title=title, panel_ratios=(4,1,2), 
             datetime_format='%Y-%m-%d', show_nontrading=False)

def print_report(df, trade_log, total_return):
    print(f"\n{'='*20} 回测报告 {'='*20}")
    print(f"策略收益率: {total_return:.2f}%")
    print(f"交易次数: {len(trade_log)}")
    print("-" * 40)
    print("最近 5 次交易记录:")
    for trade in trade_log[-5:]:
        print(f"{trade['日期'].strftime('%Y-%m-%d')} {trade['操作']} @ {trade['价格']:.2f} ({trade['数量']}股)")
    
    # 当前信号分析
    latest = df.iloc[-1]
    print(f"\n{'='*20} 今日信号分析 ({latest.name.strftime('%Y-%m-%d')}) {'='*20}")
    
    # 综合打分
    score = 0
    reasons = []
    
    # 1. 布林带位置
    if latest['Close'] > latest['BBM']:
        score += 1
        reasons.append("股价位于布林中轨上方 (强势)")
    if latest['Close'] > latest['BBU']:
        score += 1
        reasons.append("股价突破布林上轨 (极强/可能超买)")
        
    # 2. KDJ 金叉
    if latest['K'] > latest['D'] and latest['K'] < 80:
        score += 1
        reasons.append("KDJ 金叉且未钝化")
    elif latest['J'] > 100:
        score -= 1
        reasons.append("KDJ J值过高 (超买风险)")
        
    # 3. MACD
    if latest['MACD'] > latest['MACD_signal']:
        score += 1
        reasons.append("MACD 处于多头状态")
        
    print(f"综合多头评分: {score}/4")
    for r in reasons:
        print(f"  * {r}")
        
    if score >= 3:
        print("\n🚀 结论: 信号偏强，建议关注。")
    elif score <= 1:
        print("\n❄️ 结论: 信号偏弱，建议观望。")
    else:
        print("\n⚖️ 结论: 震荡行情，方向不明。")

if __name__ == "__main__":
    # 示例：钢研高纳
    symbol = "300034"
    today = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=365*2)).strftime("%Y%m%d") # 回测2年
    
    df = get_stock_data(symbol, start_date, today)
    
    if df is not None:
        df = calculate_advanced_indicators(df)
        df, trade_log, total_return = run_strategy_backtest(df)
        print_report(df, trade_log, total_return)
        plot_advanced_chart(df, symbol, trade_log, total_return)
