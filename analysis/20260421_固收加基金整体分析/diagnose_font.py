"""
字体诊断脚本——运行后把输出贴给 Claude
"""
import matplotlib
import matplotlib.font_manager as fm

print("=== 1. matplotlib 版本 ===")
print(f"  {matplotlib.__version__}")

print("\n=== 2. 缓存目录 ===")
print(f"  {matplotlib.get_cachedir()}")

print("\n=== 3. 已识别的中文相关字体 ===")
cjk = sorted({
    f.name for f in fm.fontManager.ttflist
    if any(kw in f.name for kw in [
        'Hei', 'YaHei', 'SimHei', 'SimSun', 'FangSong', 'KaiTi',
        'Noto', 'CJK', 'Gothic', 'Song', 'Kai', 'STSong', 'STHeiti',
        'PingFang', 'Source Han', 'WenQuanYi', 'Droid',
    ])
})
if cjk:
    for name in cjk:
        print(f"  {name}")
else:
    print("  （无）")

print("\n=== 4. 逐个检查常用中文字体 ===")
candidates = [
    'SimHei', 'Microsoft YaHei', 'Microsoft YaHei UI',
    'STHeiti', 'STSong', 'STKaiti', 'STFangsong',
    'PingFang SC', 'Hiragino Sans GB',
    'Noto Sans CJK SC', 'Source Han Sans CN',
    'WenQuanYi Micro Hei', 'Droid Sans Fallback',
]
for name in candidates:
    found = any(f.name == name for f in fm.fontManager.ttflist)
    print(f"  {'✓' if found else '✗'} {name}")

print("\n=== 5. 系统上实际存在的 .ttf/.otf 文件（前20个，含中文路径关键字）===")
import os, glob
font_dirs = fm.findSystemFonts(fontpaths=None)
cjk_files = [p for p in font_dirs if any(
    kw in os.path.basename(p).lower()
    for kw in ['hei', 'yah', 'sim', 'cjk', 'noto', 'chinese', 'gothic', 'song']
)]
for p in cjk_files[:20]:
    print(f"  {p}")
if not cjk_files:
    print("  （未找到，可能字体在系统目录但未被扫描）")
    print("  系统字体目录示例（手动检查）:")
    for d in [r'C:\Windows\Fonts', '/usr/share/fonts', '/System/Library/Fonts']:
        print(f"    {d} -> 存在={os.path.isdir(d)}")

print("\n=== 6. 当前 rcParams font.sans-serif ===")
import matplotlib.pyplot as plt
print(f"  {plt.rcParams['font.sans-serif']}")
