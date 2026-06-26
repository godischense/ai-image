// 设置拖拽时的自定义缩略图，避免浏览器默认的整卡片拖拽预览遮挡鼠标
// 实现逻辑：
// 1. 必须接收一个已经在 DOM 中加载完成的 <img> 元素（卡内展示用的图片），不能使用 Image() 异步加载
//    因为 dataTransfer.setDragImage 必须在 dragstart 事件处理函数中同步调用，浏览器在异步 onload
//    触发前就已经用默认拖拽图渲染了，这会导致我们的自定义预览失效
// 2. 克隆该 img 元素（保留已加载的图片数据），缩小到指定尺寸，并应用圆角 + 阴影
// 3. 临时挂到 body 上调用 setDragImage，传 (0, 0) 让光标落在图片左上角透明圆角处
// 4. 下一帧清理临时元素，避免 DOM 残留
// 5. 若未传入有效的 img 元素，则不设置自定义预览，浏览器回退到默认拖拽图
export function setCustomDragImage(dataTransfer, sourceImg, options = {}) {
  if (!dataTransfer || !sourceImg) return
  const size = options.size || 80
  const radius = options.radius || 12

  // 克隆已有的 img，图片数据已加载，可同步使用
  const dragImage = sourceImg.cloneNode(true)
  dragImage.removeAttribute('loading')
  dragImage.style.position = 'absolute'
  dragImage.style.top = '-9999px'
  dragImage.style.left = '-9999px'
  dragImage.style.width = `${size}px`
  dragImage.style.height = `${size}px`
  dragImage.style.objectFit = 'cover'
  dragImage.style.borderRadius = `${radius}px`
  dragImage.style.boxShadow = '0 6px 16px rgba(0, 0, 0, 0.25)'
  dragImage.style.pointerEvents = 'none'
  dragImage.style.opacity = '0.95'

  document.body.appendChild(dragImage)

  try {
    // setDragImage 必须在 dragstart 中同步调用
    // offset = (0, 0)：光标落在图片左上角；图片有 border-radius，左上角为透明，光标不会被遮挡
    // 同时图片整体位于光标右下方，拖动时能清楚看到目标分组
    dataTransfer.setDragImage(dragImage, 0, 0)
  } catch (e) {
    console.warn('[setCustomDragImage] 设置拖拽预览失败:', e)
  }

  // 下一帧清理临时元素，确保浏览器已完成拖拽预览截图
  setTimeout(() => {
    if (dragImage.parentNode) {
      dragImage.parentNode.removeChild(dragImage)
    }
  }, 0)
}
