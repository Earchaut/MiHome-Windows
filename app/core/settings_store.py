# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""应用设置的本地持久化。

与 tray.json / workbench.json 同目录，单独文件 settings.json，
保存用户在设置界面中调整的偏好。
"""

import sys
from pathlib import Path

from app.core import _json_store

_VERSION = 1
_FILENAME = "settings.json"

_DEFAULTS: dict = {
    "version": _VERSION,
    "minimize_to_tray": True,
    "start_minimized": False,
    "voice_fab_enabled": True,
    "theme": "system",  # system / light / dark
    "hide_no_func_devices": False,
}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), dict(_DEFAULTS))
    if raw.get("version") != _VERSION:
        return dict(_DEFAULTS)
    # 补全缺失字段
    for k, v in _DEFAULTS.items():
        raw.setdefault(k, v)
    return raw


def _write_raw(raw: dict) -> None:
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def get_minimize_to_tray() -> bool:
    """关闭窗口时是否最小化到托盘，默认 True。"""
    return bool(_read_raw().get("minimize_to_tray", True))


def set_minimize_to_tray(value: bool) -> None:
    raw = _read_raw()
    raw["minimize_to_tray"] = bool(value)
    _write_raw(raw)


def get_start_minimized() -> bool:
    """启动时是否以托盘方式静默启动，不唤出主界面。默认 False。"""
    return bool(_read_raw().get("start_minimized", False))


def set_start_minimized(value: bool) -> None:
    raw = _read_raw()
    raw["start_minimized"] = bool(value)
    _write_raw(raw)


def get_voice_fab_enabled() -> bool:
    """是否启用小爱同学悬浮对话按钮，默认 True。"""
    return bool(_read_raw().get("voice_fab_enabled", True))


def set_voice_fab_enabled(value: bool) -> None:
    raw = _read_raw()
    raw["voice_fab_enabled"] = bool(value)
    _write_raw(raw)


def get_hide_no_func_devices() -> bool:
    """是否隐藏无可控制功能的设备（无 spec / spec 无属性），默认关闭。"""
    return bool(_read_raw().get("hide_no_func_devices", False))


def set_hide_no_func_devices(value: bool) -> None:
    raw = _read_raw()
    raw["hide_no_func_devices"] = bool(value)
    _write_raw(raw)


def get_theme_mode() -> str:
    """主题配色设置：system（跟随系统）/ light / dark，默认 system。"""
    value = str(_read_raw().get("theme", "system"))
    return value if value in ("system", "light", "dark") else "system"


def set_theme_mode(value: str) -> None:
    raw = _read_raw()
    raw["theme"] = value if value in ("system", "light", "dark") else "system"
    _write_raw(raw)


# ---------- 开机自启动（Windows 注册表 HKCU Run） ----------

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "MiHome-Windows"


def autostart_supported() -> bool:
    """仅构建版（Nuitka standalone exe）支持开机自启动。

    开发模式写入的是 venv 解释器 + run.py：任务管理器显示为无名
    "Python"、venv 一旦清理即失效、安全软件对解释器自启天然不信任
    （火绒报「无效/建议删除」即此情形），因此不提供。
    """
    from app import is_packaged

    return is_packaged() and sys.platform == "win32"


def _autostart_command() -> str:
    """注册表里写入的启动命令（仅打包形态调用）。

    不能用 sys.executable：Nuitka standalone 会在产物目录附带一个
    python.exe 且 sys.executable 指向它（已实测），写进注册表就是
    开机启动裸解释器——任务管理器显示 "Python"、安全软件报无效。
    sys.argv[0] 才是用户实际启动的 exe 路径（已实测）。
    """
    argv0 = Path(sys.argv[0]).resolve()
    return f'"{argv0}"'


def get_autostart() -> bool:
    """读取注册表实际状态（而非偏好文件），外部改动也能反映。

    目标文件已不存在的残留条目视为未开启（返回 False），开关重新
    打开时会用正确的命令覆写——否则无效条目会永远谎报「已开启」。
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _RUN_VALUE_NAME)
    except OSError:
        return False
    target = _command_target(value)
    return target is not None and target.exists()


def _command_target(value: str) -> Path | None:
    """从 Run 条目命令里解析目标可执行文件路径。"""
    value = value.strip()
    if not value:
        return None
    if value.startswith('"'):
        end = value.find('"', 1)
        if end == -1:
            return None
        inner = value[1:end]
        # 空引号命令解析为 Path(".")，目录 exists() 恒真，需显式拒绝
        return Path(inner) if inner else None
    bare = value.split(" ", 1)[0]
    return Path(bare) if bare else None


def set_autostart(value: bool) -> None:
    """开启自启动仅在构建版受支持；关闭（清理残留）任何形态都允许。"""
    if sys.platform != "win32":
        return
    if value and not autostart_supported():
        # 开发模式拒绝写入（调用方负责置灰开关并提示）
        return
    import winreg

    if value:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _RUN_VALUE_NAME, 0, winreg.REG_SZ,
                              _autostart_command())
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _RUN_VALUE_NAME)
    except FileNotFoundError:
        pass
