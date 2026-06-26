// 图像分辨率检测与自动压缩工具
// 功能描述：
//   1. 检测图片原始尺寸
//   2. 与最大边长限制比较
//   3. 超过限制时按比例缩小到最大限度，同时保证两边都是 16 的倍数
// 实现逻辑：
//   1. 通过 Image 对象读取图片的 naturalWidth / naturalHeight
//   2. 若长边 <= 最大边长：直接返回原文件，不做任何处理
//   3. 若长边 > 最大边长：使用 Canvas 重新绘制缩放后的位图，按原格式导出为 Blob/File
//   4. 异常情况下（Canvas 不支持、图片损坏、格式无法导出）fallback 到原文件

/**
 * gpt-image-2 编辑接口的尺寸限制常量
 * 来源：e:\AI-image\新建文件夹\修改图片.md
 *   - 最大边长 <= 3840px
 *   - 两条边都必须为 16px 的倍数
 *   - 长短边之比 <= 3:1
 *   - 总像素数 655,360 ~ 8,294,400
 */
export const GPT_IMAGE_MAX_EDGE = 3840
export const GPT_IMAGE_MIN_EDGE_RATIO = 3 // 长边 / 短边
export const GPT_IMAGE_EDGE_MULTIPLE = 16 // 边长必须是 16 的倍数
export const GPT_IMAGE_MAX_PIXELS = 8294400 // 8,294,400
export const GPT_IMAGE_MIN_PIXELS = 655360

// 压缩分辨率预设：长边目标值（px）
// 来源：gpt-image-2 编辑接口最大边长 3840px；1K/2K/4K 习惯取整值
//   1K → 长边 1024px
//   2K → 长边 2048px
//   4K → 长边 3840px（接口上限）
export const RESOLUTION_PRESETS = [
  { value: '1K', label: '1K', description: '约 1024px，文件最小', maxEdge: 1024 },
  { value: '2K', label: '2K', description: '约 2048px，画质与体积平衡', maxEdge: 2048 },
  { value: '4K', label: '4K', description: '约 3840px，最高清晰度', maxEdge: GPT_IMAGE_MAX_EDGE }
]

/**
 * 通过预设值查找对应 maxEdge
 * 实现逻辑：
 *   1. 匹配 value（例如 '1K' / '2K' / '4K'）
 *   2. 未匹配时返回传入的 fallback
 * @param {string} value
 * @param {number} [fallback]
 * @returns {number}
 */
export function getMaxEdgeForPreset(value, fallback = GPT_IMAGE_MAX_EDGE) {
  const preset = RESOLUTION_PRESETS.find(p => p.value === value)
  return preset ? preset.maxEdge : fallback
}

/**
 * 读取图片的原始尺寸
 * 实现逻辑：
 *   1. 通过 createImageBitmap 或 Image 对象加载 blob
 *   2. 返回 { width, height }，加载失败时抛错
 * @param {Blob|File} file
 * @returns {Promise<{width:number, height:number}>}
 */
export function readImageSize(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error('未提供图片文件'))
      return
    }
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const size = { width: img.naturalWidth || img.width, height: img.naturalHeight || img.height }
      URL.revokeObjectURL(url)
      // 即使加载完成，若宽高都为 0 也视为失败
      if (!size.width || !size.height) {
        reject(new Error('图片尺寸读取失败'))
        return
      }
      resolve(size)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }
    img.src = url
  })
}

/**
 * 将尺寸按比例缩小到最大边长以下，并使两边都成为指定倍数的整数
 * 实现逻辑：
 *   1. 若原图长边 <= maxEdge，原样返回
 *   2. 计算缩放比例 scale = maxEdge / maxEdgeLong
 *   3. 按比例计算新宽高后，向上/向下取整到 nearestMultiple（这里向下取整到 16 的倍数，避免越界）
 *   4. 同步校验总像素数 <= maxPixels，必要时进一步缩小
 * @param {number} width
 * @param {number} height
 * @param {number} maxEdge
 * @param {number} multiple
 * @param {number} maxPixels
 * @returns {{width:number, height:number, scaled:boolean}}
 */
export function calculateCompressedSize(width, height, maxEdge = GPT_IMAGE_MAX_EDGE, multiple = GPT_IMAGE_EDGE_MULTIPLE, maxPixels = GPT_IMAGE_MAX_PIXELS) {
  const longEdge = Math.max(width, height)
  if (longEdge <= maxEdge) {
    return { width, height, scaled: false }
  }

  // 1) 按比例缩小
  const ratio = maxEdge / longEdge
  let newWidth = Math.floor((width * ratio) / multiple) * multiple
  let newHeight = Math.floor((height * ratio) / multiple) * multiple

  // 2) 防止取整后长边超过 maxEdge（极小概率，但仍做兜底）
  if (Math.max(newWidth, newHeight) > maxEdge) {
    const adjust = maxEdge / Math.max(newWidth, newHeight)
    newWidth = Math.floor((newWidth * adjust) / multiple) * multiple
    newHeight = Math.floor((newHeight * adjust) / multiple) * multiple
  }

  // 3) 防止总像素数超出 maxPixels（如 3840x3840 = 14745600 > 8294400，需进一步缩小）
  if (newWidth * newHeight > maxPixels) {
    const pixelRatio = Math.sqrt(maxPixels / (newWidth * newHeight))
    newWidth = Math.floor((newWidth * pixelRatio) / multiple) * multiple
    newHeight = Math.floor((newHeight * pixelRatio) / multiple) * multiple
  }

  // 4) 最小边长兜底（避免取整后变成 0）
  if (newWidth < multiple) newWidth = multiple
  if (newHeight < multiple) newHeight = multiple

  return { width: newWidth, height: newHeight, scaled: true }
}

/**
 * 使用 Canvas 将图片按目标尺寸重新绘制并导出为 Blob
 * 实现逻辑：
 *   1. 加载原图
 *   2. 用指定宽高创建离屏 canvas
 *   3. drawImage 绘制缩放后的位图
 *   4. canvas.toBlob 导出与原文件同 MIME 的图片
 * @param {Blob|File} file
 * @param {number} targetWidth
 * @param {number} targetHeight
 * @returns {Promise<Blob>}
 */
export function renderCompressedBlob(file, targetWidth, targetHeight) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = targetWidth
        canvas.height = targetHeight
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          URL.revokeObjectURL(url)
          reject(new Error('Canvas 2D 上下文不可用'))
          return
        }
        // 高质量缩放：使用浏览器默认的 smoothing
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = 'high'
        ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

        // 优先尝试以原 MIME 导出
        const sourceType = (file && file.type) || 'image/png'
        const exportType = ['image/jpeg', 'image/png', 'image/webp'].includes(sourceType) ? sourceType : 'image/png'
        const quality = exportType === 'image/png' ? undefined : 0.92

        canvas.toBlob((blob) => {
          URL.revokeObjectURL(url)
          if (!blob) {
            reject(new Error('Canvas 导出失败'))
            return
          }
          resolve(blob)
        }, exportType, quality)
      } catch (err) {
        URL.revokeObjectURL(url)
        reject(err)
      }
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }
    img.src = url
  })
}

/**
 * 将 Blob 转换为带原始文件名的 File 对象
 * 实现逻辑：
 *   1. 使用新的 File 包装 Blob，保留原始文件名
 *   2. 若类型发生变化，扩展名同步更新
 * @param {Blob} blob
 * @param {File} originalFile
 * @returns {File}
 */
export function blobToFile(blob, originalFile) {
  const originalName = (originalFile && originalFile.name) || 'image'
  const ext = (originalName.match(/\.[^.]+$/) || [''])[0]
  // 根据 mime 推断后缀
  const mimeToExt = { 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp' }
  const targetExt = mimeToExt[blob.type] || ext || '.png'
  const baseName = ext ? originalName.slice(0, -ext.length) : originalName
  const safeBaseName = baseName.replace(/[\\/:*?"<>|]/g, '_') || 'image'
  const newName = `${safeBaseName}${targetExt}`
  try {
    return new File([blob], newName, { type: blob.type, lastModified: Date.now() })
  } catch (e) {
    // 极老浏览器不支持 File 构造，回退到 Blob
    return blob
  }
}

/**
 * 主入口：检查并按需压缩图片
 * 实现逻辑：
 *   1. 读取图片尺寸
 *   2. 计算压缩目标尺寸
 *   3. 若无需缩放：直接返回原文件
 *   4. 若需缩放：使用 Canvas 重新绘制后导出 File
 *   5. 任何异常都 fallback 到原文件，并返回 { file, compressed:false, error }
 * @param {File|Blob} file
 * @param {Object} [options]
 * @param {number} [options.maxEdge=3840]
 * @param {number} [options.multiple=16]
 * @param {number} [options.maxPixels=8294400]
 * @returns {Promise<{file:File|Blob, compressed:boolean, originalSize:{width:number,height:number}, newSize?:{width:number,height:number}, error?:string}>}
 */
export async function compressImageIfOversize(file, options = {}) {
  const maxEdge = options.maxEdge || GPT_IMAGE_MAX_EDGE
  const multiple = options.multiple || GPT_IMAGE_EDGE_MULTIPLE
  const maxPixels = options.maxPixels || GPT_IMAGE_MAX_PIXELS

  // 兜底：无文件直接返回
  if (!file) {
    return { file, compressed: false, originalSize: null, error: 'empty file' }
  }

  // 兜底：Canvas 不可用
  if (typeof document === 'undefined' || !document.createElement) {
    return { file, compressed: false, originalSize: null, error: 'canvas unavailable' }
  }

  let originalSize
  try {
    originalSize = await readImageSize(file)
  } catch (err) {
    // 无法读取尺寸时不冒险压缩，直接返回原文件
    return { file, compressed: false, originalSize: null, error: err.message || 'read size failed' }
  }

  const { width, height, scaled } = calculateCompressedSize(
    originalSize.width,
    originalSize.height,
    maxEdge,
    multiple,
    maxPixels
  )

  if (!scaled) {
    return { file, compressed: false, originalSize }
  }

  try {
    const blob = await renderCompressedBlob(file, width, height)
    const newFile = blobToFile(blob, file)
    return {
      file: newFile,
      compressed: true,
      originalSize,
      newSize: { width, height }
    }
  } catch (err) {
    return {
      file,
      compressed: false,
      originalSize,
      error: err.message || 'compress failed'
    }
  }
}
