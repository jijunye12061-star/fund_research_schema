"""写入7张新幻灯片的XML内容和rels"""

SLIDES_DIR = "C:/Users/Administrator/AppData/Local/Temp/pptx_unpacked/ppt/slides"
RELS_DIR = f"{SLIDES_DIR}/_rels"

SLD_WRAP = ('<?xml version="1.0" encoding="utf-8"?>\n'
'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
'  <p:cSld>\n    <p:spTree>\n'
'      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\n'
'      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>\n'
'{content}\n'
'    </p:spTree>\n  </p:cSld>\n'
'  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>\n</p:sld>')


def title_xml(title_text):
    return (
        '      <p:sp>\n'
        '        <p:nvSpPr><p:cNvPr id="2" name="title"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>\n'
        '        <p:spPr><a:xfrm>'
        '<a:off x="533400" y="414847"/><a:ext cx="11125200" cy="500000"/>'
        '</a:xfrm></p:spPr>\n'
        '        <p:txBody>\n'
        '          <a:bodyPr><a:normAutofit/></a:bodyPr>\n'
        '          <a:lstStyle/>\n'
        '          <a:p><a:r><a:rPr lang="zh-CN" altLang="en-US" sz="2667" dirty="0">\n'
        '            <a:solidFill><a:schemeClr val="tx1">'
        '<a:lumMod val="95000"/><a:lumOff val="5000"/></a:schemeClr></a:solidFill>\n'
        '            <a:latin typeface="+mn-ea"/><a:ea typeface="+mn-ea"/>\n'
        '          </a:rPr><a:t>' + title_text + '</a:t></a:r></a:p>\n'
        '        </p:txBody>\n'
        '      </p:sp>'
    )


def bullet_para(text, bold=False):
    b_attr = ' b="1"' if bold else ''
    return (
        '          <a:p>\n'
        '            <a:pPr marL="285750" indent="-285750">\n'
        '              <a:lnSpc><a:spcPct val="160000"/></a:lnSpc>\n'
        '              <a:buFont typeface="Arial" panose="020B0604020202020204"'
        ' pitchFamily="34" charset="0"/>\n'
        '              <a:buChar char="&#x2022;"/>\n'
        '            </a:pPr>\n'
        f'            <a:r><a:rPr lang="zh-CN" altLang="en-US" sz="1500"{b_attr} dirty="0">\n'
        '              <a:solidFill><a:schemeClr val="tx1">'
        '<a:lumMod val="75000"/><a:lumOff val="25000"/></a:schemeClr></a:solidFill>\n'
        '              <a:latin typeface="+mj-ea"/><a:ea typeface="+mj-ea"/>\n'
        f'            </a:rPr><a:t>{text}</a:t></a:r>\n'
        '          </a:p>'
    )


def bullets_box(bullets, sp_id=3, y=1000000):
    paras = "\n".join(bullet_para(t, b) for t, b in bullets)
    return (
        f'      <p:sp>\n'
        f'        <p:nvSpPr><p:cNvPr id="{sp_id}" name="textbox{sp_id}"/>'
        f'<p:cNvSpPr/><p:nvPr/></p:nvSpPr>\n'
        f'        <p:spPr><a:xfrm><a:off x="762000" y="{y}"/>'
        f'<a:ext cx="10966581" cy="900000"/></a:xfrm>\n'
        f'          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>\n'
        f'        <p:txBody><a:bodyPr wrap="square"><a:spAutoFit/></a:bodyPr>'
        f'<a:lstStyle/>\n'
        f'{paras}\n'
        f'        </p:txBody>\n'
        f'      </p:sp>'
    )


def img_xml(rid, x, y, cx, cy, sp_id=4, name="img"):
    return (
        f'      <p:pic>\n'
        f'        <p:nvPicPr><p:cNvPr id="{sp_id}" name="{name}"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
        f'<p:nvPr/></p:nvPicPr>\n'
        f'        <p:blipFill><a:blip r:embed="{rid}"/>'
        f'<a:stretch><a:fillRect/></a:stretch></p:blipFill>\n'
        f'        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>\n'
        f'          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>\n'
        f'      </p:pic>'
    )


def rels_xml(images):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>',
    ]
    for rid, fname in images:
        lines.append(
            f'  <Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{fname}"/>'
        )
    lines.append('</Relationships>')
    return "\n".join(lines)


# ===== 各幻灯片定义 =====

def make_slide13():
    b = [
        ("均衡类是三年唯一净增大类：407只 -> 594只（+46%，+187只），基金数量持续增长", False),
        ("稳健类显著收缩：656只 -> 545只（-17%，-111只），分类迁移至均衡类趋势明显", True),
        ("激进类（302->286）与可转债类（81->79）基本稳定；总样本约1450~1523只", False),
    ]
    c = "\n".join([
        title_xml("固收+基金——样本与分类（2023-2025）"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1920000, 11125200, 4700000, sp_id=4),
    ])
    return c, rels_xml([("rId4", "image20.png")])


def make_slide14():
    b = [
        ("月度收益中位数：2023年整体低迷；2024年债牛各类均正收益；2025年可转债/激进大幅拉升", False),
        ("三年累计净值中位数：可转债+22.0%领跑，激进+12.7%，稳健+11.0%，均衡+10.0%", True),
    ]
    c = "\n".join([
        title_xml("固收+基金——业绩走势（2023-2025）"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1800000, 5487600, 4800000, sp_id=4, name="monthly"),
        img_xml("rId5", 6171000, 1800000, 5487600, 4800000, sp_id=5, name="cumulative"),
    ])
    return c, rels_xml([("rId4", "image21.png"), ("rId5", "image22.png")])


def make_slide15():
    b = [
        ("2023年：均衡+1.4%微正，稳健接近0，激进-0.8%，可转债-1.4%（转债市场大跌）", False),
        ("2024年：债牛全面开花，四类均实现+4.5%~+5.9%正收益，激进类略领先（+5.9%）", False),
        ("2025年：双牛格局，可转债暴涨（+18.9%），激进+6.6%，稳健+4.9%，均衡+3.2%", True),
    ]
    c = "\n".join([
        title_xml("固收+基金——年度收益分布（2023-2025）"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1950000, 11125200, 4600000, sp_id=4),
    ])
    return c, rels_xml([("rId4", "image23.png")])


def make_slide16():
    b = [
        ("总规模：2023末1.41万亿 -> 2024末1.26万亿（小幅回落）-> 2025末2.32万亿（+84.9%，净增1.07万亿）", True),
        ("均衡类规模三年增幅+141%，2025末8428亿首超稳健类（8019亿），成为最大单类", False),
        ("机构持有规模：9107亿 -> 14777亿（+62%），机构贡献2025年全年增量的65.2%", False),
    ]
    c = "\n".join([
        title_xml("固收+基金——规模演变（2023-2025）"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1900000, 5487600, 4700000, sp_id=4, name="size_cat"),
        img_xml("rId5", 6171000, 1900000, 5487600, 4700000, sp_id=5, name="inst_size"),
    ])
    return c, rels_xml([("rId4", "image24.png"), ("rId5", "image25.png")])


def make_slide17():
    b = [
        ("稳健类是机构加仓绝对规模主力（2024->2025机构增量+2923亿，占机构总增量42%）", True),
        ("激进类机构持有占比提升最显著（AUM加权+11.6pp至74%）；机构对激进类信心大幅增强", False),
        ("均衡类机构占比小幅下降，规模扩张主要由零售资金驱动（散户替代理财进入）", False),
    ]
    c = "\n".join([
        title_xml("固收+基金——机构加仓行为（2024->2025）"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1900000, 5487600, 4700000, sp_id=4, name="inst_ratio"),
        img_xml("rId5", 6171000, 1900000, 5487600, 4700000, sp_id=5, name="delta_bar"),
    ])
    return c, rels_xml([("rId4", "image26.png"), ("rId5", "image27.png")])


def make_slide18():
    b = [
        ("规模增量与收益强正相关：2025年高收益基金获得更多资金流入，头部效应显著", True),
        ("Top规模增量：单只增量超200亿共5只，最大增量487亿；集中在稳健/激进类头部基金", False),
        ("典型案例：交银荣誉庆丰利率债A（25年收益+26%，规模增量+333亿）", False),
    ]
    c = "\n".join([
        title_xml("固收+基金——规模增量与收益相关性"),
        bullets_box(b, y=1000000),
        img_xml("rId4", 533400, 1950000, 11125200, 4600000, sp_id=4),
    ])
    return c, rels_xml([("rId4", "image28.png")])


def make_slide19():
    b = [
        ("【业绩】三阶段分化：2023均衡微正；2024债牛普惠；2025双牛可转债/激进全面反超。三年累计可转债+22%领跑", True),
        ("【规模】2025年大扩张：1.26万亿->2.32万亿（+85%，净增1.07万亿）；机构贡献65%；均衡类总量增幅+141%", True),
        ("【结构迁移】均衡类已取代稳健类成最大单类（规模+数量双第一）；稳健->均衡分类迁移仍在持续", True),
        ("【机构偏好】稳健类机构增量最大（+2923亿，占42%）；激进类机构占比提升最显著（+11.6pp至74%）", False),
        ("【投资启示】2025年权益仓位越高越赚钱；均衡类是结构扩张受益者；关注2026年债市切换下各类表现", False),
    ]
    c = "\n".join([
        title_xml("固收+基金整体分析——核心结论（2023-2025）"),
        bullets_box(b, y=1000000),
    ])
    return c, rels_xml([])


# ===== 写入文件 =====
slide_makers = [
    (13, make_slide13),
    (14, make_slide14),
    (15, make_slide15),
    (16, make_slide16),
    (17, make_slide17),
    (18, make_slide18),
    (19, make_slide19),
]

for num, maker in slide_makers:
    content, rels = maker()
    slide_path = f"{SLIDES_DIR}/slide{num}.xml"
    rels_path = f"{RELS_DIR}/slide{num}.xml.rels"
    with open(slide_path, "w", encoding="utf-8") as f:
        f.write(SLD_WRAP.format(content=content))
    with open(rels_path, "w", encoding="utf-8") as f:
        f.write(rels)
    print(f"slide{num}.xml 写入完成")

print("全部完成")
