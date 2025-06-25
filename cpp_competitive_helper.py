# 文件: CppCompetitiveHelper/cpp_competitive_helper.py
# 版本 3.0 - 引入事件监听器和侧边栏 UI
# *** Python 3.3 完全兼容版本 ***

import sublime
import sublime_plugin
import subprocess
import os
import json

# --- 全局变量来追踪我们的 UI 视图 ---
# 格式是 { 'cpp_view_id': ui_view_object }
ui_views = {}

# --- 事件监听器：插件的“自动大脑” ---
class CppHelperEventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        """当一个视图被激活（被点击或切换到）时触发"""
        # 检查当前文件是不是我们关心的 C++ 文件
        file_path = view.file_name()
        if not file_path or not file_path.endswith('.cpp'):
            # 如果不是，就暂时什么都不做
            return
        
        # 如果是，就调用命令来尝试显示或更新 UI
        view.run_command('cpp_helper_show_ui')

    def on_pre_close(self, view):
        """当一个视图即将被关闭时触发"""
        # 如果关闭的是我们的 UI 视图，将它从追踪字典中移除
        if view.id() in ui_views.values():
            # 反向查找 key (cpp_view_id)
            for cpp_id, ui_id in list(ui_views.items()):
                if ui_id == view.id():
                    del ui_views[cpp_id]
                    break
        
        # 如果关闭的是 C++ 文件，也关闭它对应的 UI 视图
        if view.id() in ui_views:
            ui_view = sublime.View(ui_views[view.id()])
            if ui_view and ui_view.is_valid():
                # 先清除scratch状态，否则无法用代码关闭
                ui_view.set_scratch(False) 
                ui_view.window().focus_view(ui_view)
                ui_view.window().run_command("close_file")
            del ui_views[view.id()]


# --- 新命令：专门负责创建和更新 UI 视图 ---
class CppHelperShowUiCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        window = self.view.window()
        if not window:
            return

        # --- 1. 查找对应的测试文件 ---
        file_path = self.view.file_name()
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        test_file_path = os.path.join(os.path.expanduser('~'), 'c++', 'data', 'input', base_name + '_test.txt')

        # 如果测试文件不存在，就没必要显示UI了
        if not os.path.exists(test_file_path):
            # 如果之前有为这个文件打开的UI，现在把它关掉
            if self.view.id() in ui_views:
                ui_view = sublime.View(ui_views[self.view.id()])
                if ui_view and ui_view.is_valid():
                    ui_view.set_scratch(False)
                    ui_view.window().focus_view(ui_view)
                    ui_view.window().run_command("close_file")
                del ui_views[self.view.id()]
            return

        # --- 2. 设置窗口为两栏布局 ---
        # 如果当前不是两栏，就设置为两栏
        if window.num_groups() != 2:
            layout = {
                "cols": [0.0, 0.5, 1.0],  # 三个垂直分割点，定义了两栏
                "rows": [0.0, 1.0],      # 两个水平分割点，定义了一行
                "cells": [ [0, 0, 1, 1], [1, 0, 2, 1] ] # 单元格: [组, 左, 上, 右, 下]
            }
            window.set_layout(layout)
        
        # 将当前 C++ 文件视图移动到左侧的第一组
        window.set_view_index(self.view, 0, 0)
        window.focus_view(self.view)

        # --- 3. 创建或更新右侧的 UI 视图 ---
        ui_view = None
        if self.view.id() in ui_views and sublime.View(ui_views[self.view.id()]).is_valid():
            ui_view = sublime.View(ui_views[self.view.id()])
            window.focus_view(ui_view)
        else:
            ui_view = window.new_file()
            ui_views[self.view.id()] = ui_view.id()

        # 将 UI 视图移动到右侧的第二组
        window.set_view_index(ui_view, 1, 0)

        # --- 4. 设置 UI 视图的属性 ---
        ui_view.set_name("测试用例: {}".format(base_name))
        ui_view.set_scratch(True)  # 设置为临时文件，关闭时不提示保存
        ui_view.set_read_only(True) # 设置为只读

        # --- 5. 加载并渲染测试数据 ---
        try:
            with open(test_file_path, 'r') as f:
                test_cases = json.load(f)
            
            # 先清空旧内容
            ui_view.run_command('select_all')
            ui_view.run_command('right_delete')
            
            # 渲染新内容
            content = "测试文件: {}\n".format(test_file_path)
            content += "=" * 40 + "\n\n"
            for i, case in enumerate(test_cases):
                content += "--- 测试点 #{} ---\n".format(i + 1)
                content += "输入 (Input):\n{}\n".format(case.get('test', 'N/A'))
                # get a default value if key doesn't exist
                answers = case.get('correct_answers', [])
                content += "答案 (Answers):\n"
                for ans in answers:
                    content += "{}\n".format(ans)
                content += "\n"
            
            # 把渲染好的内容写入UI视图
            ui_view.run_command('append', {'characters': content})

        except Exception as e:
            ui_view.run_command('append', {'characters': "加载测试用例失败: {}".format(e)})

# --- 我们之前写的运行测试的命令，暂时保持不变 ---
class CppHelperRunTestsCommand(sublime_plugin.TextCommand):
    # ... (这部分代码和版本 2.3 完全一样，为了简洁此处省略)
    # ... 您可以将之前版本2.3的 CppHelperRunTestsCommand 完整代码粘贴在此处
    pass