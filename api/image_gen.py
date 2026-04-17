"""
文生图 API - 通义万相 wan2.6-t2i
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from core.settings import get_settings
from model.user import User
from utils.logger import get_logger

logger = get_logger("image_gen")

router = APIRouter(prefix="/image", tags=["文生图"])

settings = get_settings()


class TextToImageRequest(BaseModel):
    """文生图请求"""
    prompt: str = Field(..., min_length=1, max_length=2100, description="正向提示词")
    negative_prompt: str = Field(default="", max_length=500, description="反向提示词")
    size: str = Field(default="1280*1280", description="图像分辨率")
    n: int = Field(default=1, ge=1, le=4, description="生成图片数量")
    prompt_extend: bool = Field(default=True, description="是否开启提示词智能改写")
    watermark: bool = Field(default=False, description="是否添加水印")
    seed: int | None = Field(default=None, description="随机数种子")


class ImageResult(BaseModel):
    """单张图片结果"""
    url: str
    index: int


class TextToImageResponse(BaseModel):
    """文生图响应"""
    images: list[ImageResult]
    size: str
    image_count: int
    request_id: str


async def call_wanx_api(prompt: str, negative_prompt: str, size: str,
                        n: int, prompt_extend: bool, watermark: bool,
                        seed: int | None) -> dict:
    """调用通义万相 API"""
    api_key = settings.api_keys.dashscope
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 DASHSCOPE_API_KEY")

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # 构建请求体
    payload = {
        "model": "wan2.6-t2i",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ]
                }
            ]
        },
        "parameters": {
            "prompt_extend": prompt_extend,
            "watermark": watermark,
            "n": n,
            "negative_prompt": negative_prompt,
            "size": size
        }
    }

    # 如果指定了 seed，添加到请求中
    if seed is not None:
        payload["parameters"]["seed"] = seed

    logger.info(f"调用通义万相 API - prompt长度: {len(prompt)}, size: {size}, n: {n}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("通义万相 API 请求超时")
            raise HTTPException(status_code=504, detail="图片生成超时，请稍后重试")
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response.content else {}
            error_msg = error_detail.get("message", str(e))
            error_code = error_detail.get("code", "Unknown")
            logger.error(f"通义万相 API 错误: {error_code} - {error_msg}")
            raise HTTPException(status_code=502, detail=f"图片生成失败: {error_msg}")
        except Exception as e:
            logger.error(f"通义万相 API 异常: {e}")
            raise HTTPException(status_code=500, detail=f"图片生成异常: {str(e)}")


@router.post("/generate", response_model=TextToImageResponse)
async def text_to_image(
    req: TextToImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    文生图接口

    使用通义万相 wan2.6-t2i 模型生成图片。

    参数:
    - prompt: 正向提示词，描述期望生成的图像内容、风格和构图
    - negative_prompt: 反向提示词，描述不希望在图像中出现的内容
    - size: 输出图像分辨率，默认 1280*1280
    - n: 生成图片数量，1-4张，默认1张（按张计费）
    - prompt_extend: 是否开启提示词智能改写，默认开启
    - watermark: 是否添加水印，默认不添加
    - seed: 随机数种子，用于保持生成结果相对稳定
    """
    logger.info(f"用户 {current_user.username} 请求文生图 - prompt: {req.prompt[:50]}...")

    try:
        result = await call_wanx_api(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            size=req.size,
            n=req.n,
            prompt_extend=req.prompt_extend,
            watermark=req.watermark,
            seed=req.seed
        )

        # 解析响应
        output = result.get("output", {})
        choices = output.get("choices", [])
        usage = result.get("usage", {})

        images = []
        for i, choice in enumerate(choices):
            message = choice.get("message", {})
            content = message.get("content", [])
            for item in content:
                if item.get("type") == "image":
                    images.append(ImageResult(
                        url=item.get("image", ""),
                        index=i
                    ))

        if not images:
            raise HTTPException(status_code=500, detail="未获取到生成的图片")

        logger.info(f"文生图成功 - 生成 {len(images)} 张图片, request_id: {result.get('request_id')}")

        return TextToImageResponse(
            images=images,
            size=usage.get("size", req.size),
            image_count=usage.get("image_count", len(images)),
            request_id=result.get("request_id", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文生图异常: {e}")
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")
