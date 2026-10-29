# SPDX-License-Identifier: BSD-3-Clause
"""webui blocks 冒烟：确认三 Tab 都能构建（不触发 plotly 等重依赖）。"""
import gradio as gr
gr.Blocks.launch = lambda *a, **k: None  # 只验证构建，不真正起服务
import webui.app

d = webui.app.main()
print("WEBUI BLOCKS OK with 自进化 Tab")