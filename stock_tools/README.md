# A股炒股分析工具箱

这是一个简单的 Python 工具箱，用于获取和分析中国 A 股市场数据。

## 1. 环境准备

在使用本工具之前，请确保你已经安装了 Python。建议创建一个虚拟环境。

### 安装依赖库

在终端中运行以下命令安装所需的 Python 库：

```bash
pip install -r requirements.txt
```

主要使用的库：
- **AkShare**: 开源财经数据接口库，用于获取 A 股历史行情、实时行情等。
- **Pandas**: 强大的数据处理和分析库。
- **Mplfinance**: 专门用于绘制金融 K 线图的库。

## 2. 快速开始

### 方式一：可视化 Web 应用 (推荐)

这是最简单直观的方式，提供交互式界面、图表和智能分析报告。

```bash
streamlit run stock_app.py
```

### 方式二：命令行高级分析

如果你喜欢在终端查看回测结果和详细日志，可以运行：

```bash
python advanced_analysis.py
```

## 3. 进阶建议

如果你想深入进行量化分析或自动化交易，可以考虑以下工具和方向：

### 数据获取
- **AkShare**: 目前最推荐的免费开源数据源。
- **Tushare**: 老牌数据源，部分高级数据需要积分。

### 技术指标计算
- **TA-Lib**: 专业的金融技术指标库（如 MACD, RSI, Bollinger Bands 等）。
- **Pandas-TA**: 基于 Pandas 的技术指标库，使用更简单。

### 策略回测
- **Backtrader**: 功能强大的 Python 回测框架，支持多周期、多策略。
- **Zipline**: 另一个流行的回测引擎（Quantopian 出品）。

### 自动化/实盘
- **EasyTrader**: 提供模拟自动交易的接口（注意实盘风险）。

## 4. 常用代码片段

### 计算移动平均线 (MA)
```python
df['MA5'] = df['Close'].rolling(window=5).mean()
df['MA20'] = df['Close'].rolling(window=20).mean()
```

### 计算涨跌幅
```python
df['pct_change'] = df['Close'].pct_change()
```

祝你投资顺利！
