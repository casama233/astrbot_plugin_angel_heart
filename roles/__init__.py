"""AngelHeart 角色模块。

FrontDesk 保留上游主体；Cary 维护层只安装经过回归测试的最小兼容补丁，
避免把大型上游文件复制成难以审计的第二份实现。
"""

from .front_desk import FrontDesk
from .cary_front_desk_patch import install_quoted_media_cache_patch

install_quoted_media_cache_patch(FrontDesk)

__all__ = ["FrontDesk"]
