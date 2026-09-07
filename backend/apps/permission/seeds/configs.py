"""系统配置与字典种子数据。"""

from apps.permission.models import DictItem, SystemConfig


SYSTEM_CONFIGS = [
    {
        "config_name": "系统名称",
        "config_key": "basic.system.name",
        "config_value": "DevOps Admin",
        "config_group": SystemConfig.ConfigGroup.BASIC,
        "remark": "用于页面标题、系统水印和浏览器标题等展示。",
    },
    {
        "config_name": "登录页标题",
        "config_key": "basic.login.title",
        "config_value": "DevOps 运维管理平台",
        "config_group": SystemConfig.ConfigGroup.BASIC,
        "remark": "用于登录页主标题。",
    },
    {
        "config_name": "默认头像地址",
        "config_key": "basic.user.default_avatar",
        "config_value": "/media/icon/user/2022/04/17/devops.png",
        "config_group": SystemConfig.ConfigGroup.BASIC,
        "remark": "用户未上传头像时使用。",
    },
    {
        "config_name": "密码最小长度",
        "config_key": "security.password.min_length",
        "config_value": "8",
        "config_group": SystemConfig.ConfigGroup.SECURITY,
        "remark": "创建用户、重置密码时的最小长度建议值。",
    },
    {
        "config_name": "用户初始密码",
        "config_key": "security.user.default_password",
        "config_value": "123456",
        "config_group": SystemConfig.ConfigGroup.SECURITY,
        "remark": "新增用户未填写密码时使用的默认初始密码。",
    },
    {
        "config_name": "登录失败锁定次数",
        "config_key": "security.login.max_failures",
        "config_value": "5",
        "config_group": SystemConfig.ConfigGroup.SECURITY,
        "remark": "连续登录失败达到该次数后可触发锁定策略。",
    },
    {
        "config_name": "Token 过期秒数",
        "config_key": "security.jwt.access_token_seconds",
        "config_value": "86400",
        "config_group": SystemConfig.ConfigGroup.SECURITY,
        "remark": "JWT 访问令牌有效期建议值。",
    },
    {
        "config_name": "启用操作日志",
        "config_key": "log.operation.enabled",
        "config_value": "true",
        "config_group": SystemConfig.ConfigGroup.LOG,
        "remark": "控制是否记录接口操作日志。",
    },
    {
        "config_name": "记录 GET 请求",
        "config_key": "log.operation.record_get",
        "config_value": "true",
        "config_group": SystemConfig.ConfigGroup.LOG,
        "remark": "关闭后可只记录新增、修改、删除等写操作。",
    },
    {
        "config_name": "日志保留天数",
        "config_key": "log.operation.retention_days",
        "config_value": "90",
        "config_group": SystemConfig.ConfigGroup.LOG,
        "remark": "用于后续定时清理操作日志。",
    },
    {
        "config_name": "上传文件大小限制 MB",
        "config_key": "file.upload.max_size_mb",
        "config_value": "20",
        "config_group": SystemConfig.ConfigGroup.FILE,
        "remark": "单文件上传大小限制。",
    },
    {
        "config_name": "允许上传类型",
        "config_key": "file.upload.allowed_extensions",
        "config_value": "jpg,jpeg,png,gif,pdf,xlsx,docx,zip",
        "config_group": SystemConfig.ConfigGroup.FILE,
        "remark": "逗号分隔的文件后缀白名单。",
    },
    {
        "config_name": "媒体访问地址",
        "config_key": "file.media.base_url",
        "config_value": "/media/",
        "config_group": SystemConfig.ConfigGroup.FILE,
        "remark": "上传文件公开访问基础路径。",
    },
]


SYSTEM_DICTS = [
    {
        "name": "性别",
        "dict_code": "gender",
        "remark": "用户性别",
        "items": [
            {
                "label": "男",
                "value": "1",
                "sort": 1,
                "tag_type": DictItem.TagType.PRIMARY,
            },
            {
                "label": "女",
                "value": "2",
                "sort": 2,
                "tag_type": DictItem.TagType.DANGER,
            },
        ],
    },
]
