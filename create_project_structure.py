import os
from pathlib import Path

# 定義專案的結構
# 字典的鍵是目錄名，值是該目錄下的檔案列表
# 如果值是 None，則表示這是一個檔案
project_structure = {
    "uploads": [],  # 這是一個空目錄
    "results": [],  # 這也是一個空目錄
    "venv": [],     # 通常由 `python -m venv venv` 建立，這裡只是示意
    "index.html": None,
    "main.py": None,
    "tasks.py": None,
    "celery_app.py": None,
    "requirements.txt": None,
    "README.md": None
}

def create_project(base_path, structure):
    """
    根據定義的結構遞迴地建立目錄和檔案
    """
    # 確保基礎路徑存在
    base_path = Path(base_path)
    base_path.mkdir(exist_ok=True)
    print(f"專案根目錄: {base_path.resolve()}")

    for name, content in structure.items():
        current_path = base_path / name
        if content is None:  # 如果是檔案
            if not current_path.exists():
                print(f"  建立檔案: {current_path}")
                current_path.touch()
            else:
                print(f"  檔案已存在: {current_path}")
        else:  # 如果是目錄
            if not current_path.exists():
                print(f"建立目錄: {current_path}")
                current_path.mkdir(exist_ok=True)
            else:
                print(f"目錄已存在: {current_path}")
            
            # (可選) 如果目錄內有定義檔案，可以遞迴建立
            if content:
                sub_structure = {file: None for file in content}
                create_project(current_path, sub_structure)


def generate_tree_output(root_dir='.', indent=''):
    """
    產生並印出專案的樹狀結構圖
    """
    root_path = Path(root_dir)
    if not root_path.is_dir():
        return
        
    # 取得目錄下的所有項目並排序
    items = sorted(list(root_path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
    
    print(f"{indent}└── {root_path.name}/")
    indent += "    "
    
    for i, item in enumerate(items):
        connector = "└──" if i == len(items) - 1 else "├──"
        if item.is_dir():
            # 忽略 venv 和 __pycache__ 等常見的忽略目錄
            if item.name not in ['venv', '__pycache__', '.git', '.idea']:
                 # 這裡為了簡潔，不再遞迴印出子目錄內容，只顯示目錄名
                 print(f"{indent}{connector} {item.name}/")
        else:
            print(f"{indent}{connector} {item.name}")


if __name__ == "__main__":
    # 在當前目錄下建立專案結構
    project_root = "." 
    print("--- 開始建立專案結構 ---\n")
    create_project(project_root, project_structure)
    print("\n--- 專案結構建立完成 ---\n")

    print("--- 目前的專案樹狀圖 ---")
    generate_tree_output(project_root)    
