# 界面资源与实现来源

- 界面为本项目原创，采用 design-taste-frontend 的 Achromatic ledger 布局方向；石灰色背景呼应居家日常，三步进度与竖屏预览来自本项目实际工作流。所有历史数量和任务状态取自本地记录，无演示任务混入生产数据。
- GSAP 3.14.2（npm 锁定）：https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/ 。按官方 matchMedia 示例改编入场动效，遵循 prefers-reduced-motion，仅动画 transform / opacity，本地加载。
- Geist 字体通过 @fontsource/geist 5.2.8（npm 锁定）本地加载：https://fontsource.org/fonts/geist 。中文使用系统字体；字体许可随 npm 包提供。
- 简单线框图标为项目原创 SVG，无外部素材与 CDN 请求。
- Codex CLI 接口按本机 `codex exec --help` 核对，使用 stdin 输入、JSONL 事件和 output-last-message；未固定模型，沿用用户本机配置。
