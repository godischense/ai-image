const API_SOURCE_LABELS = {
  fal: 'T8Fal',
  gptsapi: 'GPTsAPI',
  apiyi: 'APIYI',
  openai: 'T8',
  t8: 'T8'
}

export const formatApiSourceLabel = (apiSource) => {
  const normalized = String(apiSource || '').trim().toLowerCase()
  return API_SOURCE_LABELS[normalized] || 'T8'
}

// URL / 本地路径扩展名 -> 图片格式显示名
// 功能描述：
//     根据图片 URL 或本地路径的扩展名返回对应的格式展示标签（PNG / JPEG / WebP / GIF / BMP），
//     供 ImageLibrary / EditBoard 卡片底部元数据使用，替换之前的硬编码 "PNG"。
// 实现逻辑：
//     1. 先剥离 query string / hash，避免扩展名后还跟着 ?v=123 这类参数
//     2. 取最后一个 .xxx 作为扩展名，做小写归一化
//     3. 未识别或缺失扩展名时回退到 PNG，与历史行为保持一致
const EXTENSION_TO_FORMAT_LABEL = {
  png: 'PNG',
  jpg: 'JPEG',
  jpeg: 'JPEG',
  webp: 'WebP',
  gif: 'GIF',
  bmp: 'BMP'
}

export const formatImageFormatLabel = (imageLike) => {
  if (!imageLike) return 'PNG'

  // 优先从显式的 format 字段读取（后续若 image_model 加 format 列可直接命中）
  const direct = String(imageLike.format || imageLike.imageFormat || '').trim().toLowerCase()
  if (direct && EXTENSION_TO_FORMAT_LABEL[direct]) {
    return EXTENSION_TO_FORMAT_LABEL[direct]
  }

  const candidates = [
    imageLike.url,
    imageLike.displayUrl,
    imageLike.display_url,
    imageLike.localPath,
    imageLike.local_path,
    imageLike.thumbnail
  ]

  for (const raw of candidates) {
    if (!raw || typeof raw !== 'string') continue
    // 去掉 query / hash 再匹配
    const cleanPath = raw.split('?')[0].split('#')[0]
    const dotIndex = cleanPath.lastIndexOf('.')
    if (dotIndex === -1 || dotIndex === cleanPath.length - 1) continue
    const ext = cleanPath.slice(dotIndex + 1).toLowerCase()
    if (EXTENSION_TO_FORMAT_LABEL[ext]) {
      return EXTENSION_TO_FORMAT_LABEL[ext]
    }
  }

  return 'PNG'
}
