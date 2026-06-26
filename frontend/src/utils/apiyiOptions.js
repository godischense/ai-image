export const APIYI_ASPECT_RATIO_OPTIONS = [
  { value: 'auto', label: 'Auto' },
  { value: '1:1', label: '1:1' },
  { value: '2:3', label: '2:3' },
  { value: '3:2', label: '3:2' },
  { value: '3:4', label: '3:4' },
  { value: '4:3', label: '4:3' },
  { value: '4:5', label: '4:5' },
  { value: '5:4', label: '5:4' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
  { value: '21:9', label: '21:9' },
  { value: 'wechat-cover', label: '公众号封面' },
  { value: 'fullscreen', label: '全屏' }
]

export const APIYI_RESOLUTIONS = [
  { value: '1K', label: '1K', key: '1k' },
  { value: '2K', label: '2K', key: '2k' },
  { value: '4K', label: '4K', key: '4k' }
]

export const APIYI_SIZE_MAP = {
  '1:1': { '1k': '1280x1280', '2k': '2048x2048', '4k': '2880x2880' },
  '2:3': { '1k': '848x1280', '2k': '1360x2048', '4k': '2336x3520' },
  '3:2': { '1k': '1280x848', '2k': '2048x1360', '4k': '3520x2336' },
  '3:4': { '1k': '960x1280', '2k': '1536x2048', '4k': '2480x3312' },
  '4:3': { '1k': '1280x960', '2k': '2048x1536', '4k': '3312x2480' },
  '4:5': { '1k': '1024x1280', '2k': '1632x2048', '4k': '2560x3216' },
  '5:4': { '1k': '1280x1024', '2k': '2048x1632', '4k': '3216x2560' },
  '9:16': { '1k': '720x1280', '2k': '1152x2048', '4k': '2160x3840' },
  '16:9': { '1k': '1280x720', '2k': '2048x1152', '4k': '3840x2160' },
  '21:9': { '1k': '1280x544', '2k': '2048x864', '4k': '3840x1632' },
  'wechat-cover': { '1k': '1456x624', '2k': '1456x624', '4k': '1456x624' },
  'fullscreen': { '1k': '688x1488', '2k': '1072x2336', '4k': '1760x3840' }
}

export function resolveApiyiSize(aspectRatio, resolution) {
  if (aspectRatio === 'auto') return 'auto'

  const resolutionKey = APIYI_RESOLUTIONS.find((item) => item.value === resolution)?.key || '1k'
  return APIYI_SIZE_MAP[aspectRatio]?.[resolutionKey] || ''
}
