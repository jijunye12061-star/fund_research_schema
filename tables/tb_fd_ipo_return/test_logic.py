# tables/tb_fd_ipo_return/test_logic.py
"""纯函数单测 — python test_logic.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _logic import parse_lock_ratio, determine_board, determine_regime


def test_parse_lock_ratio():
    # 空值
    assert parse_lock_ratio(None) == 0.0
    assert parse_lock_ratio('') == 0.0
    # 无锁定描述
    assert parse_lock_ratio('普通网下推荐配售类') == 0.0
    assert parse_lock_ratio('普通网下追加配售类') == 0.0
    # 孤立月份文本（脏数据）
    assert parse_lock_ratio('6个月') == 0.0
    assert parse_lock_ratio('9个月') == 0.0
    # "无流通限制及锁定安排" — 否定句, 应为 0
    assert parse_lock_ratio('无流通限制及锁定安排') == 0.0
    # Pattern A 主流: 90/10 锁定 → 应取 10%
    assert parse_lock_ratio(
        '即每个配售对象获配的股票中,90%的股份无限售期,'
        '自本次发行股票在上交所上市交易之日起即可流通;'
        '10%的股份限售期为6个月'
    ) == 0.10
    # Pattern B: 70/30 锁定 → 应取 30%
    assert parse_lock_ratio(
        '每个配售对象获配的股票中,70%的股份无锁定期,'
        '自本次发行股票在深交所上市交易之日起即可流通;'
        '30%的股份锁定期为6个月'
    ) == 0.30
    # Pattern C: 60/40 锁定 → 应取 40%
    assert parse_lock_ratio(
        '即每个配售对象获配的股票中,60%的股份无限售期,'
        '40%的股份限售期为6个月'
    ) == 0.40
    # Pattern D 反向: 30/70 锁定 → 应取 70%（70% 限售）
    assert parse_lock_ratio(
        '即每个配售对象获配的股票中,30%的股份无限售期;'
        '70%的股份限售期为6个月'
    ) == 0.70
    # Pattern E 短文本: "X%(向上取整计算)限售期限为..."
    assert parse_lock_ratio(
        '网下投资者应当承诺其获配股票数量的10%(向上取整计算)'
        '限售期限为自发行人首次公开发行并上市之日起6个月'
    ) == 0.10
    # Pattern F: 65% 限售
    assert parse_lock_ratio(
        '承诺其获配股票数量的65%(向上取整计算)'
        '限售期限为自发行人首次公开发行并上市之日起9个月'
    ) == 0.65


def test_determine_board():
    assert determine_board('688001') == 'star'
    assert determine_board('689001') == 'star'
    assert determine_board('300001') == 'gem'
    assert determine_board('301001') == 'gem'
    assert determine_board('601001') == 'main_sh'
    assert determine_board('600001') == 'main_sh'
    assert determine_board('000001') == 'main_sz'
    assert determine_board('001001') == 'main_sz'
    assert determine_board('002001') == 'main_sz'
    assert determine_board('003001') == 'main_sz'
    assert determine_board('830001') == 'bse'
    assert determine_board('870001') == 'bse'
    assert determine_board('920001') == 'bse'
    assert determine_board('999999') == 'unknown'


def test_determine_regime():
    # 科创板 — 开市即注册制
    assert determine_regime('star', '2019-07-22') == 'registration'
    assert determine_regime('star', '2025-01-01') == 'registration'
    # 创业板 — 2020-08-24 分界
    assert determine_regime('gem', '2020-08-23') == 'approval'
    assert determine_regime('gem', '2020-08-24') == 'registration'
    # 主板 — 2023-04-10 分界
    assert determine_regime('main_sh', '2023-04-09') == 'approval'
    assert determine_regime('main_sh', '2023-04-10') == 'registration'
    assert determine_regime('main_sz', '2023-04-09') == 'approval'
    assert determine_regime('main_sz', '2023-04-10') == 'registration'
    # 北交所 — 开市即注册制
    assert determine_regime('bse', '2021-11-15') == 'registration'
    assert determine_regime('bse', '2024-06-01') == 'registration'
    # unknown board
    assert determine_regime('unknown', '2025-01-01') == 'unknown'


if __name__ == '__main__':
    test_parse_lock_ratio()
    test_determine_board()
    test_determine_regime()
    print("All tests passed!")
