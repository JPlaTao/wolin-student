"""
分页工具模块
提供统一的分页查询功能
"""
from typing import List, Tuple, Any
from sqlalchemy.orm import Query
from sqlalchemy import func


class PaginationResult:
    """分页结果封装类"""
    def __init__(self, items: List[Any], total: int, page: int, page_size: int):
        self.items = items          # 当前页数据
        self.total = total          # 总记录数
        self.page = page             # 当前页码
        self.page_size = page_size   # 每页条数
        self.total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0  # 总页数
        self.has_next = page < self.total_pages  # 是否有下一页
        self.has_prev = page > 1  # 是否有上一页
    
    def to_dict(self) -> dict:
        """转换为字典格式，便于JSON序列化"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev
        }


def paginate_query(query: Query, page: int = 1, page_size: int = 10) -> Tuple[List[Any], int]:
    """
    对SQLAlchemy查询进行分页
    
    Args:
        query: SQLAlchemy查询对象
        page: 页码（从1开始）
        page_size: 每页条数
        
    Returns:
        Tuple[List[Any], int]: (分页后的数据列表, 总记录数)
    """
    # 参数校验
    page = max(1, page)  # 页码最小为1
    page_size = max(1, min(page_size, 100))  # 每页条数限制1-100
    
    # 计算总记录数
    total = query.count()
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 执行分页查询
    items = query.offset(offset).limit(page_size).all()
    
    return items, total


def paginate_with_dict(items: List[Any], total: int, page: int, page_size: int) -> dict:
    """
    将分页结果转换为统一格式的字典
    
    Args:
        items: 分页数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页条数
        
    Returns:
        dict: 统一分页格式
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


def get_default_pagination_params(page: int = None, page_size: int = None, 
                                   default_page: int = 1, default_page_size: int = 10,
                                   max_page_size: int = 100) -> Tuple[int, int]:
    """
    获取分页参数，支持默认值和最大值限制
    
    Args:
        page: 页码（可为None）
        page_size: 每页条数（可为None）
        default_page: 默认页码
        default_page_size: 默认每页条数
        max_page_size: 最大每页条数
        
    Returns:
        Tuple[int, int]: (page, page_size)
    """
    # 处理页码
    if page is None or page < 1:
        page = default_page
    
    # 处理每页条数
    if page_size is None or page_size < 1:
        page_size = default_page_size
    elif page_size > max_page_size:
        page_size = max_page_size
    
    return page, page_size
