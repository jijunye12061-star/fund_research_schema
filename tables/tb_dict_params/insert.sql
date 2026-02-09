-- 申万行业分类
-- 待从tytfund里面同步过来
INSERT INTO tb_dict_params (c_param_type, c_param_code, c_param_name, c_parent_code, c_remark) VALUES
('industry_sw', '801010000000', '农林牧渔', NULL, NULL),
('industry_sw', '801011000000', '农业', '801010000000', NULL),
('industry_sw', '801011010000', '种植业', '801011000000', NULL),
('industry_sw', '801020000000', '采掘', NULL, NULL),
('industry_sw', '801021000000', '煤炭开采', '801020000000', NULL);

-- 报表类型
INSERT INTO tb_dict_params (c_param_type, c_param_code, c_param_name, c_parent_code, c_remark) VALUES
('report_style', '01', '一季报', NULL, 'Q1'),
('report_style', '02', '中报', NULL, '半年报'),
('report_style', '03', '三季报', NULL, 'Q3'),
('report_style', '04', '年报', NULL, '全年'),
('report_style', '05', '二季报', NULL, 'Q2'),
('report_style', '06', '四季报', NULL, 'Q4'),
('report_style', '07', '其他', NULL, '特殊');

-- 债券类型
INSERT INTO tb_dict_params (c_param_type, c_param_code, c_param_name, c_parent_code, c_remark) VALUES
('bond_type', '1', '债券', NULL, NULL),
('bond_type', '2', '转股期可转债', NULL, NULL);