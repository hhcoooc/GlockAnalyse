import os
import sys
import streamlit.web.cli as stcli

def resolve_path(path):
    if getattr(sys, "frozen", False):
        # 如果是打包后的环境，文件在临时目录 _MEIPASS 中
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

if __name__ == "__main__":
    # 获取打包后的应用脚本路径
    app_path = resolve_path("stock_app.py")
    
    # 伪造命令行参数，相当于在终端执行 "streamlit run stock_app.py"
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]
    
    sys.exit(stcli.main())
