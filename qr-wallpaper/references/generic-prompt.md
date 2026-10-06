# 通用 Prompt：基于背景调色板的十字绣二维码壁纸

> 给"能跑代码的 agent"用的工作流指令（纯文生图模型做不到第 2、6 步）。
> 使用时把 [背景风景图] 和 [二维码图] 作为附件一起给 agent 即可。

```
# 任务
输入：[背景风景图] + [二维码图]。输出：一张手机壁纸——背景图上叠加一个"十字绣"风格二维码，
配色取自背景图的实测调色板，且成品必须可扫。

# 步骤
1. 取色：分析背景图，提取调色板。
   - 线条色：取画面中最深的彩色区域（如深绿/深蓝/深棕），作为二维码线条颜色；
   - 底板色：近白色，但带一点主色的色调（例如背景偏绿就用 #EEF5EC 这类"白里透绿"）。
   - 对比度优先：线条色在底板色上必须清晰可辨。
2. 提取二维码矩阵（关键：不要重新编码，必须从原图逐模块采样，保证内容一字不差）：
   - 二值化 → 定位二维码区域 → 识别版本（模块数 n）→ 按模块中心采样得到 n×n 的 0/1 矩阵，
     用定位角图案校验提取是否正确。
3. 十字绣重绘：
   - 数据区深色模块 → 每个画成一个小"+"（两条短线交叉），用线条色；
   - 三个定位角（finder，7×7）→ 保持实心方块，不做 stylize，确保识别率；
   - 浅色模块留空，底板色自然形成静区。
4. 底板：方形（可轻微圆角），无边框、无气泡尾巴、无多余装饰；
   尺寸 = 二维码 + 静区 + 内边距；加轻微投影。
5. 排版：在背景图中找一块干净、低细节的空白区域（避开文字和视觉主体），
   将底板水平居中放入；二维码在手机屏幕上的宽度不小于屏幕宽度的 20%。
6. 验证：用二维码解码器（如 OpenCV QRCodeDetector）解码成品图中的二维码，
   内容必须与原二维码完全一致；不一致则调整重绘参数重试，直到通过。

# 硬约束
- 只重绘样式，绝不改变二维码的数据内容。
- 所有颜色必须从背景图实测取得，不许编造、不许用固定色。
- 验证不通过 = 任务未完成，不许直接交付。
```

# Generic Prompt (English)

```
# Task
Inputs: [landscape background image] + [QR code image]. Output: a phone wallpaper —
the background overlaid with a cross-stitch-style QR code, colored from the background's
measured palette, and guaranteed scannable.

# Steps
1. Palette: analyze the background image.
   - Stroke color: sample the darkest colorful region (deep green/blue/brown) for QR strokes;
   - Panel color: near-white with a hint of the dominant hue (e.g. greenish-white #EEF5EC).
   - Contrast first: strokes must stand out clearly on the panel.
2. Extract the QR module matrix (critical: do NOT re-encode; sample the original module-by-module
   so the data is byte-identical): binarize → locate QR bounds → detect version (module count n)
   → sample each module center into an n×n 0/1 matrix, validated against the finder patterns.
3. Cross-stitch redraw:
   - Dark data modules → each drawn as a small "+" (two short crossing strokes) in the stroke color;
   - The three 7×7 finder patterns → keep as solid squares, never stylized, for detection reliability;
   - Light modules stay empty; the panel color serves as the quiet zone.
4. Panel: plain square (slightly rounded corners ok), no border, no bubble tail, no extra decoration;
   size = QR + quiet zone + padding; subtle drop shadow.
5. Layout: find a clean, low-detail empty region in the background (avoid text and main subjects),
   center the panel horizontally there; QR width ≥ ~20% of screen width so it stays scannable.
6. Verify: decode the QR in the final image with a QR decoder (e.g. OpenCV QRCodeDetector);
   content must exactly match the original QR; if not, adjust and retry until it passes.

# Hard constraints
- Restyle only; never alter the QR data.
- All colors measured from the background image — no invented or hardcoded colors.
- Failed verification = task incomplete; do not deliver.
```
