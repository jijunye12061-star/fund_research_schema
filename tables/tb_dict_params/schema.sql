-- 通用参数字典表
-- 存储各类枚举值、分类体系等参数
-- 更新频率: 按需更新
DROP TABLE IF EXISTS tytdata.tb_dict_params;

CREATE TABLE tytdata.tb_dict_params (
    c_param_type  VARCHAR(50)  COMMENT '参数类型',
    c_param_code  VARCHAR(50)  COMMENT '参数代码',
    c_param_name  VARCHAR(200) COMMENT '参数名称',
    c_parent_code VARCHAR(50)  COMMENT '父节点代码',
    c_remark      VARCHAR(1000) COMMENT '备注',
    c_updatetime  DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6) COMMENT '更新时间'
)
ENGINE = OLAP
UNIQUE KEY (c_param_type, c_param_code)
COMMENT '通用参数字典表'
DISTRIBUTED BY HASH(c_param_type)
PROPERTIES (
    "replication_allocation" = "tag.location.default: 3",
    "storage_format" = "V2",
    "enable_unique_key_merge_on_write" = "true"
);