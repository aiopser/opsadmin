"""Only advertise inventory attributes implemented by the current collectors."""

COMMON = ["实例 ID", "主机名称", "内网 IP", "云运行状态"]
CAPABILITIES = {
    "aliyun": COMMON + ["外网 IP", "操作系统", "CPU", "内存", "系统盘", "数据盘", "地域"],
    "tencent": COMMON + ["外网 IP", "操作系统", "CPU", "内存", "系统盘", "数据盘", "地域"],
    "vmware": COMMON + ["操作系统类型"],
    "openstack": COMMON + ["外网 IP", "地域"],
    "pve": COMMON,
}


def cloud_state(value):
    raw = str(value or "").upper()
    return {
        "RUNNING": "running", "ACTIVE": "running", "POWERED_ON": "running",
        "STOPPED": "stopped", "SHUTOFF": "stopped", "POWERED_OFF": "stopped",
        "STARTING": "starting", "PENDING": "starting", "BUILD": "starting",
        "STOPPING": "stopping", "SHUTDOWN": "stopping",
        "SUSPENDED": "suspended", "PAUSED": "paused", "ERROR": "error",
    }.get(raw, "unknown")
